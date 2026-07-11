### **Project Scope: Real CDC (Debezium) vs. Mini-CDC**

| Feature | Real CDC (Debezium) | Mini-CDC (Python) |
| --- | --- | --- |
| **Source** | Database WAL/binlog (Postgres logical decoding, MySQL binlog) | Postgres logical replication slot |
| **Delivery** | Publishes to Kafka, schema registry integration | Publishes to `mini-kafka` |
| **Snapshotting** | Consistent initial snapshot + incremental streaming | Initial full-table read, then streaming |
| **Schema changes** | Detects and propagates DDL changes | Detects column add/drop, fails loudly on anything else |
| **Exactly-once** | LSN-based offset tracking for idempotent restarts | LSN-based offset tracking |

Feeds into `mini-kafka` (same group) as a producer — this is where "how does
data actually get *out* of an OLTP database and into the rest of this stack"
gets answered.

---

### **Phase 1: Reading the Write-Ahead Log**

* **Logical replication slot:** Set up a Postgres logical replication slot
  (`pgoutput` or `wal2json` plugin) and read raw change events off it —
  this is the same mechanism Postgres uses for physical replica streaming,
  repurposed to expose logical row changes instead of physical bytes.
* **Decode change events:** Parse each event into `(operation, table, before,
  after, lsn)` — insert/update/delete, the affected row's old and new
  values, and its log sequence number (LSN).
* **LSN as the offset:** Treat the LSN exactly like `mini-kafka`'s offsets —
  a monotonically increasing position you can checkpoint and resume from.

### **Phase 2: Initial Snapshot + Streaming Handoff**

* **Consistent snapshot:** Before streaming starts, take a full read of
  each tracked table *at a specific LSN* (Postgres lets you start a
  transaction and note its LSN, then read consistently from that point).
* **The handoff problem:** Any change that happens *during* the snapshot
  read must not be double-applied or lost when streaming picks up from the
  snapshot's LSN — reason through (and test) the race condition directly:
  what happens to a row updated while it's mid-scan.
* **Publish to `mini-kafka`:** Emit snapshot rows and streamed changes as
  the same event shape onto a topic, so downstream consumers can't tell
  (and shouldn't need to know) which phase produced a given event.

### **Phase 3: Schema Changes**

* **Detect a column add:** Alter the source table's schema mid-stream and
  make sure new events reflect it without restarting the connector.
* **Fail loudly on unsupported DDL:** A column *rename* or *type change* is
  exactly the kind of schema evolution `iceberg/CASE_STUDY.md` §3 discussed
  (name-based matching breaks silently) — deliberately make this project
  detect and hard-fail on such changes rather than silently corrupting
  downstream data.

### **What this exposes about real tools**

CDC's core value proposition — "capture every change without touching the
source database's write path" — only works because it reads a log the
database already durably writes for its own crash recovery. Understanding
that dependency is what tells you CDC's actual failure modes in
production: WAL retention running out during a long consumer outage,
replication slot buildup causing disk pressure on the *source* database,
and why schema changes are the operation most likely to break a running
pipeline.
