#!/usr/bin/env python3
"""Unity Animation Editor - Create and modify Unity 2022 .anim (AnimationClip)
and .controller (AnimatorController) files.

Zero external dependencies: all YAML operations use text templates + regex.
"""

import os
import random
import re
import sys


# ---------------------------------------------------------------------------
# Phase 1: Infrastructure
# ---------------------------------------------------------------------------

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
    lines = content.split("\n")
    in_sprite_sheet = False
    sheet_indent = None
    current_name = None

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if re.match(r"\s+spriteSheet:\s*$", line):
            in_sprite_sheet = True
            sheet_indent = indent
            continue
        if in_sprite_sheet and stripped and indent <= sheet_indent:
            in_sprite_sheet = False

        if not in_sprite_sheet:
            continue

        name_match = re.match(r"\s+name:\s*(.+)$", line)
        if name_match:
            current_name = name_match.group(1).strip()

        id_match = re.match(r"\s+internalID:\s*(\d+)", line)
        if id_match and current_name is not None:
            sprites.append({
                "name": current_name,
                "internal_id": int(id_match.group(1)),
            })
            current_name = None

    return sprites


def parse_doc_ranges(content):
    """Parse document ranges from Unity YAML content.

    Returns a list of dicts with keys: start, end, class_id, file_id.
    """
    doc_pattern = re.compile(r"^--- !u!(\d+) &(\d+)", re.MULTILINE)
    matches = list(doc_pattern.finditer(content))

    doc_ranges = []
    for i, match in enumerate(matches):
        class_id = int(match.group(1))
        file_id = int(match.group(2))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        doc_ranges.append({
            "start": start,
            "end": end,
            "class_id": class_id,
            "file_id": file_id,
        })

    return doc_ranges


def generate_file_id(existing_ids):
    """Generate a new unique fileID not in existing_ids."""
    while True:
        new_id = random.randint(1000000, 99999999)
        if new_id not in existing_ids:
            return new_id


def write_file(path, content):
    """Write content to file with LF line endings."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


UNITY_YAML_HEADER = "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n"


# ---------------------------------------------------------------------------
# Phase 2: .anim file generation
# ---------------------------------------------------------------------------

def generate_pptr_keyframe(time, file_id, guid):
    """Generate a single PPtrCurve keyframe entry."""
    return (
        f"    - time: {format_unity_number(time)}\n"
        f"      value: {{fileID: {file_id}, guid: {guid}, type: 3}}"
    )


def generate_pptr_curve(keyframes):
    """Generate the complete m_PPtrCurves block."""
    lines = [
        "  m_PPtrCurves:",
        "  - curve:",
    ]
    for kf in keyframes:
        lines.append(kf)
    lines.extend([
        "    attribute: m_Sprite",
        "    path: ",
        "    classID: 212",
        "    script: {fileID: 0}",
    ])
    return "\n".join(lines)


def generate_clip_binding_constant(sprite_refs):
    """Generate m_ClipBindingConstant with genericBindings and pptrCurveMapping."""
    lines = [
        "  m_ClipBindingConstant:",
        "    genericBindings:",
        "    - serializedVersion: 2",
        "      path: 0",
        "      attribute: 0",
        "      script: {fileID: 0}",
        "      typeID: 212",
        "      customType: 23",
        "      isPPtrCurve: 1",
        "      isIntCurve: 0",
        "      isSerializeReferenceCurve: 0",
        "    pptrCurveMapping:",
    ]
    for ref in sprite_refs:
        lines.append(f"    - {{fileID: {ref['file_id']}, guid: {ref['guid']}, type: 3}}")
    return "\n".join(lines)


def generate_anim_file(name, image_guid, sprite_ids, sample_rate, loop):
    """Generate a complete .anim file content.

    Args:
        name: Animation clip name
        image_guid: GUID of the source sprite image
        sprite_ids: List of sprite internalIDs to use as frames
        sample_rate: Frames per second (default 12)
        loop: Whether the animation should loop
    """
    count = len(sprite_ids)
    if count == 0:
        raise ValueError("At least one sprite frame is required")

    # Generate keyframes
    keyframes = []
    sprite_refs = []
    for i, sid in enumerate(sprite_ids):
        time = i / sample_rate
        kf = generate_pptr_keyframe(time, sid, image_guid)
        keyframes.append(kf)
        sprite_refs.append({"file_id": sid, "guid": image_guid})

    stop_time = (count - 1) / sample_rate
    loop_time = 1 if loop else 0

    pptr_curve = generate_pptr_curve(keyframes)
    binding_constant = generate_clip_binding_constant(sprite_refs)

    content = UNITY_YAML_HEADER
    content += f"--- !u!74 &7400000\n"
    content += f"AnimationClip:\n"
    content += f"  m_ObjectHideFlags: 0\n"
    content += f"  m_CorrespondingSourceObject: {{fileID: 0}}\n"
    content += f"  m_PrefabInstance: {{fileID: 0}}\n"
    content += f"  m_PrefabAsset: {{fileID: 0}}\n"
    content += f"  m_Name: {name}\n"
    content += f"  serializedVersion: 7\n"
    content += f"  m_Legacy: 0\n"
    content += f"  m_Compressed: 0\n"
    content += f"  m_UseHighQualityCurve: 1\n"
    content += f"  m_RotationCurves: []\n"
    content += f"  m_CompressedRotationCurves: []\n"
    content += f"  m_EulerCurves: []\n"
    content += f"  m_PositionCurves: []\n"
    content += f"  m_ScaleCurves: []\n"
    content += f"  m_FloatCurves: []\n"
    content += pptr_curve + "\n"
    content += f"  m_SampleRate: {sample_rate}\n"
    content += f"  m_WrapMode: 0\n"
    content += f"  m_Bounds:\n"
    content += f"    m_Center: {{x: 0, y: 0, z: 0}}\n"
    content += f"    m_Extent: {{x: 0, y: 0, z: 0}}\n"
    content += binding_constant + "\n"
    content += f"  m_AnimationClipSettings:\n"
    content += f"    serializedVersion: 2\n"
    content += f"    m_AdditiveReferencePoseClip: {{fileID: 0}}\n"
    content += f"    m_AdditiveReferencePoseTime: 0\n"
    content += f"    m_StartTime: 0\n"
    content += f"    m_StopTime: {format_unity_number(stop_time)}\n"
    content += f"    m_OrientationOffsetY: 0\n"
    content += f"    m_Level: 0\n"
    content += f"    m_CycleOffset: 0\n"
    content += f"    m_HasAdditiveReferencePose: 0\n"
    content += f"    m_LoopTime: {loop_time}\n"
    content += f"    m_LoopBlend: 0\n"
    content += f"    m_LoopBlendOrientation: 0\n"
    content += f"    m_LoopBlendPositionY: 0\n"
    content += f"    m_LoopBlendPositionXZ: 0\n"
    content += f"    m_KeepOriginalOrientation: 0\n"
    content += f"    m_KeepOriginalPositionY: 1\n"
    content += f"    m_KeepOriginalPositionXZ: 0\n"
    content += f"    m_HeightFromFeet: 0\n"
    content += f"    m_Mirror: 0\n"
    content += f"  m_EditorCurves: []\n"
    content += f"  m_EulerEditorCurves: []\n"
    content += f"  m_HasGenericRootTransform: 0\n"
    content += f"  m_HasMotionFloatCurves: 0\n"
    content += f"  m_Events: []\n"

    return content


# ---------------------------------------------------------------------------
# Phase 3: .anim rewrite
# ---------------------------------------------------------------------------

def replace_yaml_block(content, block_key, new_block):
    """Replace a YAML block identified by block_key with new content.

    Finds the line containing block_key:, determines the block boundary
    by indentation scanning, and replaces the entire block.
    """
    lines = content.split("\n")

    # Find the block_key line
    block_idx = None
    block_indent = None
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)" + re.escape(block_key) + r":", line)
        if m:
            block_idx = i
            block_indent = len(m.group(1))
            break

    if block_idx is None:
        raise ValueError(f"Block '{block_key}' not found")

    # Determine block end by scanning for next line at same or lesser indent
    block_line = lines[block_idx]

    # Check if it's a single-line value (e.g., "  m_SampleRate: 12")
    if re.match(r"^\s*" + re.escape(block_key) + r":\s+\S", block_line):
        # Single scalar value line — replace just this line
        new_lines = lines[:block_idx] + new_block.split("\n") + lines[block_idx + 1:]
        return "\n".join(new_lines)

    # Check if it's an empty array on same line (e.g., "  m_PPtrCurves: []")
    if re.match(r"^\s*" + re.escape(block_key) + r":\s*\[\]", block_line):
        new_lines = lines[:block_idx] + new_block.split("\n") + lines[block_idx + 1:]
        return "\n".join(new_lines)

    # Multi-line block: find end
    # Lines at the same indent that start with "- " are list items belonging
    # to this block (YAML list syntax). Only stop at same-or-lesser indent
    # lines that are NOT list continuations of this key.
    block_end = block_idx + 1
    for i in range(block_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        if not stripped:
            block_end = i + 1
            continue
        line_indent = len(lines[i]) - len(stripped)
        if line_indent < block_indent:
            block_end = i
            break
        if line_indent == block_indent and not stripped.startswith("- "):
            block_end = i
            break
        block_end = i + 1

    new_lines = lines[:block_idx] + new_block.split("\n") + lines[block_end:]
    return "\n".join(new_lines)


def rewrite_anim_sprites(content, image_guid, sprite_ids, sample_rate, loop):
    """Rewrite an existing .anim file's sprite frames.

    Replaces m_PPtrCurves, pptrCurveMapping, updates m_SampleRate,
    m_StopTime, and m_LoopTime while preserving m_Name and other settings.
    """
    count = len(sprite_ids)
    if count == 0:
        raise ValueError("At least one sprite frame is required")

    stop_time = (count - 1) / sample_rate
    loop_time = 1 if loop else 0

    # Generate new PPtrCurves block
    keyframes = []
    sprite_refs = []
    for i, sid in enumerate(sprite_ids):
        time = i / sample_rate
        kf = generate_pptr_keyframe(time, sid, image_guid)
        keyframes.append(kf)
        sprite_refs.append({"file_id": sid, "guid": image_guid})

    pptr_block = generate_pptr_curve(keyframes)

    # Generate new pptrCurveMapping block
    mapping_lines = ["    pptrCurveMapping:"]
    for ref in sprite_refs:
        mapping_lines.append(f"    - {{fileID: {ref['file_id']}, guid: {ref['guid']}, type: 3}}")
    mapping_block = "\n".join(mapping_lines)

    # Replace m_PPtrCurves block
    content = replace_yaml_block(content, "m_PPtrCurves", pptr_block)

    # Replace pptrCurveMapping block
    content = replace_yaml_block(content, "pptrCurveMapping", mapping_block)

    # Replace m_SampleRate
    content = re.sub(
        r"^(\s+m_SampleRate:)\s*\S+",
        rf"\1 {sample_rate}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    # Replace m_StopTime
    content = re.sub(
        r"^(\s+m_StopTime:)\s*\S+",
        rf"\1 {format_unity_number(stop_time)}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    # Replace m_LoopTime
    if loop is not None:
        content = re.sub(
            r"^(\s+m_LoopTime:)\s*\S+",
            rf"\1 {loop_time}",
            content,
            count=1,
            flags=re.MULTILINE,
        )

    return content


# ---------------------------------------------------------------------------
# Phase 4: .controller file generation
# ---------------------------------------------------------------------------

def generate_animator_state(file_id, name, anim_guid):
    """Generate an AnimatorState document (ClassID 1102)."""
    lines = [
        f"--- !u!1102 &{file_id}",
        "AnimatorState:",
        "  serializedVersion: 6",
        "  m_ObjectHideFlags: 1",
        "  m_CorrespondingSourceObject: {fileID: 0}",
        "  m_PrefabInstance: {fileID: 0}",
        "  m_PrefabAsset: {fileID: 0}",
        f"  m_Name: {name}",
        "  m_Speed: 1",
        "  m_CycleOffset: 0",
        "  m_Transitions: []",
        "  m_StateMachineBehaviours: []",
        "  m_Position: {x: 50, y: 50, z: 0}",
        "  m_IKOnFeet: 0",
        "  m_WriteDefaultValues: 1",
        "  m_Mirror: 0",
        "  m_SpeedParameterActive: 0",
        "  m_MirrorParameterActive: 0",
        "  m_CycleOffsetParameterActive: 0",
        "  m_TimeParameterActive: 0",
        f"  m_Motion: {{fileID: 7400000, guid: {anim_guid}, type: 2}}",
        "  m_Tag: ",
        "  m_SpeedParameter: ",
        "  m_MirrorParameter: ",
        "  m_CycleOffsetParameter: ",
        "  m_TimeParameter: ",
    ]
    return "\n".join(lines) + "\n"


def generate_state_machine(file_id, name, child_states, default_state_id):
    """Generate an AnimatorStateMachine document (ClassID 1107).

    child_states: list of dicts with 'state_id' and 'position' (x, y)
    """
    lines = [
        f"--- !u!1107 &{file_id}",
        "AnimatorStateMachine:",
        "  serializedVersion: 6",
        "  m_ObjectHideFlags: 1",
        "  m_CorrespondingSourceObject: {fileID: 0}",
        "  m_PrefabInstance: {fileID: 0}",
        "  m_PrefabAsset: {fileID: 0}",
        f"  m_Name: {name}",
        "  m_ChildStates:",
    ]
    for cs in child_states:
        lines.extend([
            "  - serializedVersion: 1",
            f"    m_State: {{fileID: {cs['state_id']}}}",
            f"    m_Position: {{x: {cs['position'][0]}, y: {cs['position'][1]}, z: 0}}",
        ])
    lines.extend([
        "  m_ChildStateMachines: []",
        "  m_AnyStateTransitions: []",
        "  m_EntryTransitions: []",
        "  m_StateMachineTransitions: {}",
        "  m_StateMachineBehaviours: []",
        "  m_AnyStatePosition: {x: 50, y: 20, z: 0}",
        "  m_EntryPosition: {x: 50, y: 120, z: 0}",
        "  m_ExitPosition: {x: 800, y: 120, z: 0}",
        "  m_ParentStateMachinePosition: {x: 800, y: 20, z: 0}",
        f"  m_DefaultState: {{fileID: {default_state_id}}}",
    ])
    return "\n".join(lines) + "\n"


def generate_controller_file(controller_name, sm_file_id, layers):
    """Generate an AnimatorController document (ClassID 91).

    layers: list of dicts with 'name' and 'sm_file_id'
    """
    lines = [
        "--- !u!91 &9100000",
        "AnimatorController:",
        "  m_ObjectHideFlags: 0",
        "  m_CorrespondingSourceObject: {fileID: 0}",
        "  m_PrefabInstance: {fileID: 0}",
        "  m_PrefabAsset: {fileID: 0}",
        f"  m_Name: {controller_name}",
        "  serializedVersion: 5",
        "  m_AnimatorParameters: []",
        "  m_AnimatorLayers:",
    ]
    for layer in layers:
        lines.extend([
            "  - serializedVersion: 5",
            f"    m_Name: {layer['name']}",
            f"    m_StateMachine: {{fileID: {layer['sm_file_id']}}}",
            "    m_Mask: {fileID: 0}",
            "    m_Motions: []",
            "    m_Behaviours: []",
            "    m_BlendingMode: 0",
            "    m_SyncedLayerIndex: -1",
            "    m_DefaultWeight: 0",
            "    m_IKPass: 0",
            "    m_SyncedLayerAffectsTiming: 0",
            "    m_Controller: {fileID: 9100000}",
        ])
    return "\n".join(lines) + "\n"


def create_controller_file(controller_name, anim_guid, state_name):
    """Assemble a complete .controller file."""
    existing_ids = {9100000}
    sm_file_id = generate_file_id(existing_ids)
    existing_ids.add(sm_file_id)
    state_file_id = generate_file_id(existing_ids)
    existing_ids.add(state_file_id)

    content = UNITY_YAML_HEADER

    # AnimatorController document
    content += generate_controller_file(
        controller_name, sm_file_id,
        [{"name": "Base Layer", "sm_file_id": sm_file_id}]
    )

    # AnimatorStateMachine document
    content += generate_state_machine(
        sm_file_id, "Base Layer",
        [{"state_id": state_file_id, "position": (200, 0)}],
        state_file_id,
    )

    # AnimatorState document
    content += generate_animator_state(state_file_id, state_name, anim_guid)

    return content


# ---------------------------------------------------------------------------
# Phase 5: Add state to existing controller
# ---------------------------------------------------------------------------

def update_child_states_list(content, doc_ranges, sm_file_id, new_state_id, position):
    """Add a new child state entry to an AnimatorStateMachine's m_ChildStates.

    Handles both empty list (m_ChildStates: []) and existing entries.
    """
    # Find the state machine document
    sm_dr = None
    for dr in doc_ranges:
        if dr["file_id"] == sm_file_id and dr["class_id"] == 1107:
            sm_dr = dr
            break
    if sm_dr is None:
        raise ValueError(f"AnimatorStateMachine with fileID {sm_file_id} not found")

    doc_text = content[sm_dr["start"]:sm_dr["end"]]

    new_entry = (
        f"  - serializedVersion: 1\n"
        f"    m_State: {{fileID: {new_state_id}}}\n"
        f"    m_Position: {{x: {position[0]}, y: {position[1]}, z: 0}}"
    )

    # Case 1: empty list
    empty_match = re.search(r"^(\s+)m_ChildStates:\s*\[\]", doc_text, re.MULTILINE)
    if empty_match:
        indent = empty_match.group(1)
        # Adjust new_entry indentation to match document
        replacement = f"{indent}m_ChildStates:\n{new_entry}"
        new_doc = doc_text[:empty_match.start()] + replacement + doc_text[empty_match.end():]
        return content[:sm_dr["start"]] + new_doc + content[sm_dr["end"]:]

    # Case 2: existing entries — find the last m_Position line under m_ChildStates
    child_states_match = re.search(r"^\s+m_ChildStates:", doc_text, re.MULTILINE)
    if not child_states_match:
        raise ValueError("m_ChildStates not found in AnimatorStateMachine")

    # Find all m_Position lines that are part of child state entries
    pos_pattern = re.compile(r"^    m_Position: \{x: .+\}$", re.MULTILINE)
    positions = list(pos_pattern.finditer(doc_text))

    # We need positions that come after m_ChildStates and before the next top-level field
    cs_start = child_states_match.start()
    # Find the next field at indentation level 2 (same as m_ChildStates)
    next_field = re.search(r"^\s{2}m_\w+:", doc_text[child_states_match.end():], re.MULTILINE)
    cs_end = child_states_match.end() + next_field.start() if next_field else len(doc_text)

    cs_positions = [p for p in positions if cs_start < p.start() < cs_end]

    if not cs_positions:
        raise ValueError("Could not find child state entries in m_ChildStates")

    last_pos = cs_positions[-1]
    insert_point = last_pos.end()
    new_doc = doc_text[:insert_point] + "\n" + new_entry + doc_text[insert_point:]
    return content[:sm_dr["start"]] + new_doc + content[sm_dr["end"]:]


def add_state_to_controller(content, anim_guid, state_name):
    """Add a new AnimatorState to an existing .controller file.

    Appends the AnimatorState document and updates m_ChildStates.
    """
    doc_ranges = parse_doc_ranges(content)

    # Collect existing file IDs
    existing_ids = set(dr["file_id"] for dr in doc_ranges)

    # Generate new state file ID
    state_file_id = generate_file_id(existing_ids)

    # Find the first AnimatorStateMachine (1107)
    sm_dr = None
    for dr in doc_ranges:
        if dr["class_id"] == 1107:
            sm_dr = dr
            break
    if sm_dr is None:
        raise ValueError("No AnimatorStateMachine found in .controller file")

    # Count existing child states to determine Y position
    sm_text = content[sm_dr["start"]:sm_dr["end"]]
    existing_states = re.findall(r"m_State: \{fileID: \d+\}", sm_text)
    y_pos = len(existing_states) * 48
    position = (200, y_pos)

    # Update m_ChildStates list
    content = update_child_states_list(
        content, doc_ranges, sm_dr["file_id"],
        state_file_id, position,
    )

    # Append new AnimatorState document at end of file
    state_doc = generate_animator_state(state_file_id, state_name, anim_guid)
    if not content.endswith("\n"):
        content += "\n"
    content += state_doc

    return content


# ---------------------------------------------------------------------------
# Phase 6: Inspect commands
# ---------------------------------------------------------------------------

def read_anim_info(anim_path):
    """Read animation info from a .anim file."""
    with open(anim_path, "r", encoding="utf-8") as f:
        content = f.read()

    info = {}

    m = re.search(r"^\s+m_Name:\s*(.+)$", content, re.MULTILINE)
    info["name"] = m.group(1).strip() if m else "unknown"

    m = re.search(r"^\s+m_SampleRate:\s*(\S+)", content, re.MULTILINE)
    info["sample_rate"] = m.group(1) if m else "unknown"

    m = re.search(r"^\s+m_LoopTime:\s*(\S+)", content, re.MULTILINE)
    info["loop_time"] = m.group(1) if m else "unknown"

    m = re.search(r"^\s+m_StopTime:\s*(\S+)", content, re.MULTILINE)
    info["stop_time"] = m.group(1) if m else "unknown"

    # Count sprite frames in PPtrCurves
    frames = re.findall(r"value: \{fileID: (\d+), guid: ([0-9a-f]+)", content)
    info["frame_count"] = len(frames)
    info["frames"] = frames

    # Get unique guids referenced
    guids = set(f[1] for f in frames)
    info["image_guids"] = list(guids)

    return info


def read_controller_info(controller_path):
    """Read controller info from a .controller file."""
    with open(controller_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc_ranges = parse_doc_ranges(content)
    info = {"layers": [], "state_machines": [], "states": []}

    for dr in doc_ranges:
        doc_text = content[dr["start"]:dr["end"]]

        if dr["class_id"] == 91:
            # AnimatorController
            m = re.search(r"^\s+m_Name:\s*(.+)$", doc_text, re.MULTILINE)
            info["name"] = m.group(1).strip() if m else "unknown"
            # Count layers
            layers = re.findall(r"m_Name:\s*(.+)$", doc_text, re.MULTILINE)
            # First match is controller name, rest are layer names
            info["layers"] = [l.strip() for l in layers[1:]]

        elif dr["class_id"] == 1107:
            # AnimatorStateMachine
            m = re.search(r"^\s+m_Name:\s*(.+)$", doc_text, re.MULTILINE)
            name = m.group(1).strip() if m else "unknown"
            states = re.findall(r"m_State: \{fileID: (\d+)\}", doc_text)
            info["state_machines"].append({
                "file_id": dr["file_id"],
                "name": name,
                "state_count": len(states),
                "state_ids": [int(s) for s in states],
            })

        elif dr["class_id"] == 1102:
            # AnimatorState
            m = re.search(r"^\s+m_Name:\s*(.+)$", doc_text, re.MULTILINE)
            name = m.group(1).strip() if m else "unknown"
            motion = re.search(r"m_Motion: \{fileID: (\d+), guid: ([0-9a-f]+)", doc_text)
            info["states"].append({
                "file_id": dr["file_id"],
                "name": name,
                "motion_guid": motion.group(2) if motion else None,
            })

    return info


def cmd_inspect_anim(args):
    """Inspect a .anim file and print info."""
    if len(args) < 1:
        print("Usage: inspect-anim <anim_path>", file=sys.stderr)
        sys.exit(1)

    anim_path = args[0]
    if not os.path.isfile(anim_path):
        print(f"Error: File not found: {anim_path}", file=sys.stderr)
        sys.exit(1)

    info = read_anim_info(anim_path)
    print(f"File: {anim_path}")
    print(f"Name: {info['name']}")
    print(f"Sample Rate: {info['sample_rate']}")
    print(f"Stop Time: {info['stop_time']}")
    print(f"Loop: {info['loop_time']}")
    print(f"Sprite Frames: {info['frame_count']}")
    if info['image_guids']:
        print(f"Image GUIDs: {', '.join(info['image_guids'])}")
    if info['frames']:
        print()
        for i, (fid, guid) in enumerate(info['frames']):
            time = i / float(info['sample_rate']) if info['sample_rate'] != 'unknown' else '?'
            print(f"  [{i}] fileID: {fid}, guid: {guid}, time: {format_unity_number(time)}")


def cmd_inspect_controller(args):
    """Inspect a .controller file and print info."""
    if len(args) < 1:
        print("Usage: inspect-controller <controller_path>", file=sys.stderr)
        sys.exit(1)

    controller_path = args[0]
    if not os.path.isfile(controller_path):
        print(f"Error: File not found: {controller_path}", file=sys.stderr)
        sys.exit(1)

    info = read_controller_info(controller_path)
    print(f"File: {controller_path}")
    print(f"Name: {info.get('name', 'unknown')}")
    print(f"Layers: {len(info['layers'])}")
    for layer in info['layers']:
        print(f"  - {layer}")

    print(f"State Machines: {len(info['state_machines'])}")
    for sm in info['state_machines']:
        print(f"  - {sm['name']} (fileID: {sm['file_id']}, states: {sm['state_count']})")

    print(f"States: {len(info['states'])}")
    for state in info['states']:
        motion_info = f", motion guid: {state['motion_guid']}" if state['motion_guid'] else ""
        print(f"  - {state['name']} (fileID: {state['file_id']}{motion_info})")


# ---------------------------------------------------------------------------
# Phase 7: CLI commands
# ---------------------------------------------------------------------------

def parse_flags(args):
    """Parse command-line flags from args list.

    Returns (positional_args, flags_dict) where flags_dict maps
    flag names (without --) to their values.
    """
    positional = []
    flags = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            flag_name = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                flags[flag_name] = args[i + 1]
                i += 2
            else:
                flags[flag_name] = True
                i += 1
        else:
            positional.append(args[i])
            i += 1
    return positional, flags


def cmd_create_anim(args):
    """Create a new .anim file from sprite frames."""
    positional, flags = parse_flags(args)

    if len(positional) < 2:
        print("Usage: create-anim <anim_path> <image_path> [indices...] "
              "[--name N] [--sample-rate N] [--loop]", file=sys.stderr)
        sys.exit(1)

    anim_path = positional[0]
    image_path = positional[1]
    indices = [int(x) for x in positional[2:]] if len(positional) > 2 else None

    name = flags.get("name", os.path.splitext(os.path.basename(anim_path))[0])
    sample_rate = int(flags.get("sample-rate", 12))
    loop = "loop" in flags

    # Read image meta
    meta_path = image_path + ".meta"
    if not os.path.isfile(meta_path):
        print(f"Error: Meta file not found: {meta_path}", file=sys.stderr)
        sys.exit(1)

    image_guid = read_guid_from_meta(meta_path)
    sprites = read_sprites_from_meta(meta_path)

    if not sprites:
        print(f"Error: No sprites found in {meta_path}. "
              "Is the image sliced (spriteMode: 2)?", file=sys.stderr)
        sys.exit(1)

    # Select sprites by indices
    if indices is not None:
        for idx in indices:
            if idx < 0 or idx >= len(sprites):
                print(f"Error: Sprite index {idx} out of range "
                      f"(0-{len(sprites)-1})", file=sys.stderr)
                sys.exit(1)
        selected = [sprites[i] for i in indices]
    else:
        selected = sprites

    sprite_ids = [s["internal_id"] for s in selected]

    print(f"Image: {image_path}")
    print(f"Image GUID: {image_guid}")
    print(f"Sprites: {len(selected)} frames")
    print(f"Name: {name}")
    print(f"Sample Rate: {sample_rate}")
    print(f"Loop: {loop}")

    content = generate_anim_file(name, image_guid, sprite_ids, sample_rate, loop)
    write_file(anim_path, content)

    # Create .meta file if it doesn't exist
    anim_meta_path = anim_path + ".meta"
    if not os.path.isfile(anim_meta_path):
        import uuid
        meta_guid = uuid.uuid4().hex
        meta_content = (
            f"fileFormatVersion: 2\n"
            f"guid: {meta_guid}\n"
            f"NativeFormatImporter:\n"
            f"  externalObjects: {{}}\n"
            f"  mainObjectFileID: 7400000\n"
            f"  userData: \n"
            f"  assetBundleName: \n"
            f"  assetBundleVariant: \n"
        )
        write_file(anim_meta_path, meta_content)
        print(f"Created: {anim_meta_path}")

    print(f"Created: {anim_path}")


def cmd_rewrite_anim(args):
    """Rewrite sprite frames in an existing .anim file."""
    positional, flags = parse_flags(args)

    if len(positional) < 2:
        print("Usage: rewrite-anim <anim_path> <image_path> [indices...] "
              "[--sample-rate N] [--loop]", file=sys.stderr)
        sys.exit(1)

    anim_path = positional[0]
    image_path = positional[1]
    indices = [int(x) for x in positional[2:]] if len(positional) > 2 else None

    sample_rate = int(flags.get("sample-rate", 12))
    loop_flag = flags.get("loop", None)

    if not os.path.isfile(anim_path):
        print(f"Error: Anim file not found: {anim_path}", file=sys.stderr)
        sys.exit(1)

    # Read image meta
    meta_path = image_path + ".meta"
    if not os.path.isfile(meta_path):
        print(f"Error: Meta file not found: {meta_path}", file=sys.stderr)
        sys.exit(1)

    image_guid = read_guid_from_meta(meta_path)
    sprites = read_sprites_from_meta(meta_path)

    if not sprites:
        print(f"Error: No sprites found in {meta_path}", file=sys.stderr)
        sys.exit(1)

    # Select sprites by indices
    if indices is not None:
        for idx in indices:
            if idx < 0 or idx >= len(sprites):
                print(f"Error: Sprite index {idx} out of range "
                      f"(0-{len(sprites)-1})", file=sys.stderr)
                sys.exit(1)
        selected = [sprites[i] for i in indices]
    else:
        selected = sprites

    sprite_ids = [s["internal_id"] for s in selected]

    # Read existing .anim content
    with open(anim_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Determine loop setting: use flag if provided, else preserve existing
    if loop_flag is not None:
        loop = True
    else:
        m = re.search(r"^\s+m_LoopTime:\s*(\d+)", content, re.MULTILINE)
        loop = bool(int(m.group(1))) if m else False

    content = rewrite_anim_sprites(content, image_guid, sprite_ids, sample_rate, loop)
    write_file(anim_path, content)

    print(f"Image: {image_path}")
    print(f"Sprites: {len(selected)} frames")
    print(f"Sample Rate: {sample_rate}")
    print(f"Loop: {loop}")
    print(f"Updated: {anim_path}")


def cmd_create_controller(args):
    """Create a new .controller file with one animation state."""
    positional, flags = parse_flags(args)

    if len(positional) < 2:
        print("Usage: create-controller <controller_path> <anim_path> "
              "[--name N]", file=sys.stderr)
        sys.exit(1)

    controller_path = positional[0]
    anim_path = positional[1]

    name = flags.get("name", os.path.splitext(os.path.basename(controller_path))[0])

    # Read anim GUID
    anim_meta_path = anim_path + ".meta"
    if not os.path.isfile(anim_meta_path):
        print(f"Error: Anim meta file not found: {anim_meta_path}", file=sys.stderr)
        sys.exit(1)

    anim_guid = read_guid_from_meta(anim_meta_path)

    # Derive state name from anim file name
    state_name = os.path.splitext(os.path.basename(anim_path))[0]

    content = create_controller_file(name, anim_guid, state_name)
    write_file(controller_path, content)

    # Create .meta file if it doesn't exist
    ctrl_meta_path = controller_path + ".meta"
    if not os.path.isfile(ctrl_meta_path):
        import uuid
        meta_guid = uuid.uuid4().hex
        meta_content = (
            f"fileFormatVersion: 2\n"
            f"guid: {meta_guid}\n"
            f"NativeFormatImporter:\n"
            f"  externalObjects: {{}}\n"
            f"  mainObjectFileID: 9100000\n"
            f"  userData: \n"
            f"  assetBundleName: \n"
            f"  assetBundleVariant: \n"
        )
        write_file(ctrl_meta_path, meta_content)
        print(f"Created: {ctrl_meta_path}")

    print(f"Controller: {name}")
    print(f"Animation: {anim_path} (guid: {anim_guid})")
    print(f"State: {state_name}")
    print(f"Created: {controller_path}")


def cmd_add_to_controller(args):
    """Add an animation state to an existing .controller file."""
    positional, flags = parse_flags(args)

    if len(positional) < 2:
        print("Usage: add-to-controller <controller_path> <anim_path> "
              "[--state-name N]", file=sys.stderr)
        sys.exit(1)

    controller_path = positional[0]
    anim_path = positional[1]

    state_name = flags.get("state-name",
                           os.path.splitext(os.path.basename(anim_path))[0])

    if not os.path.isfile(controller_path):
        print(f"Error: Controller file not found: {controller_path}", file=sys.stderr)
        sys.exit(1)

    # Read anim GUID
    anim_meta_path = anim_path + ".meta"
    if not os.path.isfile(anim_meta_path):
        print(f"Error: Anim meta file not found: {anim_meta_path}", file=sys.stderr)
        sys.exit(1)

    anim_guid = read_guid_from_meta(anim_meta_path)

    with open(controller_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = add_state_to_controller(content, anim_guid, state_name)
    write_file(controller_path, content)

    print(f"Animation: {anim_path} (guid: {anim_guid})")
    print(f"State: {state_name}")
    print(f"Updated: {controller_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Unity Animation Editor", file=sys.stderr)
        print("", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  create-anim <anim_path> <image_path> [indices...] [--name N] [--sample-rate N] [--loop]", file=sys.stderr)
        print("  rewrite-anim <anim_path> <image_path> [indices...] [--sample-rate N] [--loop]", file=sys.stderr)
        print("  create-controller <controller_path> <anim_path> [--name N]", file=sys.stderr)
        print("  add-to-controller <controller_path> <anim_path> [--state-name N]", file=sys.stderr)
        print("  inspect-anim <anim_path>", file=sys.stderr)
        print("  inspect-controller <controller_path>", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "create-anim": cmd_create_anim,
        "rewrite-anim": cmd_rewrite_anim,
        "create-controller": cmd_create_controller,
        "add-to-controller": cmd_add_to_controller,
        "inspect-anim": cmd_inspect_anim,
        "inspect-controller": cmd_inspect_controller,
    }

    if command not in commands:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available commands: {', '.join(commands)}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
