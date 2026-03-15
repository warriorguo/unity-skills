#!/usr/bin/env python3
"""Resize images using PIL/Pillow.

Supports setting width, height, scale factor, and format conversion.
Preserves aspect ratio by default when only one dimension is specified.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

RESAMPLE_METHODS = {
    "lanczos": Image.LANCZOS,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
    "nearest": Image.NEAREST,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Resize an image.")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--width", type=int, help="Target width in pixels")
    parser.add_argument("--height", type=int, help="Target height in pixels")
    parser.add_argument("--scale", type=float, help="Scale factor (e.g. 0.5 = half size)")
    parser.add_argument(
        "--keep-ratio",
        action="store_true",
        help="When both width and height are given, fit within the box preserving aspect ratio",
    )
    parser.add_argument(
        "--resample",
        choices=RESAMPLE_METHODS.keys(),
        default="lanczos",
        help="Resampling method (default: lanczos)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="Output quality for JPEG/WEBP (1-100, default: 95)",
    )
    return parser.parse_args()


def compute_new_size(orig_w, orig_h, args):
    if args.scale is not None:
        if args.width or args.height:
            print("Error: --scale cannot be combined with --width/--height", file=sys.stderr)
            sys.exit(1)
        return round(orig_w * args.scale), round(orig_h * args.scale)

    if args.width and args.height:
        if args.keep_ratio:
            ratio = min(args.width / orig_w, args.height / orig_h)
            return round(orig_w * ratio), round(orig_h * ratio)
        return args.width, args.height

    if args.width:
        ratio = args.width / orig_w
        return args.width, round(orig_h * ratio)

    if args.height:
        ratio = args.height / orig_h
        return round(orig_w * ratio), args.height

    print("Error: specify --width, --height, or --scale", file=sys.stderr)
    sys.exit(1)


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    img = Image.open(input_path)
    orig_w, orig_h = img.size

    new_w, new_h = compute_new_size(orig_w, orig_h, args)

    if new_w <= 0 or new_h <= 0:
        print(f"Error: invalid dimensions {new_w}x{new_h}", file=sys.stderr)
        sys.exit(1)

    resample = RESAMPLE_METHODS[args.resample]
    resized = img.resize((new_w, new_h), resample)

    # Handle RGBA -> RGB for JPEG
    output_path = Path(args.output)
    output_ext = output_path.suffix.lower()
    if output_ext in (".jpg", ".jpeg") and resized.mode == "RGBA":
        resized = resized.convert("RGB")

    # Prepare save kwargs
    save_kwargs = {}
    if output_ext in (".jpg", ".jpeg", ".webp"):
        save_kwargs["quality"] = args.quality
    if output_ext == ".webp":
        save_kwargs["method"] = 6  # best compression

    output_path.parent.mkdir(parents=True, exist_ok=True)
    resized.save(output_path, **save_kwargs)

    print(f"{orig_w}x{orig_h} -> {new_w}x{new_h}  [{input_path} -> {output_path}]")


if __name__ == "__main__":
    main()
