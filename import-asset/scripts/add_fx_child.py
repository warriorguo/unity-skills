#!/usr/bin/env python3
"""Append a new SpriteSheet variant child to an existing fx prefab.

The child mirrors the shape produced by write_effect_prefab.py: a
GameObject (m_IsActive: 0) with Transform + SpriteRenderer + SpriteAnimation
MonoBehaviour with inline _frames pointing at all sliced sub-sprites of the
given PNG. The target prefab is identified either directly via
--target-prefab or by ResourcesDB key via --target-fx (e.g. fx/SpriteSheetGas).

Idempotent on child name: re-running with the same --child-name is a no-op.

Usage:
    add_fx_child.py
        (--target-prefab <path> | --target-fx <key> --resources-db <path>)
        --unity-project <path>
        --child-name <name>
        --png <png>
        [--fps 24] [--loop true|false]
        [--sorting-layer 5] [--sorting-order 10]
        [--script-guid <hex>] [--force]
"""

import argparse
import random
import re
import sys
from pathlib import Path


_ANCHOR_RE = re.compile(r"^---\s*!u!\d+\s*&(\d+)(?:\s+(\w+))?\s*$", re.MULTILINE)


def read_meta_guid(meta: Path) -> str:
    text = meta.read_text()
    m = re.search(r"^guid:\s*([a-fA-F0-9]+)", text, re.MULTILINE)
    if not m:
        sys.exit(f"error: no guid in {meta}")
    return m.group(1)


def read_image_meta(meta_path: Path):
    """Return (image_guid, [internal_id]) deduped by sprite name."""
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
                sprites.append(int(idm.group(1)))
                seen.add(cur_name)
            cur_name = None
    return image_guid, sprites


def find_unity_project(start: Path) -> Path:
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / "Assets").is_dir():
            return cand
    sys.exit(f"error: could not find Unity project (Assets/) at or above {start}")


def find_script_guid(unity_project: Path, script_name: str = "SpriteAnimation") -> str:
    for meta in unity_project.rglob(f"{script_name}.cs.meta"):
        m = re.search(r"^guid:\s*([a-fA-F0-9]+)", meta.read_text(), re.MULTILINE)
        if m:
            return m.group(1)
    sys.exit(
        f"error: could not auto-detect {script_name}.cs.meta under {unity_project}. "
        f"Pass --script-guid explicitly."
    )


def resolve_target_prefab_via_fx_key(unity_project: Path, resources_db: Path, fx_key: str) -> Path:
    """Look up <fx_key> in ResourcesDB.asset, get its asset guid, then walk
    the project for a .prefab.meta whose guid matches and return that .prefab."""
    db_text = resources_db.read_text()
    pat = re.compile(
        rf"^\s*-\s*key:\s*{re.escape(fx_key)}\s*$\n\s*asset:\s*\{{[^}}]*?guid:\s*([a-fA-F0-9]+)",
        re.MULTILINE,
    )
    m = pat.search(db_text)
    if not m:
        sys.exit(
            f"error: '{fx_key}' not found in {resources_db}. "
            f"Use --target-prefab to point at the prefab directly, or register "
            f"the key first."
        )
    target_guid = m.group(1)

    for meta in unity_project.rglob("*.prefab.meta"):
        try:
            mm = re.search(r"^guid:\s*([a-fA-F0-9]+)", meta.read_text(), re.MULTILINE)
        except (UnicodeDecodeError, OSError):
            continue
        if mm and mm.group(1).lower() == target_guid.lower():
            prefab = meta.with_suffix("")  # strips .meta
            return prefab
    sys.exit(
        f"error: ResourcesDB lists '{fx_key}' with guid {target_guid}, but no "
        f".prefab.meta under {unity_project} matches."
    )


def split_blocks(text: str):
    matches = list(_ANCHOR_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield m, start, end, text[start:end]


def existing_file_ids(text: str):
    return {int(m.group(1)) for m in _ANCHOR_RE.finditer(text)}


def fresh_file_ids(existing: set, count: int):
    out = []
    while len(out) < count:
        cand = random.randint(10**17, 10**18 - 1)
        if cand in existing or cand in out:
            continue
        out.append(cand)
    return out


def find_root_transform_id(text: str) -> int:
    matches = list(re.finditer(r"^---\s*!u!(\d+)\s*&(\d+)", text, re.MULTILINE))
    for i, m in enumerate(matches):
        if int(m.group(1)) != 4:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        if re.search(r"^\s*m_Father:\s*\{fileID:\s*0\}\s*$", body, re.MULTILINE):
            return int(m.group(2))
    sys.exit("error: could not find root Transform (m_Father: 0) in target prefab")


def child_already_present(text: str, name: str) -> bool:
    return re.search(rf"^\s*m_Name:\s*{re.escape(name)}\s*$", text, re.MULTILINE) is not None


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
  - component: {{fileID: {mb_id}}}
  m_Layer: 0
  m_Name: {child_name}
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
  m_LightProbeUsage: 0
  m_ReflectionProbeUsage: 0
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
  m_Sprite: {{fileID: {first_sprite_id}, guid: {png_guid}, type: 3}}
  m_Color: {{r: 1, g: 1, b: 1, a: 1}}
  m_FlipX: 0
  m_FlipY: 0
  m_DrawMode: 0
  m_Size: {{x: 3, y: 3}}
  m_AdaptiveModeThreshold: 0.5
  m_SpriteTileMode: 0
  m_WasSpriteAssigned: 1
  m_MaskInteraction: 0
  m_SpriteSortPoint: 0
--- !u!114 &{mb_id}
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {script_guid}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  _frames:
{frames}
  _fps: {fps}
  _loop: {loop_int}
"""


def patch_root_children(text: str, root_trans_id: int, new_child_trans_id: int) -> str:
    """Append <new_child_trans_id> to the root Transform's m_Children list."""
    matches = list(re.finditer(r"^---\s*!u!(\d+)\s*&(\d+)", text, re.MULTILINE))
    target = None
    for i, m in enumerate(matches):
        if int(m.group(1)) == 4 and int(m.group(2)) == root_trans_id:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            target = (start, end, text[start:end])
            break
    if not target:
        sys.exit(f"error: root Transform &{root_trans_id} not found")
    body_start, body_end, body = target

    if re.search(rf"-\s*\{{fileID:\s*{new_child_trans_id}\}}", body):
        return text  # already a child

    em = re.search(r"^(\s*)m_Children:\s*\[\]\s*$", body, re.MULTILINE)
    if em:
        indent = em.group(1)
        replacement = f"{indent}m_Children:\n{indent}- {{fileID: {new_child_trans_id}}}"
        body = body[:em.start()] + replacement + body[em.end():]
        return text[:body_start] + body + text[body_end:]

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
        if re.match(rf"^{re.escape(children_indent)}\s*-\s*\{{fileID:\s*\d+\}}\s*$", line):
            out_lines.append(line)
            continue
        if not inserted:
            out_lines.append(f"{children_indent}- {{fileID: {new_child_trans_id}}}")
            inserted = True
        out_lines.append(line)
        in_children = False
    if not inserted:
        sys.exit(f"error: could not patch root Transform &{root_trans_id} m_Children")
    return text[:body_start] + "\n".join(out_lines) + text[body_end:]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--target-prefab", help="Direct path to the target fx prefab")
    g.add_argument("--target-fx", help="ResourcesDB key (e.g. fx/SpriteSheetGas) to resolve")
    ap.add_argument("--unity-project", required=True)
    ap.add_argument("--resources-db", default="", help="Path to ResourcesDB.asset (required when using --target-fx)")
    ap.add_argument("--child-name", required=True)
    ap.add_argument("--png", required=True, help="Sliced sprite-sheet PNG (its .meta provides guid + sprite ids)")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--loop", default="false", choices=["true", "false"])
    ap.add_argument("--sorting-layer", type=int, default=5)
    ap.add_argument("--sorting-order", type=int, default=10)
    ap.add_argument("--script-guid", help="GUID of SpriteAnimation.cs (auto-detect if omitted)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    unity_project = Path(args.unity_project).resolve()

    if args.target_prefab:
        target = Path(args.target_prefab)
    else:
        if not args.resources_db:
            sys.exit("error: --resources-db is required when using --target-fx")
        target = resolve_target_prefab_via_fx_key(
            unity_project, Path(args.resources_db), args.target_fx
        )
        print(f"[add-fx-child] resolved {args.target_fx} -> {target}")

    if not target.exists():
        sys.exit(f"error: target prefab not found: {target}")

    png = Path(args.png)
    meta = Path(str(png) + ".meta")
    if not png.exists():
        sys.exit(f"error: png not found: {png}")
    if not meta.exists():
        sys.exit(f"error: png .meta not found: {meta}")

    text = target.read_text()
    if not args.force and child_already_present(text, args.child_name):
        print(f"[add-fx-child] {target}  skip (m_Name: {args.child_name} already present)")
        return

    png_guid, sprite_ids = read_image_meta(meta)
    if not sprite_ids:
        sys.exit(f"error: no sprite entries in {meta} (slice the sheet first)")

    script_guid = args.script_guid or find_script_guid(unity_project)
    root_trans_id = find_root_transform_id(text)

    existing = existing_file_ids(text)
    go_id, trans_id, sr_id, mb_id = fresh_file_ids(existing, 4)

    frames_block = "\n".join(
        f"  - {{fileID: {sid}, guid: {png_guid}, type: 3}}" for sid in sprite_ids
    )
    child_block = CHILD_TEMPLATE.format(
        go_id=go_id,
        trans_id=trans_id,
        sr_id=sr_id,
        mb_id=mb_id,
        child_name=args.child_name,
        root_trans_id=root_trans_id,
        sorting_layer=args.sorting_layer,
        sorting_order=args.sorting_order,
        first_sprite_id=sprite_ids[0],
        png_guid=png_guid,
        script_guid=script_guid,
        frames=frames_block,
        fps=args.fps,
        loop_int=1 if args.loop == "true" else 0,
    )

    text = patch_root_children(text, root_trans_id, trans_id)
    if not text.endswith("\n"):
        text += "\n"
    text += child_block

    target.write_text(text)
    print(f"[add-fx-child] {target}  added '{args.child_name}' with {len(sprite_ids)} frame(s) "
          f"(GO=&{go_id} T=&{trans_id} SR=&{sr_id} MB=&{mb_id})")


if __name__ == "__main__":
    main()
