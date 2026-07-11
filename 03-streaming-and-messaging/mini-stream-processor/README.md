### **Project Scope: Real Stream Processors (Flink/Kafka Streams) vs. Mini-Stream-Processor**

| Feature | Real Stream Processor | Mini-Stream-Processor (Python) |
| --- | --- | --- |
| **State backend** | RocksDB-backed, checkpointed to durable storage | In-memory dict, checkpointed to local disk |
| **Windowing** | Tumbling, sliding, session windows | Tumbling + sliding windows |
| **Time semantics** | Event time with watermarks, processing time | Event time with a simple watermark heuristic |
| **Fault tolerance** | Distributed snapshots (Chandy-Lamport-style) | Periodic full-state checkpoint to disk |
| **Exactly-once** | Two-phase commit with the sink | Best-effort, at-least-once |

Reads from `mini-kafka` (same group) as its input source — build that one
first, or stub a simple in-memory queue as a placeholder input.

---

### **Phase 1: Tumbling Windows on Event Time**

* **Windowed aggregation:** Group incoming `(event_time, key, value)`
  records into fixed-size, non-overlapping time windows (e.g. 1-minute
  tumbling windows), and compute an aggregate (count/sum) per window per
  key.
* **The late-data problem:** Feed in events out of event-time order (a
  record with an earlier `event_time` arriving after one with a later
  `event_time` — completely normal over a real network) and observe what
  happens to a window that's already been "closed" without special
  handling.

### **Phase 2: Watermarks**

* **A watermark heuristic:** Track "the event time below which we believe
  no more data will arrive" (e.g. `max_event_time_seen - allowed_lateness`)
  and only finalize/emit a window once the watermark passes its end time.
* **Tune the lateness bound:** Too tight, and you drop genuinely late (but
  valid) data; too loose, and you hold every window open far longer than
  necessary, increasing memory and result latency. Measure both failure
  modes on the same out-of-order dataset.

### **Phase 3: Checkpointing and Recovery**

* **Periodic state checkpoints:** Serialize in-flight window state to disk
  on an interval, tagged with the highest input offset processed so far.
* **Crash and recover:** Kill the process mid-stream, restart from the last
  checkpoint, and replay input from the checkpointed offset — verify
  results match a run with no crash (mod some acceptable
  at-least-once duplication).

### **What this exposes about real tools**

Watermarks are the single most misunderstood concept in stream processing
because they encode a real, irreducible tradeoff — completeness vs.
latency — dressed up as a configuration knob. Having tuned that knob
yourself and watched both failure modes (dropped late data vs. stalled
results) is the difference between setting `allowedLateness` from a
tutorial's example value and actually reasoning about your own data's
out-of-orderness distribution.
