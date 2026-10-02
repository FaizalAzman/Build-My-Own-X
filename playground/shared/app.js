import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const HOME = "/home/pyodide";
const HELPERS = `${HOME}/_playground`;
const WAREHOUSE = `${HOME}/warehouse`;

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "html") el.innerHTML = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

export function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

async function fetchText(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not fetch ${url} (HTTP ${res.status})`);
  return res.text();
}

function renderOutput(el, { stdout, result, error }) {
  el.replaceChildren();
  if (stdout) el.append(h("pre", { class: "out" }, stdout));
  if (result?.kind === "html") el.append(h("div", { class: "df-wrap", html: result.body }));
  else if (result?.kind === "text") el.append(h("pre", { class: "out" }, result.body));
  if (error) el.append(h("pre", { class: "out err" }, error));
  el.hidden = !el.childElementCount;
}

function autosize(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight + 2}px`;
}

function makeEditor(value, onRun) {
  const editor = h("textarea", { class: "code", spellcheck: "false", autocapitalize: "off", "aria-label": "Python code" });
  editor.value = value;
  editor.addEventListener("input", () => autosize(editor));
  editor.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && onRun) {
      e.preventDefault();
      onRun();
    } else if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end");
      autosize(editor);
    }
  });
  requestAnimationFrame(() => autosize(editor));
  return editor;
}

export async function startPlayground(project) {
  const $ = (id) => document.getElementById(id);
  const status = $("status");
  const setStatus = (text, kind = "busy") => { status.textContent = text; status.dataset.kind = kind; };
  const root = `${HOME}/${project.id}`;
  let py, runtime;
  let busy = true;
  const runButtons = [];
  const setBusy = (value) => {
    busy = value;
    for (const b of runButtons) b.disabled = value;
  };

  // ---- Notebook ---------------------------------------------------------
  const cells = project.steps.map((step, i) => {
    const output = h("div", { class: "output", hidden: true, "aria-live": "polite" });
    const cell = { step, output };
    cell.editor = makeEditor(step.code, () => runOne(cell));
    const button = h("button", { class: "run", disabled: true, onclick: () => runOne(cell) }, "Run");
    runButtons.push(button);
    $("steps").append(h("article", { class: "step", id: `step-${i + 1}` },
      h("header", {}, h("span", { class: "label" }, step.label), h("h2", {}, step.title)),
      h("p", { html: step.body }),
      step.think ? h("p", { class: "think" }, h("strong", {}, "Think: "), step.think) : null,
      h("div", { class: "cell" }, cell.editor, h("div", { class: "cell-bar" }, button, h("span", { class: "hint" }, "Ctrl/⌘ + Enter"))),
      output,
    ));
    return cell;
  });
  for (const id of ["run-all", "reset", "run-tests", "source-save", "source-revert"]) runButtons.push($(id));

  // ---- Python plumbing --------------------------------------------------
  let sink = null;
  const capture = (fn) => {
    sink = [];
    try {
      const value = fn();
      py.runPython("import sys; sys.stdout.flush(); sys.stderr.flush()");
      return [value, sink.join("\n")];
    } finally {
      sink = null;
    }
  };

  function runCode(code) {
    const [raw, stdout] = capture(() => runtime.run_cell(code));
    return { stdout, ...JSON.parse(raw) };
  }

  function resetWarehouse() {
    py.runPython(`import shutil, runtime\nshutil.rmtree(${JSON.stringify(WAREHOUSE)}, ignore_errors=True)\nruntime.reset_namespace()`);
    const res = runCode(project.setup);
    if (!res.ok) throw new Error(res.error);
    for (const cell of cells) renderOutput(cell.output, {});
    previewEl.replaceChildren();
  }

  function runOne(cell) {
    if (busy) return false;
    setBusy(true);
    try {
      const res = runCode(cell.editor.value);
      renderOutput(cell.output, res);
      return res.ok;
    } finally {
      refresh();
      setBusy(false);
    }
  }

  // ---- Inspector + files ------------------------------------------------
  const inspectorState = {};
  const previewEl = $("file-preview");

  function refresh() {
    try {
      const data = JSON.parse(py.runPython(project.inspect(WAREHOUSE)));
      project.renderInspector($("tab-tree"), data, { state: inspectorState });
    } catch (err) {
      $("tab-tree").replaceChildren(h("pre", { class: "out err" }, `Inspector could not read the warehouse:\n${err.message}`));
    }
    const files = JSON.parse(runtime.list_files(WAREHOUSE));
    $("file-list").replaceChildren(...(files.length ? files.map((f) => h("li", {},
      h("button", { class: "file", onclick: () => preview(f.path) },
        h("code", {}, f.path), h("span", { class: "muted" }, formatBytes(f.size))),
    )) : [h("li", { class: "muted" }, "The warehouse is empty.")]));
  }

  function preview(rel) {
    const out = JSON.parse(runtime.preview_file(`${WAREHOUSE}/${rel}`));
    previewEl.replaceChildren(
      h("div", { class: "preview-head" }, h("code", {}, rel), out.note ? h("p", { class: "muted small" }, out.note) : null),
      out.kind === "html" ? h("div", { class: "df-wrap", html: out.body }) : h("pre", { class: "out" }, out.body),
    );
    previewEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // ---- Tabs -------------------------------------------------------------
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.addEventListener("click", () => {
      for (const other of document.querySelectorAll("[role=tab]")) {
        const selected = other === tab;
        other.setAttribute("aria-selected", String(selected));
        $(other.getAttribute("aria-controls")).hidden = !selected;
      }
    });
  }

  // ---- Boot -------------------------------------------------------------
  try {
    setStatus("Loading Python…");
    py = await loadPyodide();
    py.setStdout({ batched: (s) => (sink ? sink.push(s) : console.log(s)) });
    py.setStderr({ batched: (s) => (sink ? sink.push(s) : console.warn(s)) });

    setStatus(`Installing ${project.packages.join(" + ")}…`);
    await py.loadPackage(project.packages).catch(() => py.loadPackage(project.packages));

    setStatus(`Loading ${project.packageDir} source…`);
    const sources = {};
    const mount = async (url, path) => {
      const text = await fetchText(url);
      py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
      py.FS.writeFile(path, text);
      return text;
    };
    await Promise.all([
      ...project.packageFiles.map(async (f) => {
        sources[f] = await mount(`${project.sourceBase}${project.packageDir}/${f}`, `${root}/${project.packageDir}/${f}`);
      }),
      ...project.testFiles.map((f) => mount(`${project.sourceBase}tests/${f}`, `${root}/tests/${f}`)),
      mount("../shared/runtime.py", `${HELPERS}/runtime.py`),
      ...Object.entries(project.helpers).map(([name, url]) => mount(url, `${HELPERS}/${name}`)),
    ]);
    py.runPython(`import sys\nsys.dont_write_bytecode = True\nsys.path[:0] = [${JSON.stringify(HELPERS)}, ${JSON.stringify(root)}]`);
    runtime = py.pyimport("runtime");

    resetWarehouse();
    refresh();
    setupSource(sources);
    setStatus("Ready: running real Python in your browser", "ok");
    setBusy(false);
  } catch (err) {
    console.error(err);
    setStatus(`Failed to start: ${err.message}. Check your connection and reload the page.`, "error");
    return;
  }

  // ---- Toolbar ----------------------------------------------------------
  $("reset").addEventListener("click", () => {
    if (busy) return;
    resetWarehouse();
    refresh();
  });

  $("run-all").addEventListener("click", () => {
    if (busy) return;
    resetWarehouse();
    for (const cell of cells) {
      if (cell.step.label === "Scratch") break;
      if (!runOne(cell)) {
        cell.output.scrollIntoView({ block: "center", behavior: "smooth" });
        return;
      }
    }
  });

  // ---- Source editing ---------------------------------------------------
  function setupSource(original) {
    const select = $("source-file");
    const editorHost = $("source-editor");
    const note = $("source-note");
    const edited = {};
    select.replaceChildren(...project.packageFiles.map((f) => h("option", { value: f }, `${project.packageDir}/${f}`)));
    const editor = makeEditor("", null);
    editor.classList.add("source");
    editorHost.replaceChildren(editor);

    const pathOf = (f) => `${root}/${project.packageDir}/${f}`;
    const load = () => {
      editor.value = py.FS.readFile(pathOf(select.value), { encoding: "utf8" });
      autosize(editor);
    };
    const markEdited = () => {
      for (const option of select.options) {
        option.textContent = `${project.packageDir}/${option.value}${edited[option.value] ? "  (edited)" : ""}`;
      }
    };
    const reloadPackage = (message) => {
      py.runPython(`import sys
for name in [m for m in sys.modules if m.split(".")[0] in (${JSON.stringify(project.packageDir)}, "tests") or m.startswith("test_")]:
    del sys.modules[name]`);
      const res = runCode(project.setup);
      note.textContent = res.ok ? message : res.error;
      note.dataset.kind = res.ok ? "ok" : "error";
    };

    select.addEventListener("change", load);
    $("source-save").addEventListener("click", () => {
      py.FS.writeFile(pathOf(select.value), editor.value);
      edited[select.value] = editor.value !== original[select.value];
      markEdited();
      reloadPackage("Saved and reloaded. Objects created before this still use the old code: use Run all to replay the steps, or run the tests.");
    });
    $("source-revert").addEventListener("click", () => {
      py.FS.writeFile(pathOf(select.value), original[select.value]);
      edited[select.value] = false;
      markEdited();
      load();
      reloadPackage("Reverted to the committed version and reloaded.");
    });
    load();
  }

  // ---- Tests ------------------------------------------------------------
  let pytestLoaded = false;
  $("run-tests").addEventListener("click", async () => {
    if (busy) return;
    setBusy(true);
    const out = $("test-output");
    const summary = $("test-summary");
    try {
      if (!pytestLoaded) {
        summary.textContent = "Installing pytest…";
        summary.dataset.kind = "busy";
        await py.loadPackage("pytest");
        pytestLoaded = true;
      }
      summary.textContent = "Running…";
      const [code, stdout] = capture(() => py.runPython(`import os, sys, pytest
for name in [m for m in sys.modules if m == "tests" or m.startswith("tests.") or m.startswith("test_")]:
    del sys.modules[name]
os.chdir(${JSON.stringify(root)})
int(pytest.main(["-q", "--color=no", "-p", "no:cacheprovider", "-p", "no:faulthandler", "--capture=sys", "tests"]))`));
      out.textContent = stdout;
      out.hidden = false;
      summary.textContent = code === 0 ? "All tests passed" : `pytest exited with code ${code}`;
      summary.dataset.kind = code === 0 ? "ok" : "error";
    } catch (err) {
      summary.textContent = `Could not run tests: ${err.message}`;
      summary.dataset.kind = "error";
    } finally {
      setBusy(false);
    }
  });
}
