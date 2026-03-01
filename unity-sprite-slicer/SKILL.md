---
name: unity-sprite-slicer
description: Slice Unity 2022 sprite textures into grids by modifying .meta files. Supports Grid by Cell Count mode — specify rows and columns to automatically set spriteMode to Multiple and generate grid sprite entries.
---

# Unity Sprite Slicer

This skill modifies Unity 2022 texture `.meta` files to slice sprites into grids, equivalent to using the Sprite Editor's "Grid by Cell Count" mode in the Unity Editor.

## Usage

All commands are run via `python3 scripts/sprite_slicer.py` from the `unity-sprite-slicer/` directory.

### `slice` - Slice a sprite into a grid

```bash
python3 scripts/sprite_slicer.py slice <image_path> <rows> <cols>
```

Sets `spriteMode` to Multiple (2), `textureType` to Sprite (8), and generates `rows x cols` sprite entries in the `.meta` file.

Examples:
```bash
# Slice a 256x256 spritesheet into 4x4 grid (16 sprites of 64x64)
python3 scripts/sprite_slicer.py slice Assets/Textures/character.png 4 4

# Slice into 2 rows x 8 columns
python3 scripts/sprite_slicer.py slice Assets/Textures/tileset.png 2 8
```

### `inspect` - View current sprite settings

```bash
python3 scripts/sprite_slicer.py inspect <image_path>
```

Shows the current `spriteMode`, `textureType`, sprite count, and lists all sprite entries with their names and rects.

Example:
```bash
python3 scripts/sprite_slicer.py inspect Assets/Textures/character.png
```

Output:
```
File: Assets/Textures/character.png.meta
spriteMode: 2 (Multiple)
textureType: 8 (Sprite)
Sprites: 16

  character_0: x=0, y=192, w=64, h=64
  character_1: x=64, y=192, w=64, h=64
  ...
```

## Recommended Workflow

1. Run `inspect` to check current sprite settings
2. Run `slice` with desired rows and columns
3. Run `inspect` again to verify the result
4. In Unity, the texture will auto-reimport with the new sprite layout

## Sprite Naming and Layout

- Sprites are named `{imageName}_{index}` where index starts at 0
- Index order: left-to-right, top-to-bottom (row-major)
- Coordinate system: Unity uses bottom-left origin
  - Row 0 (top) has the highest Y value
  - Row N-1 (bottom) has Y = 0

## Design Notes

- **Zero dependencies**: No PyYAML or Pillow required. PNG dimensions are read via `struct` (IHDR chunk). Meta files are manipulated with text-level operations.
- **Format preservation**: Only the modified fields (`spriteMode`, `textureType`, `sprites`) are changed. All other content in the `.meta` file is preserved exactly as-is.
- **Unity 2022 compatible**: Generated sprite entries include all fields expected by Unity 2022 (rect, alignment, pivot, border, outline, physicsShape, tessellationDetail, bones, spriteID, internalID, vertices, indices, edges, weights).

## Requirements

- Python 3.7+
- No external dependencies
