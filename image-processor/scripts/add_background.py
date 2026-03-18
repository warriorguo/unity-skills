#!/usr/bin/env python3
"""Add a background image behind a foreground image (compositing via alpha).

For Unity sprite sheets (.meta file present with multiple sprites), the background
is resized and composited per-tile so each slice gets its own background.
"""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(
        description="Composite a foreground image onto a background image. "
        "Supports Unity sliced sprite sheets (auto-detects .meta)."
    )
    parser.add_argument("foreground", help="Foreground image path (the image with transparency)")
    parser.add_argument("background", help="Background image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument(
        "--no-unity",
        action="store_true",
        help="Skip Unity .meta detection; treat as a plain image even if .meta exists",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="Output quality for JPEG/WEBP (1-100, default: 95)",
    )
    return parser.parse_args()


def parse_unity_meta_sprites(meta_path):
    """Parse sprite rects from a Unity .meta file.

    Returns a list of dicts with keys: name, x, y, width, height.
    Unity coordinates have origin at bottom-left.
    Returns empty list if spriteMode != 2 (Multiple) or no sprites found.
    """
    text = meta_path.read_text(encoding="utf-8")

    # Check spriteMode: 2 means Multiple
    mode_match = re.search(r"spriteMode:\s*(\d+)", text)
    if not mode_match or mode_match.group(1) != "2":
        return []

    # Find the sprites array under spriteSheet
    sprites_section = re.search(r"spriteSheet:.*?sprites:(.*?)(?:\n\s{2,4}\w|\Z)", text, re.DOTALL)
    if not sprites_section:
        return []

    sprites_text = sprites_section.group(1)

    # Split into individual sprite entries
    entries = re.split(r"\n\s*- serializedVersion:", sprites_text)
    results = []
    for entry in entries:
        name_m = re.search(r"name:\s*(\S+)", entry)
        rect_m = re.search(
            r"rect:.*?x:\s*([\d.]+).*?y:\s*([\d.]+).*?width:\s*([\d.]+).*?height:\s*([\d.]+)",
            entry,
            re.DOTALL,
        )
        if name_m and rect_m:
            results.append({
                "name": name_m.group(1),
                "x": int(float(rect_m.group(1))),
                "y": int(float(rect_m.group(2))),
                "width": int(float(rect_m.group(3))),
                "height": int(float(rect_m.group(4))),
            })

    return results


def composite_on_background(fg_img, bg_img):
    """Paste foreground onto a resized copy of background, using fg alpha."""
    bg = bg_img.resize(fg_img.size, Image.LANCZOS).convert("RGBA")
    fg = fg_img.convert("RGBA")
    bg.paste(fg, (0, 0), fg)
    return bg


def main():
    args = parse_args()

    fg_path = Path(args.foreground)
    bg_path = Path(args.background)
    output_path = Path(args.output)

    if not fg_path.exists():
        print(f"Error: foreground file not found: {fg_path}", file=sys.stderr)
        sys.exit(1)
    if not bg_path.exists():
        print(f"Error: background file not found: {bg_path}", file=sys.stderr)
        sys.exit(1)

    fg_img = Image.open(fg_path).convert("RGBA")
    bg_img = Image.open(bg_path).convert("RGBA")
    img_w, img_h = fg_img.size

    # Check for Unity .meta
    meta_path = Path(str(fg_path) + ".meta")
    sprites = []
    if not args.no_unity and meta_path.exists():
        sprites = parse_unity_meta_sprites(meta_path)
        if sprites:
            print(f"Unity sprite sheet detected: {len(sprites)} tiles in {meta_path.name}")

    if sprites:
        # Process each tile individually.
        # Unity rect origin is bottom-left; PIL origin is top-left.
        result = fg_img.copy()
        for sp in sprites:
            # Convert Unity bottom-left coords to PIL top-left coords
            pil_x = sp["x"]
            pil_y = img_h - sp["y"] - sp["height"]
            w, h = sp["width"], sp["height"]

            # Crop the foreground tile
            tile = fg_img.crop((pil_x, pil_y, pil_x + w, pil_y + h))

            # Composite tile onto resized background
            merged_tile = composite_on_background(tile, bg_img)

            # Paste back
            result.paste(merged_tile, (pil_x, pil_y))
            print(f"  Tile '{sp['name']}': ({pil_x},{pil_y}) {w}x{h}")
    else:
        # Plain image: composite entire foreground onto background
        result = composite_on_background(fg_img, bg_img)
        print(f"Composited {img_w}x{img_h} foreground onto background")

    # Handle output format
    output_ext = output_path.suffix.lower()
    save_kwargs = {}
    if output_ext in (".jpg", ".jpeg"):
        result = result.convert("RGB")
        save_kwargs["quality"] = args.quality
    elif output_ext == ".webp":
        save_kwargs["quality"] = args.quality
        save_kwargs["method"] = 6

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, **save_kwargs)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
