---
name: unity-prefab-reader
description: Read, browse, and query Unity 2022 prefab files with incremental tree exploration. Parses Unity's YAML-serialized prefab format and provides tree view, object inspection, component listing, search, and summary statistics.
---

# Unity Prefab Reader

This skill provides tools to read and browse Unity 2022 `.prefab` files without loading the entire content at once. It supports incremental tree exploration, making it practical for large prefabs (hundreds of KB).

## Usage

All commands are run via `python3 scripts/prefab_reader.py` from the `unity-prefab-reader/` directory.

### Commands

#### `summary` - Get an overview first

```bash
python3 scripts/prefab_reader.py summary <prefab_path>
```

Shows total object count, GameObject count, component type distribution, PrefabInstance references, and MonoBehaviour script GUIDs. **Start here** to understand the prefab's scope.

#### `tree` - Browse the hierarchy

```bash
python3 scripts/prefab_reader.py tree <prefab_path>
python3 scripts/prefab_reader.py tree <prefab_path> --depth 2
```

Displays the GameObject tree with component annotations. Use `--depth N` to limit how deep the tree expands — this is the key mechanism for incremental browsing of large prefabs.

Output format:
```
└─ RootObject &100000  [Camera, AudioListener]
   ├─ Child1 &100002  [MeshFilter, MeshRenderer]
   └─ Child2 &100004  [MonoBehaviour]
      └─ Grandchild &100006  [Light]
```

Each node shows: `name &fileID [components]`

#### `inspect` - View object details

```bash
python3 scripts/prefab_reader.py inspect <prefab_path> <fileID>
```

Shows all serialized properties of a specific object identified by its `fileID` (the `&number` shown in tree output). Works for any object type — GameObjects, Transforms, MonoBehaviours, etc.

#### `components` - List components on a GameObject

```bash
python3 scripts/prefab_reader.py components <prefab_path> <gameobject_fileID>
```

Lists all components attached to a specific GameObject with a compact summary of each. For MonoBehaviours, shows the script GUID and custom serialized field names.

#### `search` - Find GameObjects by name

```bash
python3 scripts/prefab_reader.py search <prefab_path> <keyword>
```

Case-insensitive search across all GameObject names. Results include the full hierarchy path and component list.

## Recommended Workflow

1. Run `summary` to understand the prefab's structure and size
2. Run `tree --depth 1` to see top-level objects
3. Identify interesting branches and expand with `tree --depth N` or drill into specific objects
4. Use `inspect <fileID>` to see full details of specific objects
5. Use `components <gameobject_fileID>` to understand what's attached to a GameObject
6. Use `search` to find specific objects by name

## Prefab Variant Support

The tool recognizes Prefab Variants (files containing `PrefabInstance` objects). For variants:
- `summary` shows source prefab GUIDs and modification counts
- `tree` displays PrefabInstance info and any overridden GameObjects

## Requirements

- Python 3.7+
- PyYAML (`pip install pyyaml`)

## Reference

See `references/REFERENCE.md` for Unity YAML format details and ClassID mapping table.
