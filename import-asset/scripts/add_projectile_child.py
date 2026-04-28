#!/usr/bin/env python3
"""Append a new projectile child (GameObject + Transform + SpriteRenderer)
to an existing projectile container prefab. Idempotent on child name.

The prefab is mutated in-place: three new YAML blocks are appended at end of
file, the root Transform's m_Children list is patched to reference the new
child's Transform, and the new GameObject is wired with a single sprite
reference at fileID 21300000 of the source PNG.

Usage:
    add_projectile_child.py <prefab> --name <child> --png <png>
        [--ppu N] [--layer N] [--sorting-layer N] [--sorting-order N]
        [--force]
"""

import argparse
import random
import re
import struct
import sys
from pathlib import Path


def png_size(path: Path):
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            sys.exit(f"error: not a PNG: {path}")
        # IHDR: 4-byte length, 4-byte 'IHDR', 4-byte width, 4-byte height
        f.read(4)
        if f.read(4) != b"IHDR":
            sys.exit(f"error: PNG missing IHDR: {path}")
        w, h = struct.unpack(">II", f.read(8))
    return w, h


def read_meta_guid(meta_path: Path) -> str:
    text = meta_path.read_text()
    m = re.search(r"^guid:\s*([a-fA-F0-9]+)", text, re.MULTILINE)
    if not m:
        sys.exit(f"error: no guid in {meta_path}")
    return m.group(1)


def fmt_unity_number(v) -> str:
    """Match Unity's float formatting: drop trailing zeros for clean ints."""
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return f"{v:g}"
    return str(v)


_ANCHOR_RE = re.compile(r"^---\s*!u!\d+\s*&(\d+)\s*$", re.MULTILINE)


def existing_file_ids(prefab_text: str):
    return {int(m.group(1)) for m in _ANCHOR_RE.finditer(prefab_text)}


def fresh_file_ids(existing: set, count: int):
    out = []
    while len(out) < count:
        # 18-digit space — well below 2^63, well clear of small Unity defaults.
        candidate = random.randint(10**17, 10**18 - 1)
        if candidate in existing or candidate in out:
            continue
        out.append(candidate)
    return out


def find_root_transform(prefab_text: str):
    """Return (transform_anchor_id, body_start, body_end) for the root Transform.

    The root Transform is the !u!4 block whose m_Father references fileID 0.
    """
    transforms = []
    for m in re.finditer(r"^---\s*!u!4\s*&(\d+)\s*$", prefab_text, re.MULTILINE):
        anchor = int(m.group(1))
        start = m.end()
        next_m = re.search(r"^---\s*!u!", prefab_text[start:], re.MULTILINE)
        end = start + next_m.start() if next_m else len(prefab_text)
        body = prefab_text[start:end]
        transforms.append((anchor, start, end, body))
    for anchor, start, end, body in transforms:
        if re.search(r"^\s*m_Father:\s*\{fileID:\s*0\}\s*$", body, re.MULTILINE):
            return anchor, start, end
    sys.exit("error: could not locate root Transform (m_Father: {fileID: 0})")


def patch_root_children(prefab_text: str, body_start: int, body_end: int,
                        new_transform_id: int) -> str:
    """Patch root Transform's m_Children list to include new_transform_id.

    Handles both `m_Children: []` and multi-line list cases.
    """
    body = prefab_text[body_start:body_end]
    # Case 1: empty list
    new_entry = f"  - {{fileID: {new_transform_id}}}"
    empty_pat = re.compile(r"^(\s*)m_Children:\s*\[\]\s*$", re.MULTILINE)
    m = empty_pat.search(body)
    if m:
        indent = m.group(1)
        replacement = f"{indent}m_Children:\n{indent}{new_entry.lstrip()}"
        body = body[: m.start()] + replacement + body[m.end():]
        return prefab_text[:body_start] + body + prefab_text[body_end:]
    # Case 2: existing multi-line list — insert before first non-list line.
    lines = body.split("\n")
    out_lines = []
    in_children = False
    children_indent = ""
    inserted = False
    for line in lines:
        if not in_children:
            mm = re.match(r"^(\s*)m_Children:\s*$", line)
            if mm:
                in_children = True
                children_indent = mm.group(1)
                out_lines.append(line)
                continue
            out_lines.append(line)
            continue
        # Inside m_Children
        if re.match(rf"^{re.escape(children_indent)}\s+-\s*\{{fileID:\s*\d+\}}\s*$", line):
            out_lines.append(line)
            continue
        # Hit first non-list line; insert new entry before it.
        if not inserted:
            out_lines.append(f"{children_indent}- {{fileID: {new_transform_id}}}")
            inserted = True
        out_lines.append(line)
        in_children = False
    if not inserted and in_children:
        # Reached end while still in list (rare).
        out_lines.append(f"{children_indent}- {{fileID: {new_transform_id}}}")
        inserted = True
    if not inserted:
        sys.exit("error: could not patch root m_Children (no m_Children block found)")
    return prefab_text[:body_start] + "\n".join(out_lines) + prefab_text[body_end:]


CHILD_TEMPLATE = """--- !u!1 &{go_id}
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
  - component: {{fileID: {trans_id}}}
  - component: {{fileID: {sr_id}}}
  m_Layer: {layer}
  m_Name: {name}
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 0
--- !u!4 &{trans_id}
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  serializedVersion: 2
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: 0, y: 0, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
  m_ConstrainProportionsScale: 0
  m_Children: []
  m_Father: {{fileID: {root_trans_id}}}
  m_LocalEulerAnglesHint: {{x: 0, y: 0, z: 0}}
--- !u!212 &{sr_id}
SpriteRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Enabled: 1
  m_CastShadows: 0
  m_ReceiveShadows: 0
  m_DynamicOccludee: 1
  m_StaticShadowCaster: 0
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_ReflectionProbeUsage: 1
  m_RayTracingMode: 0
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_RendererPriority: 0
  m_Materials:
  - {{fileID: 10754, guid: 0000000000000000f000000000000000, type: 0}}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {{fileID: 0}}
  m_ProbeAnchor: {{fileID: 0}}
  m_LightProbeVolumeOverride: {{fileID: 0}}
  m_ScaleInLightmap: 1
  m_ReceiveGI: 1
  m_PreserveUVs: 0
  m_IgnoreNormalsForChartDetection: 0
  m_ImportantGI: 0
  m_StitchLightmapSeams: 1
  m_SelectedEditorRenderState: 0
  m_MinimumChartSize: 4
  m_AutoUVMaxDistance: 0.5
  m_AutoUVMaxAngle: 89
  m_LightmapParameters: {{fileID: 0}}
  m_SortingLayerID: -1735802399
  m_SortingLayer: {sorting_layer}
  m_SortingOrder: {sorting_order}
  m_Sprite: {{fileID: 21300000, guid: {png_guid}, type: 3}}
  m_Color: {{r: 1, g: 1, b: 1, a: 1}}
  m_FlipX: 0
  m_FlipY: 0
  m_DrawMode: 0
  m_Size: {{x: {size_x}, y: {size_y}}}
  m_AdaptiveModeThreshold: 0.5
  m_SpriteTileMode: 0
  m_WasSpriteAssigned: 1
  m_MaskInteraction: 0
  m_SpriteSortPoint: 0
"""


def child_already_present(prefab_text: str, name: str) -> bool:
    return re.search(rf"^\s*m_Name:\s*{re.escape(name)}\s*$", prefab_text, re.MULTILINE) is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prefab", help="Target projectile container prefab")
    ap.add_argument("--name", required=True, help="Child GameObject m_Name")
    ap.add_argument("--png", required=True, help="Source sprite PNG (its .meta provides guid)")
    ap.add_argument("--ppu", type=float, default=100.0, help="Pixels per unit for m_Size")
    ap.add_argument("--layer", type=int, default=6, help="GameObject m_Layer (default 6)")
    ap.add_argument("--sorting-layer", type=int, default=5)
    ap.add_argument("--sorting-order", type=int, default=5)
    ap.add_argument("--force", action="store_true", help="Re-add even if name already present")
    args = ap.parse_args()

    prefab_path = Path(args.prefab)
    png_path = Path(args.png)
    meta_path = Path(str(png_path) + ".meta")
    if not prefab_path.exists():
        sys.exit(f"error: prefab not found: {prefab_path}")
    if not png_path.exists():
        sys.exit(f"error: png not found: {png_path}")
    if not meta_path.exists():
        sys.exit(f"error: png .meta not found: {meta_path}")

    prefab_text = prefab_path.read_text()

    if not args.force and child_already_present(prefab_text, args.name):
        print(f"[add-projectile-child] {prefab_path}  skip (m_Name: {args.name} already present)")
        return

    png_guid = read_meta_guid(meta_path)
    w, h = png_size(png_path)
    size_x = w / args.ppu
    size_y = h / args.ppu

    root_trans_id, body_start, body_end = find_root_transform(prefab_text)

    existing = existing_file_ids(prefab_text)
    go_id, trans_id, sr_id = fresh_file_ids(existing, 3)

    child_block = CHILD_TEMPLATE.format(
        go_id=go_id,
        trans_id=trans_id,
        sr_id=sr_id,
        layer=args.layer,
        name=args.name,
        root_trans_id=root_trans_id,
        sorting_layer=args.sorting_layer,
        sorting_order=args.sorting_order,
        png_guid=png_guid,
        size_x=fmt_unity_number(size_x),
        size_y=fmt_unity_number(size_y),
    )

    # Patch root m_Children first (positions/offsets in body_start..body_end).
    patched = patch_root_children(prefab_text, body_start, body_end, trans_id)

    # Append the new child block at end of file.
    if not patched.endswith("\n"):
        patched += "\n"
    patched += child_block

    prefab_path.write_text(patched)
    print(f"[add-projectile-child] {prefab_path}  added '{args.name}' "
          f"(GO={go_id} T={trans_id} SR={sr_id} size={size_x:g}x{size_y:g})")


if __name__ == "__main__":
    main()
