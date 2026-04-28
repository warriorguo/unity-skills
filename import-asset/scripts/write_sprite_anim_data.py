#!/usr/bin/env python3
"""Write a SpriteAnimationData ScriptableObject .asset for the project's custom
sprite animation system.

The asset is a MonoBehaviour referencing a SpriteAnimationData.cs script. Its
shape is project-specific; the template below uses fps/loop/frames fields,
which match the common pattern. Adjust if your project differs.

Usage:
    write_sprite_anim_data.py <output.asset> <image.png> [--name N] [--fps N]
        [--loop] [--frames I J K ...] [--script-guid GUID] [--force]

If --script-guid is omitted, the script searches the unity project (passed via
--unity-project, or auto-detected as the nearest ancestor containing Assets/)
for SpriteAnimationData.cs.meta and reads its guid.
"""

import argparse
import re
import sys
from pathlib import Path


def read_image_meta(meta_path: Path):
    """Return (image_guid, [(name, internal_id)]) from a sliced sprite-sheet .meta,
    deduped by sprite name. Unity-imported sheets sometimes list each sprite
    twice in spriteSheet.sprites (once canonical 213xxxxx, once bignum); the
    first occurrence wins, which keeps the canonical IDs."""
    text = meta_path.read_text()
    g = re.search(r"^guid:\s*([a-fA-F0-9]+)", text, re.MULTILINE)
    if not g:
        sys.exit(f"error: no guid in {meta_path}")
    image_guid = g.group(1)

    sprites = []
    seen = set()
    in_sheet = False
    sheet_indent = None
    cur_name = None
    for line in text.splitlines():
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
        nm = re.match(r"\s+name:\s*(.+)$", line)
        if nm:
            cur_name = nm.group(1).strip()
        idm = re.match(r"\s+internalID:\s*(-?\d+)", line)
        if idm and cur_name is not None:
            if cur_name not in seen:
                sprites.append((cur_name, int(idm.group(1))))
                seen.add(cur_name)
            cur_name = None
    return image_guid, sprites


def find_unity_project(start: Path) -> Path:
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / "Assets").is_dir():
            return cand
    sys.exit(f"error: could not find Unity project (Assets/) at or above {start}")


def find_script_guid(unity_project: Path, script_name: str = "SpriteAnimationData") -> str:
    for meta in unity_project.rglob(f"{script_name}.cs.meta"):
        m = re.search(r"^guid:\s*([a-fA-F0-9]+)", meta.read_text(), re.MULTILINE)
        if m:
            return m.group(1)
    sys.exit(
        f"error: could not auto-detect SpriteAnimationData.cs.meta under {unity_project}. "
        f"Pass --script-guid explicitly."
    )


YAML_TEMPLATE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!114 &11400000
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 0}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {script_guid}, type: 3}}
  m_Name: {name}
  m_EditorClassIdentifier:
  fps: {fps}
  loop: {loop}
  frames:
{frames}
"""


def render_asset(name: str, fps: int, loop: bool, image_guid: str,
                 sprite_ids: list, script_guid: str) -> str:
    if not sprite_ids:
        sys.exit("error: at least one sprite frame required")
    frames_lines = [
        f"  - {{fileID: {sid}, guid: {image_guid}, type: 3}}" for sid in sprite_ids
    ]
    return YAML_TEMPLATE.format(
        script_guid=script_guid,
        name=name,
        fps=fps,
        loop=1 if loop else 0,
        frames="\n".join(frames_lines),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("output", help="Output .asset path")
    ap.add_argument("image", help="Sliced sprite sheet PNG path (its .meta is read)")
    ap.add_argument("--name", help="Asset m_Name (default: output basename without ext)")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--frames", nargs="*", type=int,
                    help="Sprite indices (default: all)")
    ap.add_argument("--script-guid", help="GUID of SpriteAnimationData.cs (auto-detect if omitted)")
    ap.add_argument("--unity-project", help="Unity project root (for script GUID auto-detect)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    output = Path(args.output)
    image = Path(args.image)
    meta = Path(str(image) + ".meta")
    if not meta.exists():
        sys.exit(f"error: {meta} not found (run Unity to generate, then slice)")

    image_guid, sprites = read_image_meta(meta)

    if not sprites:
        # Single-mode texture: reference the default sprite at fileID 21300000.
        # Any --frames value is treated as 0 (the only sprite).
        frame_count = len(args.frames) if args.frames else 1
        ids = [21300000] * frame_count
    elif args.frames is not None:
        try:
            ids = [sprites[i][1] for i in args.frames]
        except IndexError:
            sys.exit(f"error: --frames index out of range (have {len(sprites)} sprites)")
    else:
        ids = [sid for _, sid in sprites]

    script_guid = args.script_guid
    if not script_guid:
        proj = Path(args.unity_project) if args.unity_project else find_unity_project(image)
        script_guid = find_script_guid(proj)

    name = args.name or output.stem
    new_text = render_asset(name, args.fps, args.loop, image_guid, ids, script_guid)

    if output.exists() and not args.force and output.read_text() == new_text:
        print(f"[write-sprite-anim-data] {output}  skip (unchanged)")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(new_text)
    print(f"[write-sprite-anim-data] {output}  wrote {len(ids)} frame(s)")


if __name__ == "__main__":
    main()
