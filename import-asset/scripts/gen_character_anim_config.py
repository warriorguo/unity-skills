#!/usr/bin/env python3
"""Write a CharacterAnimConfig ScriptableObject .asset that wraps a freshly-
cloned enemy prefab. Reads the prefab's .meta for its guid and parses the
prefab YAML to find the root GameObject's fileID for the modelPrefab ref.

The generated asset is a minimal-but-valid skeleton: empty
`spriteAnimStates` and `aiStateMapping`, default turn/fire fields, no
attached attack anim. The user fills these in (or extends with subsequent
import-asset steps) once the prefab is wired.

Usage:
    gen_character_anim_config.py <output.asset> --prefab <prefab>
        [--name N] [--script-guid GUID] [--force]
"""

import argparse
import re
import sys
from pathlib import Path


DEFAULT_SCRIPT_GUID = "173208a7823c34815b09efdff2ea601b"


def read_meta_guid(meta: Path) -> str:
    text = meta.read_text()
    m = re.search(r"^guid:\s*([a-fA-F0-9]+)", text, re.MULTILINE)
    if not m:
        sys.exit(f"error: no guid in {meta}")
    return m.group(1)


def find_root_go_fileid(prefab_text: str) -> int:
    """Find the root GameObject's fileID — its Transform has m_Father: 0."""
    anchor_re = re.compile(r"^---\s*!u!(\d+)\s*&(\d+)", re.MULTILINE)
    matches = list(anchor_re.finditer(prefab_text))
    for i, m in enumerate(matches):
        if int(m.group(1)) != 4:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prefab_text)
        body = prefab_text[start:end]
        if re.search(r"^\s*m_Father:\s*\{fileID:\s*0\}\s*$", body, re.MULTILINE):
            go_match = re.search(r"^\s*m_GameObject:\s*\{fileID:\s*(\d+)\}", body, re.MULTILINE)
            if go_match:
                return int(go_match.group(1))
    sys.exit("error: could not find root GameObject in prefab")


TEMPLATE = """%YAML 1.1
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
  modelPrefab: {{fileID: {root_go}, guid: {prefab_guid}, type: 3}}
  leg:
    prefab: {{fileID: 0}}
    offset: {{x: 0, y: 0}}
  heads: []
  turnRadius: 0
  turnRate: 180
  turnBeforeMove: 1
  spriteAnimStates: []
  aiStateMapping: []
  fireAnimDelay: 0
  deathFxKeys: []
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("output", help="Output .asset path")
    ap.add_argument("--prefab", required=True, help="Source prefab path (its .meta + root GO are read)")
    ap.add_argument("--name", help="Asset m_Name (default: output basename without ext)")
    ap.add_argument("--script-guid", default=DEFAULT_SCRIPT_GUID)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.output)
    prefab = Path(args.prefab)
    meta = Path(str(prefab) + ".meta")
    if not prefab.exists():
        sys.exit(f"error: prefab not found: {prefab}")
    if not meta.exists():
        sys.exit(f"error: prefab .meta not found: {meta}")

    prefab_guid = read_meta_guid(meta)
    root_go = find_root_go_fileid(prefab.read_text())
    name = args.name or out.stem

    new_text = TEMPLATE.format(
        script_guid=args.script_guid,
        name=name,
        root_go=root_go,
        prefab_guid=prefab_guid,
    )

    if out.exists() and not args.force and out.read_text() == new_text:
        print(f"[gen-character-anim-config] {out}  skip (unchanged)")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new_text)
    print(f"[gen-character-anim-config] {out}  modelPrefab={{fileID:{root_go}, guid:{prefab_guid}}}")


if __name__ == "__main__":
    main()
