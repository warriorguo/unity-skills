---
name: image-processor
description: Process and manipulate images using Python PIL/Pillow. Use this skill whenever the user wants to resize images, get image info/metadata, check image dimensions/size/format/EXIF, scale images up or down, batch resize, convert between formats (PNG, JPG, WEBP, BMP, TIFF, GIF), remove a specific color from an image (make it transparent), or add/merge a background image behind a foreground. Supports Unity sprite sheets — auto-detects .meta and composites per-tile. Trigger this even for casual requests like "make this image smaller", "what size is this image", "show me the EXIF data", "remove the background color", or "add a background to this sprite".
---

# Image Processor

A skill for image processing tasks using Python PIL/Pillow. Supports image info retrieval and resizing.

## When to use

Whenever a user wants to inspect or manipulate image files — get image info/metadata, resize, scale, change dimensions, or convert formats. The bundled scripts handle the heavy lifting so you don't need to write PIL code from scratch each time.

## Image Info

Use `scripts/info.py` to retrieve detailed information about an image file.

### Usage

```bash
python <skill-path>/scripts/info.py <image> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON (useful for programmatic processing) |
| `--no-exif` | Skip EXIF metadata extraction |

### What it reports

- **Basic**: filename, path, format, dimensions (px), megapixels
- **Color**: mode (RGB/RGBA/L/CMYK/...), channel count, bit depth
- **File**: size in bytes and human-readable form
- **DPI**: resolution if available
- **Animation**: frame count for animated GIF/WEBP/APNG
- **Transparency**: whether the image has an alpha channel
- **ICC Profile**: whether a color profile is embedded
- **EXIF**: camera make/model, date, exposure, ISO, focal length, GPS, etc.

### Examples

Human-readable output:
```bash
python <skill-path>/scripts/info.py photo.jpg
```

JSON output (for scripting):
```bash
python <skill-path>/scripts/info.py photo.jpg --json
```

## Resize Images

Use the bundled `scripts/resize.py` script. It supports several ways to specify the target size:

### Usage

```bash
python <skill-path>/scripts/resize.py <input> <output> [options]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--width W` | Set target width (preserves aspect ratio) | `--width 800` |
| `--height H` | Set target height (preserves aspect ratio) | `--height 600` |
| `--width W --height H` | Set both (stretches to exact size unless `--keep-ratio`) | `--width 800 --height 600` |
| `--scale S` | Scale by factor (e.g., 0.5 = half, 2.0 = double) | `--scale 0.5` |
| `--keep-ratio` | When both width and height are given, fit within the box without distortion | `--keep-ratio` |
| `--resample METHOD` | Resampling filter: `lanczos` (default, best quality), `bilinear`, `bicubic`, `nearest` | `--resample bilinear` |
| `--quality Q` | JPEG/WEBP quality 1-100 (default: 95) | `--quality 85` |

### Behavior

- **Aspect ratio is preserved by default** when only width or height is specified. This prevents distortion, which is almost always what the user wants.
- When both width and height are given, the image stretches to fit exactly. Add `--keep-ratio` to fit within the bounding box instead.
- The output format is inferred from the file extension. To convert formats, just use a different extension (e.g., input.png → output.webp).
- The script prints the original and new dimensions to stdout for confirmation.

### Examples

Resize to 800px wide, keeping proportions:
```bash
python <skill-path>/scripts/resize.py photo.jpg resized.jpg --width 800
```

Scale down to 50%:
```bash
python <skill-path>/scripts/resize.py banner.png banner_small.png --scale 0.5
```

Fit within 1920x1080 box without distortion:
```bash
python <skill-path>/scripts/resize.py wallpaper.png fitted.png --width 1920 --height 1080 --keep-ratio
```

Convert PNG to WEBP at lower quality:
```bash
python <skill-path>/scripts/resize.py image.png image.webp --width 640 --quality 80
```

### Batch processing

For multiple files, loop over them in bash:
```bash
for f in *.jpg; do
  python <skill-path>/scripts/resize.py "$f" "resized/$f" --width 800
done
```

Make sure the output directory exists first (`mkdir -p resized`).

## Remove Color

Use `scripts/remove_color.py` to remove a specific color from an image, replacing matched pixels with transparency.

### Usage

```bash
python <skill-path>/scripts/remove_color.py <input> <output> [options]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--color COLOR` | **(Required)** Color to remove, as hex (`'#FF00FF'` or `'FF00FF'`) or `R,G,B` (`'255,0,255'`) | `--color '#00FF00'` |
| `--tolerance T` | Euclidean distance tolerance 0–255 (default: 0 = exact match). Pixels within this distance from the target color are removed. | `--tolerance 30` |

### Behavior

- The input is converted to RGBA internally, so any format is accepted as input.
- The output format **must support transparency** (PNG or WEBP). JPEG/BMP will be rejected.
- Color matching uses Euclidean distance in RGB space: `sqrt((R₁−R₂)² + (G₁−G₂)² + (B₁−B₂)²)`.
- With `--tolerance 0` (default), only exact color matches are removed.
- The script prints how many pixels were matched and made transparent.

### Examples

Remove exact white background:
```bash
python <skill-path>/scripts/remove_color.py icon.png icon_no_bg.png --color 'FFFFFF'
```

Remove green screen with tolerance:
```bash
python <skill-path>/scripts/remove_color.py photo.png result.png --color '00FF00' --tolerance 40
```

Remove black pixels with small tolerance, using R,G,B format:
```bash
python <skill-path>/scripts/remove_color.py sprite.png clean.png --color '0,0,0' --tolerance 10
```

## Add Background

Use `scripts/add_background.py` to composite a foreground image (with transparency) onto a background image. Automatically detects Unity sliced sprite sheets and processes each tile individually.

### Usage

```bash
python <skill-path>/scripts/add_background.py <foreground> <background> <output> [options]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--no-unity` | Skip Unity .meta detection; treat as a plain image | `--no-unity` |
| `--quality Q` | JPEG/WEBP quality 1-100 (default: 95) | `--quality 85` |

### Behavior

- The **foreground** is the image with transparency (e.g., a character sprite).
- The **background** is resized to match the foreground (or tile) dimensions before compositing.
- **Unity sprite sheet detection**: If a `.meta` file exists next to the foreground image and `spriteMode` is `2` (Multiple), the script reads all sprite rects from the meta file and composites the background onto each tile independently. This ensures each slice gets a properly fitted background rather than one stretched across the whole sheet.
- For non-Unity images (or with `--no-unity`), the entire foreground is composited onto the background as a single image.
- Supports PNG, WEBP (with transparency), and JPEG (auto-converts to RGB) output.

### Examples

Plain image — add background:
```bash
python <skill-path>/scripts/add_background.py character.png grass.png result.png
```

Unity sprite sheet — auto-detects .meta and processes per-tile:
```bash
python <skill-path>/scripts/add_background.py spritesheet.png bg_texture.png spritesheet_with_bg.png
```

Force plain mode even if .meta exists:
```bash
python <skill-path>/scripts/add_background.py spritesheet.png bg.png out.png --no-unity
```

## Important notes

- Replace `<skill-path>` with the actual path to this skill directory when running the script.
- If Pillow is not installed, run `pip install Pillow` first. The remove-color script also requires NumPy (`pip install numpy`).
- For JPEG output, RGBA images are automatically converted to RGB (JPEG doesn't support transparency).
- The script exits with a non-zero code and a clear error message if something goes wrong (missing file, invalid options, etc.), so check the output if it fails.
