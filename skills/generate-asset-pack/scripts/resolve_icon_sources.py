#!/usr/bin/env python3
"""Resolve generic UI icons from Iconify before spending generation calls."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


DEFAULT_API = "https://api.iconify.design"
DEFAULT_PREFIXES = "lucide,material-symbols,tabler,ph"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="batch-plan.json from prepare_asset_pack.py")
    parser.add_argument("--out", required=True, help="Output directory for candidates and accepted SVGs")
    parser.add_argument("--api-base", default=DEFAULT_API)
    parser.add_argument("--prefixes", default=DEFAULT_PREFIXES, help="Comma-separated Iconify prefixes")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--accept-threshold", type=float, default=0.98)
    parser.add_argument("--catalog", help="Offline fixture/cache JSON; never contacts Iconify")
    parser.add_argument("--download", action="store_true", help="Download only automatically accepted SVGs")
    return parser.parse_args()


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def score_candidate(query: str, qualified_name: str) -> float:
    name = qualified_name.split(":", 1)[-1]
    query_slug = normalize(query)
    name_slug = normalize(name)
    if not query_slug or not name_slug:
        return 0.0
    if query_slug == name_slug:
        return 1.0
    if name_slug in {f"{query_slug}-outline", f"{query_slug}-rounded", f"{query_slug}-icon"}:
        return 0.99
    query_tokens = set(query_slug.split("-"))
    name_tokens = set(name_slug.split("-"))
    overlap = len(query_tokens & name_tokens) / max(1, len(query_tokens | name_tokens))
    contains = 0.78 if query_slug in name_slug or name_slug in query_slug else 0.0
    return round(max(overlap * 0.9, contains), 4)


def http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "prompt-to-icon-pack/0.7"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def http_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "prompt-to-icon-pack/0.7"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def sanitize_svg(payload: bytes) -> bytes:
    if len(payload) > 2_000_000:
        raise ValueError("SVG exceeds 2 MB safety limit")
    root = ET.fromstring(payload)
    if root.tag.split("}")[-1] != "svg":
        raise ValueError("Downloaded payload is not an SVG")
    forbidden = {"script", "foreignObject", "iframe", "object", "embed"}
    for parent in root.iter():
        for child in list(parent):
            if child.tag.split("}")[-1] in forbidden:
                parent.remove(child)
        for key in list(parent.attrib):
            local = key.split("}")[-1].casefold()
            value = html.unescape(parent.attrib[key]).strip().casefold()
            if local.startswith("on") or "javascript:" in value:
                del parent.attrib[key]
            elif local in {"href", "src"} and value and not value.startswith("#"):
                del parent.attrib[key]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def load_assets(plan_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assets = [asset for batch in plan.get("batches", []) for asset in batch.get("assets", [])]
    if plan.get("asset_kind") != "icon":
        raise ValueError("Library-first resolution is only valid for asset_kind=icon")
    if plan.get("reference_images"):
        raise ValueError("Library-first resolution is disabled for reference-identity work")
    if not assets:
        raise ValueError("Plan contains no assets")
    return plan, assets


def load_catalog(path: str | None) -> dict[str, Any] | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def search_icons(query: str, prefixes: str, limit: int, api_base: str, catalog: dict[str, Any] | None) -> list[str]:
    if catalog is not None:
        return list(catalog.get("search", {}).get(query, []))[:limit]
    params = urllib.parse.urlencode({"query": query, "limit": limit, "prefixes": prefixes})
    payload = http_json(f"{api_base.rstrip('/')}/search?{params}")
    return [str(value) for value in payload.get("icons", [])]


def get_svg(qualified_name: str, api_base: str, catalog: dict[str, Any] | None) -> bytes:
    if catalog is not None:
        value = catalog.get("svg", {}).get(qualified_name)
        if value is None:
            raise ValueError(f"Offline catalog has no SVG for {qualified_name}")
        return str(value).encode("utf-8")
    if ":" not in qualified_name:
        raise ValueError(f"Invalid Iconify name: {qualified_name}")
    prefix, name = qualified_name.split(":", 1)
    return http_bytes(f"{api_base.rstrip('/')}/{urllib.parse.quote(prefix)}/{urllib.parse.quote(name)}.svg")


def safe_name(index: int, label: str) -> str:
    slug = normalize(label) or f"icon-{index:03d}"
    return f"{index:03d}-{slug}.svg"


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    svg_dir = out_dir / "svg"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not 1 <= args.limit <= 64:
        raise ValueError("limit must be between 1 and 64")
    if not 0 <= args.accept_threshold <= 1:
        raise ValueError("accept threshold must be between 0 and 1")

    plan, assets = load_assets(plan_path)
    catalog = load_catalog(args.catalog)
    resolutions = []
    for index, asset in enumerate(assets, 1):
        query = str(asset.get("description") or asset["label"]).strip()
        names = search_icons(query, args.prefixes, args.limit, args.api_base, catalog)
        candidates = sorted(
            ({"name": name, "score": score_candidate(query, name)} for name in names),
            key=lambda item: (-item["score"], item["name"]),
        )
        selected = candidates[0] if candidates and candidates[0]["score"] >= args.accept_threshold else None
        record: dict[str, Any] = {
            "index": index,
            "id": asset.get("id"),
            "label": asset["label"],
            "query": query,
            "status": "accepted" if selected else ("review" if candidates else "unmatched"),
            "selected": selected,
            "candidates": candidates,
        }
        if selected and args.download:
            svg_dir.mkdir(parents=True, exist_ok=True)
            filename = safe_name(index, str(asset["label"]))
            (svg_dir / filename).write_bytes(sanitize_svg(get_svg(selected["name"], args.api_base, catalog)))
            record["file"] = f"svg/{filename}"
            record["source_url"] = f"{args.api_base.rstrip('/')}/{selected['name'].replace(':', '/')}.svg"
        resolutions.append(record)

    accepted = sum(record["status"] == "accepted" for record in resolutions)
    report = {
        "version": 1,
        "provider": "iconify",
        "project": plan.get("project"),
        "prefixes": [value for value in args.prefixes.split(",") if value],
        "accept_threshold": args.accept_threshold,
        "count": len(resolutions),
        "accepted": accepted,
        "requires_review": len(resolutions) - accepted,
        "license_notice": "Verify each selected icon set license before redistribution.",
        "resolutions": resolutions,
    }
    target = out_dir / "library-resolution.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Resolved {accepted}/{len(resolutions)} icons automatically; review report: {target}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}")
