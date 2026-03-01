#!/usr/bin/env python3
"""Unity Sprite Slicer - Modify Unity 2022 texture .meta files to slice
sprites into a grid using Grid by Cell Count mode.

Zero external dependencies: PNG dimensions parsed via struct, .meta files
manipulated with text-level operations (no PyYAML).
"""

import os
import re
import struct
import sys
import uuid


# ---------------------------------------------------------------------------
# Phase 1: Infrastructure
# ---------------------------------------------------------------------------

def read_image_dimensions(path):
    """Read width and height from a PNG file by parsing the IHDR chunk.

    PNG layout: 8-byte signature, then chunks. The first chunk is always IHDR
    at offset 8 (4-byte length + 4-byte type), with width and height as two
    big-endian uint32 at offsets 16 and 20.
    """
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24:
        raise ValueError(f"File too small to be a valid PNG: {path}")
    sig = header[:8]
    if sig != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a valid PNG file: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def format_unity_number(v):
    """Format a number for Unity YAML. Integers render without decimal point."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return str(v)
    return str(v)


def generate_sprite_id():
    """Generate a 32-character hex spriteID (like Unity's internal format)."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Phase 2: YAML Generation
# ---------------------------------------------------------------------------

def generate_sprite_entry(name, x, y, w, h, internal_id):
    """Generate the YAML text block for a single sprite entry.

    All fields match Unity 2022's Sprite Editor output format.
    """
    sprite_id = generate_sprite_id()
    lines = [
        f"    - serializedVersion: 2",
        f"      name: {name}",
        f"      rect:",
        f"        serializedVersion: 2",
        f"        x: {format_unity_number(x)}",
        f"        y: {format_unity_number(y)}",
        f"        width: {format_unity_number(w)}",
        f"        height: {format_unity_number(h)}",
        f"      alignment: 0",
        f"      pivot: {{x: 0.5, y: 0.5}}",
        f"      border: {{x: 0, y: 0, z: 0, w: 0}}",
        f"      outline: []",
        f"      physicsShape: []",
        f"      tessellationDetail: -1",
        f"      bones: []",
        f"      spriteID: {sprite_id}",
        f"      internalID: {internal_id}",
        f"      vertices: []",
        f"      indices: ",
        f"      edges: []",
        f"      weights: []",
    ]
    return "\n".join(lines)


def generate_sprites_block(image_name, img_w, img_h, rows, cols):
    """Generate the complete sprites: block with rows*cols sprite entries.

    Coordinate system: Unity uses bottom-left origin.
    - sprite(r, c): x = c * cellW, y = imgH - (r+1) * cellH
    - Naming: {imageName}_{index}, index goes left-to-right, top-to-bottom
    - internalID starts at 21300000, increments by 2
    """
    cell_w = img_w / cols
    cell_h = img_h / rows
    entries = []
    internal_id = 21300000
    index = 0
    for r in range(rows):
        for c in range(cols):
            name = f"{image_name}_{index}"
            x = c * cell_w
            y = img_h - (r + 1) * cell_h
            # Use integers when dimensions divide evenly
            if cell_w == int(cell_w):
                x = int(x)
                cell_w_out = int(cell_w)
            else:
                cell_w_out = cell_w
            if cell_h == int(cell_h):
                y = int(y)
                cell_h_out = int(cell_h)
            else:
                cell_h_out = cell_h
            entries.append(generate_sprite_entry(name, x, y, cell_w_out, cell_h_out, internal_id))
            internal_id += 2
            index += 1
    return "    sprites:\n" + "\n".join(entries)


# ---------------------------------------------------------------------------
# Phase 3: Text-level .meta Modification
# ---------------------------------------------------------------------------

def replace_scalar_in_meta(content, key, value):
    """Replace a scalar property value in a .meta file using regex.

    Matches lines like '  spriteMode: 1' and replaces the value portion.
    """
    pattern = re.compile(r"^(\s+" + re.escape(key) + r":)\s*\S.*$", re.MULTILINE)
    replacement = rf"\1 {format_unity_number(value)}"
    new_content, count = pattern.subn(replacement, content)
    if count == 0:
        raise ValueError(f"Key '{key}' not found in .meta file")
    return new_content


def replace_sprites_block(content, new_block):
    """Replace the sprites: block inside spriteSheet: section.

    Handles two cases:
    1. sprites: []  (empty array, single line)
    2. sprites:\\n    - ...  (multi-line entries)

    Strategy: find spriteSheet: line, then within that scope find sprites:
    and determine the block boundary by indentation scanning.
    """
    lines = content.split("\n")

    # Find spriteSheet: line
    sheet_idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s+spriteSheet:\s*$", line):
            sheet_idx = i
            break
    if sheet_idx is None:
        raise ValueError("spriteSheet: section not found in .meta file")

    # Determine spriteSheet indentation
    sheet_indent = len(lines[sheet_idx]) - len(lines[sheet_idx].lstrip())

    # Find sprites: within spriteSheet scope
    sprites_idx = None
    for i in range(sheet_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        line_indent = len(lines[i]) - len(stripped)
        # If we hit a line at same or lesser indent as spriteSheet, we've left the section
        if stripped and line_indent <= sheet_indent:
            break
        if re.match(r"\s+sprites:", lines[i]):
            sprites_idx = i
            break
    if sprites_idx is None:
        raise ValueError("sprites: not found under spriteSheet: section")

    # Determine the end of the sprites block
    sprites_line = lines[sprites_idx]
    sprites_indent = len(sprites_line) - len(sprites_line.lstrip())

    # Case 1: sprites: [] (single line, empty array)
    if re.match(r"\s+sprites:\s*\[\]\s*$", sprites_line):
        block_end = sprites_idx + 1
    else:
        # Case 2: multi-line sprites block
        # Find end by scanning for next line at same or lesser indent that isn't a continuation
        block_end = sprites_idx + 1
        for i in range(sprites_idx + 1, len(lines)):
            stripped = lines[i].lstrip()
            if not stripped:
                # Empty line - continue scanning
                block_end = i + 1
                continue
            line_indent = len(lines[i]) - len(stripped)
            if line_indent <= sprites_indent:
                block_end = i
                break
            block_end = i + 1

    # Replace the block
    new_lines = lines[:sprites_idx] + new_block.split("\n") + lines[block_end:]
    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# Phase 4: Commands
# ---------------------------------------------------------------------------

def cmd_slice(args):
    """Slice a sprite image into a grid of rows x cols."""
    if len(args) < 3:
        print("Usage: slice <image_path> <rows> <cols>", file=sys.stderr)
        sys.exit(1)

    image_path = args[0]
    try:
        rows = int(args[1])
        cols = int(args[2])
    except ValueError:
        print("Error: rows and cols must be integers", file=sys.stderr)
        sys.exit(1)

    if rows < 1 or cols < 1:
        print("Error: rows and cols must be >= 1", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(image_path):
        print(f"Error: Image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    meta_path = image_path + ".meta"
    if not os.path.isfile(meta_path):
        print(f"Error: Meta file not found: {meta_path}", file=sys.stderr)
        sys.exit(1)

    # Read image dimensions
    img_w, img_h = read_image_dimensions(image_path)
    print(f"Image dimensions: {img_w}x{img_h}")
    print(f"Grid: {rows} rows x {cols} cols")

    cell_w = img_w / cols
    cell_h = img_h / rows
    print(f"Cell size: {format_unity_number(cell_w)}x{format_unity_number(cell_h)}")

    # Read .meta file
    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Set spriteMode to 2 (Multiple)
    content = replace_scalar_in_meta(content, "spriteMode", 2)

    # Set textureType to 8 (Sprite)
    content = replace_scalar_in_meta(content, "textureType", 8)

    # Generate sprite entries
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    sprites_block = generate_sprites_block(image_name, img_w, img_h, rows, cols)

    # Replace sprites block
    content = replace_sprites_block(content, sprites_block)

    # Write back with LF line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    with open(meta_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    total = rows * cols
    print(f"Generated {total} sprite entries")
    print(f"Updated: {meta_path}")


def cmd_inspect(args):
    """Inspect current sprite import settings of an image."""
    if len(args) < 1:
        print("Usage: inspect <image_path>", file=sys.stderr)
        sys.exit(1)

    image_path = args[0]
    meta_path = image_path + ".meta"
    if not os.path.isfile(meta_path):
        print(f"Error: Meta file not found: {meta_path}", file=sys.stderr)
        sys.exit(1)

    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract key fields
    sprite_mode_match = re.search(r"^\s+spriteMode:\s*(\d+)", content, re.MULTILINE)
    texture_type_match = re.search(r"^\s+textureType:\s*(\d+)", content, re.MULTILINE)

    sprite_mode = int(sprite_mode_match.group(1)) if sprite_mode_match else None
    texture_type = int(texture_type_match.group(1)) if texture_type_match else None

    mode_names = {0: "None", 1: "Single", 2: "Multiple"}
    type_names = {0: "Default", 1: "NormalMap", 2: "GUI", 8: "Sprite"}

    print(f"File: {meta_path}")
    if sprite_mode is not None:
        print(f"spriteMode: {sprite_mode} ({mode_names.get(sprite_mode, 'Unknown')})")
    if texture_type is not None:
        print(f"textureType: {texture_type} ({type_names.get(texture_type, 'Unknown')})")

    # Count and list sprites
    sprite_names = re.findall(r"^\s+name:\s*(.+)$", content, re.MULTILINE)
    sprite_rects = re.findall(
        r"^\s+rect:\s*\n\s+serializedVersion:\s*\d+\s*\n"
        r"\s+x:\s*(\S+)\s*\n\s+y:\s*(\S+)\s*\n"
        r"\s+width:\s*(\S+)\s*\n\s+height:\s*(\S+)",
        content, re.MULTILINE
    )

    # Only count sprites under spriteSheet section
    in_sprite_sheet = False
    sprite_count = 0
    sheet_indent = None
    for line in content.split("\n"):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if re.match(r"\s+spriteSheet:\s*$", line):
            in_sprite_sheet = True
            sheet_indent = indent
            continue
        if in_sprite_sheet and stripped and indent <= sheet_indent:
            in_sprite_sheet = False
        if in_sprite_sheet and re.match(r"\s+name:\s*\S", line):
            sprite_count += 1

    print(f"Sprites: {sprite_count}")

    if sprite_count > 0:
        # Re-parse to get sprite details under spriteSheet
        lines = content.split("\n")
        in_sheet = False
        in_rect = False
        current_name = None
        current_rect = {}
        sprites_info = []

        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            if re.match(r"\s+spriteSheet:\s*$", line):
                in_sheet = True
                sheet_indent = indent
                continue
            if in_sheet and stripped and indent <= sheet_indent:
                in_sheet = False

            if not in_sheet:
                continue

            name_match = re.match(r"\s+name:\s*(.+)$", line)
            if name_match:
                if current_name is not None:
                    sprites_info.append((current_name, dict(current_rect)))
                current_name = name_match.group(1).strip()
                current_rect = {}
                in_rect = False

            if re.match(r"\s+rect:\s*$", line):
                in_rect = True
                continue

            # Exit rect context when we hit a non-rect field at the same level
            if in_rect and stripped and not re.match(r"(serializedVersion|x|y|width|height):", stripped):
                in_rect = False

            if in_rect and current_name is not None:
                for key in ("x", "y", "width", "height"):
                    m = re.match(rf"\s+{key}:\s*(\S+)$", line)
                    if m:
                        current_rect[key] = m.group(1)

        if current_name is not None:
            sprites_info.append((current_name, dict(current_rect)))

        print()
        for name, rect in sprites_info:
            if rect:
                print(f"  {name}: x={rect.get('x', '?')}, y={rect.get('y', '?')}, "
                      f"w={rect.get('width', '?')}, h={rect.get('height', '?')}")
            else:
                print(f"  {name}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Unity Sprite Slicer - Grid by Cell Count", file=sys.stderr)
        print("", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  slice <image_path> <rows> <cols>  Slice sprite into grid", file=sys.stderr)
        print("  inspect <image_path>              View sprite import settings", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "slice": cmd_slice,
        "inspect": cmd_inspect,
    }

    if command not in commands:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available commands: {', '.join(commands)}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
