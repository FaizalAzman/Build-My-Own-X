### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Consumers** | Finance reporting (daily, due by 06:00), ML features (hourly), and a customer-facing usage export that **drives invoices** | How datasets are tiered, and which SLOs each tier gets |
| **Last quarter's incidents** | (1) A bad dbt deploy silently doubled revenue for 2 days. (2) A cloud region outage stopped everything for 9 hours. (3) A source schema change set a column to NULL for a week, unnoticed. | What would have prevented, detected and recovered from each one |
| **Platform** | Iceberg tables on object storage, Airflow, dbt, Kafka, all in one region | Disaster recovery topology, and RPO/RTO per tier |
| **Team** | 8 data engineers, with an on-call rotation that is already tired | How much reliability you can afford to operate |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md),
plus a written walkthrough of the three incidents replayed against your design.

**Draws on:** `mini-airflow` (idempotency, retries, backfills),
`mini-data-observability` (freshness, volume, drift),
`mini-great-expectations` (blocking checks), `mini-data-contracts`,
`mini-iceberg` (time travel and snapshot rollback), `mini-object-store`
(replication), `mini-raft` (what high availability for metadata actually
requires).

In data, "reliability" usually means wrong data, not downtime. Wrong data is
worse than no data, because people act on it. A reliable data platform is
designed around **preventing, detecting and recovering from bad data**, and
only secondarily around keeping machines running.

---

### **Phase 1: SLOs and Tiers**

* **Tier the datasets:** For example, tier 0 means money moves on it
  (invoices, finance), tier 1 means a product or model depends on it, and
  tier 2 is everything else. Assign every dataset in the scenario to a tier.
* **Define SLIs and SLOs per tier,** covering freshness, completeness and
  correctness as well as uptime. Give each an error budget, and say what
  happens when the budget runs out.
* **Set RPO/RTO per tier.** Be explicit that disaster recovery must cover
  *metadata*: the catalog, orchestrator state and Kafka offsets. Data files
  on their own are not enough.

### **Phase 2: Prevent, Detect, Recover**

* **Prevent:** Use contracts on sources, CI that runs models against
  production-shaped data, and a **write-audit-publish** pattern: write to an
  Iceberg branch or staging snapshot, run blocking checks, and only then make
  it current. Explain where in your `mini-iceberg` model the "publish" step
  happens.
* **Detect:** Choose what observability watches per tier and what pages a
  human vs. what files a ticket. Use `mini-data-observability` to argue how
  you avoid alert fatigue on a tired rotation.
* **Recover:** Use snapshot rollback for bad writes and idempotent backfills
  for bad logic, and keep sources replayable (Kafka retention, raw-zone
  immutability). Decide how long raw data must be kept for recovery to be
  possible at all.
* **DR topology:** Compare backup and restore, a warm standby in a second
  region, and active-active. Price each option, then match tiers to options.
  Not everything deserves the same recovery target.

### **Phase 3: Replay the Incidents**

For each of last quarter's three incidents, write the timeline under your
design: when it is prevented or detected, who is told, the blast radius
(found via lineage), how it is recovered, and how long it takes. Be honest
about any incident your design would *still* not catch.

### **Constraint-change round**

1. Invoicing moves from daily to real-time usage billing.
2. Tier 0 RTO drops to **1 hour**, including a full region loss.
3. The team shrinks to 4 engineers.

### **What this trains**

Treating correctness as the main reliability concern, and spending a
limited reliability budget unevenly, on purpose, according to what each
dataset is worth. It also trains writing incident replays, which make a
design review concrete.
