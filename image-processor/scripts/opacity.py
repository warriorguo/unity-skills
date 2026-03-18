#!/usr/bin/env python3
"""Adjust the opacity (alpha) of an image.

Scales the alpha channel by a given factor, making the image more or less transparent.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Adjust image opacity (transparency).")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path (must support transparency, e.g. PNG/WEBP)")
    parser.add_argument(
        "--opacity",
        type=float,
        required=True,
        help="Opacity factor 0.0-1.0 (0 = fully transparent, 1 = original, 0.5 = half transparent)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not 0.0 <= args.opacity <= 1.0:
        print("Error: --opacity must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if output_path.suffix.lower() in (".jpg", ".jpeg", ".bmp"):
        print(
            f"Error: output format '{output_path.suffix}' does not support transparency. Use PNG or WEBP.",
            file=sys.stderr,
        )
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")

    # Split channels, scale alpha, recombine
    r, g, b, a = img.split()
    a = a.point(lambda x: round(x * args.opacity))
    result = Image.merge("RGBA", (r, g, b, a))

    save_kwargs = {}
    if output_path.suffix.lower() == ".webp":
        save_kwargs["method"] = 6

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, **save_kwargs)

    pct = args.opacity * 100
    print(f"Opacity set to {pct:.0f}% — saved to {output_path}")


if __name__ == "__main__":
    main()
