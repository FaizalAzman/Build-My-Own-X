### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Current state** | On-prem Hadoop: ~1.2 PB in Hive tables, ~3,000 scheduled jobs, ~400 tables consumed by BI. A separate on-prem MPP warehouse runs finance reporting. | Which tables and jobs to migrate, rebuild or retire |
| **Target** | Cloud. Leadership is open to an Iceberg lakehouse, a managed cloud warehouse, or both. | The target platform, with the reasoning behind it |
| **Deadline** | The data center lease ends in **14 months** | Migration strategy and sequencing |
| **Team** | 12 data engineers, who must also keep the current platform running | What gets automated vs. done by hand, and what's out of scope |
| **Network** | 10 Gbps link to the cloud provider | How the bulk data physically gets there |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md),
with a sequenced migration plan.

**Draws on:** `mini-dms` (full load + CDC, validation, cutover), `mini-iceberg`
(the target table format), `mini-lineage` (dependency order),
`mini-data-contracts`, `mini-object-store`, `mini-airflow` (re-pointing jobs).

Migrations are where architecture meets reality. The target design is
usually the easy part. The hard parts are the order of moves, running two
platforms at once, and proving the new numbers match the old ones.

---

### **Phase 1: Inventory and Back-of-Envelope**

* **Find out what's actually used:** Use query logs and lineage to classify
  every table and job as *migrate as-is*, *rebuild*, or *retire*. Expect a
  large fraction to be unused. Each one you retire is work you don't do.
* **Transfer time:** 1.2 PB over 10 Gbps is roughly 1.2×10¹⁵ × 8 / 10¹⁰ ≈
  10⁶ s ≈ 11 days *at full line rate*. At a realistic 30–50% utilisation it
  takes 3–5 weeks. Decide between the network link, a physical transfer
  appliance, or migrating only hot data and leaving cold data for later.
* **Dependency graph:** Build the DAG of tables and jobs from lineage. Sources
  must move before their consumers, or consumers must read across both
  platforms for a while.

### **Phase 2: Target and Strategy**

* **Choose the target:** an Iceberg lakehouse (with Spark/Trino), a managed
  cloud warehouse, or a split (lakehouse for raw and ML, warehouse for finance
  and BI). Fill in the decision section from your `mini-iceberg` case study
  and cite it.
* **Choose the strategy:** big-bang, migration by domain (strangler pattern),
  or dual-running with reconciliation. Justify the choice against the 14-month
  deadline and the 12-person team.
* **Keeping both platforms in sync:** During migration, both platforms need
  current data. Choose between CDC from sources into both platforms, running
  the jobs on both, or replicating outputs from old to new. Each one costs
  something different in compute, complexity and correctness risk.

### **Phase 3: Validation, Cutover, and Rollback**

* **Validation at scale:** Row counts, checksums and metric parity, on tables
  too large to diff row by row. What tolerance is acceptable, and who signs
  off on it?
* **Semantic drift:** Hive and the target engine disagree on timestamp time
  zones, integer division and NULL ordering. Find these differences before
  finance does.
* **Cutover and rollback:** Per domain, define the cutover steps, the point of
  no return, and the rollback plan up to that point.
* **The long tail:** About 200 jobs have no known owner. What's the policy?

### **Constraint-change round**

1. The deadline is cut to **6 months**.
2. Finance requires 3 months of parallel running with zero variance before
   cutting over.
3. The cloud egress/transfer budget is halved.

### **What this trains**

Sequencing and risk management for large changes: deciding what not to
migrate, putting dependency order ahead of team convenience, and turning
"the numbers match" into a defined, signed-off acceptance criterion instead
of a hope.
