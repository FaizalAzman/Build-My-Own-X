### **Project Scope: Real MPP Warehouses (Snowflake/Redshift/Trino) vs. Mini-Distributed-Warehouse**

| Feature | Real MPP Warehouses | Mini-Distributed-Warehouse (Python) |
| --- | --- | --- |
| **Storage** | Separated storage/compute, object-store-backed | `mini-object-store` (group 05) |
| **Coordination** | A coordinator/leader node per cluster (or query) | `mini-coordination-service` (group 05) |
| **Query planning** | Cost-based, distributed-aware (where does each operator run) | `mini-query-engine` + `mini-cbo` (group 02) |
| **Data movement** | Network exchange operators between compute nodes | `mini-shuffle` (group 05) |
| **Catalog** | Iceberg/Delta/Hive-compatible table format | `mini_iceberg` directly |

**The final capstone**: every other project in this curriculum is a
component of this one. There's no new theory here — the entire exercise is
integration, and integration at this scale surfaces problems none of the
individual pieces ever hit alone.

---

### **Phase 1: Distributed Storage + Catalog**

* **Tables backed by `mini-object-store`:** Point `mini_iceberg`'s data
  files at `mini-object-store` instead of the local filesystem — this
  alone will surface latency and failure-handling assumptions
  `mini_iceberg` never had to make when reads/writes were local disk
  calls.
* **A cluster-wide catalog:** Run `mini_iceberg`'s `Catalog` behind
  `mini-coordination-service` so every compute node in the cluster agrees
  on which snapshot is current — the multi-node version of the exact
  single-writer guarantee `mini-iceberg/CASE_STUDY.md` §6 discussed.

### **Phase 2: Distributed Query Execution**

* **A coordinator node:** Receives a query, uses `mini-cbo` to plan it,
  and decides which parts of the plan run on which compute nodes.
* **Exchange operators:** Where the plan requires data to move between
  nodes (a distributed join, a global aggregation), insert an "exchange"
  operator backed by `mini-shuffle`'s data-movement mechanism, now
  crossing real network boundaries between separate processes/machines
  instead of local files.
* **Partial aggregation:** For a `GROUP BY` across nodes, aggregate
  locally on each node first, then combine partial results at a final
  node — implement this and measure how much less data crosses the
  network compared to shuffling all raw rows to one place first.

### **Phase 3: Failure and Elasticity**

* **Node failure mid-query:** Kill a compute node partway through a
  distributed query and recover using the same lineage-based
  recomputation approach as `mini-spark-core` (this group) — this is
  where you find out whether your Phase 1/2 design actually composes with
  a fault-tolerance mechanism built for a different project, or needs
  rework.
* **Add a node mid-cluster-lifetime:** Bring up a new compute node and
  have the coordinator start routing work to it — the elasticity
  property that's the entire commercial pitch of cloud MPP warehouses
  (Snowflake's "add a warehouse size" is this, dressed up).
* **End-to-end benchmark:** Run the same analytical query (a join +
  aggregation over a `mini_iceberg` table) at 1 node, 2 nodes, and 4
  nodes, and plot speedup — and find where it stops being linear, and
  reason concretely (using what you measured in `mini-shuffle`) about why.

### **What this exposes about real tools**

This is the project that finally makes "why is Snowflake so expensive at
scale" and "why did adding more nodes barely help this specific query"
answerable from first principles instead of vendor benchmarks: the
plateau you'll measure in Phase 3 is shuffle/exchange cost dominating once
compute is no longer the bottleneck — the same shuffle cost curve you
first measured in isolation in `mini-shuffle`, now determining the shape
of an entire distributed warehouse's scalability. Reaching this project
having built everything underneath it is the difference between reciting
"MPP warehouses scale compute independently of storage" and being able to
say exactly where that scaling stops paying off and why.
