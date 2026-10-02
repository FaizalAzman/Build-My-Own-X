### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Spend** | Cloud data platform bill of **$180k/month**, growing 8% month over month | The cost model, and how spend is attributed to teams and workloads |
| **Goal** | The CFO wants spend down **40% within two quarters** without breaking any SLA | Which levers to pull, in what order, at what risk |
| **Breakdown** | Compute 65% (BI dashboard refreshes 30% of compute, dbt full refreshes 25%, ad hoc 20%, ML extracts 25%), storage 15%, egress/cross-region 8%, streaming 12% | Which line items are actually controllable |
| **Observations** | 60% of tables not queried in 90 days. Median data file is 4 MB. Dashboards refresh every 15 minutes but are viewed about twice a day. | Which observations matter most |
| **Org** | Nobody owns cost today, and teams can't see their own spend | The guardrails that stop spend growing back |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md),
where §10 (Cost) is the main body and includes a ranked lever table.

**Draws on:** `mini-parquet` (file size, encoding, pruning), `mini-iceberg`
(compaction, snapshot expiry), `mini-cbo` + `mini-query-engine` (bytes
scanned), `mini-materialized-views` + `mini-dbt` (incremental vs. full
refresh), `mini-data-observability` (usage signals).

Cost is an architectural property, not just a finance concern. Every design
decision in the rest of this curriculum has a cost shape, and this exercise
makes you read the bill backwards to the decisions that caused it.

---

### **Phase 1: Build the Cost Model**

* **Unit economics:** Express spend as cost per unit of work: per TB
  ingested, per dashboard view, per dbt model run, per ML extract. A
  dashboard that refreshes 96 times a day for 2 views costs about 48 refreshes
  per view.
* **Attribution:** Design tagging and attribution so that each dollar maps to
  a team and a workload. Without this, every lever you pull is a guess.
* **Growth decomposition:** Is the 8% monthly growth driven by data volume,
  new workloads, or inefficiency compounding (for example, full refreshes over
  tables that keep growing)? These need different fixes.

### **Phase 2: Levers and Alternatives**

* **List every lever, with estimated savings, effort and risk.** For example:
  * incremental models instead of full refreshes;
  * refreshing dashboards on view or on schedule, instead of every 15 minutes;
  * pre-aggregated tables or materialized views;
  * compaction to fix 4 MB files (fewer files, better pruning);
  * partitioning and clustering for pruning;
  * retention and storage tiering for the 60% of unqueried tables;
  * auto-suspend and right-sizing of compute;
  * moving workloads to a cheaper engine;
  * committed-use discounts;
  * cutting cross-region traffic.
* **Rank the levers** into a sequenced plan that reaches 40%. Don't count
  savings twice: compaction and partitioning reduce the same scanned bytes.
* **Check the alternatives honestly:** Would a platform change (say, moving
  ad hoc work to a lakehouse engine) save more than tuning? What would the
  migration itself cost?

### **Phase 3: Guardrails and Risk**

* **What you will not cut,** and the SLAs that protect it.
* **Preventing regrowth:** showback or chargeback, per-team budgets, cost
  checks in CI for new models, and anomaly alerts on spend.
* **Failure modes of cost cutting:** an over-aggressive retention policy
  deletes a table finance needed once a year; auto-suspend adds cold-start
  latency to an executive's dashboard. Plan for these.

### **Constraint-change round**

1. You get **no engineering time**: only configuration and policy changes are
   allowed.
2. The vendor raises prices by 20% mid-plan.
3. A new product launches and data volume growth jumps to 15% per month.

### **What this trains**

Reading cost as a consequence of design decisions (file sizes, refresh
strategies, layout, retention), and arguing about it in money, which is the
language that gets architecture work funded.
