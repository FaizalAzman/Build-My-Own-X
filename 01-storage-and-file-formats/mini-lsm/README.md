### **Project Scope: Real LSM Engines (RocksDB/Cassandra) vs. Mini-LSM**

| Feature | Real LSM Engine | Mini-LSM (Python) |
| --- | --- | --- |
| **Memtable** | Skip list / red-black tree, concurrent | Sorted dict, single-threaded |
| **Durability** | fsync'd WAL, group commit | Append-only WAL file, fsync per write |
| **Compaction** | Leveled, tiered, or hybrid strategies | Simple tiered (merge N same-size SSTables) |
| **Point lookups** | Bloom filters + block index per SSTable | Bloom filter + sparse index |
| **Concurrency** | MVCC, concurrent compaction | Single-threaded |

This is the direct write-optimized counterpart to `mini-btree-kv` (also in
this group) — build both, and the read/write tradeoff between them stops
being an abstract talking point.

---

### **Phase 1: Memtable + WAL**

* **In-memory sorted structure:** A `put(key, value)` goes into an
  in-memory sorted dict (memtable), not to disk directly.
* **Write-ahead log:** Before touching the memtable, append the write to a
  WAL file. On startup, replay the WAL to rebuild the memtable — this is
  what makes writes durable despite living in memory first.
* **Memtable flush:** When the memtable exceeds a size threshold, write it
  out as an immutable, sorted **SSTable** file, clear the memtable, and
  truncate the WAL.

### **Phase 2: SSTables and Reads**

* **SSTable format:** Sorted key-value pairs on disk, plus a sparse index
  (every Nth key's offset) so a lookup can binary-search the index instead
  of scanning the whole file.
* **Bloom filters:** A probabilistic "definitely not present" filter per
  SSTable, checked before doing any disk I/O for a key — the mechanism that
  makes point lookups in an LSM tree not O(number of SSTables).
* **Read path:** Check the memtable first, then SSTables newest-to-oldest
  (a key written more recently shadows an older value for the same key).

### **Phase 3: Compaction**

* **Tombstones:** A delete isn't an in-place removal — it's a special
  "tombstone" marker written like any other value, resolved at read time or
  compaction time. (You've seen this exact idea already: `mini_iceberg`'s
  compaction *omits* rather than deletes; here, a delete has to be
  positively recorded, since the LSM has no equivalent of "the manifest
  just doesn't mention it anymore" for a key that used to exist.)
* **Tiered compaction:** When you have N SSTables of similar size, merge
  them into one larger SSTable, dropping shadowed keys and resolved
  tombstones.
* **Measure write vs. read amplification:** Count actual bytes written to
  disk per logical write (write amplification) and files touched per
  lookup (read amplification) before and after compaction.

### **What this exposes about real tools**

LSM trees trade read cost for write cost: writes are always sequential
appends (fast), but a read might have to check several SSTables (slower
than a B-tree's single descent). This is *why* Cassandra/RocksDB dominate
write-heavy workloads and B-tree databases (Postgres, MySQL) dominate
read-heavy/point-lookup workloads — a fact usually stated as folklore but
rarely felt directly until you've built both and timed them yourself.
