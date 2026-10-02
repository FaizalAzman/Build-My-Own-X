import { h, formatBytes } from "../shared/app.js";

const SETUP = `import os, json, time
import pandas as pd
import pyarrow as pa
from mini_iceberg import Catalog
from mini_iceberg.compaction import compact

WAREHOUSE = "/home/pyodide/warehouse"`;

const steps = [
  {
    label: "Phase 1",
    title: "A catalog and an empty table",
    body: `The catalog is one JSON file mapping a table name to its <em>current</em> metadata file.
      Creating a table writes <code>v1.metadata.json</code> (schema, no snapshots) and points the catalog at it.`,
    think: "Every reader and writer goes through that one pointer. What has to be true of the catalog once there are many writers?",
    code: `schema = pa.schema([("id", pa.int64()), ("user", pa.string()), ("amount", pa.float64())])
catalog = Catalog(WAREHOUSE)
table = catalog.create_table("orders", schema)

print("catalog.json ->", os.path.relpath(catalog._data["tables"]["orders"], WAREHOUSE))
table.read()`,
  },
  {
    label: "Phase 2–3",
    title: "Every append is a commit",
    body: `Each <code>append()</code> writes four new files: a Parquet data file, a manifest describing it,
      a snapshot (manifest list), and a new metadata version. Nothing existing is modified.
      In the metadata tree, snapshot 2's manifest list still includes snapshot 1's manifest.`,
    think: "Four new objects per commit is cheap once. What does it cost at one commit every 10 seconds, for a year?",
    code: `table = Catalog(WAREHOUSE).load_table("orders")
s1 = table.append(pd.DataFrame({"id": [1, 2], "user": ["alice", "bob"], "amount": [30.0, 12.5]}))
s2 = table.append(pd.DataFrame({"id": [3], "user": ["carol"], "amount": [99.0]}))

print("snapshots:", [s["snapshot-id"] for s in table.history()])
table.read()`,
  },
  {
    label: "Phase 3",
    title: "Time travel is just an older pointer",
    body: `Reading snapshot 1 resolves its manifest list to an older set of files. There's no special
      time-travel mode: because nothing was overwritten, the old tree is still intact.
      Click snapshot 1 in the metadata tree to see which files it resolves to.`,
    think: "Time travel works because nothing is deleted. Which requirement in a real platform forces you to delete anyway?",
    code: `table = Catalog(WAREHOUSE).load_table("orders")
print("current snapshot:", table.current_snapshot_id)
table.read(snapshot_id=1)`,
  },
  {
    label: "Phase 4",
    title: "Compaction is a commit, not a rewrite",
    body: `Five more tiny appends, then <code>compact()</code> merges the small files into one and commits a
      new snapshot whose manifest list has a single manifest. The old small files stay on disk and are
      still referenced by older snapshots, so nothing is orphaned and snapshot 1 is still readable.`,
    think: "Storage now holds both the small files and the merged copy. Who decides when old snapshots expire, and what breaks if it's too soon?",
    code: `table = Catalog(WAREHOUSE).load_table("orders")
for i in range(4, 9):
    table.append(pd.DataFrame({"id": [i], "user": [f"user{i}"], "amount": [float(i)]}))

print("active files before:", len(table.active_entries()))
print(compact(table, small_file_threshold_bytes=1_048_576))
print("active files after: ", len(table.active_entries()))
print("snapshot 1 still has", len(table.read(snapshot_id=1)), "rows")
table.read()`,
  },
  {
    label: "Experiment",
    title: "The cost of committing too often",
    body: `The decision section of the case study (§13) claims that metadata, not storage, is what grows
      badly with commit frequency. Measure it: 100 one-row commits vs. one 100-row commit.
      Watch the object count and the size of the metadata files.`,
    think: "What commit interval would you set for a streaming writer, and what freshness are you trading for it?",
    code: `def footprint(t):
    meta = [os.path.join(t.metadata_dir, f) for f in os.listdir(t.metadata_dir)]
    data = os.listdir(t.data_dir)
    versions = [p for p in meta if p.endswith(".metadata.json")]
    return len(meta) + len(data), sum(os.path.getsize(p) for p in versions)

clicks = pa.schema([("id", pa.int64()), ("page", pa.string())])
streamed = Catalog(WAREHOUSE).create_table("clicks_streamed", clicks)
batched = Catalog(WAREHOUSE).create_table("clicks_batched", clicks)

start = time.perf_counter()
for i in range(100):
    streamed.append(pd.DataFrame({"id": [i], "page": ["/home"]}))
stream_secs = time.perf_counter() - start
batched.append(pd.DataFrame({"id": list(range(100)), "page": ["/home"] * 100}))

for name, t in [("100 commits of 1 row", streamed), ("1 commit of 100 rows", batched)]:
    objects, meta_bytes = footprint(t)
    print(f"{name:22}: {objects:4} objects, {meta_bytes:>9,} bytes across all metadata versions")
print(f"(100 commits took {stream_secs:.2f}s)")

start = time.perf_counter(); streamed.read(); before = time.perf_counter() - start
compact(streamed, small_file_threshold_bytes=1_048_576)
start = time.perf_counter(); streamed.read(); after = time.perf_counter() - start
print(f"read planning + scan: {before * 1000:.0f} ms with 100 manifests, {after * 1000:.0f} ms after compaction")`,
  },
  {
    label: "Experiment",
    title: "Two writers, no compare-and-swap",
    body: `<code>Catalog._commit()</code> overwrites the pointer without checking what it pointed at.
      Two writers load the table at the same version, like two jobs starting together, and both append.
      Writer B never saw A's commit, so it writes its own <code>v2.metadata.json</code> and
      <code>snap-1.json</code> over A's. A's data file and manifest become <strong>orphans</strong>: on disk,
      unreachable, silently lost. This is the failure that case study §6 says real catalogs prevent with
      compare-and-swap.`,
    think: "Fix it in the Source tab: make _commit check the pointer still matches what the writer read, and retry on conflict. Which other files would also collide?",
    code: `accounts = Catalog(WAREHOUSE).create_table("accounts", pa.schema([("id", pa.int64()), ("owner", pa.string())]))

writer_a = Catalog(WAREHOUSE).load_table("accounts")
writer_b = Catalog(WAREHOUSE).load_table("accounts")

writer_a.append(pd.DataFrame({"id": [1], "owner": ["written by A"]}))
writer_b.append(pd.DataFrame({"id": [2], "owner": ["written by B"]}))

# Both appends "succeeded". Ask the catalog what the table contains now:
Catalog(WAREHOUSE).load_table("accounts").read()`,
  },
  {
    label: "Scratch",
    title: "Your turn",
    body: `Everything defined above is still in scope (<code>Catalog</code>, <code>compact</code>,
      <code>pd</code>, <code>pa</code>, <code>WAREHOUSE</code>). Try a schema mismatch, a table with
      thousands of files, or reading a snapshot id that doesn't exist.`,
    code: `table = Catalog(WAREHOUSE).load_table("orders")
table.history()`,
  },
];

function shortName(path) {
  const base = path.split("/").pop();
  const match = base.match(/^(manifest-)?([0-9a-f]{32})(\.\w+)$/);
  return match ? `${match[1] || ""}${match[2].slice(0, 8)}…${match[3]}` : base;
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function stat(label, value) {
  return h("div", { class: "stat" }, h("span", { class: "stat-value" }, String(value)), h("span", { class: "stat-label" }, label));
}

function renderInspector(el, data, ctx) {
  const state = ctx.state;
  state.known ??= new Set();
  state.current ??= {};
  el.replaceChildren();

  if (!data.tables.length) {
    el.append(h("p", { class: "muted" }, "No tables yet. Run Phase 1 to create one."));
    return;
  }

  const fresh = data.tables.filter((t) => !state.known.has(t.name));
  data.tables.forEach((t) => state.known.add(t.name));
  if (fresh.length) state.table = fresh[fresh.length - 1].name;
  if (!data.tables.some((t) => t.name === state.table)) state.table = data.tables[0].name;

  const table = data.tables.find((t) => t.name === state.table);
  if (state.current[table.name] !== table.current_snapshot_id || state.snapshotTable !== table.name) {
    state.snapshot = table.current_snapshot_id;
    state.snapshotTable = table.name;
  }
  state.current[table.name] = table.current_snapshot_id;
  const rerender = () => renderInspector(el, data, ctx);

  el.append(
    h("div", { class: "chips", role: "tablist", "aria-label": "Tables" },
      data.tables.map((t) => h("button", {
        class: "chip", "aria-selected": String(t.name === table.name),
        onclick: () => { state.table = t.name; rerender(); },
      }, t.name)),
    ),
    h("div", { class: "pointer" },
      h("code", {}, "catalog.json"), h("span", { class: "arrow" }, "→"),
      h("code", { title: table.current_metadata }, table.current_metadata.split("/").pop()), h("span", { class: "arrow" }, "→"),
      h("code", {}, table.current_snapshot_id == null ? "no snapshot" : `snapshot ${table.current_snapshot_id}`),
    ),
    h("div", { class: "stats" },
      stat("data files", table.counts.data_files),
      stat("manifests", table.counts.manifests),
      stat("snapshots", table.counts.snapshots),
      stat("metadata versions", table.counts.metadata_versions),
      stat("on disk", formatBytes(table.counts.bytes)),
    ),
  );

  if (table.orphans.length) {
    el.append(h("div", { class: "callout warn" },
      h("strong", {}, `${plural(table.orphans.length, "orphaned file")}`),
      h("p", {}, "On disk, but no snapshot in the current metadata references them, so nothing can ever read them. In this table that means a commit was lost. Real Iceberg cleans these up with remove_orphan_files."),
      h("ul", { class: "files" }, table.orphans.map((p) => h("li", { title: p }, h("code", {}, shortName(p))))),
    ));
  }

  if (!table.snapshots.length) {
    el.append(h("p", { class: "muted" }, "No snapshots yet: the table exists but has never been written to."));
    return;
  }

  const current = table.snapshots.find((s) => s.id === table.current_snapshot_id);
  const currentFiles = new Set(current ? current.active_files : []);

  el.append(h("h3", {}, "Snapshots"));
  const list = h("ol", { class: "snapshots" });
  for (const snap of [...table.snapshots].reverse()) {
    const selected = snap.id === state.snapshot;
    const row = h("li", { class: selected ? "selected" : "" },
      h("button", {
        class: "snap-row", "aria-expanded": String(selected),
        onclick: () => { state.snapshot = selected ? null : snap.id; rerender(); },
      },
        h("span", { class: "snap-id" }, `#${snap.id}`),
        h("span", { class: `op op-${snap.operation}` }, snap.operation),
        h("span", { class: "muted" }, `${plural(snap.rows, "row")} · ${plural(snap.active_files.length, "file")} · ${plural(snap.manifests.length, "manifest")}`),
        snap.id === table.current_snapshot_id ? h("span", { class: "badge" }, "current") : null,
      ),
    );
    if (selected) {
      const detail = h("div", { class: "snap-detail" },
        h("div", { class: "muted" }, "manifest list ", h("code", {}, snap.manifest_list.split("/").pop()),
          snap.parent == null ? " · first commit" : ` · parent #${snap.parent}`),
      );
      for (const manifest of snap.manifests) {
        detail.append(h("div", { class: "manifest" },
          h("code", { title: manifest.path }, shortName(manifest.path)),
          h("ul", { class: "files" }, manifest.files.map((f) => h("li", { title: f.path },
            h("code", {}, shortName(f.path)),
            h("span", { class: "muted" }, ` ${plural(f.rows, "row")} · ${formatBytes(f.bytes)}`),
            currentFiles.has(f.path) ? null : h("span", { class: "tag" }, "kept for time travel"),
            f.missing ? h("span", { class: "tag danger" }, "missing") : null,
          ))),
        ));
      }
      row.append(detail);
    }
    list.append(row);
  }
  el.append(list);

  el.append(
    h("h3", {}, "Metadata versions"),
    h("p", { class: "versions" }, table.metadata_versions.map((v) => {
      const name = v.split("/").pop().replace(".metadata.json", "");
      return h("code", { class: v === table.current_metadata ? "current" : "" }, name);
    })),
    h("p", { class: "muted small" }, "Each version is a complete, standalone record of every snapshot so far, never edited after it's written. The catalog points at exactly one."),
  );
}

export const project = {
  id: "mini-iceberg",
  sourceBase: "../../01-storage-and-file-formats/mini-iceberg/",
  packageDir: "mini_iceberg",
  packageFiles: ["__init__.py", "catalog.py", "cli.py", "compaction.py", "manifest.py", "metadata.py", "snapshot.py", "table.py", "types.py"],
  testFiles: ["__init__.py", "test_phase1_catalog.py", "test_phase2_manifest_snapshot.py", "test_phase3_table.py", "test_phase4_compaction.py"],
  packages: ["pandas", "pyarrow"],
  helpers: { "inspector.py": "./inspector.py" },
  inspect: (warehouse) => `import inspector; inspector.describe(${JSON.stringify(warehouse)})`,
  setup: SETUP,
  steps,
  renderInspector,
};
