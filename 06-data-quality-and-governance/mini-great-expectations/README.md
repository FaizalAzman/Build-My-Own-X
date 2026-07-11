### **Project Scope: Real Great Expectations vs. Mini-Great-Expectations**

| Feature | Real Great Expectations | Mini-Great-Expectations (Python) |
| --- | --- | --- |
| **Expectations** | 50+ built-in (`expect_column_values_to_be_between`, etc.) | A core set: not-null, unique, range, regex-match, referential |
| **Execution engines** | Pandas, Spark, SQL (via SQLAlchemy) | Pandas, plus a `mini_iceberg`-backed table adapter |
| **Result store** | JSON result documents, "data docs" HTML reports | JSON result documents |
| **Integration** | Checkpoints run as part of orchestrated pipelines | Runs as a `mini-airflow` (group 04) task |

The assertion engine `mini-dbt`'s tests (group 04) are a restricted special
case of — build this to understand the general mechanism, then notice how
much of dbt's testing feature is "the same idea, SQL-shaped."

---

### **Phase 1: Core Expectations**

* **Row-level expectations:** `not_null`, `unique`, `values_between(min,
  max)`, `matches_regex` — each takes a column and returns which rows (if
  any) violate it, not just pass/fail.
* **Table-level expectations:** `row_count_between(min, max)`,
  `columns_match_set({...})` — assertions about the table as a whole
  rather than individual rows.
* **A result object:** Every expectation run produces a structured result
  — expectation type, pass/fail, and (for failures) the actual offending
  values/count, not just a boolean. This is what makes a failed check
  debuggable instead of just alarming.

### **Phase 2: Referential and Cross-Table Expectations**

* **Referential integrity:** `expect_column_values_to_exist_in(other_table,
  other_column)` — e.g. every `customer_id` in `orders` exists in
  `customers`. This requires reading two tables, not one, and is exactly
  the kind of check a single-table schema constraint can't express.
* **Distributional expectations:** `expect_column_mean_to_be_between(...)`
  or a simple KL-divergence-style check against a reference distribution —
  catching "the data is still well-typed and non-null, but the values
  have drifted" (e.g. a currency field silently switching from USD cents
  to USD dollars).

### **Phase 3: Suites and Checkpoints**

* **Expectation suites:** Group related expectations for a table into one
  named suite, run together, with an overall pass/fail.
* **Checkpoint integration:** Run a suite as a `mini-airflow` (group 04)
  task immediately after a table loads, and fail the DAG run (blocking
  downstream tasks) if the suite fails — connecting data quality directly
  to pipeline control flow, not just a passive report nobody reads.

### **What this exposes about real tools**

The gap between "we have data quality checks" and "our data quality checks
actually prevent bad data from propagating" is entirely about whether a
failed check *blocks* downstream execution (Phase 3) or just logs a
warning someone might read later. Building the checkpoint-blocks-the-DAG
integration yourself is what makes that distinction concrete — a data
quality suite with no enforcement teeth is documentation, not quality
control.
