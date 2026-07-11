### **Project Scope: Real Materialized Views (Snowflake/BigQuery/dbt incremental) vs. Mini-Materialized-Views**

| Feature | Real Systems | Mini-Materialized-Views (Python) |
| --- | --- | --- |
| **Refresh** | Full, incremental, or continuous (streaming) | Full + incremental |
| **Staleness tracking** | Query rewrite decides live-table vs. view based on freshness needs | Explicit `is_stale()` check based on source watermark |
| **Incremental logic** | Automatic diff detection (Snowflake), or manually declared (dbt `incremental`) | Manually declared "what changed since last refresh" predicate |
| **Query rewrite** | Optimizer transparently substitutes a view for its base query when safe | None — caller must explicitly choose to query the view |

Sits between `mini-query-engine` (this group) and `mini-dbt` (group 04) —
dbt's `incremental` materialization is a restricted, SQL-authored version of
exactly what this project builds generally.

---

### **Phase 1: Full Refresh**

* **A view definition:** A stored query plus a materialized result table
  (query it once, cache the output).
* **Full refresh:** Re-run the entire defining query and replace the
  materialized table's contents — correct, but wasteful if only a small
  fraction of the source data changed.
* **Staleness tracking:** Record a watermark (e.g. max source `updated_at`,
  or a source snapshot id if built on `mini_iceberg`) at refresh time, so
  you can later answer "is this view stale relative to its source right
  now?"

### **Phase 2: Incremental Refresh**

* **Change identification:** Given the last refresh's watermark, identify
  only the source rows that changed since then (new rows, or rows past a
  given `updated_at`).
* **Incremental merge:** Apply just those changes to the existing
  materialized result — for an aggregate view (e.g. `SUM(amount) GROUP BY
  customer_id`), this means adjusting existing aggregate rows, not
  recomputing every group from scratch.
* **Where incremental logic gets wrong answers:** Deliberately implement
  an incremental refresh for a view with a `COUNT DISTINCT` or a windowed
  aggregate, and show that "just add the new rows' contribution" produces
  an incorrect result for these — some aggregates are not incrementally
  composable without extra state (e.g. tracking distinct-value sets, not
  just a running count).

### **Phase 3: Freshness-Aware Query Routing**

* **A staleness threshold per query:** Given a query that can tolerate
  results up to N minutes stale, decide automatically whether to serve
  from the materialized view or fall back to querying the live source.
* **Cost comparison:** Measure query latency serving from the view vs.
  recomputing live, at a few different source table sizes — this is the
  actual value proposition materialized views sell, made measurable
  instead of assumed.

### **What this exposes about real tools**

"Just materialize it" quietly assumes the aggregate being materialized is
*incrementally composable* — true for `SUM`/`COUNT`/`MIN`/`MAX`, false or
much harder for `COUNT DISTINCT`, medians, and most window functions.
Having hit that wall directly in Phase 2 is what makes "why is this dbt
incremental model producing wrong numbers after a backfill" a diagnosable
bug instead of a mystery.
