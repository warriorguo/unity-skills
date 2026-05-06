#!/usr/bin/env python3
"""Convert an image from one format to another.

Handles common formats (jpg/jpeg, png, webp, bmp, tiff, gif), preserves
transparency where the target format supports it, and flattens RGBA over a
configurable background color when going to a non-alpha format like JPEG.
EXIF Orientation is applied on input so the output is always upright.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

# Map user-facing format names to Pillow's canonical format string.
FORMAT_ALIASES = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
    "gif": "GIF",
}

# Formats that support an alpha channel.
ALPHA_FORMATS = {"PNG", "WEBP", "GIF", "TIFF"}

# Default extension for each canonical format.
FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "GIF": ".gif",
}


def normalize_format(name):
    """Normalize a user-supplied format name to Pillow's canonical name."""
    key = name.lower().lstrip(".")
    if key not in FORMAT_ALIASES:
        raise ValueError(
            f"Unsupported format '{name}'. Supported: {', '.join(sorted(FORMAT_ALIASES))}"
        )
    return FORMAT_ALIASES[key]


def parse_color(spec):
    """Parse 'R,G,B' or 'R,G,B,A' (each 0-255) into a tuple."""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) not in (3, 4):
        raise ValueError(f"Background color must have 3 or 4 components, got: {spec}")
    try:
        values = tuple(int(p) for p in parts)
    except ValueError:
        raise ValueError(f"Background color components must be integers, got: {spec}")
    for v in values:
        if not 0 <= v <= 255:
            raise ValueError(f"Background color components must be 0-255, got: {spec}")
    return values


def parse_args():
    parser = argparse.ArgumentParser(description="Convert an image between formats.")
    parser.add_argument("input", help="Input image path")
    parser.add_argument(
        "output",
        nargs="?",
        help=(
            "Output image path. If omitted, the output is written next to the "
            "input with the target extension (requires --to)."
        ),
    )
    parser.add_argument(
        "--to",
        dest="target_format",
        help=(
            "Target format (e.g. jpg, png, webp, bmp, tiff, gif). Overrides "
            "the format inferred from the output extension."
        ),
    )
    parser.add_argument(
        "--bg-color",
        default="255,255,255",
        help=(
            "Background color used to flatten transparency when the target "
            "format has no alpha channel (e.g. JPEG). 'R,G,B' or 'R,G,B,A', "
            "default: '255,255,255' (white)."
        ),
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="Quality for lossy formats (JPEG/WEBP). 1-100, default: 95.",
    )
    parser.add_argument(
        "--no-auto-orient",
        action="store_true",
        help="Skip applying EXIF Orientation on input.",
    )
    parser.add_argument(
        "--keep-exif",
        action="store_true",
        help=(
            "Preserve EXIF metadata in the output (orientation is reset to "
            "Top-left since pixels are already rotated)."
        ),
    )
    return parser.parse_args()


def resolve_target_format(args):
    if args.target_format:
        return normalize_format(args.target_format)
    if args.output:
        ext = Path(args.output).suffix
        if not ext:
            raise ValueError(
                "Cannot infer target format from output path with no extension. "
                "Pass --to <format>."
            )
        return normalize_format(ext)
    raise ValueError("Either an output path with extension or --to <format> is required.")


def resolve_output_path(args, target_format):
    if args.output:
        return Path(args.output)
    return Path(args.input).with_suffix(FORMAT_EXTENSIONS[target_format])


def flatten_on_background(img, bg_color):
    """Composite an RGBA/LA image onto a solid background, returning RGB."""
    if img.mode not in ("RGBA", "LA") and not (img.mode == "P" and "transparency" in img.info):
        return img.convert("RGB")
    rgba = img.convert("RGBA")
    if len(bg_color) == 4:
        bg_color = bg_color[:3]
    background = Image.new("RGB", rgba.size, bg_color)
    background.paste(rgba, mask=rgba.split()[3])
    return background


def main():
    args = parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    try:
        target_format = resolve_target_format(args)
        out_path = resolve_output_path(args, target_format)
        bg_color = parse_color(args.bg_color)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        img = Image.open(in_path)
    except Exception as e:
        print(f"Error: failed to open image: {e}", file=sys.stderr)
        sys.exit(1)

    src_format = img.format or "?"
    src_mode = img.mode

    # Apply EXIF orientation so the output is upright.
    if not args.no_auto_orient:
        img = ImageOps.exif_transpose(img)

    # Decide the output mode based on whether the target format supports alpha.
    if target_format in ALPHA_FORMATS:
        if img.mode == "P" and "transparency" in img.info:
            img = img.convert("RGBA")
        elif img.mode not in ("RGBA", "LA", "RGB", "L", "P"):
            img = img.convert("RGBA")
    else:
        img = flatten_on_background(img, bg_color)

    save_kwargs = {"format": target_format}
    if target_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = args.quality
    if target_format == "JPEG":
        save_kwargs["optimize"] = True

    if args.keep_exif:
        exif = img.getexif()
        if exif:
            # Orientation is now Top-left because we already applied exif_transpose.
            exif[0x0112] = 1
            save_kwargs["exif"] = exif.tobytes()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        img.save(out_path, **save_kwargs)
    except Exception as e:
        print(f"Error: failed to save image: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"{in_path} ({src_format}, {src_mode}) -> {out_path} ({target_format}, {img.mode})"
    )


if __name__ == "__main__":
    main()
