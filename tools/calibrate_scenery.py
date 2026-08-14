"""Detect the playable Home Village diamond in downloaded scenery images.

The detector starts from the image centre, segments the relatively uniform
placeable field, and reports four normalized corners. It is intentionally kept
dependency-light (Pillow + NumPy) so the catalog can be regenerated locally.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SCENERY_DIR = ROOT / "assets" / "game" / "scenery"


def connected_component(mask: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    height, width = mask.shape
    sx, sy = start
    if not mask[sy, sx]:
        return np.zeros_like(mask)
    seen = np.zeros_like(mask)
    queue = deque([(sx, sy)])
    seen[sy, sx] = True
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                queue.append((nx, ny))
    return seen


def detect_corners(path: Path) -> dict[str, list[float]]:
    with Image.open(path) as source:
        ratio = source.height / source.width
        image = source.convert("RGB").resize((320, max(140, round(320 * ratio))))
    image = image.filter(ImageFilter.GaussianBlur(radius=3.2))
    pixels = np.asarray(image, dtype=np.float32)
    height, width, _ = pixels.shape
    cx, cy = width // 2, height // 2
    dx = np.sqrt(np.sum((pixels[:, 1:] - pixels[:, :-1]) ** 2, axis=2))
    dy = np.sqrt(np.sum((pixels[1:] - pixels[:-1]) ** 2, axis=2))
    gradient = np.zeros((height, width), dtype=np.float32)
    gradient[:, 1:] += dx
    gradient[1:, :] += dy

    candidates = []
    for tolerance in (7, 10, 13, 17, 22, 28, 36, 46):
        component = connected_component(gradient < tolerance, (cx, cy))
        area = component.mean()
        if not (0.02 <= area <= 0.62):
            continue
        ys0, xs0 = np.nonzero(component)
        box_area = (xs0.max() - xs0.min() + 1) * (ys0.max() - ys0.min() + 1) / (width * height)
        fill = area / max(box_area, 1e-6)
        touches_edge = xs0.min() == 0 or ys0.min() == 0 or xs0.max() == width - 1 or ys0.max() == height - 1
        score = abs(fill - 0.52) + (0.8 if touches_edge else 0) + abs(area - 0.20) * 0.25
        candidates.append((score, component))
    best = min(candidates, key=lambda item: item[0])[1] if candidates else None
    if best is None or not best.any():
        raise RuntimeError(f"Could not segment playable field: {path.name}")

    ys, xs = np.nonzero(best)
    # Quantiles reject trees, paths, and isolated pixels that leak through the
    # colour threshold while retaining the straight edges of the field.
    def corner(score: np.ndarray, quantile: float, low: bool) -> list[float]:
        limit = np.quantile(score, quantile)
        chosen = score <= limit if low else score >= limit
        return [float(np.median(xs[chosen]) / width), float(np.median(ys[chosen]) / height)]

    top = corner(ys, 0.004, True)
    right = corner(xs, 0.996, False)
    bottom = corner(ys, 0.996, False)
    left = corner(xs, 0.004, True)
    return {"top": top, "right": right, "bottom": bottom, "left": left}


def calibrated_corners(path: Path, slug: str) -> dict[str, list[float]]:
    with Image.open(path) as source:
        aspect = source.width / source.height
    # The original 3705x2545 captures share one camera transform. Their broad
    # grassy border sometimes connects to the forest during segmentation, so a
    # measured preset is more reliable than colour-based detection.
    if 1.42 <= aspect <= 1.50:
        return {"top": [0.51, 0.10], "right": [0.85, 0.48], "bottom": [0.51, 0.87], "left": [0.19, 0.52]}
    # XL/legendary panorama captures keep a much smaller village plateau in the
    # middle of the artwork.
    if aspect >= 1.55:
        return {"top": [0.50, 0.29], "right": [0.65, 0.50], "bottom": [0.50, 0.70], "left": [0.35, 0.50]}
    # Portrait arena artwork (currently Mash-A-Rama) uses this taller framing.
    if aspect < 0.90:
        return {"top": [0.50, 0.35], "right": [0.84, 0.51], "bottom": [0.50, 0.68], "left": [0.16, 0.51]}
    try:
        return detect_corners(path)
    except RuntimeError:
        return {"top": [0.50, 0.18], "right": [0.79, 0.46], "bottom": [0.50, 0.74], "left": [0.21, 0.46]}


def display_name(slug: str) -> str:
    special = {
        "9th-clashiversary": "9th Clashiversary",
        "10th-clashiversary": "10th Clashiversary",
        "13th-clash-a-versary": "13th Clash-A-Versary",
        "clash-a-rama": "Clash-A-Rama",
        "clashamania": "ClashaMania",
    }
    return special.get(slug, slug.replace("-", " ").title())


catalog = []
requested = set(sys.argv[1:])
manifest_path = SCENERY_DIR / "manifest.json"
if manifest_path.exists():
    records = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["id"], []).append(record)
    assets = []
    for slug, variants in sorted(grouped.items()):
        preferred = next((item for item in variants if item["variant"] == "closeup"), None)
        preferred = preferred or next((item for item in variants if item["variant"] == "default"), None)
        preferred = preferred or variants[0]
        assets.append((slug, SCENERY_DIR / preferred["file"]))
else:
    # Backward compatibility for manually supplied scenery files.
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    files = [path for path in SCENERY_DIR.iterdir() if path.suffix.lower() in extensions]
    bases = [path for path in files if not path.stem.endswith(("-closeup", "-full"))]
    assets = []
    for asset in sorted(bases):
        closeup = next((path for path in files if path.stem == f"{asset.stem}-closeup"), None)
        assets.append((asset.stem, closeup or asset))

for slug, display_asset in assets:
    if requested and slug not in requested:
        continue
    catalog.append({
        "id": slug,
        "name": display_name(slug),
        "file": display_asset.name,
        "grid": calibrated_corners(display_asset, slug),
    })

payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
output = ROOT / "assets" / "js" / "scenery-catalog.js"
output.write_text(f"window.SCENERY_CATALOG={payload};\n", encoding="utf-8")
print(f"Wrote {len(catalog)} calibrated sceneries to {output.relative_to(ROOT)}")
