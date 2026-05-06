#!/usr/bin/env python3
"""Mirror-copy regions within an image along midlines or diagonals.

Clears the target region, then mirror-copies the source region into it.
Supports horizontal/vertical midlines and 45/135 degree diagonals.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

VALID_SOURCES = {
    "horizontal": ("top", "bottom"),
    "vertical": ("left", "right"),
    "diagonal-45": ("upper", "lower"),
    "diagonal-135": ("upper", "lower"),
}


def mirror_horizontal(arr, source):
    """Mirror along horizontal midline (top <-> bottom)."""
    h = arr.shape[0]
    mid = h // 2
    result = arr.copy()

    if source == "top":
        result[h - mid :] = arr[:mid][::-1]
    else:
        result[:mid] = arr[h - mid :][::-1]

    return result


def mirror_vertical(arr, source):
    """Mirror along vertical midline (left <-> right)."""
    w = arr.shape[1]
    mid = w // 2
    result = arr.copy()

    if source == "left":
        result[:, w - mid :] = arr[:, :mid][:, ::-1]
    else:
        result[:, :mid] = arr[:, w - mid :][:, ::-1]

    return result


def mirror_diagonal_45(arr, source):
    """Mirror along 45 deg diagonal (top-left to bottom-right, y=x line).

    Operates on the square region side=min(W,H).
    'upper' = top-right triangle (y < x), 'lower' = bottom-left triangle (y > x).
    Mapping: (x, y) <-> (y, x).
    """
    h, w = arr.shape[:2]
    side = min(w, h)
    result = arr.copy()

    yy, xx = np.mgrid[0:side, 0:side]
    src_sq = arr[:side, :side]

    if source == "upper":
        mask = yy > xx  # target = lower-left
        ty, tx = np.where(mask)
        result[:side, :side][mask] = 0
        result[ty, tx] = src_sq[tx, ty]
    else:
        mask = yy < xx  # target = upper-right
        ty, tx = np.where(mask)
        result[:side, :side][mask] = 0
        result[ty, tx] = src_sq[tx, ty]

    return result


def mirror_diagonal_135(arr, source):
    """Mirror along 135 deg diagonal (top-right to bottom-left, y+x=side-1 line).

    Operates on the square region side=min(W,H).
    'upper' = top-left triangle (y+x < side-1), 'lower' = bottom-right triangle (y+x > side-1).
    Mapping: (x, y) <-> (side-1-y, side-1-x).
    """
    h, w = arr.shape[:2]
    side = min(w, h)
    result = arr.copy()

    yy, xx = np.mgrid[0:side, 0:side]
    s = side - 1
    src_sq = arr[:side, :side]

    if source == "upper":
        mask = (yy + xx) > s  # target = lower-right
        ty, tx = np.where(mask)
        result[:side, :side][mask] = 0
        result[ty, tx] = src_sq[s - tx, s - ty]
    else:
        mask = (yy + xx) < s  # target = upper-left
        ty, tx = np.where(mask)
        result[:side, :side][mask] = 0
        result[ty, tx] = src_sq[s - tx, s - ty]

    return result


HANDLERS = {
    "horizontal": mirror_horizontal,
    "vertical": mirror_vertical,
    "diagonal-45": mirror_diagonal_45,
    "diagonal-135": mirror_diagonal_135,
}


def main():
    parser = argparse.ArgumentParser(
        description="Mirror-copy regions within an image along midlines or diagonals."
    )
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument(
        "--axis",
        required=True,
        choices=list(VALID_SOURCES.keys()),
        help="Mirror axis: horizontal (top/bottom), vertical (left/right), "
        "diagonal-45 (TL-BR), diagonal-135 (TR-BL)",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=["top", "bottom", "left", "right", "upper", "lower"],
        help="Source region to keep and mirror-copy to the opposite side",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG/WEBP quality 1-100 (default: 95)",
    )
    args = parser.parse_args()

    valid = VALID_SOURCES[args.axis]
    if args.source not in valid:
        print(
            f"Error: --source '{args.source}' invalid for --axis '{args.axis}'. "
            f"Use: {', '.join(valid)}",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")
    w, h = img.size
    arr = np.array(img)

    result = HANDLERS[args.axis](arr, args.source)

    if args.axis.startswith("diagonal-") and w != h:
        side = min(w, h)
        print(f"Note: non-square image, diagonal operates on {side}x{side} region")

    out_img = Image.fromarray(result)
    output_ext = output_path.suffix.lower()
    save_kw = {}
    if output_ext in (".jpg", ".jpeg"):
        out_img = out_img.convert("RGB")
        save_kw["quality"] = args.quality
    elif output_ext == ".webp":
        save_kw["quality"] = args.quality

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(output_path, **save_kw)

    print(f"{w}x{h} -> {w}x{h}  [axis={args.axis}, source={args.source}]")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
