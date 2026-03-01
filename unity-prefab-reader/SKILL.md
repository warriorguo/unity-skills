---
name: unity-prefab-reader
description: Read, browse, query, and modify Unity 2022 prefab files. Parses Unity's YAML-serialized prefab format and provides tree view, object inspection, component listing, search, summary statistics, and write operations (modify properties, rename, set-active, set-transform, add-child, remove).
---

# Unity Prefab Reader

This skill provides tools to read, browse, and modify Unity 2022 `.prefab` files without loading the entire content at once. It supports incremental tree exploration and text-level write operations that preserve the original file format.

## Usage

All commands are run via `python3 scripts/prefab_reader.py` from the `unity-prefab-reader/` directory.

### Read Commands

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

### Write Commands

#### `modify` - Modify any scalar property

```bash
python3 scripts/prefab_reader.py modify <prefab_path> <fileID> <property> <value>
```

Modifies a scalar property on any object. Supports simple properties and nested flow mapping keys (dot notation).

Examples:
```bash
# Change a MonoBehaviour field
python3 scripts/prefab_reader.py modify player.prefab 11400004 damage 50

# Change a nested flow mapping value
python3 scripts/prefab_reader.py modify player.prefab 400000 m_LocalPosition.y 2.5
```

#### `rename` - Rename a GameObject

```bash
python3 scripts/prefab_reader.py rename <prefab_path> <go_fileID> <new_name>
```

Example:
```bash
python3 scripts/prefab_reader.py rename player.prefab 100002 Torso
```

#### `set-active` - Enable/disable a GameObject

```bash
python3 scripts/prefab_reader.py set-active <prefab_path> <go_fileID> <0|1>
```

Example:
```bash
# Enable a disabled GameObject
python3 scripts/prefab_reader.py set-active player.prefab 100006 1
```

#### `set-transform` - Modify Transform properties

```bash
python3 scripts/prefab_reader.py set-transform <prefab_path> <transform_fileID> [--position X Y Z] [--rotation X Y Z W] [--scale X Y Z]
```

Modifies position, rotation, and/or scale on a Transform. At least one of `--position`, `--rotation`, or `--scale` must be provided.

Example:
```bash
python3 scripts/prefab_reader.py set-transform player.prefab 400004 --position 1 2 3 --scale 2 2 2
```

#### `add-child` - Add an empty child GameObject

```bash
python3 scripts/prefab_reader.py add-child <prefab_path> <parent_go_fileID> <name>
```

Creates a new empty GameObject with a Transform as a child of the specified parent. The new object is appended to the end of the file.

Example:
```bash
python3 scripts/prefab_reader.py add-child player.prefab 100000 Shield
```

#### `remove` - Remove a GameObject and its descendants

```bash
python3 scripts/prefab_reader.py remove <prefab_path> <go_fileID>
```

Removes the specified GameObject, all its components, and all descendant GameObjects recursively. Also updates the parent Transform's `m_Children` list.

Example:
```bash
# Remove Weapon and its child MuzzleFlash
python3 scripts/prefab_reader.py remove player.prefab 100004
```

## Recommended Workflow

### Reading
1. Run `summary` to understand the prefab's structure and size
2. Run `tree --depth 1` to see top-level objects
3. Identify interesting branches and expand with `tree --depth N` or drill into specific objects
4. Use `inspect <fileID>` to see full details of specific objects
5. Use `components <gameobject_fileID>` to understand what's attached to a GameObject
6. Use `search` to find specific objects by name

### Writing
1. Use read commands to find the `fileID` of the object you want to modify
2. Use `modify` for arbitrary property changes, or specialized commands (`rename`, `set-active`, `set-transform`) for common operations
3. Use `add-child` to create new empty GameObjects in the hierarchy
4. Use `remove` to delete GameObjects (cascades to all descendants)
5. Verify changes with `inspect` or `tree` after writing

## Design Notes

- **Text-level replacement**: Write commands (`modify`, `rename`, `set-active`, `set-transform`) operate directly on the raw text, preserving the original file formatting. No YAML re-serialization occurs for these operations.
- **Structural changes**: `add-child` and `remove` use a custom serializer that produces Unity-compatible YAML output with flow mappings for references and vectors.
- **fileID stability**: Write operations never change existing fileIDs.

## Prefab Variant Support

The tool recognizes Prefab Variants (files containing `PrefabInstance` objects). For variants:
- `summary` shows source prefab GUIDs and modification counts
- `tree` displays PrefabInstance info and any overridden GameObjects

## Requirements

- Python 3.7+
- PyYAML (`pip install pyyaml`)

## Reference

See `references/REFERENCE.md` for Unity YAML format details and ClassID mapping table.
