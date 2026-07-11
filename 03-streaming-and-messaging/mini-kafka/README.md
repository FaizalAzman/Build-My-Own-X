### **Project Scope: Real Kafka vs. Mini-Kafka**

| Feature | Real Kafka | Mini-Kafka (Python) |
| --- | --- | --- |
| **Storage** | Append-only log segments, page-cache-optimized | Append-only log segments, plain files |
| **Replication** | ISR (in-sync replica) protocol, configurable acks | Single leader, one synchronous follower |
| **Consumer offsets** | Stored in an internal `__consumer_offsets` topic | Stored in a local JSON file per consumer group |
| **Partitioning** | Configurable partitioner, key-based hashing | Key-based hashing (Python's `hash()`) |
| **Delivery guarantees** | At-least-once, exactly-once (idempotent producer + transactions) | At-least-once only |

This is the foundation for `mini-stream-processor` and `mini-cdc` (same
group) — both assume a log-based broker to publish into.

---

### **Phase 1: Log Segments and Partitions**

* **Append-only segments:** A topic-partition is a directory of segment
  files; producing a message appends to the active (newest) segment, never
  rewrites an old one.
* **Offsets:** Each message gets a monotonically increasing offset within
  its partition — the position it was written at, not a value the producer
  chooses.
* **Partitioning:** Route a produced message to `hash(key) % num_partitions`
  so all messages with the same key land in the same partition (this is
  what gives per-key ordering guarantees).

### **Phase 2: Consumers and Consumer Groups**

* **Sequential reads from an offset:** A consumer reads forward from a
  given offset, never randomly — mirroring how a real segment file is
  read (sequential I/O, not random access).
* **Consumer groups:** Partitions within a topic are divided among
  consumers in the same group, so each partition is only read by one
  consumer at a time (this is what lets you scale consumption
  horizontally without duplicate processing).
* **Offset commits:** A consumer periodically persists "I've processed up
  to offset N" — and on restart, resumes from there, not from the
  beginning.

### **Phase 3: Replication and Failure**

* **Leader + follower:** Each partition has one leader (handles all
  reads/writes) and at least one follower that replicates the leader's
  log.
* **Kill the leader mid-stream:** Simulate a leader crash and promote the
  follower — verify no acknowledged message is lost, and reason about
  which *unacknowledged* messages might be.
* **`acks` configurability:** Implement both "acknowledge after leader
  write" (fast, can lose data on leader crash) and "acknowledge after
  follower replication" (slower, safer) — and measure the latency
  difference directly.

### **What this exposes about real tools**

"Kafka guarantees at-least-once delivery" sounds simple until you've
implemented the specific mechanism (offset commits can happen before *or*
after processing completes, and which order you pick determines whether a
crash causes a duplicate or a loss) — and "exactly-once" is a much bigger
lift (idempotent producers, transactional writes) that this project
deliberately stops short of, so you feel exactly where the complexity
jumps.
