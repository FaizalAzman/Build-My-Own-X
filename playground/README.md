# Playgrounds

In-browser versions of the finished projects. Each page loads the project's
real, unmodified source into [Pyodide](https://pyodide.org) (CPython compiled
to WebAssembly, with pandas and pyarrow) and runs it in the browser. No server
or install is needed.

A playground isn't a demo of the happy path. Each one has two parts:

1. **Build phases:** the project's phases as runnable cells, with an
   inspector that shows what each step wrote to disk.
2. **Experiments:** cells that test a claim from the project's case study.
   For example: what committing too often actually costs, or what happens to
   two writers without compare-and-swap. Each experiment ends with a *Think*
   question that connects the result to an architecture decision.

You can also edit the library in the **Source** tab and re-run the project's
pytest suite in the **Tests** tab. That's how you try a fix suggested by an
experiment.

## Run locally

Pages load source files with `fetch`, so they need an HTTP server rather
than `file://`. From the repo root:

```sh
python -m http.server 8000
```

Then open <http://localhost:8000/playground/>. The first load downloads
Pyodide, pandas and pyarrow (~30 MB) from the jsDelivr CDN. After that the
browser caches them.

## Publish

Enable GitHub Pages for the repo: Settings → Pages → *Deploy from a branch*,
branch `main`, folder `/ (root)`. The playgrounds are then served at
<https://faizalazman.github.io/Build-My-Own-X/playground/>. The empty `.nojekyll`
file at the repo root is required: without it, Pages' Jekyll step skips files
that start with an underscore, such as `__init__.py`.

## Add a playground for another project

1. Copy `mini-iceberg/` to `playground/<project>/`.
2. In `project.js`, set:
   * `sourceBase`, `packageDir`, `packageFiles` and `testFiles`. There is no
     directory listing on a static host, so the file lists are explicit. A new
     module that isn't listed here won't be loaded.
   * `packages` (anything not built into Pyodide can be installed with
     `micropip` in `setup`);
   * `steps`.
3. Replace `inspector.py` and `renderInspector` with a view that shows *this*
   project's internal state, such as SSTable levels for `mini-lsm` or row
   groups and page stats for `mini-parquet`.
4. Write at least one experiment that tests a claim from the project's case
   study, not only the build phases.
5. Add a card to `playground/index.html`.

`shared/` (the Pyodide boot, notebook cells, Files/Source/Tests tabs, and
`runtime.py`) is project-independent and shouldn't need changes.
