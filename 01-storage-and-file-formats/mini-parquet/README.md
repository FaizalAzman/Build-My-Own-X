### **Project Scope: Real Parquet vs. Mini-Parquet**

| Feature | Real Parquet | Mini-Parquet (Python) |
| --- | --- | --- |
| **Encoding** | Dictionary, RLE/bit-packed, delta, byte-stream-split | Dictionary + RLE only |
| **Compression** | Snappy, Zstd, Gzip per column chunk | Optional: one codec (zlib) or none |
| **Layout** | Row groups → column chunks → pages | Row groups → column chunks (skip page-level splitting) |
| **Nesting** | Full Dremel-style repetition/definition levels for nested/repeated fields | Flat schemas only (no structs/lists) |
| **Footer** | Thrift-encoded metadata at file end | JSON metadata at file end |

`mini-iceberg` used `pyarrow.parquet` as a black box. This project opens that box:
you're writing the actual byte layout a Parquet reader parses, not calling a
library that does it for you.

---

### **Phase 1: Column Chunks and the Footer**

* **Column-oriented layout:** Write each column's values contiguously, not
  row-by-row — the whole reason Parquet is a *columnar* format. Prove it by
  writing a table with 10 columns and reading back just 1 without touching
  the other 9's bytes.
* **Footer metadata:** Write a footer at the end of the file (Parquet does
  this so a reader can seek to the last 4 bytes to find the footer's length
  and offset, then jump straight there) recording each column's byte range,
  row count, and encoding.
* **File format sniff test:** Your file should be readable with only
  `open()`/`seek()` and your own metadata — no dependency on `pyarrow` for
  reading what you wrote.

### **Phase 2: Encoding**

* **Dictionary encoding:** For low-cardinality columns, write a
  dictionary (list of unique values) plus a column of small integer indexes
  into it, instead of repeating full values. Measure the size difference on
  a column like `country_code`.
* **Run-length encoding (RLE):** For a sorted or low-cardinality integer
  column, encode `(value, run_length)` pairs instead of every value.
* **Per-column min/max/null-count stats:** Same shape as `mini_iceberg`'s
  manifest stats, but now stored in *this* file's own footer, one level
  lower in the stack.

### **Phase 3: Row Groups and Predicate Pushdown**

* **Row groups:** Split a large table into multiple row groups (Parquet's
  unit of parallelism and pruning), each with its own stats in the footer.
* **Row-group skipping:** Given a filter like `col > 100`, use each row
  group's stats to skip reading row groups that can't match — before
  touching any column data. This is the mechanism `mini-query-engine`
  (02) will eventually use one layer up, at the *file* level instead of the
  *row-group* level.

### **What this exposes about real tools**

Compression codec choice (Snappy vs. Zstd) is a latency/ratio tradeoff you
can only really feel once you've implemented "no compression" and timed it
yourself. Same for RLE vs. dictionary encoding — they win on opposite data
shapes (sorted/repetitive vs. low-cardinality-but-unsorted), and picking
wrong is a real, measurable performance bug in production warehouses.
