#!/usr/bin/env python3
"""Get detailed information about an image file.

Outputs dimensions, format, color mode, file size, DPI, bit depth,
EXIF data (if present), and other metadata.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def get_file_size_str(size_bytes):
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_bit_depth(img):
    """Estimate bit depth per channel."""
    mode_bits = {
        "1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8,
        "CMYK": 8, "YCbCr": 8, "LAB": 8, "HSV": 8,
        "I": 32, "F": 32, "LA": 8, "PA": 8, "RGBa": 8,
        "I;16": 16, "I;16L": 16, "I;16B": 16,
    }
    return mode_bits.get(img.mode, None)


def get_channel_count(img):
    """Get number of channels."""
    mode_channels = {
        "1": 1, "L": 1, "P": 1, "RGB": 3, "RGBA": 4,
        "CMYK": 4, "YCbCr": 3, "LAB": 3, "HSV": 3,
        "I": 1, "F": 1, "LA": 2, "PA": 2, "RGBa": 4,
    }
    return mode_channels.get(img.mode, len(img.getbands()))


def parse_exif(img):
    """Extract EXIF data as a readable dict."""
    exif_data = {}
    try:
        raw_exif = img._getexif()
        if not raw_exif:
            return exif_data
    except (AttributeError, Exception):
        return exif_data

    for tag_id, value in raw_exif.items():
        tag_name = TAGS.get(tag_id, f"Unknown({tag_id})")

        # Handle GPS info specially
        if tag_name == "GPSInfo" and isinstance(value, dict):
            gps = {}
            for gps_tag_id, gps_value in value.items():
                gps_tag_name = GPSTAGS.get(gps_tag_id, f"Unknown({gps_tag_id})")
                gps[gps_tag_name] = str(gps_value)
            exif_data["GPSInfo"] = gps
            continue

        # Convert bytes and other non-serializable types to string
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:
                value = repr(value)
        elif not isinstance(value, (str, int, float, bool, list)):
            value = str(value)

        exif_data[tag_name] = value

    return exif_data


def get_image_info(image_path, include_exif=True):
    """Gather all image information into a dict."""
    path = Path(image_path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    file_size = path.stat().st_size
    img = Image.open(path)
    width, height = img.size

    info = {
        "file": str(path.resolve()),
        "filename": path.name,
        "format": img.format or path.suffix.lstrip(".").upper(),
        "mode": img.mode,
        "channels": get_channel_count(img),
        "bit_depth": get_bit_depth(img),
        "width": width,
        "height": height,
        "megapixels": round(width * height / 1_000_000, 2),
        "file_size_bytes": file_size,
        "file_size": get_file_size_str(file_size),
        "dpi": img.info.get("dpi", None),
    }

    # Animation info
    is_animated = getattr(img, "is_animated", False)
    if is_animated:
        info["animated"] = True
        info["frames"] = getattr(img, "n_frames", 1)

    # Transparency
    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        info["has_transparency"] = True

    # ICC profile
    if "icc_profile" in img.info:
        info["has_icc_profile"] = True

    # EXIF
    if include_exif:
        exif = parse_exif(img)
        if exif:
            info["exif"] = exif

    return info


def print_text(info):
    """Print info in a readable text format."""
    print(f"File:        {info['filename']}")
    print(f"Path:        {info['file']}")
    print(f"Format:      {info['format']}")
    print(f"Dimensions:  {info['width']} x {info['height']} px")
    print(f"Megapixels:  {info['megapixels']} MP")
    print(f"Color Mode:  {info['mode']} ({info['channels']} channel{'s' if info['channels'] > 1 else ''})")
    if info["bit_depth"]:
        print(f"Bit Depth:   {info['bit_depth']} bits/channel")
    print(f"File Size:   {info['file_size']} ({info['file_size_bytes']} bytes)")
    if info.get("dpi"):
        print(f"DPI:         {info['dpi'][0]} x {info['dpi'][1]}")
    if info.get("animated"):
        print(f"Animated:    Yes ({info['frames']} frames)")
    if info.get("has_transparency"):
        print(f"Transparent: Yes")
    if info.get("has_icc_profile"):
        print(f"ICC Profile: Yes")

    exif = info.get("exif", {})
    if exif:
        print(f"\nEXIF Data ({len(exif)} tags):")
        # Show the most useful EXIF fields first
        priority_tags = [
            "Make", "Model", "DateTime", "DateTimeOriginal",
            "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength",
            "LensModel", "Software", "ImageWidth", "ImageLength",
        ]
        shown = set()
        for tag in priority_tags:
            if tag in exif:
                val = exif[tag]
                if not isinstance(val, dict):
                    print(f"  {tag}: {val}")
                    shown.add(tag)

        # Then show remaining tags
        for tag, val in sorted(exif.items()):
            if tag in shown or tag == "GPSInfo":
                continue
            if isinstance(val, dict):
                continue
            print(f"  {tag}: {val}")

        # GPS info last
        if "GPSInfo" in exif:
            print("  GPS:")
            for k, v in exif["GPSInfo"].items():
                print(f"    {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Get image file information.")
    parser.add_argument("input", help="Image file path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-exif", action="store_true", help="Skip EXIF data extraction")
    args = parser.parse_args()

    info = get_image_info(args.input, include_exif=not args.no_exif)

    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False, default=str))
    else:
        print_text(info)


if __name__ == "__main__":
    main()
