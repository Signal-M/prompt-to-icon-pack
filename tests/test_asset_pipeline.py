from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "skills/generate-asset-pack/scripts/prepare_asset_pack.py"
CROSS = ROOT / "skills/generate-asset-pack/scripts/cross_batch_qa.py"
PACKAGE = ROOT / "skills/generate-asset-pack/scripts/package_asset_pack.py"
EXPORT = ROOT / "skills/export-asset-pack/scripts/export_asset_pack.py"
CAPTION = ROOT / "skills/generate-sticker-pack/scripts/render_sticker_text.py"
VECTOR = ROOT / "skills/vectorize-asset-pack/scripts/vectorize_asset_pack.py"
SPLITTER = ROOT / "skills/split-icon-sheet/scripts/split_icon_sheet.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], check=True, capture_output=True, text=True)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AssetPipelineTests(unittest.TestCase):
    def test_protected_polygon_restores_only_reviewed_white_region(self) -> None:
        module = load_module(SPLITTER, "split_icon_sheet")
        source = Image.new("RGBA", (40, 40), (252, 252, 250, 255))
        rgba = __import__("numpy").zeros((40, 40, 4), dtype="uint8")
        restored = module.restore_protected_polygons(
            rgba,
            source,
            [100, 200, 140, 240],
            [[[110, 210], [130, 210], [130, 230], [110, 230]]],
        )
        self.assertGreater(restored, 0)
        self.assertEqual(int(rgba[20, 20, 3]), 255)
        self.assertEqual(int(rgba[2, 2, 3]), 0)

    def test_qa_comparison_includes_source_and_contrast_panels(self) -> None:
        module = load_module(SPLITTER, "split_icon_sheet_comparison")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            icons = root / "icons"
            icons.mkdir()
            icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(icon).ellipse((12, 8, 52, 56), fill=(252, 252, 250, 255))
            icon.save(icons / "001-test.png")
            source = Image.new("RGBA", (80, 80), "white")
            ImageDraw.Draw(source).ellipse((18, 12, 62, 68), fill=(252, 252, 250, 255), outline=(70, 150, 40, 255), width=2)
            entries = [{
                "index": 1,
                "label": "test",
                "file": "001-test.png",
                "qa": {"selected_attempt": 1, "attempts": [{"attempt": 1, "source_box": [0, 0, 80, 80]}]},
            }]
            target = root / "qa-comparison.png"
            module.save_qa_comparison(source, entries, icons, target)
            with Image.open(target) as rendered:
                self.assertEqual(rendered.width, 540)
                self.assertGreater(rendered.height, 180)

    def test_quality_plans_45_as_five_nine_asset_sheets(self) -> None:
        module = load_module(PREPARE, "prepare_asset_pack")
        self.assertEqual(module.plan_batch_counts(45, 9), [9, 9, 9, 9, 9])

    def test_presets_and_style_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "plan"
            run(str(PREPARE), "--spec", str(ROOT / "tests/fixtures/asset-spec.json"), "--out", str(out))
            plan = json.loads((out / "batch-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["asset_kind"], "sticker")
            self.assertEqual(plan["count"], 24)
            self.assertTrue(plan["requires_style_anchor"])
            self.assertTrue(all(batch["count"] <= 9 for batch in plan["batches"]))
            self.assertEqual(sum(batch["count"] for batch in plan["batches"]), 24)
            self.assertTrue((out / "style-contract.json").exists())

    def test_universal_48_balanced_uses_multiple_complete_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps({"preset": "universal-ui-48", "density": "balanced"}), encoding="utf-8")
            out = Path(temp) / "plan"
            run(str(PREPARE), "--spec", str(spec_path), "--out", str(out))
            plan = json.loads((out / "batch-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["count"], 48)
            self.assertGreater(len(plan["batches"]), 1)
            self.assertTrue(all(batch["rows"] * batch["columns"] == batch["count"] for batch in plan["batches"]))

    def test_export_and_caption(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            assets.mkdir()
            records = []
            for index, color in enumerate(((80, 190, 50, 255), (255, 160, 40, 255)), 1):
                image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.ellipse((16, 12, 80, 84), fill=color)
                name = f"{index:03d}-asset.png"
                image.save(assets / name)
                records.append({"index": index, "id": f"asset-{index:03d}", "label": f"表情{index}", "file": name})
            manifest = {"project": "test", "asset_kind": "sticker", "count": 2, "assets": records}
            manifest_path = root / "asset-map.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            exported = root / "exported"
            run(str(EXPORT), "--manifest", str(manifest_path), "--assets", str(assets), "--out", str(exported),
                "--formats", "png,webp", "--sizes", "64,96", "--sprite")
            self.assertTrue((exported / "png/64/001-asset.png").exists())
            self.assertTrue((exported / "webp/96/002-asset.webp").exists())
            self.assertTrue((exported / "sprite/asset-sprite.png").exists())
            self.assertTrue((exported / "asset-export.zip").exists())

            captioned = root / "captioned"
            run(str(CAPTION), "--manifest", str(manifest_path), "--assets", str(assets), "--out", str(captioned))
            self.assertTrue((captioned / "001-asset.png").exists())
            report = json.loads((captioned / "caption-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["count"], 2)

    def test_cross_batch_gate_and_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shapes = ("ellipse", "rectangle", "triangle", "cross")
            batches = []
            for batch_index in (1, 2):
                batch_name = f"batch-{batch_index:02d}"
                split = root / batch_name / "split"
                icons = split / "icons"
                icons.mkdir(parents=True)
                mapped = []
                planned = []
                for local in (1, 2):
                    global_index = (batch_index - 1) * 2 + local
                    label = f"shape-{global_index}"
                    filename = f"{local:03d}-{label}.png"
                    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(image)
                    shape = shapes[global_index - 1]
                    if shape == "ellipse":
                        draw.ellipse((18, 14, 78, 82), fill=(80, 190, 50, 255))
                    elif shape == "rectangle":
                        draw.rounded_rectangle((15, 22, 81, 74), radius=8, fill=(245, 160, 35, 255))
                    elif shape == "triangle":
                        draw.polygon(((48, 12), (82, 80), (14, 80)), fill=(70, 145, 235, 255))
                    else:
                        draw.rectangle((39, 12, 57, 84), fill=(225, 80, 120, 255))
                        draw.rectangle((12, 39, 84, 57), fill=(225, 80, 120, 255))
                    image.save(icons / filename)
                    mapped.append({"label": label, "file": filename})
                    planned.append({
                        "id": f"asset-{global_index:03d}-{label}", "global_index": global_index,
                        "label": label, "description": label,
                    })
                (split / "icon-map.json").write_text(json.dumps({"count": 2, "icons": mapped}), encoding="utf-8")
                (split / "qa-report.json").write_text(json.dumps({
                    "status": "pass", "checks": {}, "publish_gate": {"passed": True}
                }), encoding="utf-8")
                (root / batch_name / "semantic-qa.json").write_text(json.dumps({
                    "status": "pass", "expected_count": 2, "observed_count": 2,
                    "checks": {
                        "count": True, "order_and_semantics": True, "style_consistency": True,
                        "identity_consistency": True, "no_duplicates_or_omissions": True,
                        "crop_and_alpha": True, "source_fidelity": True,
                        "white_preservation": True, "naming": True,
                    },
                }), encoding="utf-8")
                batches.append({
                    "batch": batch_index, "count": 2, "global_start": (batch_index - 1) * 2 + 1,
                    "split_output": f"{batch_name}/split", "semantic_qa": f"{batch_name}/semantic-qa.json",
                    "assets": planned,
                })
            plan = {
                "version": 2, "project": "qa-test", "asset_kind": "icon", "style": "test style",
                "count": 4, "cross_batch_qa": "cross-batch-qa.json", "global_visual_qa": "global-visual-qa.json",
                "targets": ["generic"], "batches": batches,
            }
            plan_path = root / "batch-plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            run(str(CROSS), "--plan", str(plan_path))
            cross = json.loads((root / "cross-batch-qa.json").read_text(encoding="utf-8"))
            self.assertEqual(cross["status"], "pass")
            (root / "global-visual-qa.json").write_text(json.dumps({
                "status": "pass", "checks": {
                    "style_anchor_adherence": True, "cross_batch_palette": True,
                    "cross_batch_scale_and_padding": True, "character_identity": True,
                    "global_semantic_coverage": True,
                },
            }), encoding="utf-8")
            final = root / "final"
            run(str(PACKAGE), "--plan", str(plan_path), "--out", str(final))
            self.assertTrue((final / "asset-pack.zip").exists())
            self.assertEqual(json.loads((final / "asset-map.json").read_text(encoding="utf-8"))["count"], 4)

    def test_svg_sanitizer_removes_active_content(self) -> None:
        module = load_module(VECTOR, "vectorize_asset_pack")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "unsafe.svg"
            target = root / "safe.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" onclick="alert(1)">'
                '<script>alert(1)</script><path d="M2 2h20v20H2z" fill="#7ac943"/>'
                '</svg>', encoding="utf-8")
            report = module.sanitize_svg(source, target, 20, 10000)
            content = target.read_text(encoding="utf-8")
            self.assertNotIn("script", content)
            self.assertNotIn("onclick", content)
            self.assertEqual(report["shape_count"], 1)


if __name__ == "__main__":
    unittest.main()
