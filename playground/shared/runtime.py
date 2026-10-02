"""Shared in-browser runtime for every playground page.

Loaded into Pyodide once per page. Gives the JS side three things:
run a cell notebook-style, list the in-memory filesystem, and preview a file.
"""

import ast
import json
import os
import traceback

import pandas as pd
import pyarrow.parquet as pq

NAMESPACE = {"__name__": "__main__"}


def reset_namespace():
    NAMESPACE.clear()
    NAMESPACE["__name__"] = "__main__"


def _render(value):
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        return {"kind": "html", "body": value.to_html(index=False, border=0, classes="df")}
    return {"kind": "text", "body": repr(value)}


def run_cell(code):
    """Exec `code`; if its last statement is an expression, return it rendered (like a notebook)."""
    try:
        tree = ast.parse(code, mode="exec")
        last = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = ast.Expression(tree.body.pop().value)
        exec(compile(tree, "<cell>", "exec"), NAMESPACE)
        value = eval(compile(last, "<cell>", "eval"), NAMESPACE) if last else None
        return json.dumps({"ok": True, "result": _render(value)})
    except Exception:
        return json.dumps({"ok": False, "error": traceback.format_exc(limit=-3)})


def list_files(root):
    """Every file under `root` as {path, size}, sorted, paths relative to `root`."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            files.append({"path": os.path.relpath(full, root), "size": os.path.getsize(full)})
    return json.dumps(sorted(files, key=lambda f: f["path"]))


def preview_file(path, max_rows=50):
    if path.endswith(".parquet"):
        table = pq.read_table(path)
        head = table.slice(0, max_rows).to_pandas()
        return json.dumps({
            "kind": "html",
            "body": head.to_html(index=False, border=0, classes="df"),
            "note": f"{table.num_rows} rows, {table.num_columns} columns. Schema: {table.schema}",
        })
    with open(path) as f:
        return json.dumps({"kind": "text", "body": f.read()})
