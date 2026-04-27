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
| [`unity-animation-editor`](unity-animation-editor/SKILL.md) | Create and modify `.anim` and `.controller` files — sprite flipbook clips and AnimatorControllers. |
| [`unity-prefab-reader`](unity-prefab-reader/SKILL.md) | Browse, query, and modify Unity prefab YAML — tree view, component inspection, property edits, transform/active/child operations. |
| [`import-asset`](import-asset/SKILL.md) | One-shot importer with config-driven, idempotent pipelines. Ships pipelines for `leg-icon`, `leg-walk`, `leg-track`, `enemy-sprite`, and `sound-effect`. |

## Installation

Symlink the whole repo or individual skills into your Claude skills directory:

```bash
# All skills
ln -s "$(pwd)" ~/.claude/skills/unity-skills

# Or one at a time
ln -s "$(pwd)/import-asset" ~/.claude/skills/import-asset
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

Scripts are zero-dependency where possible. The image-processor needs
Pillow (and NumPy for color removal); everything else parses Unity's YAML
with text + regex so there are no PyYAML or `unityparser` requirements.

## Composition

The skills are designed to compose — `import-asset` pipelines call
`unity-sprite-slicer` and `image-processor` scripts via its `run-script`
step, and ship a `write_sprite_anim_data.py` helper for the project's
custom `SpriteAnimationData` ScriptableObject. To add a new asset import
flow, drop a JSON file in `import-asset/pipelines/` — no dispatcher
changes needed unless you need a new step type.

## License

MIT — see [LICENSE](LICENSE).
