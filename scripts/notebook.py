#!/usr/bin/env python3
"""Jupytext path resolution and atomic content updates for Neovim.

JSON on stdin/stdout keeps filenames and notebook text out of shell commands.
This helper never executes notebook code.
"""

import io
import json
import os
import tempfile
import tokenize
from pathlib import Path

import jupytext
import nbformat
from jupytext.combine import combine_inputs_with_outputs
from jupytext.config import load_jupytext_config, notebook_formats
from jupytext.paired_paths import find_base_path_and_format, paired_paths


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def resolve(path, text=None):
    path = str(Path(path).resolve())
    config = load_jupytext_config(path)
    notebook = (
        jupytext.reads(text, fmt="py:percent", config=config)
        if text is not None
        else jupytext.read(path, config=config)
    )
    formats = notebook_formats(notebook, config, path, fallback_on_current_fmt=False)
    pairs = []
    if formats:
        _, current = find_base_path_and_format(path, formats)
        pairs = [
            (str(Path(p).resolve()), f) for p, f in paired_paths(path, current, formats)
        ]
    notebooks = [p for p, f in pairs if f["extension"] == ".ipynb"]
    scripts = [p for p, f in pairs if f["extension"] == ".py"]
    if pairs and (len(notebooks) != 1 or len(scripts) != 1 or len(pairs) != 2):
        raise ValueError(
            "Only one Python script paired with one ipynb is supported; use Jupytext CLI for other pairings"
        )
    target = path if path.endswith(".ipynb") else (notebooks[0] if notebooks else None)
    return notebook, {
        "target": target,
        "paths": [p for p, _ in pairs],
        "paired": bool(pairs),
    }


def update(target, text, source, kernelspec=None):
    config = load_jupytext_config(source)
    notebook = jupytext.reads(text, fmt="py:percent", config=config)
    if Path(target).exists():
        original = nbformat.read(target, as_version=4)
        notebook = combine_inputs_with_outputs(notebook, original, fmt="py:percent")
        # Text headers can deliberately filter metadata: retain fields not represented there.
        notebook.metadata = nbformat.from_dict(
            {**original.metadata, **notebook.metadata}
        )
    notebook.metadata.setdefault("language_info", {"name": "python"})
    if kernelspec and "kernelspec" not in notebook.metadata:
        notebook.metadata["kernelspec"] = kernelspec
    atomic_write(target, nbformat.writes(notebook))


def export_check(target):
    notebook = nbformat.read(target, as_version=4)
    seen = set()
    for cell in notebook.cells:
        if cell.cell_type != "code" or not cell.source.strip():
            continue
        tokens = tokenize.generate_tokens(io.StringIO(cell.source).readline)
        key = tuple(
            (t.type, t.string)
            for t in tokens
            if t.type
            not in {
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.ENDMARKER,
            }
        )
        if key in seen:
            raise ValueError(
                "Output export skipped: duplicate code cells are ambiguous in Molten (comments do not distinguish them). Make code unique, save, then rerun complete cells."
            )
        seen.add(key)


def dispatch(request):
    mode, path = request["mode"], str(Path(request["path"]).resolve())
    if mode == "check":
        export_check(path)
        return {}
    text = request.get("text")
    if mode == "pair":
        notebook, info = resolve(path, text)
        if info["paired"]:
            return info
        target = str(Path(path).with_suffix(".ipynb"))
        if Path(target).exists():
            raise ValueError(
                "Companion already exists; establish pairing with Jupytext CLI after reviewing both files"
            )
        metadata = notebook.metadata.setdefault("jupytext", {})
        metadata["formats"] = "ipynb,py:percent"
        metadata["notebook_metadata_filter"] = "all"
        script = jupytext.writes(notebook, fmt="py:percent")
        # Pairing writes the script only; Neovim's normal save then creates the ipynb.
        atomic_write(path, script)
        return {"target": target, "paired": True, "paths": [path, target]}
    _, info = resolve(path, text if path.endswith(".py") else None)
    if mode == "write":
        if info["target"]:
            update(info["target"], text, path, request.get("kernelspec"))
        if info["paired"] and path.endswith(".ipynb"):
            for companion in info["paths"]:
                if companion.endswith(".py"):
                    atomic_write(companion, text + "\n")
    return info


if __name__ == "__main__":
    try:
        print(json.dumps(dispatch(json.load(__import__("sys").stdin))))
    except Exception as error:  # noqa: BLE001 - JSON CLI boundary: report a concise error to Neovim.
        print(str(error), file=__import__("sys").stderr)
        raise SystemExit(1)
