---
name: import-asset
description: One-shot importer that ingests a raw asset (image, sprite sheet, audio) from outside the Unity project and runs an ordered, idempotent pipeline to copy it into the right place, generate engine assets (.anim/.asset/.meta), register it with project registries (ResourcesDB, SoundConfig, loot tables), and update catalog docs. Pipelines are declared per asset type via JSON config under `pipelines/<type>.json` and routed by `--as <type>`. Trigger this when the user wants to "import a new leg sprite", "add a sound effect", "register a new enemy spritesheet", "drop in a new icon", or any phrasing that implies "take this raw file and wire it into the game project end-to-end".
---

# import-asset

Single-entry asset import for Unity projects. The user gives a source file plus
`--as <type>`; the dispatcher loads `pipelines/<type>.json` and executes each
step in order. Steps are idempotent — re-running the same command after fixing
something (e.g. an .meta that finally appeared) skips work that's already done.

## Usage

```bash
python3 <skill-path>/scripts/import_asset.py <source> --as <type> --unity-project <path> [type-specific args] [--dry-run] [--force]
```

Common arguments (handled by dispatcher):

| Flag | Description |
|------|-------------|
| `<source>` | Path to the raw asset (image, audio, etc.) being imported. |
| `--as <type>` | Pipeline name; must match a file under `pipelines/<type>.json`. |
| `--unity-project <path>` | Unity project root. Defaults to `$UNITY_PROJECT` or the cwd. |
| `--dry-run` | Print every planned step without writing anything. |
| `--force` | Overwrite/rewrite even when the target looks up-to-date. |

Per-pipeline arguments (e.g. `--name`, `--rows`, `--rarity`) are declared in
the pipeline JSON's `arguments` array and added to the parser dynamically.

## Asset types

Each `--as <type>` corresponds to a pipeline JSON. Concrete pipelines are
shipped in their own tickets:

| Type | What it does | Status |
|------|--------------|--------|
| `leg-icon` | Resize → copy → ResourcesDB `item/{id}` → ItemData spriteKey | implemented |
| `leg-walk` | Resize → slice → Walk/Idle anim → ResourcesDB `anim/{id}_*` → LegData/ItemData/loot | implemented |
| `leg-track` | Resize 128² → 1-frame Walk/Idle anim → ResourcesDB → LegData(track)/ItemData/loot | implemented |
| `enemy-sprite` | Copy → slice → SpriteAnimationData → ResourcesDB `anim/{id}` → optional CharacterAnimConfig | implemented |
| `sound-effect` | Copy to `Assets/Audio/SFX/` → await .meta → register in `SoundConfig.asset` | implemented |

Add a new type by dropping a new file under `pipelines/`. No code changes are
required for the common case.

## Pipeline config schema

```json
{
  "name": "leg-icon",
  "description": "Import a 64x64 inventory icon for a leg item",
  "arguments": [
    { "name": "name",   "required": true,  "help": "PascalCase asset filename (e.g. HeavyTrack)" },
    { "name": "item",   "required": true,  "help": "ItemData id (e.g. legs_heavytrack)" },
    { "name": "size",   "type": "int", "default": 64, "help": "Icon size in px" }
  ],
  "steps": [
    { "type": "resize", "source": "{source}", "dest": "{unity_project}/Assets/.../{name}Icon.png",
      "width": "{size}", "height": "{size}" },
    { "type": "await-meta", "path": "{unity_project}/Assets/.../{name}Icon.png" },
    { "type": "text-insert", "path": "{unity_project}/Assets/.../ResourcesDB.asset",
      "anchor": "...", "insert": "...", "marker": "item/{item}:" }
  ]
}
```

Templates use `{var}` for substitution from the argument context. Built-in
variables:

- `{source}` — absolute path to the source file
- `{unity_project}` — absolute path to `--unity-project`
- All declared `arguments` are exposed as `{name}`
- `{Name}` and `{NAME}` — auto-derived PascalCase / UPPERCASE of `{name}` when
  a `name` argument is declared

## Step types

All steps are idempotent: a re-run skips work whose output already exists in
the expected state. `--force` bypasses the check.

### `resize`

```json
{ "type": "resize", "source": "{source}", "dest": "<path>", "width": 64, "height": 64 }
```

Delegates to `image-processor/scripts/resize.py`. Preserves aspect ratio when
only one dimension is given. Skips if `<dest>` already exists at the target
dimensions.

### `copy`

```json
{ "type": "copy", "source": "{source}", "dest": "<path>" }
```

Plain file copy with `mkdir -p` on the destination directory. Skips if the
destination's MD5 matches the source.

### `run-script`

```json
{ "type": "run-script", "script": "unity-sprite-slicer/scripts/sprite_slicer.py",
  "args": ["slice", "<path>", "{rows}", "{cols}"] }
```

Invokes another script from the unity-skills repo. `script` is resolved
relative to the parent directory of this skill (i.e. the unity-skills repo
root). Use this to call into `unity-sprite-slicer`, `unity-animation-editor`,
etc. Idempotency is the called script's responsibility (most are idempotent —
slicing the same grid twice is a no-op).

### `await-meta`

```json
{ "type": "await-meta", "path": "<path-to-asset>" }
```

Asserts that `<path>.meta` exists. If it doesn't, the step fails with a
clear instruction to open Unity (which generates `.meta` files on import) and
then re-run the same command. Earlier steps are skipped via idempotency, so
the pipeline simply resumes at this point.

### `read-meta`

```json
{ "type": "read-meta", "path": "<asset>", "guid_var": "guid" }
```

Reads `<asset>.meta` and binds the `guid:` value as a template variable
(default name `{guid}`). Use this between `await-meta` and any step that
needs the GUID — typically a `text-insert` that registers the asset in a
project registry like ResourcesDB. Sets a stable placeholder GUID under
`--dry-run` so downstream rendering works.

### `write-json`

```json
{ "type": "write-json", "path": "<path>.json", "merge": true,
  "content": { "id": "{name}", "type": "track" } }
```

Writes a JSON file. With `merge: true` and an existing file, top-level keys
are shallow-merged. Without `merge`, an existing identical file is left alone;
otherwise it's overwritten (use `--force` if you want to overwrite when the
content differs from your spec — by default differing content is overwritten,
identical content is skipped).

### `text-insert`

```json
{ "type": "text-insert", "path": "<file>",
  "anchor": "^# Begin Items\\b.*$",
  "insert": "  - { id: legs_heavytrack, sprite: ... }\n",
  "marker": "id: legs_heavytrack" }
```

Idempotent insertion. If `marker` is found anywhere in the file, the step is
a no-op. Otherwise, `insert` is placed immediately after the regex match for
`anchor`. `anchor` is matched in MULTILINE mode against the file text. Use
this for ResourcesDB / SoundConfig / loot-table registrations.

### `md-append`

```json
{ "type": "md-append", "path": "<doc>.md", "marker": "## HeavyTrack",
  "content": "## HeavyTrack\n\nUncommon track-type leg.\n" }
```

Appends a section to a markdown doc if the marker isn't already present.

## Idempotency model

Pipelines are designed to be re-run safely. A typical recovery flow:

1. Run the import. Some early step (e.g. `resize`, `copy`) succeeds; a later
   step (`await-meta`) fails because Unity hasn't yet imported the file.
2. Open Unity. It generates the missing `.meta`.
3. Re-run the exact same command. Steps 1..N skip themselves; the pipeline
   continues from where it left off.

`--force` overrides the skip-if-already-done logic for the entire run.

## Adding a new asset type

1. Drop `pipelines/<type>.json` with `name`, `description`, `arguments`, `steps`.
2. Test it: `python3 scripts/import_asset.py <source> --as <type> --dry-run ...`.
3. Run for real once dry-run looks correct.
4. Document the type in the table above and in any project-side catalogs.

No changes to `scripts/import_asset.py` are needed for pipelines that compose
existing step types. Adding a new step type means editing the `STEPS` table
in the dispatcher.

## Requirements

- Python 3.7+
- Pillow for the `resize` step (`pip install Pillow`)
- The other unity-skills scripts (`unity-sprite-slicer`, `unity-animation-editor`,
  `image-processor`) must live alongside this skill — `run-script` resolves
  paths relative to the unity-skills repo root.
