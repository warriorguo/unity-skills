# unity-skills

Claude Code skills for Unity 2022 game development. Each subdirectory is a
self-contained skill that Claude can invoke to manipulate Unity assets without
opening the editor — slicing sprites, generating animation clips, reading and
editing prefab YAML, and end-to-end importing of new assets.

## Skills

| Skill | What it does |
|-------|--------------|
| [`image-processor`](image-processor/SKILL.md) | Resize, info, EXIF, color removal, opacity, rotate/flip, and Unity-aware per-tile background compositing using PIL/Pillow. |
| [`unity-sprite-slicer`](unity-sprite-slicer/SKILL.md) | Slice a sprite texture into a `rows × cols` grid by editing the `.meta` file (Grid by Cell Count). |
| [`unity-animation-editor`](unity-animation-editor/SKILL.md) | Create and modify `SpriteAnimationData` ScriptableObject `.asset` files for the project's custom `SpriteAnimation` system. |
| [`unity-prefab-tool`](unity-prefab-tool/SKILL.md) | Browse, query, and modify Unity prefab YAML — tree view, component inspection, property edits, transform/active/child operations, and Unity-legal GUID/fileID generation. |
| [`import-asset`](import-asset/SKILL.md) | One-shot importer with config-driven, idempotent pipelines. Ships pipelines for `leg-icon`, `leg-walk`, `leg-track`, `enemy-sprite`, `sound-effect`, and `effect-sprite`. |

## Installation

Claude Code discovers skills as direct entries under `~/.claude/skills/`, so symlink each skill individually rather than the whole repo. From a clone of this repo:

```bash
REPO="$(pwd)"
for s in image-processor unity-sprite-slicer unity-animation-editor unity-prefab-tool import-asset; do
  ln -s "$REPO/$s" "$HOME/.claude/skills/$s"
done
```

If a skill of the same name already exists as a real directory, move it aside before symlinking so you do not lose local edits:

```bash
mkdir -p ~/.claude/skills_backup
mv ~/.claude/skills/image-processor ~/.claude/skills_backup/image-processor.$(date +%Y%m%d) 2>/dev/null || true
ln -s "$REPO/image-processor" ~/.claude/skills/image-processor
```

After symlinking, Claude Code picks up the skills on the next session.

## Layout conventions

Each skill follows the same shape:

```
<skill-name>/
  SKILL.md          frontmatter + usage docs (the file Claude reads)
  scripts/          Python entry points
  tests/            optional fixtures and unit tests
  references/       optional reference docs
```

Scripts are minimal-dependency where possible. `image-processor` needs
Pillow (and NumPy for color removal and mirror-copy). `unity-sprite-slicer`
needs Pillow only for `--skip-empty` cell detection (pass `--no-skip-empty`
to avoid it). `unity-prefab-tool` needs PyYAML. `unity-animation-editor`
and `import-asset` parse Unity YAML with text + regex and have no external
requirements.

## Composition

The skills are designed to compose — `import-asset` pipelines call
`unity-sprite-slicer` and `image-processor` scripts via its `run-script`
step, and ship a `write_sprite_anim_data.py` helper for the project's
custom `SpriteAnimationData` ScriptableObject. To add a new asset import
flow, drop a JSON file in `import-asset/pipelines/` — no dispatcher
changes needed unless you need a new step type.

## License

MIT — see [LICENSE](LICENSE).
