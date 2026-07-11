### **Project Scope: Real Vectorized Engines (DuckDB/Velox) vs. Mini-Vectorized-Exec**

| Feature | Real Vectorized Engine | Mini-Vectorized-Exec (Python) |
| --- | --- | --- |
| **Batch unit** | SIMD-friendly fixed-size vectors (e.g. 2048 rows) | PyArrow `RecordBatch` |
| **Operators** | Compiled/JIT'd per-type kernels | PyArrow `compute` kernels, interpreted |
| **Null handling** | Validity bitmaps, branchless kernels | PyArrow's built-in null handling |
| **Pipelining** | Push-based, operators fused across stages | Simple pull-based iterator chain |

The point of this project is a head-to-head against a naive row-at-a-time
engine you build first *in the same project* — the speedup has to be
something you measure, not something you're told.

---

### **Phase 1: Row-at-a-Time Baseline**

* **A naive interpreter:** Implement `filter`, `project`, and `sum`/`count`
  aggregates as plain Python loops over rows (list of dicts or tuples).
* **Timing harness:** Run this over a few million synthetic rows and record
  wall-clock time per operator — this is your baseline to beat.

### **Phase 2: Vectorized Operators**

* **Batch-at-a-time execution:** Re-implement the same operators, but each
  one consumes and produces a `pyarrow.RecordBatch` (or `ChunkedArray`) at
  once, using `pyarrow.compute` kernels instead of Python-level loops.
* **The iterator protocol:** Each operator is a generator that pulls
  batches from its input and yields batches — same pull-based pipeline
  shape as the row-at-a-time version, just a different unit of work per
  pull.
* **Re-run the timing harness:** Same synthetic data, same operators — now
  compare wall-clock time directly against Phase 1.

### **Phase 3: Where Vectorization Breaks Down**

* **A genuinely branchy operator:** Implement something that can't
  vectorize cleanly — e.g. a `CASE WHEN` with several conditions, or a
  string operation with variable-length outputs — and measure how much of
  the speedup from Phase 2 survives.
* **Batch size sweep:** Vary the batch size (16 rows vs. 2048 vs. 100,000)
  and plot throughput — there's a real sweet spot, not "bigger is always
  better" (cache effects and per-batch overhead pull in opposite
  directions).

### **What this exposes about real tools**

"DuckDB is fast because it's vectorized" is true but incomplete — the real
lesson is *which* operators benefit (arithmetic, comparisons, aggregates:
huge win) and which don't (branchy control flow, variable-length string
ops: much smaller win, sometimes none). Knowing that distinction is what
lets you predict *before* running a query whether a given engine's
vectorization will actually help it, instead of treating "vectorized" as a
marketing word that always means fast.
