### **Project Scope: Real Data Observability (Monte Carlo/Bigeye) vs. Mini-Data-Observability**

| Feature | Real Tools | Mini-Data-Observability (Python) |
| --- | --- | --- |
| **Freshness monitoring** | Auto-detected expected update cadence per table | Declared expected cadence, deviation alerting |
| **Volume anomaly detection** | Statistical models on historical row-count trends | Rolling mean/stddev z-score threshold |
| **Schema drift detection** | Automatic, diffed against last-known schema | Diffed against last-known schema (reuses `mini_iceberg`'s schema JSON) |
| **Lineage-aware alerting** | Traces an anomaly to downstream-affected assets | Uses `mini-lineage`'s graph to list downstream-affected models |

The "did anything break, and who does it affect" layer sitting on top of
everything else — pairs with `mini-airflow` (pipelines to watch),
`mini_iceberg`/`mini-dbt` (tables to watch), and `mini-lineage` (group 06,
for blast-radius).

---

### **Phase 1: Freshness Monitoring**

* **Expected cadence:** For each monitored table, declare how often it's
  expected to update (e.g. "daily by 6am").
* **Freshness check:** Compare the table's actual last-updated time (a
  `mini_iceberg` table's latest snapshot timestamp, for instance) against
  the expected cadence, and flag it stale if overdue.
* **Alert fatigue, deliberately induced:** Set an unrealistically tight
  cadence on a normal table and watch false alerts fire — this is the
  actual, most common failure mode of freshness monitoring in production
  (thresholds set once at rollout, never revisited as real pipeline
  timing drifts).

### **Phase 2: Volume Anomaly Detection**

* **Historical row-count tracking:** Record each table's row count (or
  row-count delta per load) over time.
* **Z-score alerting:** Flag a load as anomalous if its row count is more
  than N standard deviations from the trailing mean — implement this, then
  feed it a table with a real weekly seasonality pattern (e.g. weekend
  volume drops) and watch it false-positive every weekend until you
  account for seasonality.
* **Fix the seasonality blind spot:** Compare against "same day of week,
  trailing N weeks" instead of a flat trailing window, and re-run the same
  test.

### **Phase 3: Schema Drift and Lineage-Aware Alerts**

* **Schema diff:** On each load, compare the current schema (reusing
  `mini_iceberg`'s `schema_to_json` shape) against the last known one, and
  flag additions/removals/type changes.
* **Blast-radius alerting:** Given `mini-lineage`'s (group 06) dependency
  graph, turn "table X's schema changed" into "table X changed, which
  affects these 6 downstream dbt models and this 1 dashboard" — the
  difference between a raw alert and an actionable one.

### **What this exposes about real tools**

Every observability tool's hardest problem isn't detection — it's the
false-positive rate, and that problem is *always* a statistics problem
(seasonality, trend, insufficient history) dressed up as a monitoring
problem. Having built a naive z-score alert and personally watched it cry
wolf every weekend is what makes "our data observability tool is too
noisy, nobody reads the alerts anymore" a diagnosable, fixable statement
instead of an accepted cost of doing monitoring.
