### **Project Scope: Real DMS (AWS DMS/Debezium-based migration tooling) vs. Mini-DMS**

| Feature | Real DMS | Mini-DMS (Python) |
| --- | --- | --- |
| **Initial load** | Parallelized full-table copy with consistent snapshot | Single-threaded full-table copy at a snapshot LSN |
| **Ongoing replication** | CDC-based, same mechanism as Debezium/AWS DMS | Reuses `mini-cdc` (group 03) directly |
| **Schema mapping** | Type conversion rules across engines (e.g. Postgres → MySQL) | A configurable type-mapping table |
| **Cutover** | Validation + a coordinated switch of the application's connection | A validation report + manual cutover step |

Builds directly on `mini-cdc` (group 03) — that project reads a database's
change stream; this one uses it to move an entire database from one engine
to another with minimal downtime.

---

### **Phase 1: Full Load with Schema Mapping**

* **Type mapping table:** A declarative mapping from source types to
  target types (e.g. Postgres `timestamptz` → MySQL `datetime`, noting
  where this loses timezone information — a real, common DMS gotcha worth
  hitting directly).
* **Consistent full load:** Using the same "note the LSN, then read"
  technique as `mini-cdc`'s Phase 2, copy every row of every source table
  into the target at a known consistent point.
* **Handle type-mapping failures:** Deliberately include a column whose
  value doesn't fit the target type's mapping (e.g. a source integer
  exceeding the target type's range) and decide — and implement — a
  policy: fail the load, truncate, or null it out, and log which happened.

### **Phase 2: Change Application**

* **Stream changes via `mini-cdc`:** From immediately after the full
  load's snapshot LSN, apply each subsequent insert/update/delete to the
  target, translating types the same way as Phase 1.
* **Ordering within a transaction:** Multiple changes from the same
  source transaction must apply to the target in the same order (or
  atomically) — implement this and test it against a source transaction
  that updates the same row twice.
* **Replication lag tracking:** Measure and expose the gap between the
  source's current LSN and the target's last-applied LSN — the metric
  every real migration's go/no-go cutover decision hinges on.

### **Phase 3: Validation and Cutover**

* **Row-count and checksum validation:** Compare row counts and a simple
  per-table checksum (e.g. hash of sorted primary keys, or column sums)
  between source and target *while replication is still running* — and
  reason about why this can never show a perfect match during active
  replication (there's always some lag), only converge as lag approaches
  zero.
* **Cutover:** Once lag is acceptably near zero and validation passes,
  simulate stopping writes to the source, letting replication fully
  drain, and switching reads/writes to the target — the actual moment a
  real migration either succeeds cleanly or reveals a missed edge case.

### **What this exposes about real tools**

Database migrations fail almost exclusively at the type-mapping and
cutover-timing edges, never at "can it copy rows" — this project makes you
hit both directly: a type that silently loses precision across engines,
and the fact that "replication caught up" is a lag metric approaching zero
asymptotically, never a clean boolean. Understanding that a migration
project's real risk lives in those two specific places (not in the bulk
copy) is exactly the judgment that separates planning a smooth cutover
from an incident.
