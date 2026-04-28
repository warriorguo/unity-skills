#!/usr/bin/env python3
"""Apply the standard enemy-prefab setup steps to a freshly-cloned prefab:
rename the root GameObject, fix Rigidbody2D constraints, and embed the
BloodBar nested prefab + wire EnemyView._bloodBar to it. Each operation
is idempotent.

Usage:
    prefab_setup_enemy.py <prefab>
        --new-name <Name>
        [--no-fix-constraints]
        [--no-bloodbar]
        [--bloodbar-y 0.38] [--bloodbar-scale 1.0]
        [--enemy-view-script-guid <hex>]
        [--bloodbar-prefab-guid <hex>]
        [--bloodbar-script-guid <hex>]
        [--bloodbar-root-transform-source-id <int>]
        [--bloodbar-game-object-source-id <int>]
        [--bloodbar-monobehaviour-source-id <int>]
"""

import argparse
import random
import re
import sys
from pathlib import Path


DEFAULT_BLOODBAR_PREFAB_GUID = "1129068682e604d0cbf66cd8211b18e5"
DEFAULT_BLOODBAR_SCRIPT_GUID = "37b73c30bc8d14e1eabc4dbbb120ee25"
DEFAULT_ENEMY_VIEW_SCRIPT_GUID = "ddfd4382b062b4938ad1abb2f4d52b6a"
DEFAULT_BB_ROOT_TRANS_SOURCE = 2553071445036949854
DEFAULT_BB_GO_SOURCE = 4299180530178147584
DEFAULT_BB_MB_SOURCE = 1100000000000000001


_ANCHOR_RE = re.compile(r"^---\s*!u!(\d+)\s*&(\d+)(?:\s+(\w+))?\s*$", re.MULTILINE)


def existing_file_ids(text: str):
    return {int(m.group(2)) for m in _ANCHOR_RE.finditer(text)}


def fresh_file_ids(existing: set, count: int):
    out = []
    while len(out) < count:
        cand = random.randint(10**17, 10**18 - 1)
        if cand in existing or cand in out:
            continue
        out.append(cand)
    return out


def split_blocks(text: str):
    """Yield (anchor_match, start, end, body) for each YAML document."""
    matches = list(_ANCHOR_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield m, start, end, text[start:end]


def find_root_gameobject(text: str):
    """Return (root_go_fileid, root_transform_fileid)."""
    transforms = []  # (anchor_id, body)
    gos = {}  # anchor_id -> body
    for m, _s, _e, body in split_blocks(text):
        cls = int(m.group(1))
        anchor = int(m.group(2))
        if cls == 4:
            transforms.append((anchor, body))
        elif cls == 1:
            gos[anchor] = body
    for trans_id, body in transforms:
        if re.search(r"^\s*m_Father:\s*\{fileID:\s*0\}\s*$", body, re.MULTILINE):
            go_match = re.search(r"^\s*m_GameObject:\s*\{fileID:\s*(\d+)\}", body, re.MULTILINE)
            if go_match:
                return int(go_match.group(1)), trans_id
    sys.exit("error: could not find root GameObject (no Transform with m_Father: 0)")


def replace_in_block(text: str, anchor_id: int, key: str, new_value: str) -> str:
    """Replace the first `<key>: ...` line within the block having &<anchor_id>."""
    for m, start, end, body in split_blocks(text):
        if int(m.group(2)) != anchor_id:
            continue
        pat = re.compile(rf"^(\s*){re.escape(key)}:\s*.+$", re.MULTILINE)
        new_body, n = pat.subn(rf"\g<1>{key}: {new_value}", body, count=1)
        if n == 0:
            sys.exit(f"error: '{key}:' not found in block &{anchor_id}")
        return text[:start] + new_body + text[end:]
    sys.exit(f"error: anchor &{anchor_id} not found in prefab")


def find_enemy_view_block_id(text: str, script_guid: str):
    for m, _s, _e, body in split_blocks(text):
        if int(m.group(1)) != 114:
            continue
        sm = re.search(
            r"m_Script:\s*\{fileID:\s*\d+,\s*guid:\s*([a-fA-F0-9]+)", body
        )
        if sm and sm.group(1).lower() == script_guid.lower():
            return int(m.group(2))
    return None


def patch_enemy_view_bloodbar(text: str, ev_anchor: int, bloodbar_mb_id: int) -> str:
    """Set EnemyView._bloodBar to {fileID: <bloodbar_mb_id>} (replace existing
    value or insert before block end). Idempotent: re-running with the same
    id is a no-op."""
    target_line = f"  _bloodBar: {{fileID: {bloodbar_mb_id}}}"
    pieces = []
    found_block = False
    for m, start, end, body in split_blocks(text):
        if int(m.group(2)) == ev_anchor:
            found_block = True
            existing_pat = re.compile(r"^(\s*)_bloodBar:\s*\{fileID:\s*\d+\}\s*$", re.MULTILINE)
            mm = existing_pat.search(body)
            if mm:
                # Replace existing line
                body = existing_pat.sub(f"{mm.group(1)}_bloodBar: {{fileID: {bloodbar_mb_id}}}", body, count=1)
            else:
                # Insert as last line of block (before any trailing blank)
                trimmed = body.rstrip("\n")
                body = trimmed + "\n" + target_line + "\n"
            pieces.append((start, end, body))
        else:
            pieces.append((start, end, body))
    if not found_block:
        sys.exit(f"error: EnemyView block &{ev_anchor} not found")
    # Reassemble
    out = []
    cursor = 0
    matches = list(_ANCHOR_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append(text[cursor:start])
        # use possibly-modified body
        for ps, pe, pb in pieces:
            if ps == start and pe == end:
                out.append(pb)
                break
        else:
            out.append(text[start:end])
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def rename_root(text: str, new_name: str) -> str:
    root_go, _ = find_root_gameobject(text)
    # Idempotency check: is m_Name already <new_name>?
    for m, _s, _e, body in split_blocks(text):
        if int(m.group(2)) == root_go:
            mm = re.search(r"^\s*m_Name:\s*(.+)$", body, re.MULTILINE)
            if mm and mm.group(1).strip() == new_name:
                print(f"  rename-root: skip (already '{new_name}')")
                return text
    print(f"  rename-root: GO &{root_go} -> '{new_name}'")
    return replace_in_block(text, root_go, "m_Name", new_name)


def fix_constraints(text: str) -> str:
    """Replace `m_Constraints: 0` with `m_Constraints: 4` on Rigidbody2D blocks."""
    pat = re.compile(r"^(\s*)m_Constraints:\s*0\s*$", re.MULTILINE)
    new_text, n = pat.subn(r"\g<1>m_Constraints: 4", text)
    if n == 0:
        print("  fix-constraints: skip (no `m_Constraints: 0` found)")
        return text
    print(f"  fix-constraints: replaced {n} occurrence(s)")
    return new_text


BLOODBAR_PREFAB_INSTANCE = """--- !u!1001 &{instance_id}
PrefabInstance:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_Modification:
    serializedVersion: 3
    m_TransformParent: {{fileID: {root_trans_id}}}
    m_Modifications:
{mods}
    m_RemovedComponents: []
    m_RemovedGameObjects: []
    m_AddedGameObjects: []
    m_AddedComponents: []
  m_SourcePrefab: {{fileID: 100100000, guid: {bb_prefab_guid}, type: 3}}
--- !u!4 &{stripped_trans_id} stripped
Transform:
  m_CorrespondingSourceObject: {{fileID: {bb_root_trans_source}, guid: {bb_prefab_guid}, type: 3}}
  m_PrefabInstance: {{fileID: {instance_id}}}
  m_PrefabAsset: {{fileID: 0}}
--- !u!114 &{stripped_mb_id} stripped
MonoBehaviour:
  m_CorrespondingSourceObject: {{fileID: {bb_mb_source}, guid: {bb_prefab_guid}, type: 3}}
  m_PrefabInstance: {{fileID: {instance_id}}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 0}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {bb_script_guid}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
"""


def render_modifications(bb_root_trans_source: int, bb_go_source: int,
                         bb_prefab_guid: str, y: float, scale: float):
    base_target = f"{{fileID: {bb_root_trans_source}, guid: {bb_prefab_guid}, type: 3}}"
    go_target = f"{{fileID: {bb_go_source}, guid: {bb_prefab_guid}, type: 3}}"
    items = []
    for axis, val in [("x", 0), ("y", y), ("z", 0)]:
        items.append(("m_LocalPosition." + axis, val, base_target))
    items.append(("m_LocalRotation.w", 1, base_target))
    for axis in "xyz":
        items.append(("m_LocalRotation." + axis, 0, base_target))
    for axis in "xyz":
        items.append(("m_LocalEulerAnglesHint." + axis, 0, base_target))
    if scale != 1.0:
        for axis in "xyz":
            items.append(("m_LocalScale." + axis, scale, base_target))
    items.append(("m_Name", "BloodBar", go_target))

    out = []
    for path, value, target in items:
        out.append(f"    - target: {target}")
        out.append(f"      propertyPath: {path}")
        out.append(f"      value: {value}")
        out.append(f"      objectReference: {{fileID: 0}}")
    return "\n".join(out)


def already_has_bloodbar(text: str, bb_prefab_guid: str) -> bool:
    pat = rf"m_SourcePrefab:\s*\{{fileID:\s*100100000,\s*guid:\s*{re.escape(bb_prefab_guid)}"
    return re.search(pat, text) is not None


def insert_bloodbar(text: str, *, bloodbar_y: float, bloodbar_scale: float,
                    bb_prefab_guid: str, bb_script_guid: str,
                    bb_root_trans_source: int, bb_go_source: int, bb_mb_source: int,
                    enemy_view_script_guid: str) -> str:
    if already_has_bloodbar(text, bb_prefab_guid):
        print("  insert-bloodbar: skip (already present)")
        return text

    _, root_trans_id = find_root_gameobject(text)

    existing = existing_file_ids(text)
    instance_id, stripped_trans_id, stripped_mb_id = fresh_file_ids(existing, 3)

    mods = render_modifications(bb_root_trans_source, bb_go_source,
                                bb_prefab_guid, bloodbar_y, bloodbar_scale)
    block = BLOODBAR_PREFAB_INSTANCE.format(
        instance_id=instance_id,
        root_trans_id=root_trans_id,
        mods=mods,
        stripped_trans_id=stripped_trans_id,
        stripped_mb_id=stripped_mb_id,
        bb_prefab_guid=bb_prefab_guid,
        bb_root_trans_source=bb_root_trans_source,
        bb_mb_source=bb_mb_source,
        bb_script_guid=bb_script_guid,
    )

    text2 = text.rstrip("\n") + "\n" + block

    # Patch root Transform's m_Children to include the stripped Transform.
    text2 = patch_root_children(text2, root_trans_id, stripped_trans_id)

    # Wire EnemyView._bloodBar to the stripped MonoBehaviour.
    ev_anchor = find_enemy_view_block_id(text2, enemy_view_script_guid)
    if ev_anchor is None:
        print("  insert-bloodbar: warning — EnemyView MonoBehaviour not found; "
              "BloodBar inserted but _bloodBar field not wired")
    else:
        text2 = patch_enemy_view_bloodbar(text2, ev_anchor, stripped_mb_id)
        print(f"  insert-bloodbar: wired EnemyView &{ev_anchor}._bloodBar -> &{stripped_mb_id}")

    print(f"  insert-bloodbar: instance=&{instance_id} stripped_t=&{stripped_trans_id} "
          f"stripped_mb=&{stripped_mb_id} y={bloodbar_y} scale={bloodbar_scale}")
    return text2


def patch_root_children(text: str, root_trans_id: int, new_child_trans_id: int) -> str:
    """Append a new entry to the root Transform's m_Children list. Reused
    logic from add_projectile_child.py (kept inline here to avoid a circular
    import via different sys.paths)."""
    # Locate root Transform block
    target_block = None
    for m, start, end, body in split_blocks(text):
        if int(m.group(1)) == 4 and int(m.group(2)) == root_trans_id:
            target_block = (start, end, body)
            break
    if not target_block:
        sys.exit(f"error: root Transform &{root_trans_id} not found")
    body_start, body_end, body = target_block

    new_entry_pat = re.compile(rf"-\s*\{{fileID:\s*{new_child_trans_id}\}}")
    if new_entry_pat.search(body):
        return text  # already a child

    empty_pat = re.compile(r"^(\s*)m_Children:\s*\[\]\s*$", re.MULTILINE)
    em = empty_pat.search(body)
    if em:
        indent = em.group(1)
        replacement = f"{indent}m_Children:\n{indent}- {{fileID: {new_child_trans_id}}}"
        body = body[:em.start()] + replacement + body[em.end():]
        return text[:body_start] + body + text[body_end:]

    # Multi-line list: insert after last list entry.
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
    ap.add_argument("prefab")
    ap.add_argument("--new-name", help="Rename the root GameObject to this")
    ap.add_argument("--no-fix-constraints", action="store_true")
    ap.add_argument("--no-bloodbar", action="store_true")
    ap.add_argument("--bloodbar-y", type=float, default=0.38)
    ap.add_argument("--bloodbar-scale", type=float, default=1.0)
    ap.add_argument("--enemy-view-script-guid", default=DEFAULT_ENEMY_VIEW_SCRIPT_GUID)
    ap.add_argument("--bloodbar-prefab-guid", default=DEFAULT_BLOODBAR_PREFAB_GUID)
    ap.add_argument("--bloodbar-script-guid", default=DEFAULT_BLOODBAR_SCRIPT_GUID)
    ap.add_argument("--bloodbar-root-transform-source-id", type=int, default=DEFAULT_BB_ROOT_TRANS_SOURCE)
    ap.add_argument("--bloodbar-game-object-source-id", type=int, default=DEFAULT_BB_GO_SOURCE)
    ap.add_argument("--bloodbar-monobehaviour-source-id", type=int, default=DEFAULT_BB_MB_SOURCE)
    args = ap.parse_args()

    p = Path(args.prefab)
    if not p.exists():
        sys.exit(f"error: prefab not found: {p}")
    text = p.read_text()
    original = text

    print(f"[prefab-setup-enemy] {p}")
    if args.new_name:
        text = rename_root(text, args.new_name)
    if not args.no_fix_constraints:
        text = fix_constraints(text)
    if not args.no_bloodbar:
        text = insert_bloodbar(
            text,
            bloodbar_y=args.bloodbar_y,
            bloodbar_scale=args.bloodbar_scale,
            bb_prefab_guid=args.bloodbar_prefab_guid,
            bb_script_guid=args.bloodbar_script_guid,
            bb_root_trans_source=args.bloodbar_root_transform_source_id,
            bb_go_source=args.bloodbar_game_object_source_id,
            bb_mb_source=args.bloodbar_monobehaviour_source_id,
            enemy_view_script_guid=args.enemy_view_script_guid,
        )
    if text != original:
        p.write_text(text)
        print("  written.")
    else:
        print("  no changes.")


if __name__ == "__main__":
    main()
