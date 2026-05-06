---
name: unity-animation-editor
description: Create and modify SpriteAnimationData ScriptableObject .asset files for the custom SpriteAnimation system. Supports creating sprite animations from sliced sprite sheets, rewriting animation frames, and inspecting animation assets.
---

# Unity SpriteAnimation Editor

This skill creates and modifies `SpriteAnimationData` ScriptableObject `.asset` files for the project's custom `SpriteAnimation` system (defined in `Game.Unity.Effects`). It generates frame-by-frame sprite animations from sliced sprite sheets (produced by `unity-sprite-slicer`).

> **Note**: This project uses a custom `SpriteAnimation` + `SpriteAnimationData` system instead of Unity's built-in Animator/AnimationClip. Do NOT generate `.anim` or `.controller` files.

## Usage

All commands are run via `python3 scripts/animation_editor.py` from the `unity-animation-editor/` directory.

### `create` - Create a new SpriteAnimationData asset

```bash
python3 scripts/animation_editor.py create <asset_path> <image_path> [indices...] [--name N] [--fps N] [--loop]
```

Creates a new `.asset` file (SpriteAnimationData ScriptableObject) referencing sprites from a sliced image. The image must already be sliced (spriteMode: 2) with a `.meta` file containing sprite entries.

- `indices`: Optional sprite indices to include (0-based). If omitted, all sprites are used.
- `--name`: Asset name (default: filename without extension)
- `--fps`: Frames per second (default: 24)
- `--loop`: Enable looping

Examples:
```bash
# Create a 16-frame shield animation at 12fps with looping
python3 scripts/animation_editor.py create Assets/Prefabs/Weapons/Shield/ShieldRedAnimData.asset Assets/Images/Weapons/Shield/Shield01_Red.png --fps 12 --loop

# Create animation using specific frames
python3 scripts/animation_editor.py create Assets/Resources/anim/enemy_death.asset Assets/Images/Enemy/Explosion.png 0 1 2 3 --fps 8

# Create animation using all sprites at default 24fps
python3 scripts/animation_editor.py create Assets/Resources/anim/idle.asset Assets/Images/Character/idle_sheet.png --loop
```

### `rewrite` - Rewrite animation frames

```bash
python3 scripts/animation_editor.py rewrite <asset_path> <image_path> [indices...] [--fps N] [--loop/--no-loop]
```

Replaces the sprite frames in an existing `.asset` file while preserving the asset name. Optionally update fps and loop settings.

Example:
```bash
# Replace frames with sprites 0-7 at 6fps
python3 scripts/animation_editor.py rewrite Assets/Resources/anim/walk.asset Assets/Images/Character/walk_sheet.png 0 1 2 3 4 5 6 7 --fps 6
```

### `inspect` - View animation info

```bash
python3 scripts/animation_editor.py inspect <asset_path>
```

Shows animation name, FPS, loop setting, duration, and lists all sprite frame references.

### `list-sprites` - List sprites in a sliced image

```bash
python3 scripts/animation_editor.py list-sprites <image_path>
```

Lists all sprite entries from a sliced image's `.meta` file with their indices and internalIDs. Useful for selecting specific frames when creating animations.

## Recommended Workflow

1. Slice a sprite sheet with `unity-sprite-slicer`
2. Preview available frames with `list-sprites`
3. Create a SpriteAnimationData asset with `create`
4. Register in ResourcesDB if loaded via asset service (key format: `anim/name`)
5. Verify with `inspect`

## How SpriteAnimationData Works

`SpriteAnimationData` is a ScriptableObject with these fields:
- `frames: Sprite[]` — Array of sprite frame references (GUID + fileID)
- `fps: float` — Playback frame rate (default 24)
- `loop: bool` — Whether animation repeats
- `hideOnComplete: bool` — Whether to `SetActive(false)` on non-loop completion
- `frameEvents: FrameEvent[]` — Tagged frame events (fires `OnFrameEvent` callback when crossed)
- `alphaCurve: AnimationCurve` — Optional. Sampled over normalized playback time `[0, 1]` and written into `SpriteRenderer.color.a` each frame. An empty curve (no keys) leaves alpha untouched. Suppressed during `Dissolve()` (which owns alpha).

It is consumed by the `SpriteAnimation` MonoBehaviour at runtime via `SetData()`, or configured inline on prefabs. Used for character animations, shield effects, door animations, and visual FX.

> **Note on `alphaCurve`**: This script's `create`/`rewrite` commands do not currently emit an alpha curve. To configure one, set the field via the Unity Inspector (the curve editor). Existing `.asset` files written without this field deserialize with an empty curve (disabled), so they are unaffected.

## Design Notes

- **Zero dependencies**: No PyYAML required. All YAML operations use text templates and regex.
- **Sprite input**: Reads the sliced image's `.meta` file for GUID and sprite internalID list.
- **Script GUID**: References `SpriteAnimationData.cs` via its fixed GUID (`e255f71bed24451b8118c587b72fadd5`).
- **Meta generation**: Automatically creates `.meta` files for new `.asset` files.
- **Format compatibility**: Generated files match Unity 2022's serialization format.

## Requirements

- Python 3.7+
- No external dependencies
- Input images must be pre-sliced (spriteMode: 2) with sprite entries in the `.meta` file
