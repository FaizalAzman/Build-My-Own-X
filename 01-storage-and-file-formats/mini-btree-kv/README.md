### **Project Scope: Real B-Tree Engines (Postgres/MySQL/SQLite) vs. Mini-Btree-KV**

| Feature | Real B-Tree Engine | Mini-Btree-KV (Python) |
| --- | --- | --- |
| **Node size** | Tuned to disk page size (4-16KB) | Fixed, configurable page size |
| **Concurrency** | Latch-based or MVCC page access | Single-threaded |
| **Crash recovery** | WAL + checkpointing | WAL, no checkpointing |
| **Variable-length keys** | Yes, with overflow pages | Fixed-size keys for simplicity |
| **Rebalancing** | Node merges on delete-heavy workloads | Splits on insert only (no merge-on-delete) |

Build this alongside `mini-lsm` (also in this group) — same interface
(`get`/`put`/`delete`), opposite internal structure. The point isn't either
project alone; it's having both to compare.

---

### **Phase 1: In-Memory B-Tree**

* **Node structure:** Fixed branching factor, keys kept sorted within a
  node, each internal node holding pointers to child nodes.
* **Search:** Binary-search within a node, descend to the correct child —
  O(log n) with a very small constant (each "step" reads many keys at
  once, unlike a binary search tree).
* **Insert with splits:** When a node overflows its capacity, split it and
  push the median key up to the parent — implement this recursively up to
  a possible new root.

### **Phase 2: Disk-Backed Pages**

* **Page-based storage:** Each node becomes a fixed-size "page" on disk,
  addressed by page number (not a Python object reference). Reads/writes
  go through a `read_page(n)`/`write_page(n, data)` abstraction.
* **A free list:** Track deleted/reusable page numbers so the file doesn't
  grow unboundedly as you split and (eventually) merge nodes.
* **WAL for crash safety:** Before mutating a page, log the change; on
  restart, replay the log to reach a consistent state — the same idea as
  `mini-lsm`'s WAL, now protecting in-place page writes instead of an
  append-only structure.

### **Phase 3: Range Scans and Comparison Benchmarks**

* **Range queries:** `scan(start_key, end_key)` — walk the leaf level via
  sibling pointers (a B+tree detail: leaves are linked so a range scan
  doesn't need to walk back up the tree between adjacent leaves).
* **Head-to-head benchmark against `mini-lsm`:** Same workload (random
  point lookups, sequential writes, random writes, range scans) against
  both engines. Plot write throughput and read latency for each.

### **What this exposes about real tools**

A B-tree keeps data sorted in place, so range scans and point lookups are
both cheap — at the cost of writes being more expensive (in-place mutation,
occasional page splits/rebalancing) than an LSM tree's pure sequential
append. This is the actual reason OLTP databases (order-heavy, point-lookup
workloads) default to B-trees while wide-column/write-heavy stores default
to LSM — a decision that's easy to state and hard to *justify* without
having measured both yourself.
