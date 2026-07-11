### **Project Scope: Real ELT Connectors (Fivetran/Airbyte) vs. Mini-ELT-Connector**

| Feature | Real ELT Connectors | Mini-ELT-Connector (Python) |
| --- | --- | --- |
| **Source diversity** | Hundreds of pre-built API/DB connectors | A generic HTTP/REST connector framework + one concrete example |
| **Incremental extraction** | Per-source cursor strategies (timestamp, auto-increment ID, cursor token) | Timestamp-based and ID-based cursors |
| **Schema drift handling** | Auto-detects and evolves the destination schema | Detects drift, auto-adds new columns, flags removed ones |
| **Failure recovery** | Checkpointed, resumable from last successful cursor | Checkpointed to a local file, resumable |

The generalized ingestion framework `mini-cdc` (group 03) is one specific
(log-based) strategy for — this project covers the more common case:
polling an API or table on an interval instead of streaming a WAL.

---

### **Phase 1: A Generic Connector Interface**

* **The extract/load contract:** Define a small interface any source
  must implement: `get_cursor_field()`, `extract(since_cursor)` (returns
  records + the new cursor value), and `get_schema()`.
* **A concrete connector:** Implement one real one against a paginated
  REST API (even a simple one you stand up yourself) — extract every page
  until exhausted, tracking the cursor as you go.
* **Load into `mini_iceberg`:** Take extracted records and `append()` them
  into a `mini_iceberg` table, reusing that project's write path directly.

### **Phase 2: Incremental Extraction and Checkpointing**

* **Cursor-based incremental sync:** Instead of re-extracting everything
  every run, request only records since the last successful run's cursor
  value (a timestamp or an incrementing ID field).
* **Checkpoint after each successful batch, not just at the end:** If a
  sync of 100 pages fails on page 73, a naive "checkpoint only on full
  success" design forces re-extracting pages 1-72 unnecessarily on retry —
  implement per-batch checkpointing and measure the difference in
  redundant work after a simulated mid-sync failure.
* **At-least-once, and the dedup it requires:** A retry after a partial
  failure can re-extract and re-load some already-loaded records — decide
  and implement a dedup strategy on load (e.g. upsert by primary key)
  rather than assuming extraction is exactly-once.

### **Phase 3: Schema Drift**

* **Detect drift:** Compare the source's current schema (from
  `get_schema()`) against what was last seen; a new field appearing is
  common and should auto-add a column to the destination.
* **Handle a removed or type-changed field:** Unlike a new field, these
  can't be safely auto-resolved (matching `iceberg/CASE_STUDY.md` §3's
  point about name-based schema matching) — implement this as a sync that
  pauses and flags for human review rather than guessing.

### **What this exposes about real tools**

The entire pitch of Fivetran/Airbyte-style tools is "we handle schema
drift and incremental sync so you don't have to write connector code" —
and Phase 2's checkpoint granularity plus Phase 3's drift-handling are
exactly the two places that pitch is hardest to deliver on well. Having
built a connector that gets checkpointing wrong first (full-sync-only) and
then fixed it is what lets you evaluate a vendor connector's actual
resilience instead of trusting a marketing page's claim of "reliable
incremental sync."
