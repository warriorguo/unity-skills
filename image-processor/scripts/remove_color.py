#!/usr/bin/env python3
"""Remove a specific color from an image, replacing it with transparency.

Supports RGB hex colors and a tolerance parameter to catch near-matches.
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def hex_to_rgb(hex_str):
    """Parse a hex color string (e.g. '#FF00FF' or 'FF00FF') to (R, G, B)."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        print(f"Error: invalid hex color '{hex_str}', expected 6 hex digits (e.g. FF00FF)", file=sys.stderr)
        sys.exit(1)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        print(f"Error: invalid hex color '{hex_str}'", file=sys.stderr)
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove a specific color from an image, making matched pixels transparent."
    )
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path (must support transparency, e.g. PNG/WEBP)")
    parser.add_argument(
        "--color",
        required=True,
        help="Color to remove as hex (e.g. '#FF00FF' or 'FF00FF') or 'R,G,B' (e.g. '255,0,255')",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="Color distance tolerance 0-255 (default: 0 = exact match). "
        "Pixels within this Euclidean distance from the target color are removed.",
    )
    return parser.parse_args()


def parse_color(color_str):
    """Parse color from hex or R,G,B format."""
    if "," in color_str:
        parts = color_str.split(",")
        if len(parts) != 3:
            print(f"Error: invalid color '{color_str}', expected R,G,B", file=sys.stderr)
            sys.exit(1)
        try:
            rgb = tuple(int(p.strip()) for p in parts)
        except ValueError:
            print(f"Error: invalid color '{color_str}'", file=sys.stderr)
            sys.exit(1)
        for v in rgb:
            if not 0 <= v <= 255:
                print(f"Error: color values must be 0-255, got {v}", file=sys.stderr)
                sys.exit(1)
        return rgb
    return hex_to_rgb(color_str)


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if output_path.suffix.lower() in (".jpg", ".jpeg", ".bmp"):
        print(
            f"Error: output format '{output_path.suffix}' does not support transparency. Use PNG or WEBP.",
            file=sys.stderr,
        )
        sys.exit(1)

    target = parse_color(args.color)
    tolerance = args.tolerance
    if tolerance < 0 or tolerance > 255:
        print("Error: --tolerance must be between 0 and 255", file=sys.stderr)
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")
    data = np.array(img, dtype=np.float64)

    # Compute Euclidean distance in RGB space
    diff = data[:, :, :3] - np.array(target, dtype=np.float64)
    dist = np.sqrt(np.sum(diff ** 2, axis=2))

    # Create mask of pixels to make transparent
    mask = dist <= tolerance

    # Apply: set alpha to 0 for matched pixels
    result = np.array(img)
    result[mask, 3] = 0

    out_img = Image.fromarray(result, "RGBA")

    save_kwargs = {}
    if output_path.suffix.lower() == ".webp":
        save_kwargs["method"] = 6

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(output_path, **save_kwargs)

    matched_count = int(np.sum(mask))
    total = mask.size
    pct = matched_count / total * 100
    print(f"Removed color ({target[0]},{target[1]},{target[2]}) with tolerance {tolerance}")
    print(f"Matched {matched_count}/{total} pixels ({pct:.1f}%)")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
