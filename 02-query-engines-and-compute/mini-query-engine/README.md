### **Project Scope: Real Query Engines (Trino/Spark SQL) vs. Mini-Query-Engine**

| Feature | Real Query Engine | Mini-Query-Engine (Python) |
| --- | --- | --- |
| **Parsing** | Full ANSI SQL grammar | A small subset: `SELECT ... FROM ... WHERE ... JOIN ...` |
| **Execution** | Distributed, multi-stage, vectorized | Single-process, row-at-a-time (contrast with `mini-vectorized-exec`) |
| **Pruning** | File + row-group + partition pruning | File-level pruning via manifest stats only |
| **Joins** | Broadcast, shuffle hash, sort-merge, adaptive | Hash join + sort-merge join, manually chosen |
| **Catalog** | Pluggable (Hive, Glue, Iceberg REST) | Reads directly from `mini_iceberg`'s `Catalog` |

This is the direct sequel to `mini-iceberg`: it reads the exact tables that
project produces, and finally uses the column stats `mini_iceberg` computes
but never acts on (see `mini-iceberg/CASE_STUDY.md` §4).

---

### **Phase 1: Parse and Plan**

* **A minimal SQL parser:** Handle `SELECT <cols> FROM <table> WHERE <predicate>`,
  producing a simple AST — don't reach for a parser generator yet, hand-roll
  it for a fixed grammar subset first.
* **Logical plan:** Turn the AST into a small tree of logical operators
  (`Scan(table)` → `Filter(predicate)` → `Project(columns)`).
* **Catalog binding:** Resolve `<table>` against a `mini_iceberg.Catalog`,
  loading its current schema and snapshot.

### **Phase 2: Predicate Pushdown**

* **Manifest-level pruning:** Before reading any Parquet file, compare the
  `WHERE` clause's predicate against each active manifest entry's
  `column-stats` (min/max) and skip files that provably can't match —
  exactly the extension `mini-iceberg/CASE_STUDY.md` names as the natural next
  step.
* **Residual predicate:** After pruning, the filter still has to be applied
  row-by-row to whatever files remain (stats only *rule out* files, they
  don't guarantee a match).
* **Measure it:** Build a table with 50+ small files across a wide value
  range, run a selective filter, and count files opened with pruning on vs.
  off.

### **Phase 3: Joins**

* **Hash join:** Build a hash table from the smaller side, probe with the
  larger side — good when one side fits comfortably in memory.
* **Sort-merge join:** Sort both sides on the join key, then merge — no
  hash table, but requires both sides sorted (or a sort step first).
* **Cost comparison:** Same join, same data, both algorithms — measure
  where the crossover point is as one side's size grows relative to the
  other.

### **What this exposes about real tools**

"Just add an index" and "just push the predicate down" are the two most
overused pieces of query-tuning advice in practice — this project is where
you find out predicate pushdown has a real ceiling (stats only prune whole
files, never rows) and that join algorithm choice is workload-shape
dependent, not a universal "always use X." That's the difference between
repeating query-optimization folklore and actually being able to diagnose
why a specific query is slow.
