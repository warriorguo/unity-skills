#!/usr/bin/env python3
"""Unity SpriteAnimationData Editor - Create and modify SpriteAnimationData
ScriptableObject .asset files for the custom SpriteAnimation system.

Zero external dependencies: all YAML operations use text templates + regex.
"""

import os
import re
import sys
import uuid

# GUID of the SpriteAnimationData.cs script (from its .meta file)
SPRITE_ANIM_DATA_SCRIPT_GUID = "e255f71bed24451b8118c587b72fadd5"


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

def read_guid_from_meta(meta_path):
    """Read the guid field from a Unity .meta file."""
    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"^guid:\s*([0-9a-f]+)", content, re.MULTILINE)
    if not m:
        raise ValueError(f"guid not found in {meta_path}")
    return m.group(1)


def read_sprites_from_meta(image_meta_path):
    """Read sprite entries from a sliced image .meta file.

    Scans the spriteSheet.sprites section and extracts each sprite's name
    and internalID. Returns list of dicts with 'name' and 'internal_id'.
    """
    with open(image_meta_path, "r", encoding="utf-8") as f:
        content = f.read()

    sprites = []
    # Match sprite entries: each starts with "- serializedVersion:" followed
    # by "name:" and "internalID:" lines
    sprite_blocks = re.split(r"^\s+- serializedVersion:\s*\d+", content, flags=re.MULTILINE)
    for block in sprite_blocks[1:]:  # skip first (before any sprite)
        name_m = re.search(r"^\s+name:\s*(.+)", block, re.MULTILINE)
        id_m = re.search(r"^\s+internalID:\s*(-?\d+)", block, re.MULTILINE)
        if name_m and id_m:
            sprites.append({
                "name": name_m.group(1).strip(),
                "internal_id": int(id_m.group(1)),
            })
    return sprites


def generate_guid():
    """Generate a Unity-style GUID (32 hex chars, no dashes)."""
    return uuid.uuid4().hex


def generate_meta_file(asset_path):
    """Generate a .meta file for a ScriptableObject .asset."""
    meta_path = asset_path + ".meta"
    if os.path.exists(meta_path):
        return  # don't overwrite existing meta
    guid = generate_guid()
    content = f"""fileFormatVersion: 2
guid: {guid}
NativeFormatImporter:
  externalObjects: {{}}
  mainObjectFileID: 11400000
  userData:
  assetBundleName:
  assetBundleVariant:
"""
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Created {meta_path}")


# ---------------------------------------------------------------------------
# SpriteAnimationData .asset generation
# ---------------------------------------------------------------------------

def build_asset_yaml(name, frames, fps, loop):
    """Build the YAML content for a SpriteAnimationData .asset file.

    frames: list of dicts with 'file_id' and 'guid'
    """
    lines = [
        "%YAML 1.1",
        "%TAG !u! tag:unity3d.com,2011:",
        "--- !u!114 &11400000",
        "MonoBehaviour:",
        "  m_ObjectHideFlags: 0",
        "  m_CorrespondingSourceObject: {fileID: 0}",
        "  m_PrefabInstance: {fileID: 0}",
        "  m_PrefabAsset: {fileID: 0}",
        "  m_GameObject: {fileID: 0}",
        "  m_Enabled: 1",
        "  m_EditorHideFlags: 0",
        f"  m_Script: {{fileID: 11500000, guid: {SPRITE_ANIM_DATA_SCRIPT_GUID}, type: 3}}",
        f"  m_Name: {name}",
        "  m_EditorClassIdentifier:",
        "  frames:",
    ]

    for frame in frames:
        lines.append(f"  - {{fileID: {frame['file_id']}, guid: {frame['guid']}, type: 3}}")

    # fps: integer if whole, otherwise float
    fps_val = int(fps) if fps == int(fps) else fps
    loop_val = 1 if loop else 0

    lines.append(f"  fps: {fps_val}")
    lines.append(f"  loop: {loop_val}")
    lines.append("")

    return "\n".join(lines)


def parse_asset_yaml(content):
    """Parse a SpriteAnimationData .asset file. Returns dict with name, frames, fps, loop."""
    name_m = re.search(r"^\s+m_Name:\s*(.+)", content, re.MULTILINE)
    fps_m = re.search(r"^\s+fps:\s*(\S+)", content, re.MULTILINE)
    loop_m = re.search(r"^\s+loop:\s*(\S+)", content, re.MULTILINE)

    # Parse frames — only entries under the "frames:" section (lines starting with "  - {")
    frames = []
    in_frames = False
    for line in content.splitlines():
        if re.match(r"^\s+frames:", line):
            in_frames = True
            continue
        if in_frames:
            m = re.match(r"^\s+- \{fileID:\s*(-?\d+),\s*guid:\s*([0-9a-f]+),\s*type:\s*3\}", line)
            if m:
                frames.append({"file_id": int(m.group(1)), "guid": m.group(2)})
            elif not line.strip().startswith("-"):
                in_frames = False

    return {
        "name": name_m.group(1).strip() if name_m else "Unknown",
        "frames": frames,
        "fps": float(fps_m.group(1)) if fps_m else 24.0,
        "loop": bool(int(loop_m.group(1))) if loop_m else False,
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args):
    """Create a new SpriteAnimationData .asset file."""
    if len(args) < 2:
        print("Usage: create <asset_path> <image_path> [indices...] [--name N] [--fps N] [--loop]")
        sys.exit(1)

    asset_path = args[0]
    image_path = args[1]

    # Parse optional args
    indices = []
    name = os.path.splitext(os.path.basename(asset_path))[0]
    fps = 24.0
    loop = False

    i = 2
    while i < len(args):
        if args[i] == "--name":
            name = args[i + 1]
            i += 2
        elif args[i] == "--fps":
            fps = float(args[i + 1])
            i += 2
        elif args[i] == "--loop":
            loop = True
            i += 1
        else:
            indices.append(int(args[i]))
            i += 1

    # Read sprite data from image .meta
    meta_path = image_path + ".meta"
    if not os.path.exists(meta_path):
        print(f"Error: {meta_path} not found. Image must be sliced first.", file=sys.stderr)
        sys.exit(1)

    image_guid = read_guid_from_meta(meta_path)
    sprites = read_sprites_from_meta(meta_path)

    if not sprites:
        print(f"Error: No sprite entries found in {meta_path}. Image must be sliced (spriteMode: 2).", file=sys.stderr)
        sys.exit(1)

    # Select frames
    if indices:
        selected = []
        for idx in indices:
            if idx < 0 or idx >= len(sprites):
                print(f"Error: Index {idx} out of range (0-{len(sprites)-1})", file=sys.stderr)
                sys.exit(1)
            selected.append(sprites[idx])
    else:
        selected = sprites

    # Build frame references
    frames = [{"file_id": s["internal_id"], "guid": image_guid} for s in selected]

    # Generate asset
    content = build_asset_yaml(name, frames, fps, loop)

    os.makedirs(os.path.dirname(asset_path) or ".", exist_ok=True)
    with open(asset_path, "w", encoding="utf-8") as f:
        f.write(content)

    generate_meta_file(asset_path)

    print(f"Created SpriteAnimationData: {asset_path}")
    print(f"  Name: {name}")
    print(f"  Frames: {len(frames)} (from {os.path.basename(image_path)})")
    print(f"  FPS: {fps}")
    print(f"  Loop: {loop}")


def cmd_rewrite(args):
    """Rewrite frames in an existing SpriteAnimationData .asset file."""
    if len(args) < 2:
        print("Usage: rewrite <asset_path> <image_path> [indices...] [--fps N] [--loop/--no-loop]")
        sys.exit(1)

    asset_path = args[0]
    image_path = args[1]

    if not os.path.exists(asset_path):
        print(f"Error: {asset_path} not found", file=sys.stderr)
        sys.exit(1)

    # Read existing asset to preserve name
    with open(asset_path, "r", encoding="utf-8") as f:
        existing = parse_asset_yaml(f.read())

    # Parse optional args
    indices = []
    fps = existing["fps"]
    loop = existing["loop"]

    i = 2
    while i < len(args):
        if args[i] == "--fps":
            fps = float(args[i + 1])
            i += 2
        elif args[i] == "--loop":
            loop = True
            i += 1
        elif args[i] == "--no-loop":
            loop = False
            i += 1
        else:
            indices.append(int(args[i]))
            i += 1

    # Read sprite data
    meta_path = image_path + ".meta"
    if not os.path.exists(meta_path):
        print(f"Error: {meta_path} not found", file=sys.stderr)
        sys.exit(1)

    image_guid = read_guid_from_meta(meta_path)
    sprites = read_sprites_from_meta(meta_path)

    if not sprites:
        print(f"Error: No sprite entries found in {meta_path}", file=sys.stderr)
        sys.exit(1)

    if indices:
        selected = []
        for idx in indices:
            if idx < 0 or idx >= len(sprites):
                print(f"Error: Index {idx} out of range (0-{len(sprites)-1})", file=sys.stderr)
                sys.exit(1)
            selected.append(sprites[idx])
    else:
        selected = sprites

    frames = [{"file_id": s["internal_id"], "guid": image_guid} for s in selected]

    content = build_asset_yaml(existing["name"], frames, fps, loop)
    with open(asset_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Rewrote SpriteAnimationData: {asset_path}")
    print(f"  Frames: {len(frames)} (from {os.path.basename(image_path)})")
    print(f"  FPS: {fps}")
    print(f"  Loop: {loop}")


def cmd_inspect(args):
    """Inspect a SpriteAnimationData .asset file."""
    if len(args) < 1:
        print("Usage: inspect <asset_path>")
        sys.exit(1)

    asset_path = args[0]
    if not os.path.exists(asset_path):
        print(f"Error: {asset_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(asset_path, "r", encoding="utf-8") as f:
        data = parse_asset_yaml(f.read())

    print(f"SpriteAnimationData: {asset_path}")
    print(f"  Name: {data['name']}")
    print(f"  FPS: {data['fps']}")
    print(f"  Loop: {data['loop']}")
    print(f"  Duration: {len(data['frames']) / data['fps']:.2f}s")
    print(f"  Frames ({len(data['frames'])}):")

    # Group frames by source GUID
    guids = {}
    for i, frame in enumerate(data["frames"]):
        guid = frame["guid"]
        if guid not in guids:
            guids[guid] = []
        guids[guid].append((i, frame["file_id"]))

    for guid, entries in guids.items():
        print(f"    Source GUID: {guid}")
        for idx, file_id in entries:
            print(f"      [{idx}] fileID: {file_id}")


def cmd_list_sprites(args):
    """List available sprites in a sliced image .meta file."""
    if len(args) < 1:
        print("Usage: list-sprites <image_path>")
        sys.exit(1)

    image_path = args[0]
    meta_path = image_path + ".meta"
    if not os.path.exists(meta_path):
        print(f"Error: {meta_path} not found", file=sys.stderr)
        sys.exit(1)

    sprites = read_sprites_from_meta(meta_path)
    if not sprites:
        print(f"No sprite entries found in {meta_path}")
        return

    print(f"Sprites in {os.path.basename(image_path)} ({len(sprites)} total):")
    for i, s in enumerate(sprites):
        print(f"  [{i}] {s['name']} (internalID: {s['internal_id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMANDS = {
    "create": cmd_create,
    "rewrite": cmd_rewrite,
    "inspect": cmd_inspect,
    "list-sprites": cmd_list_sprites,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Unity SpriteAnimationData Editor")
        print()
        print("Commands:")
        print("  create       Create a new SpriteAnimationData .asset file")
        print("  rewrite      Rewrite frames in an existing .asset file")
        print("  inspect      Inspect a SpriteAnimationData .asset file")
        print("  list-sprites List sprites in a sliced image .meta file")
        print()
        print("Usage: animation_editor.py <command> [args...]")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Available: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
