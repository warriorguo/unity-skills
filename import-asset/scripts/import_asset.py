#!/usr/bin/env python3
"""import-asset dispatcher.

Loads pipelines/<type>.json and executes its ordered steps idempotently.
See ../SKILL.md for the schema and step reference.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SKILL_DIR.parent
PIPELINES_DIR = SKILL_DIR / "pipelines"


class PipelineError(Exception):
    pass


# ---------- pipeline loading & templating ----------

def load_pipeline(name: str) -> dict:
    p = PIPELINES_DIR / f"{name}.json"
    if not p.exists():
        available = sorted(x.stem for x in PIPELINES_DIR.glob("*.json"))
        raise PipelineError(
            f"unknown --as type: {name!r}. Available: {', '.join(available) or '(none)'}"
        )
    return json.loads(p.read_text())


_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render(template, ctx: dict):
    if not isinstance(template, str):
        return template

    def repl(m):
        key = m.group(1)
        if key not in ctx or ctx[key] is None:
            raise PipelineError(f"template references unknown/empty var: {{{key}}}")
        return str(ctx[key])

    return _VAR_RE.sub(repl, template)


def render_obj(obj, ctx: dict):
    if isinstance(obj, str):
        return render(obj, ctx)
    if isinstance(obj, list):
        return [render_obj(x, ctx) for x in obj]
    if isinstance(obj, dict):
        return {k: render_obj(v, ctx) for k, v in obj.items()}
    return obj


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- step implementations ----------

def step_resize(args: dict, ctx: dict, dry_run: bool):
    src = Path(render(args["source"], ctx))
    dst = Path(render(args["dest"], ctx))
    width = args.get("width")
    height = args.get("height")
    if isinstance(width, str):
        width = int(render(width, ctx))
    if isinstance(height, str):
        height = int(render(height, ctx))
    print(f"[resize] {src} -> {dst} (w={width} h={height})")
    if dry_run:
        return
    if not src.exists():
        raise PipelineError(f"source not found: {src}")
    if dst.exists() and not ctx["_force"]:
        try:
            from PIL import Image
            with Image.open(dst) as im:
                w_ok = width is None or im.width == width
                h_ok = height is None or im.height == height
                if w_ok and h_ok:
                    print(f"  skip: already {im.width}x{im.height}")
                    return
        except ImportError:
            pass  # fall through and re-run

    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(REPO_DIR / "image-processor" / "scripts" / "resize.py"),
        str(src), str(dst),
    ]
    if width is not None:
        cmd += ["--width", str(width)]
    if height is not None:
        cmd += ["--height", str(height)]
    subprocess.run(cmd, check=True)


def step_copy(args: dict, ctx: dict, dry_run: bool):
    src = Path(render(args["source"], ctx))
    dst = Path(render(args["dest"], ctx))
    print(f"[copy] {src} -> {dst}")
    if dry_run:
        return
    if not src.exists():
        raise PipelineError(f"source not found: {src}")
    if dst.exists() and not ctx["_force"] and _md5(src) == _md5(dst):
        print("  skip: dest already matches source")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def step_run_script(args: dict, ctx: dict, dry_run: bool):
    script_rel = render(args["script"], ctx)
    script_path = REPO_DIR / script_rel
    if not script_path.exists():
        raise PipelineError(f"script not found: {script_path}")
    cmd_args = [render(a, ctx) for a in args.get("args", [])]
    cmd = [sys.executable, str(script_path)] + cmd_args
    print(f"[run-script] {' '.join(cmd)}")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def step_await_meta(args: dict, ctx: dict, dry_run: bool):
    target = Path(render(args["path"], ctx))
    meta = Path(str(target) + ".meta")
    print(f"[await-meta] {meta}")
    if dry_run:
        return
    if meta.exists():
        print("  ok (.meta present)")
        return
    raise PipelineError(
        f".meta missing for {target}.\n"
        f"Open Unity to import this asset (it generates the .meta), then re-run "
        f"the same command. Earlier steps will be skipped via idempotency."
    )


def step_write_json(args: dict, ctx: dict, dry_run: bool):
    path = Path(render(args["path"], ctx))
    content = render_obj(args["content"], ctx)
    merge = bool(args.get("merge", False))
    print(f"[write-json] {path}{' (merge)' if merge else ''}")
    if dry_run:
        print("  content:", json.dumps(content, indent=2))
        return
    if path.exists():
        existing = json.loads(path.read_text())
        if merge and isinstance(existing, dict) and isinstance(content, dict):
            merged = dict(existing)
            merged.update(content)
            content = merged
        if existing == content:
            print("  skip: already up to date")
            return
        if not ctx["_force"] and not merge:
            # write anyway when content differs — this is the common case for
            # data files; --force is only needed to bypass other idempotency.
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + "\n")


def step_text_insert(args: dict, ctx: dict, dry_run: bool):
    path = Path(render(args["path"], ctx))
    anchor = render(args["anchor"], ctx)
    insert = render(args["insert"], ctx)
    marker = render(args.get("marker", ""), ctx) or insert.strip().splitlines()[0]
    print(f"[text-insert] {path}")
    if dry_run:
        print(f"  marker: {marker}")
        return
    if not path.exists():
        raise PipelineError(f"target file not found: {path}")
    text = path.read_text()
    if marker and marker in text:
        print(f"  skip: marker '{marker[:50]}' already present")
        return
    m = re.search(anchor, text, re.MULTILINE)
    if not m:
        raise PipelineError(f"anchor regex did not match in {path}: {anchor!r}")
    new_text = text[: m.end()] + insert + text[m.end() :]
    path.write_text(new_text)


def step_md_append(args: dict, ctx: dict, dry_run: bool):
    path = Path(render(args["path"], ctx))
    content = render(args["content"], ctx)
    marker = render(args.get("marker", ""), ctx) or content.strip().splitlines()[0]
    print(f"[md-append] {path}")
    if dry_run:
        print(f"  marker: {marker}")
        return
    if path.exists():
        text = path.read_text()
        if marker in text:
            print(f"  skip: marker '{marker[:50]}' already present")
            return
        text = text.rstrip() + "\n\n" + content + ("\n" if not content.endswith("\n") else "")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content + ("\n" if not content.endswith("\n") else "")
    path.write_text(text)


STEPS = {
    "resize": step_resize,
    "copy": step_copy,
    "run-script": step_run_script,
    "await-meta": step_await_meta,
    "write-json": step_write_json,
    "text-insert": step_text_insert,
    "md-append": step_md_append,
}


# ---------- argparse + main ----------

def build_parser(pipeline: dict) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="import-asset",
        description=pipeline.get("description", ""),
    )
    p.add_argument("source", help="Source file path")
    p.add_argument("--as", dest="asset_type", required=True,
                   help="Pipeline type (file under pipelines/)")
    p.add_argument("--unity-project",
                   default=os.environ.get("UNITY_PROJECT", os.getcwd()),
                   help="Unity project root (or env UNITY_PROJECT, default cwd)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print planned steps without executing")
    p.add_argument("--force", action="store_true",
                   help="Bypass idempotency skip-checks")
    for arg in pipeline.get("arguments", []):
        kwargs = {"help": arg.get("help", "")}
        if arg.get("required"):
            kwargs["required"] = True
        if "default" in arg:
            kwargs["default"] = arg["default"]
        if "choices" in arg:
            kwargs["choices"] = arg["choices"]
        atype = arg.get("type")
        if atype == "int":
            kwargs["type"] = int
        elif atype == "float":
            kwargs["type"] = float
        p.add_argument(f"--{arg['name']}", **kwargs)
    return p


def list_pipelines():
    if not PIPELINES_DIR.exists():
        print("(no pipelines/ directory)")
        return
    found = sorted(PIPELINES_DIR.glob("*.json"))
    if not found:
        print("(no pipelines defined)")
        return
    print("Available --as types:")
    for f in found:
        try:
            data = json.loads(f.read_text())
            print(f"  {f.stem:20} {data.get('description', '')}")
        except Exception as e:
            print(f"  {f.stem:20} (broken: {e})")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("--list", "list"):
        list_pipelines()
        return

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--as", dest="asset_type")
    pre_args, _ = pre.parse_known_args()
    if not pre_args.asset_type:
        print("error: --as <type> is required (use --list to see available types)",
              file=sys.stderr)
        sys.exit(2)

    pipeline = load_pipeline(pre_args.asset_type)
    parser = build_parser(pipeline)
    args = parser.parse_args()

    ctx = {
        "source": str(Path(args.source).resolve()),
        "unity_project": str(Path(args.unity_project).resolve()),
        "_force": args.force,
    }
    for arg in pipeline.get("arguments", []):
        py_name = arg["name"].replace("-", "_")
        ctx[py_name] = getattr(args, py_name)

    name = ctx.get("name")
    if isinstance(name, str) and name:
        ctx.setdefault("Name", name[:1].upper() + name[1:])
        ctx.setdefault("NAME", name.upper())

    print(f"=== import-asset --as {pre_args.asset_type} ===")
    print(f"    {pipeline.get('description', '')}")
    if args.dry_run:
        print("    (dry-run — no files will be modified)")

    steps = pipeline.get("steps", [])
    for i, step in enumerate(steps, 1):
        kind = step.get("type")
        fn = STEPS.get(kind)
        if not fn:
            raise PipelineError(f"step {i}: unknown step type {kind!r}")
        print(f"\n--- step {i}/{len(steps)}: {kind} ---")
        fn(step, ctx, args.dry_run)

    print("\n=== done ===")


if __name__ == "__main__":
    try:
        main()
    except PipelineError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"error: subprocess failed (exit {e.returncode}): {' '.join(e.cmd)}",
              file=sys.stderr)
        sys.exit(1)
