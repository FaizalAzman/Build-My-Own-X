### **Project Scope: Real Spark Core vs. Mini-Spark-Core**

| Feature | Real Spark Core | Mini-Spark-Core (Python) |
| --- | --- | --- |
| **Cluster manager** | YARN/Kubernetes/Standalone | A fixed set of local worker processes |
| **Scheduling** | DAG scheduler (stages) + task scheduler (tasks within a stage) | Same two-level scheduling, simplified |
| **Fault tolerance** | Lineage-based recomputation (RDD lineage) | Same, via `mini-shuffle`'s (group 05) lineage tracking |
| **Data movement** | Shuffle service, in-memory + disk spill | `mini-shuffle` directly |

**A capstone**: this project's entire point is combining primitives you
already built — `mini-shuffle` (group 05) for data movement,
`mini-raft`/`mini-coordination-service` (group 05) for driver/worker
coordination — into the thing they were always building toward.

---

### **Phase 1: Driver/Executor Architecture**

* **A driver process:** Accepts a job (a chain of transformations),
  builds an execution plan, and dispatches tasks to workers — this is the
  "brain" that never processes data itself, only coordinates.
* **Worker processes:** Long-running processes that receive tasks (a
  function + a data partition), execute them, and report results/status
  back to the driver — implement this as separate local processes
  communicating over sockets/RPC, not just Python threads, to actually
  face serialization and network-failure concerns.
* **Task serialization:** A task (a closure over some function plus its
  input partition reference) has to be sent to a worker process — hit the
  real, famous Spark pain point directly: what happens when a closure
  captures something unpicklable (a database connection, an open file
  handle) and has to cross a process boundary.

### **Phase 2: The DAG Scheduler and Stages**

* **Narrow vs. wide transformations:** A `map` doesn't require data
  movement between partitions (narrow); a `groupBy`/`join` does (wide,
  requiring a shuffle). Classify your supported operations into these two
  categories — this classification *is* what determines stage boundaries.
* **Stage boundaries at shuffles:** Split a job's transformation chain
  into stages, cutting a new stage every time a wide transformation
  (shuffle) is needed — using `mini-shuffle` (group 05) as the actual data
  movement mechanism between stages.
* **Task parallelism within a stage:** Within one stage, tasks for
  different partitions have no dependencies on each other and can run
  concurrently across workers — implement this and measure wall-clock
  time with 1 worker vs. N workers on the same job.

### **Phase 3: Fault Tolerance via Lineage**

* **RDD lineage:** Track, for each partition of data at any point in the
  pipeline, the exact sequence of transformations (and source partitions)
  that produced it — not the data itself, just the recipe to reproduce it.
* **Recompute on worker failure:** Kill a worker mid-job and have the
  driver detect the missing task result, then re-schedule *just that
  task* on a surviving worker, using lineage to know exactly what
  computation to redo — directly reusing `mini-shuffle`'s Phase 3
  recomputation mechanism, now at the level of a full multi-stage job
  instead of a single shuffle.
* **Compare recomputation cost against checkpointing:** For a job with a
  long transformation chain, measure recompute-from-lineage cost vs. what
  it would cost to checkpoint intermediate results at every stage instead
  — this is the actual tradeoff behind Spark's `.persist()`/`.checkpoint()`
  API decisions.

### **What this exposes about real tools**

"Spark is fault-tolerant" is specifically a bet that recomputation from
lineage is usually cheaper than replicating or checkpointing every
intermediate result — a bet that stops paying off for very long
transformation chains or very expensive stages, which is exactly why
`.persist()`/`.checkpoint()` exist as manual escape hatches. Having built
the lineage-recompute path yourself and measured where it gets expensive
is what turns "should I checkpoint this DataFrame" from a guess into a
calculation.
