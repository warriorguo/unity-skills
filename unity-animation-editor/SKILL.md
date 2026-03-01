---
name: unity-animation-editor
description: Create and modify Unity 2022 .anim (AnimationClip) and .controller (AnimatorController) files. Supports creating sprite flipbook animations from sliced sprite sheets, rewriting animation frames, and building AnimatorControllers with states.
---

# Unity Animation Editor

This skill creates and modifies Unity 2022 `.anim` (AnimationClip) and `.controller` (AnimatorController) files. It generates sprite flipbook animations from sliced sprite sheets (produced by `unity-sprite-slicer`) and builds AnimatorControllers to reference those animations.

## Usage

All commands are run via `python3 scripts/animation_editor.py` from the `unity-animation-editor/` directory.

### `create-anim` - Create a new animation clip

```bash
python3 scripts/animation_editor.py create-anim <anim_path> <image_path> [indices...] [--name N] [--sample-rate N] [--loop]
```

Creates a new `.anim` file with a PPtrCurve referencing sprites from the sliced image. The image must already be sliced (spriteMode: 2) with a `.meta` file containing sprite entries.

- `indices`: Optional sprite indices to include (0-based). If omitted, all sprites are used.
- `--name`: Animation clip name (default: filename without extension)
- `--sample-rate`: Frames per second (default: 12)
- `--loop`: Enable looping

Examples:
```bash
# Create a 4-frame walk animation at 12fps with looping
python3 scripts/animation_editor.py create-anim Assets/Animations/walk.anim Assets/Textures/character.png 0 1 2 3 --name walk --loop

# Create animation using all sprites at 8fps
python3 scripts/animation_editor.py create-anim Assets/Animations/idle.anim Assets/Textures/character.png --sample-rate 8 --loop
```

### `rewrite-anim` - Rewrite animation frames

```bash
python3 scripts/animation_editor.py rewrite-anim <anim_path> <image_path> [indices...] [--sample-rate N] [--loop]
```

Replaces the sprite frames in an existing `.anim` file while preserving the clip name and other settings.

Example:
```bash
# Replace frames with sprites 0 and 2 at 6fps
python3 scripts/animation_editor.py rewrite-anim Assets/Animations/walk.anim Assets/Textures/character.png 0 2 --sample-rate 6
```

### `create-controller` - Create a new AnimatorController

```bash
python3 scripts/animation_editor.py create-controller <controller_path> <anim_path> [--name N]
```

Creates a new `.controller` file with a Base Layer, one AnimatorStateMachine, and one AnimatorState referencing the given animation.

- `--name`: Controller name (default: filename without extension)

Example:
```bash
python3 scripts/animation_editor.py create-controller Assets/Animations/PlayerAnim.controller Assets/Animations/walk.anim --name PlayerAnim
```

### `add-to-controller` - Add animation state to existing controller

```bash
python3 scripts/animation_editor.py add-to-controller <controller_path> <anim_path> [--state-name N]
```

Appends a new AnimatorState to an existing `.controller` file's first state machine.

- `--state-name`: State name (default: anim filename without extension)

Example:
```bash
python3 scripts/animation_editor.py add-to-controller Assets/Animations/PlayerAnim.controller Assets/Animations/idle.anim --state-name Idle
```

### `inspect-anim` - View animation info

```bash
python3 scripts/animation_editor.py inspect-anim <anim_path>
```

Shows animation name, sample rate, stop time, loop setting, and lists all sprite frames.

### `inspect-controller` - View controller info

```bash
python3 scripts/animation_editor.py inspect-controller <controller_path>
```

Shows controller name, layers, state machines, and all animation states.

## Recommended Workflow

1. Slice a sprite sheet with `unity-sprite-slicer`
2. Create animation clips with `create-anim` for each animation (walk, idle, attack, etc.)
3. Create an AnimatorController with `create-controller` using the first animation
4. Add remaining animations with `add-to-controller`
5. Verify with `inspect-anim` and `inspect-controller`

## Design Notes

- **Zero dependencies**: No PyYAML required. All YAML operations use text templates and regex.
- **Sprite input**: Reads the sliced image's `.meta` file for GUID and sprite internalID list.
- **Time calculation**: `keyframe_time = frame_index / sample_rate` (matches Unity's SpriteUtility.cs).
- **fileID conventions**: AnimationClip uses fixed fileID 7400000; AnimatorController uses 9100000; StateMachine and State use randomly generated IDs.
- **Format compatibility**: Generated files match Unity 2022's serialization format.

## Requirements

- Python 3.7+
- No external dependencies
- Input images must be pre-sliced (spriteMode: 2) with sprite entries in the `.meta` file
