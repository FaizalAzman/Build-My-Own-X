### **Project Scope: Real dbt vs. Mini-dbt**

| Feature | Real dbt | Mini-dbt (Python) |
| --- | --- | --- |
| **Models** | `.sql` files with Jinja templating | `.sql` files with `{{ ref('other_model') }}` only |
| **Dependency graph** | Built from `ref()`/`source()` calls, DAG-ordered execution | Same idea, simpler resolution |
| **Materializations** | View, table, incremental, ephemeral | View + table only |
| **Testing** | Built-in + custom generic tests (`unique`, `not_null`, etc.) | A handful of built-in assertion tests |
| **Compilation** | Jinja → raw SQL, target-database-aware | Simple string substitution → raw SQL |

Pairs naturally with `mini-airflow` (same group) as the thing being
orchestrated — dbt compiles and runs SQL; something like Airflow decides
*when*.

---

### **Phase 1: `ref()` and the Dependency Graph**

* **Model files:** A folder of `.sql` files, each one query, referencing
  other models via `{{ ref('model_name') }}` instead of a hardcoded table
  name.
* **Build the DAG:** Parse every model's `ref()` calls to build a
  dependency graph between models — this *is* the DAG, derived entirely
  from the SQL itself rather than declared separately (the core idea that
  distinguishes dbt from "just a folder of SQL scripts run in some order").
* **Topological run order:** Execute models in dependency order, same
  underlying problem as `mini-airflow`'s Phase 1, this time with the graph
  inferred from `ref()` calls instead of declared explicitly.

### **Phase 2: Compilation and Materialization**

* **`ref()` resolution at compile time:** Before executing, replace every
  `{{ ref('x') }}` with the actual resolved table/view name for the target
  environment — this separation (compile, then run) is what lets the same
  model file target dev/staging/prod without editing SQL.
* **Materializations:** Support `view` (wrap the query in `CREATE VIEW`)
  and `table` (run the query, write results into a real table) —
  implement both and compare: a view re-computes on every query, a table
  computes once and goes stale until rebuilt.

### **Phase 3: Testing**

* **Generic tests:** Implement `unique` and `not_null` as tests that
  compile to a `SELECT` that should return zero rows if the assertion
  holds — the exact mechanism real dbt tests use (a failing test is a
  non-empty result set, not a special test runtime).
* **Run tests as part of the DAG:** A model's tests run immediately after
  it builds, and downstream models don't run if their upstream's tests
  failed — connecting this project directly back to `mini-great-expectations`
  (group 06)'s broader assertion engine, at the specific point where SQL
  transformation and data quality checking meet.

### **What this exposes about real tools**

dbt's actual innovation isn't "SQL with templating" — it's making the
dependency graph a *derived* property of the SQL (from `ref()` calls)
rather than a separately maintained artifact, which is what keeps large
analytics codebases from drifting out of sync with their own
documentation. Building the `ref()` resolver yourself is what makes that
distinction — "the DAG is inferred, not declared" — click as a design
choice rather than a marketing description.
