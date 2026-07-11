### **Project Scope: Real Shuffle Services (Spark) vs. Mini-Shuffle**

| Feature | Real Shuffle (Spark) | Mini-Shuffle (Python) |
| --- | --- | --- |
| **Partitioning** | Hash, range, or custom partitioners | Hash + range partitioning |
| **Spill handling** | Spills to local disk when memory exceeded, external sort-merge | Same: spill-to-disk past a memory threshold |
| **Transfer** | Network fetch between executors, external shuffle service option | Local files, simulating network transfer with a fetch API |
| **Fault tolerance** | Recompute lost map output from lineage | Recompute lost map output from a stored task DAG |

The data-movement primitive underneath `mini-spark-core` (group 09) — build
this first, since that capstone assumes it exists.

---

### **Phase 1: The Map Side**

* **Partition function:** Given N output partitions and a key, decide
  which partition a record belongs in (hash-based first, since it's the
  simplest correct choice).
* **Map-side write:** Each "map task" processes an input split and writes
  one output file per destination partition — so M map tasks each produce
  N files, for M×N total shuffle files (this quadratic-ish file count is
  a real, famous Spark pain point at high partition counts — reproduce it
  by cranking M and N up and counting files).
* **In-memory buffering with spill:** Buffer map output per partition in
  memory up to a threshold, then spill to disk and merge spills — this is
  what keeps a single map task from needing to hold its entire output in
  memory at once.

### **Phase 2: The Reduce Side**

* **Fetch:** Each "reduce task" fetches its partition's files from every
  map task that produced one (task R reads the R-th output file from
  every map task) — implement this as local file reads, but structure
  the API as if it were a network fetch (a function call that can fail
  independently per source).
* **External sort-merge:** If a reduce task's input (all fetched files
  combined) doesn't fit in memory, sort-merge it from disk instead —
  same fundamental technique as `mini-btree-kv`'s range scans, applied to
  external sorting instead of indexed lookup.
* **Measure shuffle cost directly:** For a fixed total data size, vary the
  number of map and reduce tasks and measure total bytes written +
  network-fetch-equivalent calls — this is the concrete cost "too many
  small partitions" imposes in real Spark jobs.

### **Phase 3: Fault Tolerance via Recomputation**

* **Lineage tracking:** Record, for each partition of shuffle output,
  which map task and input split produced it.
* **Simulate a lost map output:** Delete a map task's output files
  mid-job (simulating a node failure) and have the reduce side detect the
  missing fetch, then trigger *just that map task* to re-run from its
  original input — not the whole job.
* **Compare to full-job restart:** Measure recomputation cost for "re-run
  one lost map task" vs. "re-run the entire job from scratch" at
  different job sizes — this is precisely why lineage-based recovery
  (Spark's actual mechanism) beats checkpoint-the-whole-job approaches at
  scale.

### **What this exposes about real tools**

"Spark job is slow because of shuffle" is the single most common real-world
diagnosis, and it's almost always one of two things you'll have measured
directly here: too many small partitions (file-count and fetch-count
overhead dominates) or too few large ones (spill-to-disk dominates).
Having built the M×N file explosion and the spill path yourself turns
"reduce your shuffle partitions" from advice you follow into a tradeoff you
can size correctly for a specific job.
