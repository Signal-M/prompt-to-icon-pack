#!/usr/bin/env python3
"""Plan or execute one named Recraft SVG generation request per unresolved icon."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any

from resolve_icon_sources import sanitize_svg


API_BASE = "https://external.api.recraft.ai/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="batch-plan.json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--library-resolution", help="Generate only records not accepted by library-first routing")
    parser.add_argument("--model", default="recraftv4_1_vector")
    parser.add_argument("--size", default="1:1")
    parser.add_argument("--style-id", help="Recraft V3 custom style UUID")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--execute", action="store_true", help="Spend API units and download outputs")
    return parser.parse_args()


def load_prices() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "assets" / "provider-pricing.json"
    return json.loads(path.read_text(encoding="utf-8"))


def post_json(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "prompt-to-icon-pack/0.7"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bytes(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Recraft download URL must use HTTPS")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "prompt-to-icon-pack/0.7"}), timeout=90) as response:
        return response.read()


def decode_result(payload: dict[str, Any]) -> bytes:
    data = payload.get("data") or []
    if not data:
        raise ValueError("Recraft response contains no data")
    record = data[0]
    if record.get("b64_json"):
        return base64.b64decode(record["b64_json"], validate=True)
    if record.get("url"):
        return get_bytes(str(record["url"]))
    raise ValueError("Recraft response contains neither url nor b64_json")


def safe_slug(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "icon"


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("asset_kind") != "icon":
        raise ValueError("Recraft SVG routing currently supports asset_kind=icon")
    assets = [asset for batch in plan.get("batches", []) for asset in batch.get("assets", [])]

    skip_ids: set[str] = set()
    if args.library_resolution:
        library = json.loads(Path(args.library_resolution).read_text(encoding="utf-8"))
        skip_ids = {str(item.get("id")) for item in library.get("resolutions", []) if item.get("status") == "accepted"}
    assets = [asset for asset in assets if str(asset.get("id")) not in skip_ids]

    prices = load_prices()
    model_price = prices["providers"]["recraft"].get(args.model)
    if model_price is None:
        raise ValueError(f"No reviewed price for model {args.model}; update provider-pricing.json first")
    style_contract = str(plan.get("style", "cohesive production icon system"))
    requests = []
    for index, asset in enumerate(assets, 1):
        prompt = (
            f"Create one standalone UI icon for: {asset['description']}. "
            f"Shared icon-system style: {style_contract}. "
            "Centered, simple silhouette, consistent optical weight, no text, no watermark, transparent or empty background, one icon only."
        )
        body: dict[str, Any] = {"prompt": prompt, "model": args.model, "size": args.size, "n": 1, "response_format": "url"}
        if args.style_id:
            if not args.model.startswith("recraftv3"):
                raise ValueError("style-id is supported only with Recraft V3 models")
            body["style_id"] = args.style_id
        requests.append({"index": index, "id": asset.get("id"), "label": asset["label"], "request": body})

    run = {
        "version": 1,
        "provider": "recraft",
        "endpoint": f"{args.api_base.rstrip('/')}/images/generations",
        "model": args.model,
        "status": "planned",
        "request_count": len(requests),
        "unit_price_usd": model_price,
        "estimated_cost_usd": round(len(requests) * float(model_price), 4),
        "pricing_as_of": prices["as_of"],
        "requests": requests,
        "outputs": [],
    }
    report_path = out_dir / "recraft-run.json"
    report_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.execute:
        print(f"DRY_RUN: {len(requests)} SVG request(s), estimated ${run['estimated_cost_usd']:.2f}; plan: {report_path}")
        return 0

    token = os.environ.get("RECRAFT_API_TOKEN", "").strip()
    if not token:
        raise ValueError("--execute requires RECRAFT_API_TOKEN")
    svg_dir = out_dir / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    for request_record in requests:
        response = post_json(run["endpoint"], token, request_record["request"])
        payload = decode_result(response)
        if b"<svg" not in payload[:4096].lower():
            raise ValueError(f"Expected SVG output for {request_record['label']}")
        payload = sanitize_svg(payload)
        filename = f"{request_record['index']:03d}-{safe_slug(str(request_record['label']))}.svg"
        (svg_dir / filename).write_bytes(payload)
        run["outputs"].append({"id": request_record["id"], "label": request_record["label"], "file": f"svg/{filename}"})
        report_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run["status"] = "complete"
    report_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(run['outputs'])} SVG icon(s): {svg_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}")
