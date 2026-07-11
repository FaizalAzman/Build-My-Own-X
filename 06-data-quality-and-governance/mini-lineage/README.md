### **Project Scope: Real Lineage Tools (OpenLineage/dbt docs) vs. Mini-Lineage**

| Feature | Real Lineage Tools | Mini-Lineage (Python) |
| --- | --- | --- |
| **Extraction** | SQL parsing + query-log scraping across many engines | SQL parsing of a single dialect (your `mini-query-engine`'s subset) |
| **Granularity** | Table-level and column-level | Both — table-level first, column-level as an extension |
| **Graph model** | Directed graph, often stored in a graph database | Directed graph, adjacency-list in memory/JSON |
| **Integration** | OpenLineage events emitted by orchestrators/engines | Consumed by `mini-data-catalog`/`mini-data-observability` |

Feeds `mini-data-catalog` and `mini-data-observability` (both this group) —
this is the project that turns "table X changed" into "here's exactly what
that affects."

---

### **Phase 1: Table-Level Lineage from SQL**

* **Parse `FROM`/`JOIN`:** Given a `CREATE TABLE AS SELECT ...` or a dbt
  model's SQL, extract every table referenced in `FROM`/`JOIN` clauses as
  upstream sources, and the table being created as the downstream output.
* **Build the graph:** A directed edge per (upstream → downstream)
  relationship; run this over every model in a `mini-dbt` project (group
  04) to build the full dependency graph — compare it against the `ref()`
  -based graph `mini-dbt` already builds internally; they should agree.

### **Phase 2: Column-Level Lineage**

* **Track column provenance through `SELECT`:** For `SELECT a, b + c AS d
  FROM t`, record that output column `d` derives from input columns `b`
  and `c` (and `a` passes through unchanged) — this requires actually
  parsing the select-list expressions, not just the `FROM` clause.
* **Track it through a `JOIN`:** Extend this so a column derived from a
  joined table correctly attributes to *that* table, not the base table —
  the detail that makes column lineage meaningfully harder than table
  lineage.
* **Break it on purpose:** Feed in a `SELECT *` and a subquery with a
  computed column referencing an aliased expression, and see where your
  parser's column tracking gets confused — production lineage tools get
  this wrong constantly for exactly these constructs.

### **Phase 3: Blast-Radius Queries**

* **Downstream traversal:** Given a table (or specific column), return
  every downstream table/column that transitively depends on it — this is
  the query `mini-data-observability` (group 04) runs to turn a schema
  change into an actionable alert.
* **Upstream traversal (root-cause):** Given a broken table, walk
  *upstream* to find candidate root causes — the opposite direction,
  used for "why does this number look wrong" investigations instead of
  "what do I break if I change this."

### **What this exposes about real tools**

Column-level lineage is disproportionately harder than table-level lineage
— roughly linear vs. genuinely requiring a real SQL expression parser —
which is exactly why so many "lineage" features in commercial tools quietly
stop at table-level despite marketing suggesting otherwise. Having
attempted column-level parsing yourself, and watched it break on `SELECT *`
and computed-column joins, is what lets you correctly judge a vendor's
lineage claim instead of taking "we support column-level lineage" at
face value.
