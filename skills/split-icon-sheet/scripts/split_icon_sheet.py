#!/usr/bin/env python3
"""Split an irregular labeled icon sheet into QA-validated transparent PNGs."""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class TextItem:
    text: str
    confidence: float
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> int:
        return self.y1 - self.y0


@dataclass
class Component:
    area: int
    x0: int
    y0: int
    x1: int
    y1: int
    touches: tuple[bool, bool, bool, bool]
    pixels: list[tuple[int, int]]

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split a labeled, irregular icon sheet without assuming a global grid."
    )
    parser.add_argument("--image", required=True, help="Source PNG/JPEG/WebP icon sheet")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument(
        "--mode",
        choices=("auto", "captioned", "unlabeled"),
        default="auto",
        help="Detection route. Auto falls back to foreground objects when no caption rows exist.",
    )
    parser.add_argument(
        "--labels",
        help="Optional UTF-8 labels file, one caption per detected icon in reading order",
    )
    parser.add_argument(
        "--ocr-json",
        help="Optional cached output from ocr_vision.swift; skips live OCR",
    )
    parser.add_argument(
        "--overrides",
        help="Optional JSON with per-icon label/source_box corrections keyed by icon index",
    )
    parser.add_argument("--size", type=int, default=256, help="Output canvas size")
    parser.add_argument("--padding", type=int, default=18, help="Transparent output padding")
    parser.add_argument("--max-attempts", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument(
        "--segmentation-backend",
        choices=("auto", "boundary", "birefnet", "sam", "ensemble"),
        default="boundary",
        help="Alpha backend. Use ensemble explicitly to compare optional semantic candidates.",
    )
    parser.add_argument(
        "--rembg-model",
        default="birefnet-general-lite",
        help="rembg model for birefnet/ensemble; use a reviewed model available in the local rembg install",
    )
    parser.add_argument(
        "--min-name-confidence",
        type=float,
        default=0.55,
        help="Block publishing OCR-only names below this confidence",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Create a ZIP even when deterministic QA fails",
    )
    parser.add_argument("--zip-name", help="ZIP path; defaults to OUT/icons.zip")
    return parser.parse_args()


def run_vision_ocr(image_path: Path) -> list[dict[str, Any]]:
    swift_source = Path(__file__).with_name("ocr_vision.swift")
    if not swift_source.exists():
        raise RuntimeError(f"Missing OCR helper: {swift_source}")

    cache_root = Path(tempfile.gettempdir()) / "split-icon-sheet-swift-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    stamp = f"{swift_source.stat().st_mtime_ns:x}"
    executable = cache_root / f"ocr-vision-{stamp}"
    if not executable.exists():
        compile_result = subprocess.run(
            [
                "swiftc",
                "-module-cache-path",
                str(cache_root),
                str(swift_source),
                "-o",
                str(executable),
            ],
            capture_output=True,
            text=True,
        )
        if compile_result.returncode != 0:
            raise RuntimeError(
                "Unable to compile macOS Vision OCR helper:\n"
                + compile_result.stderr.strip()
            )

    result = subprocess.run(
        [str(executable), str(image_path)], capture_output=True, text=True
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown Vision OCR error"
        raise RuntimeError(
            f"macOS Vision OCR failed: {message}\n"
            "When running under Codex sandbox, rerun this command with approval for local "
            "macOS Vision access, or provide --ocr-json."
        )
    return json.loads(result.stdout)


def load_ocr(image_path: Path, ocr_json: str | None) -> list[dict[str, Any]]:
    if ocr_json:
        return json.loads(Path(ocr_json).read_text(encoding="utf-8"))
    return run_vision_ocr(image_path)


def pixel_text_items(raw: Iterable[dict[str, Any]], width: int, height: int) -> list[TextItem]:
    items: list[TextItem] = []
    for item in raw:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        x0 = max(0, min(width - 1, round(float(item["x"]) * width)))
        y0 = max(0, min(height - 1, round(float(item["y"]) * height)))
        x1 = max(x0 + 1, min(width, round((float(item["x"]) + float(item["width"])) * width)))
        y1 = max(y0 + 1, min(height, round((float(item["y"]) + float(item["height"])) * height)))
        items.append(
            TextItem(
                text=text,
                confidence=float(item.get("confidence", 0.0)),
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
            )
        )
    return items


def cluster_caption_rows(
    items: list[TextItem], image_width: int, image_height: int
) -> list[list[TextItem]]:
    if not items:
        raise RuntimeError("OCR found no text")
    typical_height = max(4.0, median(item.height for item in items))
    tolerance = max(6.0, typical_height * 0.9, image_height * 0.012)
    clusters: list[list[TextItem]] = []
    centers: list[float] = []
    for item in sorted(items, key=lambda value: value.cy):
        best = None
        best_distance = float("inf")
        for index, center in enumerate(centers):
            distance = abs(item.cy - center)
            if distance <= tolerance and distance < best_distance:
                best = index
                best_distance = distance
        if best is None:
            clusters.append([item])
            centers.append(item.cy)
        else:
            clusters[best].append(item)
            centers[best] = sum(value.cy for value in clusters[best]) / len(clusters[best])

    # Caption baselines normally contain several labels spread horizontally. Embedded
    # words such as NEW, R, and COURT occur alone and must remain part of the icon.
    candidates = []
    for cluster in clusters:
        cluster.sort(key=lambda value: value.cx)
        span = cluster[-1].cx - cluster[0].cx if len(cluster) > 1 else 0
        if len(cluster) >= 3 and span >= 0.12 * image_width:
            candidates.append(cluster)
    if not candidates:
        raise RuntimeError(
            "Could not identify caption rows. Provide an OCR JSON with accurate boxes or "
            "use a sheet containing at least three labeled icons per row."
        )
    return sorted(candidates, key=lambda row: median(item.cy for item in row))


def read_labels(path: str | None) -> list[str] | None:
    if not path:
        return None
    labels = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    return [label for label in labels if label]


def apply_overrides(records: list[dict[str, Any]], path: str | None) -> None:
    if not path:
        return
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    icon_overrides = payload.get("icons", payload)
    if not isinstance(icon_overrides, dict):
        raise RuntimeError("Overrides JSON must contain an object keyed by icon index")
    by_index = {record["index"]: record for record in records}
    for raw_index, override in icon_overrides.items():
        index = int(raw_index)
        if index not in by_index:
            raise RuntimeError(f"Override references unknown icon index {index}")
        if not isinstance(override, dict):
            raise RuntimeError(f"Override for icon {index} must be an object")
        record = by_index[index]
        if "label" in override:
            record["label"] = str(override["label"]).strip()
            record["label_overridden"] = True
        for key in ("source_box", "label_box"):
            if key in override:
                box = [int(value) for value in override[key]]
                if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                    raise RuntimeError(f"Invalid {key} override for icon {index}: {box}")
                record[key] = box
        if "protected_polygons" in override:
            polygons = override["protected_polygons"]
            if not isinstance(polygons, list):
                raise RuntimeError(f"protected_polygons for icon {index} must be a list")
            normalized: list[list[list[int]]] = []
            for polygon in polygons:
                if not isinstance(polygon, list) or len(polygon) < 3:
                    raise RuntimeError(
                        f"Each protected polygon for icon {index} needs at least three points"
                    )
                points: list[list[int]] = []
                for point in polygon:
                    if not isinstance(point, list) or len(point) != 2:
                        raise RuntimeError(
                            f"Invalid protected polygon point for icon {index}: {point!r}"
                        )
                    points.append([int(point[0]), int(point[1])])
                normalized.append(points)
            record["protected_polygons"] = normalized
        record["manual_override"] = True


def prepare_output_directory(out_dir: Path) -> None:
    marker = out_dir / ".split-icon-sheet-output"
    if out_dir.exists() and any(out_dir.iterdir()):
        if not marker.exists():
            raise RuntimeError(
                f"Output directory is not empty and was not created by this tool: {out_dir}"
            )
        for name in (
            "icons",
            "icon-map.json",
            "icons.ts",
            "qa-report.json",
            "ocr-raw.json",
            "detection-debug.png",
            "contact-sheet.png",
            "qa-comparison.png",
            "icons.zip",
        ):
            path = out_dir / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text("Generated by split-icon-sheet.\n", encoding="utf-8")


def build_icon_records(
    rows: list[list[TextItem]], width: int, height: int, labels: list[str] | None
) -> list[dict[str, Any]]:
    ordered = [item for row in rows for item in row]
    if labels is not None and len(labels) != len(ordered):
        raise RuntimeError(
            f"Labels count {len(labels)} does not match detected caption count {len(ordered)}"
        )

    records: list[dict[str, Any]] = []
    previous_caption_bottom = 0
    item_index = 0
    for row_index, row in enumerate(rows):
        row.sort(key=lambda item: item.cx)
        centers = [item.cx for item in row]
        boundaries = [0]
        boundaries.extend(round((centers[i - 1] + centers[i]) / 2) for i in range(1, len(centers)))
        boundaries.append(width)

        row_top = 0 if row_index == 0 else min(height, previous_caption_bottom + 2)
        label_top = min(item.y0 for item in row)
        icon_bottom = max(row_top + 1, label_top - max(2, round(median(item.height for item in row) * 0.25)))
        previous_caption_bottom = max(item.y1 for item in row)

        for column_index, item in enumerate(row):
            text = labels[item_index] if labels is not None else item.text
            records.append(
                {
                    "index": item_index + 1,
                    "row": row_index + 1,
                    "column": column_index + 1,
                    "label": text,
                    "ocr_text": item.text,
                    "ocr_confidence": item.confidence,
                    "label_box": [item.x0, item.y0, item.x1, item.y1],
                    "source_box": [boundaries[column_index], row_top, boundaries[column_index + 1], icon_bottom],
                    "label_overridden": labels is not None,
                }
            )
            item_index += 1
    return records


def flood_from_edges(candidate: np.ndarray) -> np.ndarray:
    height, width = candidate.shape
    result = np.zeros_like(candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    def seed(y: int, x: int) -> None:
        if candidate[y, x] and not result[y, x]:
            result[y, x] = True
            queue.append((y, x))

    for x in range(width):
        seed(0, x)
        seed(height - 1, x)
    for y in range(height):
        seed(y, 0)
        seed(y, width - 1)

    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width and candidate[ny, nx] and not result[ny, nx]:
                result[ny, nx] = True
                queue.append((ny, nx))
    return result


def dilate_once(mask: np.ndarray) -> np.ndarray:
    result = mask.copy()
    result[1:, :] |= mask[:-1, :]
    result[:-1, :] |= mask[1:, :]
    result[:, 1:] |= mask[:, :-1]
    result[:, :-1] |= mask[:, 1:]
    return result


def connected_components(mask: np.ndarray) -> list[Component]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[Component] = []
    for start_y, start_x in zip(*np.where(mask & ~visited)):
        if visited[start_y, start_x]:
            continue
        queue = [(int(start_y), int(start_x))]
        visited[start_y, start_x] = True
        pixels: list[tuple[int, int]] = []
        x0 = x1 = int(start_x)
        y0 = y1 = int(start_y)
        touches = [False, False, False, False]  # left, top, right, bottom
        while queue:
            y, x = queue.pop()
            pixels.append((y, x))
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            touches[0] |= x == 0
            touches[1] |= y == 0
            touches[2] |= x == width - 1
            touches[3] |= y == height - 1
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
        components.append(
            Component(
                area=len(pixels),
                x0=x0,
                y0=y0,
                x1=x1 + 1,
                y1=y1 + 1,
                touches=tuple(touches),
                pixels=pixels,
            )
        )
    return components


def estimate_background(rgb: np.ndarray) -> np.ndarray:
    border = np.concatenate(
        [rgb[0, :, :], rgb[-1, :, :], rgb[:, 0, :], rgb[:, -1, :]], axis=0
    )
    bright = border[border.min(axis=1) >= 180]
    sample = bright if len(bright) >= 8 else border
    return np.median(sample.astype(np.float32), axis=0)


def segment_foreground(
    crop: Image.Image, brightness_floor: int, color_tolerance: int
) -> tuple[np.ndarray, dict[str, Any]]:
    rgba = np.asarray(crop.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3]
    source_alpha = rgba[:, :, 3]
    bg_color = estimate_background(rgb)
    rgb_i = rgb.astype(np.int16)
    neutral = (rgb_i.max(axis=2) - rgb_i.min(axis=2) <= 18) & (
        rgb_i.min(axis=2) >= brightness_floor
    )
    close = np.max(np.abs(rgb.astype(np.float32) - bg_color), axis=2) <= color_tolerance
    candidate = neutral | close | (source_alpha == 0)
    background = flood_from_edges(candidate)

    alpha = np.where(background, 0, source_alpha).astype(np.uint8)
    ring = dilate_once(background) & ~background
    distance = np.sqrt(
        np.sum((rgb.astype(np.float32) - bg_color.reshape(1, 1, 3)) ** 2, axis=2)
    )
    soft_alpha = np.clip((distance - 3.0) / 42.0 * 255.0, 0, 255).astype(np.uint8)
    alpha[ring] = np.minimum(alpha[ring], soft_alpha[ring])

    foreground = alpha >= 20
    removed_small = 0
    removed_frames = 0
    for component in connected_components(foreground):
        touches_count = sum(component.touches)
        spans_width = component.width >= 0.86 * foreground.shape[1]
        spans_height = component.height >= 0.78 * foreground.shape[0]
        fill = component.area / max(1, component.width * component.height)
        if component.area < 3:
            for y, x in component.pixels:
                alpha[y, x] = 0
            removed_small += 1
        elif touches_count >= 3 and spans_width and spans_height and fill < 0.24:
            for y, x in component.pixels:
                alpha[y, x] = 0
            removed_frames += 1

    rgba[:, :, 3] = alpha
    return rgba, {
        "background_color": [round(float(value), 2) for value in bg_color],
        "brightness_floor": brightness_floor,
        "color_tolerance": color_tolerance,
        "removed_small_components": removed_small,
        "removed_frame_components": removed_frames,
    }


_REMBG_SESSIONS: dict[str, Any] = {}


def rembg_available() -> bool:
    try:
        import rembg  # noqa: F401
    except ImportError:
        return False
    return True


def segment_with_rembg(crop: Image.Image, model: str) -> tuple[np.ndarray, dict[str, Any]]:
    """Run an optional semantic alpha model while retaining exact source RGB."""
    try:
        from rembg import new_session, remove
    except ImportError as error:
        raise RuntimeError(
            "Semantic segmentation requires the optional rembg dependency. "
            "Install requirements-segmentation.txt or use --segmentation-backend boundary."
        ) from error
    if model not in _REMBG_SESSIONS:
        _REMBG_SESSIONS[model] = new_session(model)
    result = remove(crop.convert("RGBA"), session=_REMBG_SESSIONS[model])
    if isinstance(result, np.ndarray):
        result = Image.fromarray(result)
    elif isinstance(result, bytes):
        result = Image.open(io.BytesIO(result))
    elif not isinstance(result, Image.Image):
        raise RuntimeError(f"Unsupported rembg result type: {type(result).__name__}")
    semantic = np.asarray(result.convert("RGBA"), dtype=np.uint8)
    source = np.asarray(crop.convert("RGBA"), dtype=np.uint8).copy()
    source[:, :, 3] = semantic[:, :, 3]
    return source, {
        "method": "rembg",
        "model": model,
        "foreground_ratio": round(float((source[:, :, 3] >= 20).mean()), 6),
    }


def conservative_alpha_union(
    source_crop: Image.Image, boundary: np.ndarray, semantic: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    """Preserve pixels kept by either method; QA must reject resulting leakage."""
    source = np.asarray(source_crop.convert("RGBA"), dtype=np.uint8).copy()
    boundary_alpha = boundary[:, :, 3]
    semantic_alpha = semantic[:, :, 3]
    source[:, :, 3] = np.maximum(boundary_alpha, semantic_alpha)
    disagreement = np.abs(boundary_alpha.astype(np.int16) - semantic_alpha.astype(np.int16))
    return source, {
        "method": "conservative_union",
        "alpha_disagreement_ratio": round(float((disagreement >= 20).mean()), 6),
        "pixels_restored_from_semantic": int(((boundary_alpha < 20) & (semantic_alpha >= 20)).sum()),
    }


def segmentation_candidates(
    crop: Image.Image,
    brightness_floor: int,
    color_tolerance: int,
    backend: str,
    rembg_model: str,
) -> list[tuple[str, np.ndarray, dict[str, Any]]]:
    boundary, boundary_meta = segment_foreground(crop, brightness_floor, color_tolerance)
    candidates = [("boundary", boundary, {"method": "boundary", **boundary_meta})]
    effective = backend
    if backend == "auto":
        effective = "ensemble" if rembg_available() else "boundary"
    if effective == "boundary":
        return candidates
    model = "sam" if effective == "sam" else rembg_model
    semantic, semantic_meta = segment_with_rembg(crop, model)
    if effective in {"birefnet", "sam"}:
        return [(effective, semantic, semantic_meta)]
    union, union_meta = conservative_alpha_union(crop, boundary, semantic)
    # Prefer the semantic mask when it passes source-fidelity QA. Fall back to the
    # conservative union for white preservation, then to the deterministic boundary mask.
    return [
        ("semantic", semantic, semantic_meta),
        ("conservative_union", union, union_meta),
        *candidates,
    ]


def restore_protected_polygons(
    rgba: np.ndarray,
    source_crop: Image.Image,
    global_box: list[int],
    polygons: list[list[list[int]]] | None,
) -> int:
    """Restore source opacity inside QA-approved semantic keep polygons."""
    if not polygons:
        return 0
    mask_image = Image.new("L", source_crop.size, 0)
    draw = ImageDraw.Draw(mask_image)
    for polygon in polygons:
        local = [(x - global_box[0], y - global_box[1]) for x, y in polygon]
        draw.polygon(local, fill=255)
    protect = np.asarray(mask_image, dtype=np.uint8) >= 128
    before = rgba[:, :, 3].copy()
    source_alpha = np.asarray(source_crop.convert("RGBA"), dtype=np.uint8)[:, :, 3]
    rgba[:, :, 3][protect] = source_alpha[protect]
    return int(((before < 20) & (rgba[:, :, 3] >= 20)).sum())


def cluster_component_rows(components: list[Component]) -> list[list[Component]]:
    if not components:
        raise RuntimeError("No foreground icon objects detected")
    tolerance = max(8.0, median(component.height for component in components) * 0.45)
    rows: list[list[Component]] = []
    centers: list[float] = []
    for component in sorted(components, key=lambda value: value.cy):
        best = None
        best_distance = float("inf")
        for index, center in enumerate(centers):
            distance = abs(component.cy - center)
            if distance <= tolerance and distance < best_distance:
                best = index
                best_distance = distance
        if best is None:
            rows.append([component])
            centers.append(component.cy)
        else:
            rows[best].append(component)
            centers[best] = sum(value.cy for value in rows[best]) / len(rows[best])
    for row in rows:
        row.sort(key=lambda value: value.cx)
    return sorted(rows, key=lambda row: median(component.cy for component in row))


def build_unlabeled_records(
    source: Image.Image, labels: list[str] | None
) -> tuple[list[dict[str, Any]], list[int], dict[str, Any]]:
    width, height = source.size
    rgba, segmentation = segment_foreground(source, brightness_floor=238, color_tolerance=18)
    mask = rgba[:, :, 3] >= 20
    min_area = max(80, round(width * height * 0.003))
    min_dimension = max(12, round(min(width, height) * 0.045))
    max_dimension = round(max(width, height) * 0.48)
    objects = []
    for component in connected_components(mask):
        aspect = component.width / max(1, component.height)
        if (
            component.area >= min_area
            and component.width >= min_dimension
            and component.height >= min_dimension
            and component.width <= max_dimension
            and component.height <= max_dimension
            and 0.35 <= aspect <= 2.85
        ):
            objects.append(component)
    if len(objects) < 2:
        raise RuntimeError(
            f"Unlabeled object detection found only {len(objects)} candidate(s); refusing to split"
        )

    rows = cluster_component_rows(objects)
    ordered = [component for row in rows for component in row]
    if labels is not None and len(labels) != len(ordered):
        raise RuntimeError(
            f"Labels count {len(labels)} does not match detected object count {len(ordered)}"
        )

    typical_size = median(max(component.width, component.height) for component in ordered)
    outer_padding = max(6, round(typical_size * 0.045))
    records: list[dict[str, Any]] = []
    item_index = 0
    for row_index, row in enumerate(rows):
        for column_index, component in enumerate(row):
            item_index += 1
            source_box = [
                max(0, component.x0 - outer_padding),
                max(0, component.y0 - outer_padding),
                min(width, component.x1 + outer_padding),
                min(height, component.y1 + outer_padding),
            ]
            label_y0 = min(height, source_box[3] + outer_padding + 1)
            label_y1 = min(height, label_y0 + 1)
            label = labels[item_index - 1] if labels is not None else f"icon-{item_index:03d}"
            records.append(
                {
                    "index": item_index,
                    "row": row_index + 1,
                    "column": column_index + 1,
                    "label": label,
                    "ocr_text": "",
                    "ocr_confidence": 1.0,
                    "label_box": [component.x0, label_y0, component.x1, label_y1],
                    "source_box": source_box,
                    "label_overridden": labels is not None,
                    "detection_mode": "unlabeled",
                }
            )
    segmentation["candidate_object_count"] = len(objects)
    segmentation["minimum_object_area"] = min_area
    return records, [len(row) for row in rows], segmentation


def bbox_from_alpha(alpha: np.ndarray, threshold: int = 20) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(alpha >= threshold)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def premultiplied_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    premultiplied = np.concatenate([rgba[:, :, :3] * alpha, rgba[:, :, 3:4]], axis=2)
    resized = np.asarray(
        Image.fromarray(np.clip(premultiplied, 0, 255).astype(np.uint8), "RGBA").resize(
            size, Image.Resampling.LANCZOS
        ),
        dtype=np.float32,
    )
    out_alpha = resized[:, :, 3:4]
    out_rgb = np.where(out_alpha > 0, resized[:, :, :3] * 255.0 / np.maximum(out_alpha, 1), 0)
    out = np.concatenate([out_rgb, out_alpha], axis=2)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def center_on_canvas(rgba: np.ndarray, size: int, padding: int) -> Image.Image:
    image = Image.fromarray(rgba, "RGBA")
    box = bbox_from_alpha(rgba[:, :, 3])
    if box is None:
        raise RuntimeError("No foreground pixels")
    image = image.crop(box)
    available = max(1, size - 2 * padding)
    scale = min(available / image.width, available / image.height)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    image = premultiplied_resize(image, new_size)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size - new_size[0]) // 2, (size - new_size[1]) // 2))
    return canvas


def safe_filename(index: int, label: str) -> str:
    value = unicodedata.normalize("NFKC", label).strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-._")
    if not value:
        value = "icon"
    if value == f"icon-{index:03d}":
        return f"icon-{index:03d}.png"
    return f"{index:03d}-{value}.png"


def qa_segment(
    rgba: np.ndarray,
    source_crop: Image.Image,
    global_box: list[int],
    image_size: tuple[int, int],
    label_center_x: float,
    neighbor_centers: tuple[float | None, float | None],
) -> dict[str, Any]:
    alpha = rgba[:, :, 3]
    mask = alpha >= 20
    issues: list[dict[str, Any]] = []
    box = bbox_from_alpha(alpha)
    if box is None:
        return {"passed": False, "issues": [{"type": "empty", "severity": 3}]}

    height, width = mask.shape
    edge_counts = {
        "left": int(mask[:, :2].sum()),
        "top": int(mask[:2, :].sum()),
        "right": int(mask[:, max(0, width - 2) :].sum()),
        "bottom": int(mask[max(0, height - 2) :, :].sum()),
    }
    for side, count in edge_counts.items():
        if count > 2:
            issues.append({"type": "clipped", "side": side, "pixels": count, "severity": 3})

    components = connected_components(mask)
    significant = [component for component in components if component.area >= max(8, mask.sum() * 0.015)]
    crop_x0 = global_box[0]
    for component in significant:
        center = crop_x0 + (component.x0 + component.x1) / 2
        left_neighbor, right_neighbor = neighbor_centers
        if left_neighbor is not None and abs(center - left_neighbor) + 2 < abs(center - label_center_x):
            issues.append({"type": "neighbor_contamination", "side": "left", "severity": 3})
            break
        if right_neighbor is not None and abs(center - right_neighbor) + 2 < abs(center - label_center_x):
            issues.append({"type": "neighbor_contamination", "side": "right", "severity": 3})
            break

    foreground_ratio = float(mask.mean())
    if foreground_ratio < 0.005:
        issues.append({"type": "too_little_foreground", "ratio": foreground_ratio, "severity": 2})
    if foreground_ratio > 0.72:
        issues.append({"type": "background_or_frame_remaining", "ratio": foreground_ratio, "severity": 3})

    rgb = rgba[:, :, :3]
    enclosed_white = int(((rgb.min(axis=2) >= 238) & mask).sum())
    source_rgb = np.asarray(source_crop.convert("RGB"), dtype=np.uint8)
    source_i = source_rgb.astype(np.int16)
    bright_neutral = (
        (source_i.max(axis=2) - source_i.min(axis=2) <= 18)
        & (source_i.min(axis=2) >= 238)
    )
    horizontal_interior = np.zeros_like(mask)
    # Fill the horizontal interior of each significant component separately. Using
    # one span across all components falsely marks the white gap to a detached prop.
    for component in significant:
        by_y: dict[int, list[int]] = {}
        for y, x in component.pixels:
            by_y.setdefault(y, []).append(x)
        for y, xs in by_y.items():
            if len(xs) >= 2:
                horizontal_interior[y, min(xs) : max(xs) + 1] = True
    suspicious_white = bright_neutral & ~mask & horizontal_interior
    suspicious_components = connected_components(suspicious_white)
    largest_suspicious = max((component.area for component in suspicious_components), default=0)
    white_removal_risk = largest_suspicious >= max(96, int(mask.sum() * 0.018))
    if white_removal_risk:
        issues.append(
            {
                "type": "white_removed",
                "pixels": largest_suspicious,
                "severity": 3,
            }
        )
    return {
        "passed": not issues,
        "issues": issues,
        "edge_pixels": edge_counts,
        "foreground_ratio": round(foreground_ratio, 6),
        "component_count": len(components),
        "significant_component_count": len(significant),
        "enclosed_white_pixels_preserved": enclosed_white,
        "white_removal_risk": white_removal_risk,
        "largest_suspicious_white_region": largest_suspicious,
        "source_content_box": [
            global_box[0] + box[0],
            global_box[1] + box[1],
            global_box[0] + box[2],
            global_box[1] + box[3],
        ],
        "source_image_size": list(image_size),
    }


def attempt_icon(
    source: Image.Image,
    record: dict[str, Any],
    row_records: list[dict[str, Any]],
    max_attempts: int,
    output_size: int,
    padding: int,
    segmentation_backend: str,
    rembg_model: str,
) -> tuple[Image.Image | None, dict[str, Any]]:
    configs = [
        {"expand": 0, "brightness_floor": 240, "color_tolerance": 14},
        {"expand": 4, "brightness_floor": 232, "color_tolerance": 22},
        {"expand": 8, "brightness_floor": 220, "color_tolerance": 34},
    ][:max_attempts]
    x0, y0, x1, y1 = record["source_box"]
    label_top = record["label_box"][1]
    width, height = source.size
    row_position = next(i for i, item in enumerate(row_records) if item["index"] == record["index"])
    left_neighbor = row_records[row_position - 1] if row_position > 0 else None
    right_neighbor = row_records[row_position + 1] if row_position + 1 < len(row_records) else None
    neighbor_centers = (
        (left_neighbor["label_box"][0] + left_neighbor["label_box"][2]) / 2 if left_neighbor else None,
        (right_neighbor["label_box"][0] + right_neighbor["label_box"][2]) / 2 if right_neighbor else None,
    )
    label_center = (record["label_box"][0] + record["label_box"][2]) / 2

    attempts: list[dict[str, Any]] = []
    best: tuple[int, Image.Image, dict[str, Any]] | None = None
    for attempt_number, config in enumerate(configs, start=1):
        expand = config["expand"]
        box = [
            max(0, x0 - expand),
            max(0, y0 - expand),
            min(width, x1 + expand),
            min(label_top - 1, y1 + expand),
        ]
        crop = source.crop(box)
        candidate_results = segmentation_candidates(
            crop,
            brightness_floor=config["brightness_floor"],
            color_tolerance=config["color_tolerance"],
            backend=segmentation_backend,
            rembg_model=rembg_model,
        )
        candidate_attempts = []
        for candidate_name, candidate_rgba, segmentation in candidate_results:
            rgba = candidate_rgba.copy()
            restored = restore_protected_polygons(
                rgba,
                crop,
                box,
                record.get("protected_polygons"),
            )
            segmentation = dict(segmentation)
            segmentation["protected_white_pixels_restored"] = restored
            qa = qa_segment(rgba, crop, box, source.size, label_center, neighbor_centers)
            candidate = {"name": candidate_name, "segmentation": segmentation, "qa": qa}
            candidate_attempts.append(candidate)
            if bbox_from_alpha(rgba[:, :, 3]) is None:
                continue
            output = center_on_canvas(rgba, output_size, padding)
            score = sum(int(issue.get("severity", 1)) for issue in qa["issues"])
            attempt = {
                "attempt": attempt_number,
                "source_box": box,
                "selected_candidate": candidate_name,
                "segmentation": segmentation,
                "qa": qa,
                "candidates": candidate_attempts,
            }
            if best is None or score < best[0]:
                best = (score, output, attempt)
            if qa["passed"]:
                attempts.append(attempt)
                return output, {
                    "passed": True,
                    "selected_attempt": attempt_number,
                    "selected_candidate": candidate_name,
                    "attempts": attempts,
                }
        attempts.append(
            {
                "attempt": attempt_number,
                "source_box": box,
                "selected_candidate": None,
                "segmentation": {},
                "qa": {"passed": False, "issues": []},
                "candidates": candidate_attempts,
            }
        )

    if best is None:
        return None, {"passed": False, "selected_attempt": None, "attempts": attempts}
    return best[1], {
        "passed": False,
        "selected_attempt": best[2]["attempt"],
        "selected_candidate": best[2].get("selected_candidate"),
        "attempts": attempts,
    }


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def save_detection_debug(source: Image.Image, records: list[dict[str, Any]], path: Path) -> None:
    debug = source.convert("RGB")
    draw = ImageDraw.Draw(debug)
    font = find_font(13)
    for record in records:
        draw.rectangle(record["source_box"], outline=(0, 170, 80), width=2)
        if record.get("detection_mode") != "unlabeled":
            draw.rectangle(record["label_box"], outline=(40, 100, 255), width=2)
        draw.text(
            (record["source_box"][0] + 3, record["source_box"][1] + 2),
            f'{record["index"]:02d}',
            fill=(220, 20, 20),
            font=font,
        )
    debug.save(path)


def checkerboard(size: int, block: int = 12) -> Image.Image:
    image = Image.new("RGB", (size, size), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    for y in range(0, size, block):
        for x in range(0, size, block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(226, 226, 226))
    return image


def save_contact_sheet(entries: list[dict[str, Any]], icons_dir: Path, path: Path) -> None:
    columns = min(6, max(1, math.ceil(math.sqrt(len(entries)))))
    tile = 150
    label_height = 34
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * tile, rows * (tile + label_height)), "white")
    font = find_font(13)
    draw = ImageDraw.Draw(sheet)
    for index, entry in enumerate(entries):
        row, column = divmod(index, columns)
        x = column * tile
        y = row * (tile + label_height)
        bg = checkerboard(tile)
        icon_path = icons_dir / entry["file"]
        if icon_path.exists():
            icon = Image.open(icon_path).convert("RGBA")
            icon.thumbnail((tile - 16, tile - 16), Image.Resampling.LANCZOS)
            bg.paste(icon, ((tile - icon.width) // 2, (tile - icon.height) // 2), icon)
        sheet.paste(bg, (x, y))
        label = f'{entry["index"]:02d} {entry["label"]}'
        draw.text((x + 5, y + tile + 6), label, fill=(20, 20, 20), font=font)
    sheet.save(path)


def save_qa_comparison(
    source: Image.Image,
    entries: list[dict[str, Any]],
    icons_dir: Path,
    path: Path,
) -> None:
    """Render source/output pairs on high-contrast backgrounds for visual QA."""
    panel = 180
    label_height = 30
    header_height = 34
    row_height = panel + label_height
    sheet = Image.new("RGB", (panel * 3, header_height + row_height * len(entries)), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = find_font(14)
    label_font = find_font(13)
    for column, title in enumerate(("SOURCE", "CHECKER", "COLOR")):
        draw.text((column * panel + 8, 8), title, fill=(20, 20, 20), font=title_font)

    for offset, entry in enumerate(entries):
        y = header_height + offset * row_height
        attempts = entry["qa"].get("attempts", [])
        selected = entry["qa"].get("selected_attempt")
        attempt = next((item for item in attempts if item["attempt"] == selected), None)
        box = attempt["source_box"] if attempt else [0, 0, source.width, source.height]
        crop = source.crop(box).convert("RGB")
        crop.thumbnail((panel - 16, panel - 16), Image.Resampling.LANCZOS)
        source_panel = Image.new("RGB", (panel, panel), "white")
        source_panel.paste(crop, ((panel - crop.width) // 2, (panel - crop.height) // 2))
        sheet.paste(source_panel, (0, y))

        icon = Image.open(icons_dir / entry["file"]).convert("RGBA")
        icon.thumbnail((panel - 16, panel - 16), Image.Resampling.LANCZOS)
        checker = checkerboard(panel)
        checker.paste(icon, ((panel - icon.width) // 2, (panel - icon.height) // 2), icon)
        sheet.paste(checker, (panel, y))

        contrast = Image.new("RGB", (panel, panel), (25, 35, 56))
        contrast_draw = ImageDraw.Draw(contrast)
        contrast_draw.rectangle((panel // 2, 0, panel, panel), fill=(210, 38, 105))
        contrast.paste(icon, ((panel - icon.width) // 2, (panel - icon.height) // 2), icon)
        sheet.paste(contrast, (panel * 2, y))
        draw.text(
            (8, y + panel + 6),
            f'{entry["index"]:02d} {entry["label"]}',
            fill=(20, 20, 20),
            font=label_font,
        )
    sheet.save(path)


def write_typescript(entries: list[dict[str, Any]], path: Path) -> None:
    lines = ["export const Icons = {"]
    for entry in entries:
        lines.append(f'  {entry["id"]}: "/assets/icons/{entry["file"]}",')
    lines.append("} as const;\n")
    lines.append("export const IconLabels: Record<keyof typeof Icons, string> = {")
    for entry in entries:
        label = json.dumps(entry["label"], ensure_ascii=False)
        lines.append(f'  {entry["id"]}: {label},')
    lines.extend(["};", "", "export type IconName = keyof typeof Icons;", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def create_zip(out_dir: Path, zip_path: Path, entries: list[dict[str, Any]]) -> None:
    files = [out_dir / "icon-map.json", out_dir / "icons.ts", out_dir / "qa-report.json"]
    files.extend(out_dir / "icons" / entry["file"] for entry in entries)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists():
                archive.write(path, path.relative_to(out_dir))


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    prepare_output_directory(out_dir)
    icons_dir = out_dir / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    source = Image.open(image_path).convert("RGBA")
    width, height = source.size
    labels = read_labels(args.labels)
    raw_ocr: list[dict[str, Any]] = []
    records: list[dict[str, Any]]
    row_counts: list[int]
    detection_mode = args.mode
    detection_details: dict[str, Any] = {}
    caption_error: str | None = None
    if args.mode != "unlabeled":
        try:
            raw_ocr = load_ocr(image_path, args.ocr_json)
            text_items = pixel_text_items(raw_ocr, width, height)
            caption_rows = cluster_caption_rows(text_items, width, height)
            records = build_icon_records(caption_rows, width, height, labels)
            for record in records:
                record["detection_mode"] = "captioned"
            row_counts = [len(row) for row in caption_rows]
            detection_mode = "captioned"
        except RuntimeError as error:
            if args.mode == "captioned":
                raise
            caption_error = str(error)
            detection_mode = "unlabeled"

    if detection_mode == "unlabeled":
        records, row_counts, detection_details = build_unlabeled_records(source, labels)

    (out_dir / "ocr-raw.json").write_text(
        json.dumps(raw_ocr, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    apply_overrides(records, args.overrides)
    save_detection_debug(source, records, out_dir / "detection-debug.png")

    by_row: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        by_row.setdefault(record["row"], []).append(record)

    entries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for record in records:
        icon, qa = attempt_icon(
            source,
            record,
            by_row[record["row"]],
            args.max_attempts,
            args.size,
            args.padding,
            args.segmentation_backend,
            args.rembg_model,
        )
        filename = safe_filename(record["index"], record["label"])
        entry = {
            "index": record["index"],
            "id": f'icon{record["index"]:03d}',
            "label": record["label"],
            "file": filename,
            "ocr_text": record["ocr_text"],
            "ocr_confidence": record["ocr_confidence"],
            "label_overridden": record["label_overridden"],
            "detection_mode": record["detection_mode"],
            "row": record["row"],
            "column": record["column"],
            "qa": qa,
        }
        if icon is not None:
            icon.save(icons_dir / filename)
        if not qa["passed"] or icon is None:
            failures.append(
                {
                    "index": record["index"],
                    "label": record["label"],
                    "type": "extraction_qa_failed",
                }
            )
        entries.append(entry)

    uncertain_names = []
    if detection_mode == "captioned" and labels is None:
        uncertain_names = [
            {
                "index": entry["index"],
                "ocr_text": entry["ocr_text"],
                "confidence": entry["ocr_confidence"],
            }
            for entry in entries
            if entry["ocr_confidence"] < args.min_name_confidence
        ]

    manifest = {
        "source": str(image_path),
        "count": len(entries),
        "icons": [
            {key: entry[key] for key in ("index", "id", "label", "file", "row", "column")}
            for entry in entries
        ],
    }
    (out_dir / "icon-map.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_typescript(entries, out_dir / "icons.ts")
    save_contact_sheet(entries, icons_dir, out_dir / "contact-sheet.png")
    save_qa_comparison(source, entries, icons_dir, out_dir / "qa-comparison.png")

    passed = not failures and not uncertain_names
    report = {
        "status": "pass" if passed else "needs_review",
        "source": str(image_path),
        "detection_mode": detection_mode,
        "segmentation_backend": args.segmentation_backend,
        "rembg_model": args.rembg_model if args.segmentation_backend != "boundary" else None,
        "detection_details": detection_details,
        "caption_fallback_reason": caption_error,
        "detected_rows": row_counts,
        "detected_caption_rows": row_counts if detection_mode == "captioned" else None,
        "detected_icon_count": len(entries),
        "labels_overridden": labels is not None,
        "uncertain_names": uncertain_names,
        "failures": failures,
        "icons": entries,
        "publish_gate": {
            "passed": passed,
            "zip_created": False,
            "reason": None if passed else "Resolve QA failures and uncertain OCR names before publishing.",
        },
        "visual_qa": {
            "required": True,
            "artifact": "qa-comparison.png",
            "instruction": "Compare every SOURCE panel with CHECKER and COLOR; reject any white_removed or missing_component result.",
        },
    }
    report_path = out_dir / "qa-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = Path(args.zip_name).expanduser().resolve() if args.zip_name else out_dir / "icons.zip"
    if passed or args.allow_failures:
        report["publish_gate"]["zip_created"] = True
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        create_zip(out_dir, zip_path, entries)
        print(f"PASS: exported {len(entries)} icons to {zip_path}")
        return 0 if passed else 2

    print(
        f"NEEDS_REVIEW: detected {len(entries)} icons; "
        f"failures={len(failures)}, uncertain_names={len(uncertain_names)}. "
        f"See {report_path}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
