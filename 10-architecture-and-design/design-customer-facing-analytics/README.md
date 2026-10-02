### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Product** | B2B SaaS with dashboards embedded in the product for ~4,000 tenant companies | Which engine serves these queries, and whether it's the same engine as internal analytics |
| **Volume** | ~2B events/day across all tenants, heavily skewed: the largest tenant is 40% of the data, and the median tenant is tiny | How data is laid out and isolated per tenant |
| **Latency and concurrency** | Dashboard queries at **p95 < 1 s**, up to 500 concurrent queries at peak | How much is precomputed and how much is computed at query time |
| **Freshness** | Events visible in dashboards within 5 minutes | The ingestion path and how it interacts with precomputation |
| **Isolation** | A tenant must never see another tenant's data. Enterprise tenants also get ad hoc SQL export. | How isolation is enforced, and how one tenant is kept from starving the others |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md).

**Draws on:** `mini-query-engine` + `mini-vectorized-exec` (what makes a single
query fast), `mini-materialized-views` (precomputation and staleness),
`mini-rbac-data-access` (row-level security), `mini-kafka` (ingestion).

Internal analytics and customer-facing analytics look similar but are opposite
workloads. Internal analytics means a few heavy, unpredictable queries where
seconds to minutes is fine. Customer-facing analytics means many small,
predictable queries with a hard latency target, and every slow query is seen
by a paying customer. Most bad designs here start by pointing the product at
the internal warehouse.

---

### **Phase 1: Workload and Back-of-Envelope**

* **Characterize the queries:** What fraction are fixed dashboard tiles and
  what fraction are ad hoc? Which dimensions get filtered and grouped? Over
  which time ranges?
* **Size the tenants:** Estimate the data volume per tenant at the median,
  the 99th percentile and the maximum. A design that works for the median
  tenant and falls over for the largest one doesn't work.
* **Concurrency maths:** At 500 concurrent queries and a 1 s p95, how many
  queries per second must the system sustain? What does that imply for each
  query's scan budget in bytes?

### **Phase 2: Architecture and Alternatives**

* **Compare serving engines:**
  * query the internal cloud warehouse directly;
  * a real-time OLAP store (Pinot, Druid or ClickHouse-shaped) with ingest-time
    rollups;
  * precomputed aggregates in Postgres or a key-value store;
  * a DuckDB-style embedded engine over per-tenant files.

  Compare them on latency, concurrency, freshness, cost per query and
  operational burden.
* **Tenant isolation:** Choose between a shared table with a tenant filter,
  a schema per tenant, or a database/cluster per tenant. Say where the large
  tenant goes, and whether "one design for everyone" survives that tenant.
* **Noisy neighbours:** Decide how one tenant's expensive query is prevented
  from breaking everyone else's 1 s target. Options include admission
  control, per-tenant quotas, separate pools and query timeouts.

### **Phase 3: Failure, Lifecycle, and Cost**

* **Bad ingest:** A bug corrupted 6 hours of events for 300 tenants. How do
  you backfill when rollups were computed at ingest time?
* **Tenant offboarding:** A tenant leaves and requires proof that their data
  was deleted, including from rollups and backups.
* **Cost attribution:** Estimate cost per tenant. Sales wants to know whether
  the cheapest plan is profitable for the median tenant.

### **Constraint-change round**

1. Freshness tightens from 5 minutes to **5 seconds**.
2. A large tenant demands that their data stay in the EU.
3. The company moves down-market: 40,000 tenants, but each one 10× smaller.

### **What this trains**

Telling workloads apart by their shape (concurrency, latency, how predictable
the queries are) rather than by the engine's marketing category. It also
trains you to treat multi-tenancy as a first-class architectural axis,
instead of a `WHERE tenant_id = ?` clause added at the end.
