"""Create full-resolution diagnostic views for Skeleton Kingdom's 44x44 grid."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "game" / "scenery" / "skeleton-kingdom.jpg"
OUTPUT = ROOT / "tools" / "_skeleton-grid-rectified.png"
OVERLAY = ROOT / "tools" / "_skeleton-grid-overlay.jpg"
CENTER = ROOT / "tools" / "_skeleton-grid-center.png"
CORNERS_VIEW = ROOT / "tools" / "_skeleton-grid-corners.png"

# Initial boundary read from the full 9930x5370 source; optimization is performed
# in normalized coordinates so it remains independent from preview resolution.
CORNERS = {
    "top": (0.500, 0.224),
    "right": (0.647, 0.423),
    "bottom": (0.500, 0.628),
    "left": (0.354, 0.423),
}


def bilinear_sample(gray: np.ndarray, corners: dict[str, tuple[float, float]], size: int) -> np.ndarray:
    height, width = gray.shape
    points = {key: np.array([x * (width - 1), y * (height - 1)]) for key, (x, y) in corners.items()}
    axis = np.linspace(0.0, 1.0, size, dtype=np.float64)
    u, v = np.meshgrid(axis, axis)
    top, right, bottom, left = (points[key] for key in ("top", "right", "bottom", "left"))
    x = ((1-u)*(1-v)*top[0] + u*(1-v)*right[0] + u*v*bottom[0] + (1-u)*v*left[0])
    y = ((1-u)*(1-v)*top[1] + u*(1-v)*right[1] + u*v*bottom[1] + (1-u)*v*left[1])
    x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
    wx, wy = x - x0, y - y0
    return (
        gray[y0, x0] * (1-wx) * (1-wy)
        + gray[y0, x1] * wx * (1-wy)
        + gray[y1, x0] * (1-wx) * wy
        + gray[y1, x1] * wx * wy
    )


with Image.open(SOURCE) as image:
    rgb = image.convert("RGB")
    rgb_array = np.asarray(rgb, dtype=np.float32)
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    width, height = rgb.size

def border_score(points: np.ndarray) -> float:
    center = points.mean(axis=0)
    values = []
    for start, end in zip(points, np.roll(points, -1, axis=0)):
        vector = end - start
        normal = np.array([-vector[1], vector[0]], dtype=np.float64)
        normal /= np.linalg.norm(normal)
        midpoint = (start + end) / 2
        if np.dot(center - midpoint, normal) < 0:
            normal *= -1
        t = np.linspace(0.08, 0.92, 320)[:, None]
        edge = start + t * vector
        for distance in (8, 16, 24):
            inside = np.rint(edge + normal * distance).astype(np.int32)
            outside = np.rint(edge - normal * distance).astype(np.int32)
            inside[:, 0] = np.clip(inside[:, 0], 0, width - 1)
            inside[:, 1] = np.clip(inside[:, 1], 0, height - 1)
            outside[:, 0] = np.clip(outside[:, 0], 0, width - 1)
            outside[:, 1] = np.clip(outside[:, 1], 0, height - 1)
            a = rgb_array[inside[:, 1], inside[:, 0]]
            b = rgb_array[outside[:, 1], outside[:, 0]]
            values.append(np.linalg.norm(a - b, axis=1).mean())
    return float(np.mean(values))

optimized = np.array([[x * width, y * height] for x, y in CORNERS.values()], dtype=np.float64)
for step in (48, 24, 12, 6, 3, 1):
    improved = True
    while improved:
        improved = False
        baseline = border_score(optimized)
        for point_index in range(4):
            for axis_index in range(2):
                for direction in (-1, 1):
                    candidate = optimized.copy()
                    candidate[point_index, axis_index] += direction * step
                    score = border_score(candidate)
                    if score > baseline:
                        optimized, baseline, improved = candidate, score, True
print("optimized score", border_score(optimized))
for key, point in zip(CORNERS, optimized):
    print(f"optimized {key}: pixel=({point[0]:.1f}, {point[1]:.1f}) normalized=({point[0]/width:.6f}, {point[1]/height:.6f})")
CORNERS = {key: (float(point[0] / width), float(point[1] / height)) for key, point in zip(CORNERS, optimized)}

rectified = bilinear_sample(gray, CORNERS, 1408)
central = rectified[140:-140, 140:-140]
edge_x = np.abs(np.diff(central, axis=1)).mean(axis=0)
edge_y = np.abs(np.diff(central, axis=0)).mean(axis=1)
kernel = np.ones(5, dtype=np.float32) / 5
edge_x = np.convolve(edge_x, kernel, mode="same")
edge_y = np.convolve(edge_y, kernel, mode="same")

def phase_scores(profile: np.ndarray, offset: int, period: int = 32) -> list[tuple[float, int]]:
    scores = []
    for phase in range(period):
        indices = np.arange(phase, len(profile), period)
        scores.append((float(profile[indices].mean()), phase))
    return sorted(scores, reverse=True)

print("x phases", phase_scores(edge_x, 140)[:8])
print("y phases", phase_scores(edge_y, 140)[:8])
def period_search(profile: np.ndarray) -> list[tuple[float, float, int]]:
    candidates = []
    for period in np.arange(28.0, 36.01, 0.1):
        for phase in np.arange(0.0, period, 0.5):
            indices = np.rint(phase + np.arange(0, len(profile) / period) * period).astype(int)
            indices = indices[indices < len(profile)]
            candidates.append((float(profile[indices].mean()), float(period), int(round(phase * 2))))
    return sorted(candidates, reverse=True)

print("x periods", period_search(edge_x)[:8])
print("y periods", period_search(edge_y)[:8])
rectified_image = Image.fromarray(np.clip(rectified, 0, 255).astype(np.uint8), "L").convert("RGB")
rect_draw = ImageDraw.Draw(rectified_image, "RGBA")
for index in range(45):
    position = round(index * (1407 / 44))
    color = (255, 205, 65, 220) if index in (0, 44) else ((255, 226, 134, 145) if index % 5 == 0 else (255, 255, 255, 70))
    line_width = 3 if index in (0, 44) else (2 if index % 5 == 0 else 1)
    rect_draw.line((position, 0, position, 1407), fill=color, width=line_width)
    rect_draw.line((0, position, 1407, position), fill=color, width=line_width)
rectified_image.save(OUTPUT)
rectified_image.crop((384, 384, 1024, 1024)).save(CENTER)

overlay = rgb.copy()
draw = ImageDraw.Draw(overlay, "RGBA")
pixels = {key: (round(x * width), round(y * height)) for key, (x, y) in CORNERS.items()}
for index in range(45):
    t = index / 44
    a = (
        round((1-t) * pixels["top"][0] + t * pixels["right"][0]),
        round((1-t) * pixels["top"][1] + t * pixels["right"][1]),
    )
    b = (
        round((1-t) * pixels["left"][0] + t * pixels["bottom"][0]),
        round((1-t) * pixels["left"][1] + t * pixels["bottom"][1]),
    )
    c = (
        round((1-t) * pixels["top"][0] + t * pixels["left"][0]),
        round((1-t) * pixels["top"][1] + t * pixels["left"][1]),
    )
    d = (
        round((1-t) * pixels["right"][0] + t * pixels["bottom"][0]),
        round((1-t) * pixels["right"][1] + t * pixels["bottom"][1]),
    )
    color = (255, 210, 65, 205) if index in (0, 44) else ((255, 228, 145, 125) if index % 5 == 0 else (255, 255, 255, 45))
    line_width = 14 if index in (0, 44) else (8 if index % 5 == 0 else 3)
    draw.line((a, b), fill=color, width=line_width)
    draw.line((c, d), fill=color, width=line_width)
overlay.resize((1986, 1074), Image.Resampling.LANCZOS).save(OVERLAY, quality=94)

corner_sheet = Image.new("RGB", (1400, 1400), "black")
sheet_draw = ImageDraw.Draw(corner_sheet)
for slot, key in enumerate(("top", "right", "bottom", "left")):
    cx, cy = pixels[key]
    crop = rgb.crop((cx - 350, cy - 350, cx + 350, cy + 350))
    crop.save(ROOT / "tools" / f"_skeleton-grid-corner-{key}-raw.png")
    sample = np.asarray(crop, dtype=np.int16)
    red, green, blue = sample[:, :, 0], sample[:, :, 1], sample[:, :, 2]
    pavement = (
        (red >= 48) & (red <= 145) & (green >= 43) & (green <= 135)
        & (blue >= 30) & (blue <= 105) & (np.abs(red-green) <= 24)
        & ((green-blue) <= 30) & ((red-blue) >= 4)
    )
    density = sum(np.roll(np.roll(pavement, dy, axis=0), dx, axis=1) for dy in range(-3, 4) for dx in range(-3, 4))
    pavement = density >= 34
    rois = {"top": (310, 430, 300, 420), "right": (250, 400, 285, 420), "bottom": (290, 420, 300, 455), "left": (330, 465, 285, 420)}
    xmin, xmax, ymin, ymax = rois[key]
    rows, cols = np.indices(pavement.shape)
    yy, xx = np.nonzero(pavement & (rows >= ymin) & (rows <= ymax) & (cols >= xmin) & (cols <= xmax))
    if key == "top":
        edge = yy.min(); selected = xx[yy <= edge + 5]; detected = (int(np.median(selected)), int(edge))
    elif key == "right":
        edge = xx.max(); selected = yy[xx >= edge - 5]; detected = (int(edge), int(np.median(selected)))
    elif key == "bottom":
        edge = yy.max(); selected = xx[yy >= edge - 5]; detected = (int(np.median(selected)), int(edge))
    else:
        edge = xx.min(); selected = yy[xx <= edge + 5]; detected = (int(edge), int(np.median(selected)))
    print(f"detected {key}: crop={detected} source=({cx-350+detected[0]}, {cy-350+detected[1]})")
    crop_draw = ImageDraw.Draw(crop, "RGBA")
    crop_draw.line((350, 0, 350, 700), fill=(255, 80, 50, 210), width=4)
    crop_draw.line((0, 350, 700, 350), fill=(255, 80, 50, 210), width=4)
    crop_draw.ellipse((338, 338, 362, 362), outline=(255, 238, 90, 255), width=5)
    crop.save(ROOT / "tools" / f"_skeleton-grid-corner-{key}.png")
    x = (slot % 2) * 700
    y = (slot // 2) * 700
    corner_sheet.paste(crop, (x, y))
    sheet_draw.text((x + 16, y + 14), f"{key}: {cx}, {cy}", fill=(255, 245, 190))
corner_sheet.save(CORNERS_VIEW)

print(f"source={width}x{height}")
print(f"rectified={OUTPUT}")
print(f"overlay={OVERLAY}")
print(f"center={CENTER}")
print(f"corners={CORNERS_VIEW}")
