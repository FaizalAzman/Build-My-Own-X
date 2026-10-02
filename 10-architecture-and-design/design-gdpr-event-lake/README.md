### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Users** | Consumer app, ~50M users across the EU and US | How personal data is identified, classified and keyed |
| **Data** | 3 years of clickstream (~800 TB) in Iceberg tables. Copies and derivatives in the warehouse, feature store, ML training sets, Kafka (7-day retention) and backups. | Which copies exist at all, and how each one is kept compliant |
| **Erasure** | ~20,000 right-to-erasure requests per month, each to be completed within **30 days** | The deletion mechanism and how completion is proven |
| **Residency** | EU users' personal data must be stored and processed in the EU | Regional topology for storage and compute |
| **Analytics** | Analysts need behavioural analysis and multi-year lifetime value (LTV) per user | What analytics is still possible after deletion and pseudonymisation |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md).

**Draws on:** `mini-iceberg` (immutability, time travel, and the deletes and
maintenance sections of its case study), `mini-rbac-data-access`
(masking), `mini-data-catalog` + `mini-lineage` (finding every copy),
`mini-cdc`.

An immutable lake with time travel is designed so that nothing ever really
disappears. The law requires that some things do. Resolving that tension is a
real architecture problem with real costs, and "we'll run a DELETE" is not a
design.

---

### **Phase 1: Map and Estimate**

* **Find every copy:** Using lineage and the catalog, list every place
  personal data lands, including the copies people forget: ML training
  snapshots, CSV exports, BI extracts, Kafka topics, backups and Iceberg
  snapshots kept for time travel.
* **Estimate deletion cost:** A user's events are spread across hundreds of
  daily partitions. With 20,000 users deleted per month, estimate what
  fraction of data files contain at least one of those users. That number
  decides whether copy-on-write deletes are affordable. Show the arithmetic.
* **Classify columns:** direct identifiers, quasi-identifiers (IP address,
  device ID, location) and non-personal fields. Decide what counts as
  personal data in the aggregates.

### **Phase 2: Mechanism and Alternatives**

* **Compare deletion mechanisms:**
  * physical deletion via Iceberg copy-on-write or merge-on-read deletes,
    followed by compaction and snapshot expiry;
  * **crypto-shredding**: encrypt each user's personal fields with a per-user
    key, and destroy the key to delete;
  * **pseudonymisation at ingest**: store a surrogate ID in the lake, and keep
    the ID-to-person mapping in a small identity vault, where deletion is a
    single row;
  * retention limits and aggregation, so raw events simply age out.

  Most real designs combine these. Decide which mechanism applies to which
  data.
* **Residency:** Choose between separate EU and US lakes, each with its own
  compute, or a global lake with regional storage and access policy. Then work
  out what happens to global analytics and cross-region joins.

### **Phase 3: The Hard Edges**

* **Time travel vs. erasure:** Deleted rows survive in older snapshots. Set
  the snapshot-expiry and orphan-file policy so that erasure completes within
  30 days, and state what that does to your time-travel horizon.
* **Derived data:** A deleted user's data was used to train a model and is
  baked into aggregates. Decide what you must re-derive and what you can
  defend leaving as it is. Write down your reasoning.
* **Proof:** An auditor asks you to prove user X was deleted everywhere. What
  evidence does your system produce, and how is it stored without itself
  holding personal data?

### **Constraint-change round**

1. The erasure deadline tightens to **7 days**.
2. A new jurisdiction defines device IDs and IP addresses as directly
   identifying.
3. The LTV model needs to join one user's activity across all 3 years.

### **What this trains**

Treating compliance as a constraint that shapes the architecture from day
one, rather than as a cleanup job. It also builds the habit of finding every
copy of the data, since a design is only as compliant as its most
forgotten copy.
