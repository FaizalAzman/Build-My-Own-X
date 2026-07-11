### **Project Scope: Real Object Stores (S3/GCS/HDFS) vs. Mini-Object-Store**

| Feature | Real Object Stores | Mini-Object-Store (Python) |
| --- | --- | --- |
| **Data placement** | Erasure coding or N-way replication across racks/AZs | N-way replication across local processes |
| **Metadata** | Separate metadata service (S3's internal indexing, HDFS NameNode) | A metadata service backed by `mini-raft` |
| **Consistency** | Strong read-after-write (modern S3); HDFS is strongly consistent | Strong, via quorum reads/writes |
| **API** | REST (S3-style `PUT`/`GET`/`DELETE` on keys) | Same REST-shaped API, local implementation |

Builds directly on `mini-raft` (same group) for its metadata service — this
is the project where consensus stops being an abstract exercise and starts
answering "which replica is authoritative for this object."

---

### **Phase 1: Chunked Storage on One Node**

* **Object → chunks:** Split a large object into fixed-size chunks on
  write, and store each chunk as a file; reassemble on read. (This is what
  lets a real object store handle objects far larger than any single
  disk's convenient I/O unit, and what makes partial replication of a huge
  object possible.)
* **A flat key-value API:** `put(key, bytes)`, `get(key)`, `delete(key)` —
  no directories, no hierarchy, exactly S3's actual data model (the
  "folder" appearance in S3 UIs is purely a key-naming convention, not a
  real structure).

### **Phase 2: Replication**

* **N-way replication:** Each chunk is written to multiple nodes; a write
  only succeeds once a quorum (e.g. 2 of 3) acknowledge it.
* **Metadata service:** Use `mini-raft` to run a small, strongly-consistent
  service mapping `key → [list of chunk locations]` — this is conceptually
  HDFS's NameNode, and it's exactly why `mini-raft` had to exist first (a
  metadata service that disagreed with itself about where an object's
  chunks live would be far worse than one that's simply down).
* **Read from any healthy replica:** A read only needs one healthy replica
  per chunk, not all of them — verify reads still succeed with one
  replica node killed.

### **Phase 3: Failure and Repair**

* **Detect a dead replica:** A node that stops heartbeating gets marked
  unhealthy; the metadata service should stop routing new reads to it.
* **Re-replication:** When a chunk drops below its target replication
  factor (a node died), copy it from a healthy replica to a new node to
  restore the target count — this is the mechanism that makes replicated
  storage self-healing rather than merely fault-tolerant-once.
* **Simulate a full rack/AZ failure:** Kill enough nodes at once to lose
  a majority for some chunks and observe (correctly) that those specific
  objects become unavailable, while others (with surviving quorums)
  remain readable — real object stores' replica *placement* strategy
  (rack/AZ-aware) exists specifically to make this scenario rare.

### **What this exposes about real tools**

"S3 has eleven nines of durability" is a replication-and-repair-loop
guarantee, not a single-copy hardware guarantee — and the actual
engineering is almost entirely in the metadata layer (knowing precisely
where every chunk of every object lives, and continuously repairing
towards the target replication factor) rather than the storage layer
itself. Building the metadata service on top of `mini-raft` is what makes
that visible: durability is a consensus problem wearing a storage
costume.
