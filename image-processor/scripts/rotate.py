#!/usr/bin/env python3
"""Rotate or flip an image.

Supports 90/180/270 quick rotations, arbitrary angle rotation,
and horizontal/vertical flips.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Rotate or flip an image.")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument(
        "--angle",
        type=float,
        help="Rotation angle in degrees (counter-clockwise). Positive = CCW, negative = CW.",
    )
    parser.add_argument(
        "--flip",
        choices=["horizontal", "vertical", "both"],
        help="Flip the image: horizontal (left-right), vertical (top-bottom), or both",
    )
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Expand the canvas to fit the entire rotated image (default: crop to original size)",
    )
    parser.add_argument(
        "--bg-color",
        default="0,0,0,0",
        help="Background color for empty areas after rotation, as R,G,B or R,G,B,A (default: transparent)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="Output quality for JPEG/WEBP (1-100, default: 95)",
    )
    return parser.parse_args()


def parse_color(color_str):
    """Parse R,G,B or R,G,B,A color string."""
    parts = color_str.split(",")
    if len(parts) not in (3, 4):
        print(f"Error: invalid color '{color_str}', expected R,G,B or R,G,B,A", file=sys.stderr)
        sys.exit(1)
    try:
        values = tuple(int(p.strip()) for p in parts)
    except ValueError:
        print(f"Error: invalid color '{color_str}'", file=sys.stderr)
        sys.exit(1)
    for v in values:
        if not 0 <= v <= 255:
            print(f"Error: color values must be 0-255, got {v}", file=sys.stderr)
            sys.exit(1)
    if len(values) == 3:
        return values + (255,)
    return values


def main():
    args = parse_args()

    if args.angle is None and args.flip is None:
        print("Error: specify --angle, --flip, or both", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")
    orig_w, orig_h = img.size

    # Apply flip first
    if args.flip:
        if args.flip == "horizontal":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif args.flip == "vertical":
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif args.flip == "both":
            img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)

    # Apply rotation
    if args.angle is not None:
        angle = args.angle
        # Use fast transpose for exact 90/180/270
        normalized = angle % 360
        if normalized == 90:
            img = img.transpose(Image.ROTATE_90)
        elif normalized == 180:
            img = img.transpose(Image.ROTATE_180)
        elif normalized == 270:
            img = img.transpose(Image.ROTATE_270)
        elif normalized != 0:
            bg_color = parse_color(args.bg_color)
            img = img.rotate(angle, resample=Image.BICUBIC, expand=args.expand, fillcolor=bg_color)

    # Handle output format
    output_ext = output_path.suffix.lower()
    save_kwargs = {}
    if output_ext in (".jpg", ".jpeg"):
        img = img.convert("RGB")
        save_kwargs["quality"] = args.quality
    elif output_ext == ".webp":
        save_kwargs["quality"] = args.quality
        save_kwargs["method"] = 6

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, **save_kwargs)

    new_w, new_h = img.size
    actions = []
    if args.flip:
        actions.append(f"flip={args.flip}")
    if args.angle is not None:
        actions.append(f"rotate={args.angle}°")
    print(f"{orig_w}x{orig_h} -> {new_w}x{new_h}  [{', '.join(actions)}]")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
