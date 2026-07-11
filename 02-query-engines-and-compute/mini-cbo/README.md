### **Project Scope: Real Cost-Based Optimizers (Postgres/Calcite) vs. Mini-CBO**

| Feature | Real CBO | Mini-CBO (Python) |
| --- | --- | --- |
| **Statistics** | Histograms, most-common-values, correlation | Row count + min/max + distinct-count estimate only |
| **Search space** | Dynamic programming or genetic/heuristic search over large join graphs | Exhaustive search, capped at ~6 tables |
| **Cost model** | Calibrated to actual I/O + CPU cost on the target engine | A simple abstract cost unit (estimated rows processed) |
| **Plan caching** | Yes, with invalidation on stats change | None |

Pairs directly with `mini-query-engine` (same group) — that project executes
a plan; this one decides *which* plan to execute in the first place.

---

### **Phase 1: Statistics Collection**

* **Per-table stats:** Row count, and per-column min/max + a rough
  distinct-value count (exact for small data, or via a simple
  approximation like counting unique values in a sample).
* **Selectivity estimation:** For a predicate like `col = value`, estimate
  the fraction of rows that match as `1 / distinct_count` (the standard
  naive assumption real optimizers start from before histograms refine it).
* **Join cardinality estimation:** Estimate a join's output row count from
  both sides' row counts and an assumption about key overlap — and
  deliberately get this wrong on a skewed dataset to see the failure mode.

### **Phase 2: Cost Model**

* **Assign a cost to each physical operator:** e.g. a hash join costs
  roughly `build_side_rows + probe_side_rows`; a full scan costs
  `table_row_count`. These don't need to be realistic in absolute terms —
  they need to be *consistently comparable* to each other.
* **Plan enumeration:** For a query with 3-4 tables, enumerate every valid
  join order and join algorithm choice.
* **Pick the minimum-cost plan** and explain (print) *why* — which
  alternative plans were considered and rejected, and by how much.

### **Phase 3: Where Estimation Fails**

* **Correlated columns:** Build a table where two columns are correlated
  (e.g. `city` and `zip_code`) and show that a cost model assuming
  independence badly over- or under-estimates a combined filter's
  selectivity.
* **Skewed distributions:** Same exercise with a heavily skewed column
  (e.g. 90% of rows share one value) — show the naive `1/distinct_count`
  estimate is wrong by an order of magnitude, and that a histogram-based
  estimate (bucket counts instead of a single distinct-count number) fixes
  it.

### **What this exposes about real tools**

Every "the query planner picked a bad plan" incident in a real production
database traces back to exactly this: a selectivity or cardinality
estimate that was wrong, usually due to correlated columns or skew the
optimizer's statistics didn't capture. Building the estimator yourself, and
then deliberately breaking it with correlated/skewed data, is what turns
"update your table statistics" from cargo-culted advice into a specific,
diagnosable fix.
