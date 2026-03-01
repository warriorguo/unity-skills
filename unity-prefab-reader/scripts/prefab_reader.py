#!/usr/bin/env python3
"""Unity Prefab Reader - Parse and browse Unity 2022 prefab files.

Supports tree browsing, object inspection, component listing,
searching, and summary statistics for Unity YAML-serialized prefabs.
"""

import argparse
import re
import sys
from collections import Counter, OrderedDict

import yaml

# ---------------------------------------------------------------------------
# Unity ClassID -> Human-readable name mapping
# ---------------------------------------------------------------------------
CLASS_ID_MAP = {
    1: "GameObject",
    2: "Component",
    4: "Transform",
    8: "Behaviour",
    12: "ParticleAnimator",
    13: "Input",
    20: "Camera",
    21: "Material",
    23: "MeshRenderer",
    25: "Renderer",
    28: "Texture2D",
    33: "MeshFilter",
    43: "Mesh",
    48: "Shader",
    54: "Rigidbody",
    56: "Collider",
    58: "CircleCollider2D",
    59: "HingeJoint",
    60: "PolygonCollider2D",
    61: "BoxCollider2D",
    64: "MeshCollider",
    65: "BoxCollider",
    66: "CompositeCollider2D",
    68: "EdgeCollider2D",
    70: "CapsuleCollider2D",
    78: "AudioListener",
    81: "AudioSource",
    82: "AudioClip",
    83: "RenderTexture",
    84: "Cubemap",
    87: "Avatar",
    89: "CubemapArray",
    90: "RuntimeAnimatorController",
    91: "AnimatorController",
    92: "Animation",
    95: "Animator",
    96: "TrailRenderer",
    98: "BillboardAsset",
    102: "TextMesh",
    104: "RenderSettings",
    108: "Light",
    109: "CGProgram",
    110: "BaseAnimationTrack",
    111: "AnimationClip",
    114: "MonoBehaviour",
    115: "MonoScript",
    120: "LineRenderer",
    124: "Behaviour",
    128: "Font",
    131: "GUITexture",
    132: "Flare",
    133: "LandscapeProxy",
    134: "PhysicMaterial",
    135: "SphereCollider",
    136: "CapsuleCollider",
    137: "SkinnedMeshRenderer",
    141: "BuildSettings",
    142: "AssetBundle",
    143: "CharacterController",
    144: "CharacterJoint",
    145: "SpringJoint",
    146: "WheelCollider",
    147: "ResourceManager",
    150: "PreloadData",
    152: "MovieTexture",
    153: "ConfigurableJoint",
    154: "TerrainCollider",
    156: "TerrainData",
    157: "LightmapSettings",
    158: "WebCamTexture",
    159: "EditorSettings",
    162: "EditorUserSettings",
    164: "AudioReverbFilter",
    165: "AudioHighPassFilter",
    166: "AudioChorusFilter",
    167: "AudioReverbZone",
    168: "AudioEchoFilter",
    169: "AudioLowPassFilter",
    170: "AudioDistortionFilter",
    171: "SparseTexture",
    180: "AudioBehaviour",
    181: "AudioFilter",
    182: "WindZone",
    183: "Cloth",
    184: "SubstanceArchive",
    185: "ProceduralMaterial",
    186: "ProceduralTexture",
    191: "OffMeshLink",
    192: "OcclusionArea",
    193: "OcclusionPortal",
    195: "NavMeshObsolete",
    196: "NavMeshAgent",
    198: "Terrain",
    199: "TerrainManager",
    200: "LightProbeGroup",
    205: "ParticleSystem",
    206: "ParticleSystemRenderer",
    207: "ShaderVariantCollection",
    208: "LODGroup",
    210: "BlendTree",
    212: "SpriteRenderer",
    213: "Sprite",
    214: "CachedSpriteAtlas",
    215: "ReflectionProbe",
    218: "Terrain",
    220: "LightProbeProxyVolume",
    222: "CanvasRenderer",
    223: "Canvas",
    224: "RectTransform",
    225: "CanvasGroup",
    226: "BillboardRenderer",
    227: "EventTrigger",
    228: "HaloLayer",
    229: "AvatarMask",
    236: "PlayableDirector",
    237: "VideoPlayer",
    238: "VideoClip",
    240: "SpriteMask",
    248: "Grid",
    249: "Tilemap",
    250: "TilemapRenderer",
    258: "SortingGroup",
    271: "SpriteShapeRenderer",
    290: "VisualEffect",
    310: "UnityConnectSettings",
    319: "AimConstraint",
    320: "PositionConstraint",
    321: "RotationConstraint",
    322: "ScaleConstraint",
    1001: "PrefabInstance",
    1660057539: "SceneRoots",
}


# ---------------------------------------------------------------------------
# Custom YAML loader for Unity's tagged multi-document format
# ---------------------------------------------------------------------------

class UnityYAMLLoader(yaml.SafeLoader):
    """Custom YAML loader that handles Unity's !u! tags."""
    pass


def _unity_tag_constructor(loader, tag_suffix, node):
    """Handle !u!<classID> tags by returning the parsed mapping/sequence."""
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


# Register a multi-constructor for the Unity tag prefix
UnityYAMLLoader.add_multi_constructor(
    "tag:unity3d.com,2011:",
    _unity_tag_constructor,
)


def parse_prefab(path):
    """Parse a Unity prefab file into a list of (class_id, file_id, data) tuples."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on document separators: --- !u!<classID> &<fileID>
    doc_pattern = re.compile(r"^--- !u!(\d+) &(\d+)", re.MULTILINE)
    matches = list(doc_pattern.finditer(content))

    objects = []
    for i, match in enumerate(matches):
        class_id = int(match.group(1))
        file_id = int(match.group(2))

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        doc_text = content[start:end].strip()

        if not doc_text:
            objects.append((class_id, file_id, {}))
            continue

        # Handle the "stripped" marker that appears in prefab variants
        doc_text = doc_text.replace(" stripped", "")

        try:
            data = yaml.load(doc_text, Loader=UnityYAMLLoader)
            if data is None:
                data = {}
        except yaml.YAMLError:
            data = {"_parse_error": True, "_raw": doc_text[:200]}

        objects.append((class_id, file_id, data))

    return objects


# ---------------------------------------------------------------------------
# Helper: resolve fileID references
# ---------------------------------------------------------------------------

def _ref_id(ref):
    """Extract fileID from a Unity object reference dict like {fileID: 123}."""
    if isinstance(ref, dict):
        return ref.get("fileID", 0)
    return 0


def _class_name(class_id):
    return CLASS_ID_MAP.get(class_id, f"Unknown({class_id})")


# ---------------------------------------------------------------------------
# Build indexed structures from parsed objects
# ---------------------------------------------------------------------------

def build_index(objects):
    """Build lookup dicts from parsed objects.

    Returns:
        by_id: dict mapping fileID -> (class_id, data)
        game_objects: dict mapping fileID -> GameObject data
        transforms: dict mapping fileID -> Transform/RectTransform data with extra keys
    """
    by_id = {}
    for class_id, file_id, data in objects:
        by_id[file_id] = (class_id, data)

    game_objects = {}
    transforms = {}

    for class_id, file_id, data in objects:
        if class_id == 1:  # GameObject
            go_data = data.get("GameObject", data)
            game_objects[file_id] = go_data
        elif class_id in (4, 224):  # Transform or RectTransform
            key = "Transform" if class_id == 4 else "RectTransform"
            t_data = data.get(key, data)
            t_data["_fileID"] = file_id
            t_data["_classID"] = class_id
            transforms[file_id] = t_data

    return by_id, game_objects, transforms


def build_tree(game_objects, transforms, by_id):
    """Build parent-child tree of GameObjects via Transform hierarchy.

    Returns:
        roots: list of fileIDs of root GameObjects
        children_map: dict mapping GO fileID -> list of child GO fileIDs
        go_transform: dict mapping GO fileID -> transform data
        go_components: dict mapping GO fileID -> list of (class_id, file_id, data)
    """
    # Map: transform fileID -> GO fileID
    transform_to_go = {}
    # Map: GO fileID -> transform data
    go_transform = {}
    # Map: GO fileID -> list of (class_id, component_fileID)
    go_components = {}

    for t_fid, t_data in transforms.items():
        go_ref = _ref_id(t_data.get("m_GameObject", {}))
        if go_ref:
            transform_to_go[t_fid] = go_ref
            go_transform[go_ref] = t_data

    # Build component lists for each GameObject
    for go_fid, go_data in game_objects.items():
        comp_list = go_data.get("m_Component", [])
        components = []
        for entry in comp_list:
            if isinstance(entry, dict):
                comp_ref = entry.get("component", {})
                comp_fid = _ref_id(comp_ref)
                if comp_fid and comp_fid in by_id:
                    cid, _ = by_id[comp_fid]
                    components.append((cid, comp_fid))
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                comp_ref = entry[1]
                comp_fid = _ref_id(comp_ref)
                if comp_fid and comp_fid in by_id:
                    cid, _ = by_id[comp_fid]
                    components.append((cid, comp_fid))
        go_components[go_fid] = components

    # Build children map
    children_map = {}
    child_gos = set()

    for t_fid, t_data in transforms.items():
        parent_go = transform_to_go.get(t_fid)
        if not parent_go:
            continue
        child_transforms = t_data.get("m_Children", [])
        kids = []
        for child_ref in child_transforms:
            child_t_fid = _ref_id(child_ref)
            child_go = transform_to_go.get(child_t_fid)
            if child_go:
                kids.append(child_go)
                child_gos.add(child_go)
        children_map[parent_go] = kids

    # Roots: GameObjects that are not children of any other
    roots = [fid for fid in game_objects if fid not in child_gos]

    return roots, children_map, go_transform, go_components


def _go_name(game_objects, fid):
    go = game_objects.get(fid, {})
    return go.get("m_Name", f"<unnamed:{fid}>")


# ---------------------------------------------------------------------------
# Subcommand: tree
# ---------------------------------------------------------------------------

def cmd_tree(args):
    objects = parse_prefab(args.prefab_path)
    by_id, game_objects, transforms = build_index(objects)
    roots, children_map, go_transform, go_components = build_tree(
        game_objects, transforms, by_id
    )

    max_depth = args.depth if args.depth is not None else float("inf")

    def print_node(fid, prefix, is_last, depth):
        if depth > max_depth:
            return
        name = _go_name(game_objects, fid)
        comps = go_components.get(fid, [])
        # Filter out Transform/RectTransform/GameObject from component display
        visible = [
            _class_name(cid)
            for cid, _ in comps
            if cid not in (1, 4, 224)
        ]
        comp_str = f"  [{', '.join(visible)}]" if visible else ""
        connector = "\u2514\u2500 " if is_last else "\u251c\u2500 "
        print(f"{prefix}{connector}{name} &{fid}{comp_str}")

        children = children_map.get(fid, [])
        new_prefix = prefix + ("   " if is_last else "\u2502  ")
        for i, child in enumerate(children):
            print_node(child, new_prefix, i == len(children) - 1, depth + 1)

    if not roots:
        # Possibly a prefab variant with PrefabInstance
        prefab_instances = [
            (fid, data)
            for cid, fid, data in objects
            if cid == 1001
        ]
        if prefab_instances:
            print("[Prefab Variant]")
            for fid, data in prefab_instances:
                pi = data.get("PrefabInstance", data)
                source = pi.get("m_SourcePrefab", {})
                guid = source.get("guid", "?") if isinstance(source, dict) else "?"
                print(f"  PrefabInstance &{fid} (source guid: {guid})")
                mods = pi.get("m_Modification", {})
                if isinstance(mods, dict):
                    mod_list = mods.get("m_Modifications", [])
                    print(f"    modifications: {len(mod_list)}")
            # Also show any overridden GameObjects
            if game_objects:
                print("\n[Overridden GameObjects]")
                for i, fid in enumerate(game_objects):
                    is_last = i == len(game_objects) - 1
                    print_node(fid, "", is_last, 0)
        else:
            print("(no GameObjects found)")
        return

    for i, root in enumerate(roots):
        is_last = i == len(roots) - 1
        print_node(root, "", is_last, 0)


# ---------------------------------------------------------------------------
# Subcommand: inspect
# ---------------------------------------------------------------------------

def cmd_inspect(args):
    objects = parse_prefab(args.prefab_path)
    by_id, _, _ = build_index(objects)

    file_id = int(args.file_id)
    if file_id not in by_id:
        print(f"Error: fileID {file_id} not found in prefab.", file=sys.stderr)
        sys.exit(1)

    class_id, data = by_id[file_id]
    print(f"--- !u!{class_id} &{file_id}  ({_class_name(class_id)})")
    _print_yaml(data, indent=0)


def _print_yaml(obj, indent=0):
    """Pretty-print a parsed YAML object in a readable format."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                print(f"{prefix}{key}:")
                _print_yaml(val, indent + 1)
            else:
                print(f"{prefix}{key}: {val}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                print(f"{prefix}-")
                _print_yaml(item, indent + 1)
            else:
                print(f"{prefix}- {item}")
    else:
        print(f"{prefix}{obj}")


# ---------------------------------------------------------------------------
# Subcommand: components
# ---------------------------------------------------------------------------

def cmd_components(args):
    objects = parse_prefab(args.prefab_path)
    by_id, game_objects, transforms = build_index(objects)
    roots, children_map, go_transform, go_components = build_tree(
        game_objects, transforms, by_id
    )

    go_fid = int(args.gameobject_id)
    if go_fid not in game_objects:
        print(f"Error: GameObject &{go_fid} not found.", file=sys.stderr)
        sys.exit(1)

    name = _go_name(game_objects, go_fid)
    print(f"Components of '{name}' &{go_fid}:")
    print()

    comps = go_components.get(go_fid, [])
    if not comps:
        print("  (no components)")
        return

    for cid, comp_fid in comps:
        class_name = _class_name(cid)
        _, comp_data = by_id.get(comp_fid, (None, {}))
        print(f"  [{class_name}] &{comp_fid}")
        # Show a compact summary of key fields
        _print_component_summary(cid, comp_data, class_name)
        print()


def _print_component_summary(class_id, data, class_name):
    """Print a compact summary of important fields for a component."""
    # Unwrap the top-level key (e.g. {"MonoBehaviour": {...}})
    inner = data
    if isinstance(data, dict) and len(data) == 1:
        inner = list(data.values())[0]
    if not isinstance(inner, dict):
        return

    # For MonoBehaviour, show the script reference
    if class_id == 114:
        script = inner.get("m_Script", {})
        if isinstance(script, dict):
            guid = script.get("guid", "")
            if guid:
                print(f"    script guid: {guid}")
        m_name = inner.get("m_Name", "")
        if m_name:
            print(f"    m_Name: {m_name}")
        enabled = inner.get("m_Enabled")
        if enabled is not None:
            print(f"    m_Enabled: {enabled}")
        # Show custom serialized fields (skip internal Unity fields)
        skip = {
            "m_ObjectHideFlags", "m_CorrespondingSourceObject",
            "m_PrefabInstance", "m_PrefabAsset", "m_GameObject",
            "m_Enabled", "m_EditorHideFlags", "m_Script",
            "m_Name", "m_EditorClassIdentifier",
        }
        custom = {k: v for k, v in inner.items() if k not in skip}
        if custom:
            count = len(custom)
            keys = list(custom.keys())[:5]
            extra = f" (+{count - 5} more)" if count > 5 else ""
            print(f"    fields: {', '.join(keys)}{extra}")
    elif class_id in (4, 224):
        # Transform: show position/rotation/scale
        pos = inner.get("m_LocalPosition", {})
        rot = inner.get("m_LocalRotation", {})
        scale = inner.get("m_LocalScale", {})
        if isinstance(pos, dict):
            print(f"    position: ({pos.get('x', 0)}, {pos.get('y', 0)}, {pos.get('z', 0)})")
        if isinstance(rot, dict):
            print(f"    rotation: ({rot.get('x', 0)}, {rot.get('y', 0)}, {rot.get('z', 0)}, {rot.get('w', 1)})")
        if isinstance(scale, dict):
            print(f"    scale: ({scale.get('x', 1)}, {scale.get('y', 1)}, {scale.get('z', 1)})")
        children = inner.get("m_Children", [])
        print(f"    children: {len(children)}")
    elif class_id == 1:
        # GameObject
        name = inner.get("m_Name", "")
        layer = inner.get("m_Layer", 0)
        tag = inner.get("m_TagString", "Untagged")
        active = inner.get("m_IsActive", 1)
        print(f"    name: {name}, layer: {layer}, tag: {tag}, active: {active}")
    else:
        # Generic: show m_Enabled and a few key fields
        enabled = inner.get("m_Enabled")
        if enabled is not None:
            print(f"    m_Enabled: {enabled}")
        skip = {
            "m_ObjectHideFlags", "m_CorrespondingSourceObject",
            "m_PrefabInstance", "m_PrefabAsset", "m_GameObject",
            "m_Enabled", "m_EditorHideFlags",
        }
        fields = {k: v for k, v in inner.items() if k not in skip}
        keys = list(fields.keys())[:5]
        if keys:
            extra = f" (+{len(fields) - 5} more)" if len(fields) > 5 else ""
            print(f"    fields: {', '.join(keys)}{extra}")


# ---------------------------------------------------------------------------
# Subcommand: search
# ---------------------------------------------------------------------------

def cmd_search(args):
    objects = parse_prefab(args.prefab_path)
    by_id, game_objects, transforms = build_index(objects)
    roots, children_map, go_transform, go_components = build_tree(
        game_objects, transforms, by_id
    )

    keyword = args.keyword.lower()
    results = []

    for fid, go_data in game_objects.items():
        name = go_data.get("m_Name", "")
        if keyword in name.lower():
            results.append((fid, name))

    if not results:
        print(f"No GameObjects matching '{args.keyword}'.")
        return

    print(f"Found {len(results)} GameObject(s) matching '{args.keyword}':")
    print()
    for fid, name in results:
        # Build path from root
        path = _build_path(fid, game_objects, transforms, go_transform)
        comps = go_components.get(fid, [])
        visible = [
            _class_name(cid)
            for cid, _ in comps
            if cid not in (1, 4, 224)
        ]
        comp_str = f"  [{', '.join(visible)}]" if visible else ""
        print(f"  &{fid}  {path}{comp_str}")


def _build_path(go_fid, game_objects, transforms, go_transform):
    """Build the hierarchy path string for a GameObject (e.g. Root/Child/Grandchild)."""
    parts = []
    current = go_fid
    visited = set()
    while current and current not in visited:
        visited.add(current)
        name = _go_name(game_objects, current)
        parts.append(name)
        # Find parent via Transform
        t_data = go_transform.get(current)
        if not t_data:
            break
        father_ref = t_data.get("m_Father", {})
        father_t_fid = _ref_id(father_ref)
        if not father_t_fid:
            break
        # Find which GO owns that parent transform
        parent_go = None
        for tfid, td in transforms.items():
            if tfid == father_t_fid:
                parent_go = _ref_id(td.get("m_GameObject", {}))
                break
        current = parent_go
    parts.reverse()
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Subcommand: summary
# ---------------------------------------------------------------------------

def cmd_summary(args):
    objects = parse_prefab(args.prefab_path)
    by_id, game_objects, transforms = build_index(objects)
    roots, children_map, go_transform, go_components = build_tree(
        game_objects, transforms, by_id
    )

    print(f"Prefab: {args.prefab_path}")
    print(f"Total objects: {len(objects)}")
    print(f"GameObjects: {len(game_objects)}")
    print(f"Root nodes: {len(roots)}")
    print()

    # Component type distribution
    class_counter = Counter()
    for class_id, file_id, data in objects:
        class_counter[_class_name(class_id)] += 1

    print("Object type distribution:")
    for name, count in class_counter.most_common():
        print(f"  {name}: {count}")
    print()

    # Prefab variant info
    prefab_instances = [
        (fid, data) for cid, fid, data in objects if cid == 1001
    ]
    if prefab_instances:
        print(f"PrefabInstance references: {len(prefab_instances)}")
        for fid, data in prefab_instances:
            pi = data.get("PrefabInstance", data)
            source = pi.get("m_SourcePrefab", {})
            guid = source.get("guid", "?") if isinstance(source, dict) else "?"
            mods = pi.get("m_Modification", {})
            mod_count = len(mods.get("m_Modifications", [])) if isinstance(mods, dict) else 0
            print(f"  &{fid}  source: {guid}  modifications: {mod_count}")
        print()

    # MonoBehaviour scripts
    mono_scripts = []
    for class_id, file_id, data in objects:
        if class_id == 114:
            inner = data.get("MonoBehaviour", data)
            if isinstance(inner, dict):
                script = inner.get("m_Script", {})
                guid = script.get("guid", "") if isinstance(script, dict) else ""
                mono_scripts.append((file_id, guid))

    if mono_scripts:
        guid_counter = Counter(guid for _, guid in mono_scripts if guid)
        print(f"MonoBehaviours: {len(mono_scripts)}")
        print("Script GUIDs:")
        for guid, count in guid_counter.most_common(10):
            print(f"  {guid}: {count}")
        if len(guid_counter) > 10:
            print(f"  ... and {len(guid_counter) - 10} more unique scripts")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="prefab_reader",
        description="Read and browse Unity 2022 prefab files.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # tree
    p_tree = subparsers.add_parser("tree", help="Show GameObject hierarchy tree")
    p_tree.add_argument("prefab_path", help="Path to the .prefab file")
    p_tree.add_argument("--depth", type=int, default=None, help="Max tree depth")
    p_tree.set_defaults(func=cmd_tree)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect a specific object by fileID")
    p_inspect.add_argument("prefab_path", help="Path to the .prefab file")
    p_inspect.add_argument("file_id", help="The fileID of the object to inspect")
    p_inspect.set_defaults(func=cmd_inspect)

    # components
    p_comps = subparsers.add_parser("components", help="List components on a GameObject")
    p_comps.add_argument("prefab_path", help="Path to the .prefab file")
    p_comps.add_argument("gameobject_id", help="The fileID of the GameObject")
    p_comps.set_defaults(func=cmd_components)

    # search
    p_search = subparsers.add_parser("search", help="Search GameObjects by name")
    p_search.add_argument("prefab_path", help="Path to the .prefab file")
    p_search.add_argument("keyword", help="Keyword to search for (case-insensitive)")
    p_search.set_defaults(func=cmd_search)

    # summary
    p_summary = subparsers.add_parser("summary", help="Show prefab statistics summary")
    p_summary.add_argument("prefab_path", help="Path to the .prefab file")
    p_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
