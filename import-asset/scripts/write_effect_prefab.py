#!/usr/bin/env python3
"""Write a SpriteSheet effect prefab matching the project's SpriteSheetSmoke
template — root GameObject containing a single (initially-inactive) child with
Transform + SpriteRenderer + SpriteAnimation MonoBehaviour with inline frames.

Usage:
    write_effect_prefab.py <prefab_path> <png_path>
        [--root-name N] [--child-name N] [--fps N] [--loop]
        [--sorting-layer N] [--sorting-order N]
        [--script-guid GUID] [--unity-project PATH] [--force]

Reads <png_path>.meta to extract the PNG guid and the sliced sprite
internalIDs (row-major order); the first sprite is used as the
SpriteRenderer's m_Sprite, and all sprites are inlined into the
SpriteAnimation MonoBehaviour's _frames array.
"""

import argparse
import re
import sys
from pathlib import Path


def read_image_meta(meta_path: Path):
    """Return (image_guid, [(name, internal_id)]) deduped by name.

    Some Unity-imported sheets list each sprite twice in spriteSheet.sprites:
    once with the slicer-assigned canonical 213xxxxx internalID, then again
    with a Unity-generated random bignum. Both refer to the same sub-sprite.
    Keeping the first occurrence per name yields the canonical IDs and
    eliminates the duplicate-frames bug downstream.
    """
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


def find_script_guid(unity_project: Path, script_name: str = "SpriteAnimation") -> str:
    for meta in unity_project.rglob(f"{script_name}.cs.meta"):
        m = re.search(r"^guid:\s*([a-fA-F0-9]+)", meta.read_text(), re.MULTILINE)
        if m:
            return m.group(1)
    sys.exit(
        f"error: could not auto-detect {script_name}.cs.meta under {unity_project}. "
        f"Pass --script-guid explicitly."
    )


PREFAB_TEMPLATE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1001
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
  - component: {fileID: 1002}
  - component: {fileID: 1003}
  - component: {fileID: 1004}
  m_Layer: 0
  m_Name: __CHILD_NAME__
  m_TagString: Untagged
  m_Icon: {fileID: 0}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 0
--- !u!4 &1002
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1001}
  serializedVersion: 2
  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}
  m_LocalPosition: {x: 0, y: 0, z: 0}
  m_LocalScale: {x: 1, y: 1, z: 1}
  m_ConstrainProportionsScale: 0
  m_Children: []
  m_Father: {fileID: 100001}
  m_LocalEulerAnglesHint: {x: 0, y: 0, z: 0}
--- !u!212 &1003
SpriteRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1001}
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
  - {fileID: 10754, guid: 0000000000000000f000000000000000, type: 0}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {fileID: 0}
  m_ProbeAnchor: {fileID: 0}
  m_LightProbeVolumeOverride: {fileID: 0}
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
  m_LightmapParameters: {fileID: 0}
  m_SortingLayerID: -1735802399
  m_SortingLayer: __SORTING_LAYER__
  m_SortingOrder: __SORTING_ORDER__
  m_Sprite: {fileID: __FIRST_SPRITE_ID__, guid: __PNG_GUID__, type: 3}
  m_Color: {r: 1, g: 1, b: 1, a: 1}
  m_FlipX: 0
  m_FlipY: 0
  m_DrawMode: 0
  m_Size: {x: 3, y: 3}
  m_AdaptiveModeThreshold: 0.5
  m_SpriteTileMode: 0
  m_WasSpriteAssigned: 1
  m_MaskInteraction: 0
  m_SpriteSortPoint: 0
--- !u!114 &1004
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1001}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: __SCRIPT_GUID__, type: 3}
  m_Name:
  m_EditorClassIdentifier:
  _frames:
__FRAMES_BLOCK__
  _fps: __FPS__
  _loop: __LOOP__
--- !u!1 &100000
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
  - component: {fileID: 100001}
  m_Layer: 0
  m_Name: __ROOT_NAME__
  m_TagString: Untagged
  m_Icon: {fileID: 0}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!4 &100001
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 100000}
  serializedVersion: 2
  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}
  m_LocalPosition: {x: 0, y: 0, z: 0}
  m_LocalScale: {x: 1, y: 1, z: 1}
  m_ConstrainProportionsScale: 0
  m_Children:
  - {fileID: 1002}
  m_Father: {fileID: 0}
  m_LocalEulerAnglesHint: {x: 0, y: 0, z: 0}
"""


def render_prefab(root_name, child_name, fps, loop, sorting_layer, sorting_order,
                  png_guid, sprite_ids, script_guid):
    if not sprite_ids:
        sys.exit("error: no sprite frames (slice the sheet first)")
    frames_lines = [
        f"  - {{fileID: {sid}, guid: {png_guid}, type: 3}}" for sid in sprite_ids
    ]
    out = PREFAB_TEMPLATE
    out = out.replace("__ROOT_NAME__", root_name)
    out = out.replace("__CHILD_NAME__", child_name)
    out = out.replace("__SORTING_LAYER__", str(sorting_layer))
    out = out.replace("__SORTING_ORDER__", str(sorting_order))
    out = out.replace("__FIRST_SPRITE_ID__", str(sprite_ids[0]))
    out = out.replace("__PNG_GUID__", png_guid)
    out = out.replace("__SCRIPT_GUID__", script_guid)
    out = out.replace("__FRAMES_BLOCK__", "\n".join(frames_lines))
    out = out.replace("__FPS__", str(fps))
    out = out.replace("__LOOP__", "1" if loop else "0")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prefab", help="Output .prefab path")
    ap.add_argument("png", help="Sliced sprite-sheet PNG (its .meta provides guid + sprite ids)")
    ap.add_argument("--root-name", required=True, help="Root GameObject m_Name (e.g. SpriteSheetGas)")
    ap.add_argument("--child-name", required=True, help="Child GameObject m_Name (e.g. gas_01)")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--loop", default="false", choices=["true", "false"])
    ap.add_argument("--sorting-layer", type=int, default=5)
    ap.add_argument("--sorting-order", type=int, default=10)
    ap.add_argument("--script-guid", help="GUID of SpriteAnimation.cs (auto-detect if omitted)")
    ap.add_argument("--unity-project", help="Unity project root (for script GUID auto-detect)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    prefab = Path(args.prefab)
    png = Path(args.png)
    meta = Path(str(png) + ".meta")
    if not meta.exists():
        sys.exit(f"error: {meta} not found (run Unity to import + slice first)")

    png_guid, sprites = read_image_meta(meta)
    if not sprites:
        sys.exit(f"error: {meta} has no sprite entries (slice the sheet first)")

    sprite_ids = [sid for _, sid in sprites]

    script_guid = args.script_guid
    if not script_guid:
        proj = Path(args.unity_project) if args.unity_project else find_unity_project(png)
        script_guid = find_script_guid(proj)

    new_text = render_prefab(
        args.root_name, args.child_name, args.fps, args.loop == "true",
        args.sorting_layer, args.sorting_order,
        png_guid, sprite_ids, script_guid,
    )

    if prefab.exists() and not args.force and prefab.read_text() == new_text:
        print(f"[write-effect-prefab] {prefab}  skip (unchanged)")
        return
    prefab.parent.mkdir(parents=True, exist_ok=True)
    prefab.write_text(new_text)
    print(f"[write-effect-prefab] {prefab}  wrote {len(sprite_ids)} frame(s)")


if __name__ == "__main__":
    main()
