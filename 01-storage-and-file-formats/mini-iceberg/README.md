### **Project Scope: Mini-Iceberg vs. Apache Iceberg**

| Feature | Real Apache Iceberg | Mini-Iceberg (Python) |
| --- | --- | --- |
| **Storage** | Object Stores (S3, GCS) | Local File System |
| **Data Format** | Parquet, ORC, Avro | PyArrow / Parquet |
| **Catalog** | REST, Hive, AWS Glue | Local JSON file |
| **Concurrency** | Optimistic Concurrency Control | Single-threaded |
| **Compute Engine** | Spark, Trino, Flink | Pure Python (Pandas/Arrow) |

---

### **Phase 1: The Storage and Catalog Foundation**

Before we track data, we need a place to put it and a way to know it exists.

* **The Directory Structure:** Create a strict file layout simulating a data lake. You will need a root directory containing a `data/` folder for Parquet files and a `metadata/` folder for JSON tracking files.
* **The Catalog:** Write a simple `catalog.json` at the root level. Its only job is to map a table name (e.g., `users`) to the absolute path of its most recent table metadata file.
* **The Schema Definition:** Use `pyarrow.schema` to define a strict schema for your test data. Iceberg's core promise is schema evolution, so establishing a rigid baseline is required before you can mutate it.

### **Phase 2: The Metadata Hierarchy**

This is the brain of the format. You will build the three layers of Iceberg's metadata tree from the bottom up using JSON.

* **Manifest Files:** Write a Python class that generates a JSON file tracking individual Parquet files. It must record the file path, row count, and the min/max values for key columns.
* **Snapshots (Manifest Lists):** Write a script to generate a Snapshot JSON. This file acts as a commit. It will list the paths to the active Manifest Files and record a timestamp and a unique Snapshot ID.
* **Table Metadata:** Create the root metadata JSON. This tracks the current schema, the history of all Snapshot IDs, and explicitly points to the "current" Snapshot ID.

### **Phase 3: Core Operations**

With the hierarchy in place, you will script the actual data manipulation.

* **The Append Operation:** Write a function that takes a Pandas DataFrame, writes it as a new Parquet file in the `data/` folder, and walks up the tree. It must create a new Manifest, generate a new Snapshot, and update the Table Metadata to point to this new state.
* **Time Travel Reads:** Write a query function that accepts a Snapshot ID. It should read the Table Metadata, find that specific snapshot, resolve its manifests, and load only the referenced Parquet files into memory.

### **Phase 4: The Capstone (Compaction)**

This is where you recreate your recent architectural win at the byte level.

* **Identify Small Files:** Write a function to scan the current snapshot's manifests and identify Parquet files under a certain byte threshold.
* **Rewrite Data:** Load those small files into a single PyArrow table and write them back out as one large Parquet file.
* **Commit the Compaction:** Generate a new snapshot. This is the critical learning step: you must mark the old data files as "deleted" (or simply omit them from the new manifests) and add the new, large data file. The old files remain on disk, allowing time travel to work, but the current state is now optimized.

---

### **Implementation Plan**

Build this as a small, importable Python library (mirrors how real PyIceberg/Spark-Iceberg is used: `catalog.load_table(...).append(df)` / `.read()`), with a thin CLI wrapper on top for manual poking, plus an automated end-to-end test/demo that proves all 4 phases work together (create → append → time-travel read → compaction → read again).

**Package layout**

```
mini-iceberg/
  README.md
  requirements.txt          # pyarrow, pandas, pytest
  mini_iceberg/
    __init__.py
    types.py                # pyarrow <-> JSON schema (de)serialization, column min/max stats
    manifest.py             # manifest file read/write (Phase 2)
    snapshot.py             # snapshot / manifest-list read/write (Phase 2)
    metadata.py             # table metadata (vN.metadata.json) read/write (Phase 2)
    catalog.py               # catalog.json + Catalog class: create_table/load_table (Phase 1)
    table.py                    # Table class: append() + read() (Phase 3)
    compaction.py                 # compact() (Phase 4)
    cli.py                          # argparse CLI wrapping the library
  tests/
    test_end_to_end.py               # pytest walking through all 4 phases
  demo.py                             # narrated script: same walkthrough, human-readable prints
```

**On-disk layout (a "warehouse")**

```
warehouse/
  catalog.json                          # {"tables": {"users": ".../users/metadata/v3.metadata.json"}}
  users/
    data/
      <uuid>.parquet                    # actual data files, never deleted (enables time travel)
    metadata/
      v1.metadata.json, v2.metadata.json, ...   # one per commit, immutable
      snap-<id>.json                    # manifest list for that snapshot
      manifest-<uuid>.json              # one per append; lists "added" data files + stats
```

**Phase-by-phase design**

- **Phase 1 — Storage & Catalog** (`catalog.py`, `types.py`)
  - `Catalog(root_dir)`: loads/creates `catalog.json`.
  - `Catalog.create_table(name, schema: pa.Schema) -> Table`: makes `data/` + `metadata/` dirs, writes `v1.metadata.json` with empty snapshot history, registers path in `catalog.json`.
  - `Catalog.load_table(name) -> Table`: reads `catalog.json`, loads the metadata file it points to.
  - `types.py`: converts a `pyarrow.Schema` to/from the JSON representation stored in table metadata.

- **Phase 2 — Metadata hierarchy** (`manifest.py`, `snapshot.py`, `metadata.py`)
  - Manifest JSON: list of entries `{status: "added", file-path, record-count, file-size-bytes, column-stats: {col: {min,max}}}`. `types.py` computes min/max per column via pandas.
  - Snapshot (manifest-list) JSON: `{snapshot-id, timestamp-ms, parent-snapshot-id, manifests: [manifest paths]}`.
  - Table metadata JSON: `{schema, current-snapshot-id, snapshots: [{snapshot-id, timestamp-ms, manifest-list, summary}]}`. Written as a new `vN.metadata.json` on every commit (never overwritten) — mirrors real Iceberg's immutable-metadata-file + atomic-pointer-swap commit protocol; `catalog.json` is updated last (via write-temp-then-`os.replace`) so a crash mid-commit never leaves the catalog pointing at a partial state.

- **Phase 3 — Core operations** (`table.py`)
  - `Table.append(df: pd.DataFrame)`:
    1. validate/cast `df` against the table's pyarrow schema
    2. write `df` to a new Parquet file in `data/`
    3. write a **new** manifest file containing only this file's entry (real Iceberg never rewrites old manifests on append)
    4. new snapshot's manifest-list = parent snapshot's manifests + [new manifest] (this is what makes "many small manifests" pile up — setting up the Phase 4 payoff)
    5. write new `vN.metadata.json`, then atomically update `catalog.json`
  - `Table.read(snapshot_id=None) -> pd.DataFrame`: resolve snapshot (defaults to current), walk its manifest list, collect all "added" file paths, load + concat via `pyarrow.parquet`. Passing an old `snapshot_id` is the time-travel path.
  - `Table.history()`: returns the snapshot list for inspection (used by CLI/demo).

- **Phase 4 — Compaction** (`compaction.py`)
  - `compact(table, small_file_threshold_bytes)`:
    1. resolve current snapshot's active files (path + size) from its manifests
    2. filter files `< threshold`; no-op if fewer than 2
    3. load the small files into one `pa.Table`, write out as a single new large Parquet file
    4. build one new manifest = `[new large file]` + `[carried-forward entries for files that were active but not compacted]` — the small files' old entries are simply omitted (not marked deleted, per the Phase 4 note above)
    5. commit a new snapshot (`summary.operation = "compaction"`) whose manifest list is just this one new manifest
    6. old Parquet files and old manifest files are left on disk untouched, so `table.read(snapshot_id=<old>)` still works after compaction

**Usage (what this is for)**

Library, mirroring PyIceberg's ergonomics:

```python
from mini_iceberg.catalog import Catalog
import pyarrow as pa, pandas as pd

catalog = Catalog("warehouse")
schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
table = catalog.create_table("users", schema)

table.append(pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}))   # snapshot 1
table.append(pd.DataFrame({"id": [3], "name": ["c"]}))            # snapshot 2

table.read()                      # current state (3 rows)
table.read(snapshot_id=1)         # time travel (2 rows)

from mini_iceberg.compaction import compact
compact(table, small_file_threshold_bytes=1_048_576)
```

Thin CLI over the same calls (`mini_iceberg/cli.py`, run via `python -m mini_iceberg.cli`):

```
create-table <warehouse> <name> --schema id:int64,name:string
append       <warehouse> <name> <data.csv>
read         <warehouse> <name> [--snapshot-id N]
history      <warehouse> <name>
compact      <warehouse> <name> [--threshold-bytes N]
```

**Verification**

- `tests/test_end_to_end.py` (pytest, uses `tmp_path`): create table → two appends → assert `read()` row count and `read(snapshot_id=1)` time-travel row count → several more small appends → `compact()` → assert data file count drops, `read()` still returns all correct rows, and reading an old snapshot ID still succeeds post-compaction.
- From `01-storage-and-file-formats/mini-iceberg/`, run `pip install -r requirements.txt && pytest tests -v` — all tests green.
- Run `python demo.py` (from that same folder) to manually eyeball the narrated walkthrough (snapshot IDs, file counts before/after compaction).