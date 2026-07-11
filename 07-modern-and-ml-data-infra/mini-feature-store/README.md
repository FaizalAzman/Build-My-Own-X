### **Project Scope: Real Feature Stores (Feast/Tecton) vs. Mini-Feature-Store**

| Feature | Real Feature Stores | Mini-Feature-Store (Python) |
| --- | --- | --- |
| **Offline store** | Data warehouse/lake (e.g. an Iceberg table) | A `mini_iceberg` table |
| **Online store** | Redis/DynamoDB, low-latency key-value | An in-memory dict with a simple TTL |
| **Point-in-time correctness** | "As-of" joins preventing label leakage | Explicit as-of join implementation |
| **Sync** | Batch materialization jobs, offline → online | A `materialize()` job, same idea |

This is where `mini_iceberg`'s time travel (its actual headline feature)
gets used for something with real stakes: preventing an ML model from
training on information it wouldn't have had at prediction time.

---

### **Phase 1: Offline Store and Point-in-Time Joins**

* **Feature tables in `mini_iceberg`:** Store features (e.g. `user_id`,
  `feature_name`, `value`, `event_timestamp`) as `mini_iceberg` tables,
  appended to over time exactly like any other table in that project.
* **The point-in-time join:** Given a set of training labels each with its
  own timestamp, join each label to the *feature values that were true as
  of that label's timestamp* — not the current/latest feature values.
  This is the single most important correctness property a feature store
  provides.
* **Deliberately leak the future first:** Implement the naive version
  (join to current feature values regardless of label timestamp), train
  a toy model, and notice suspiciously good offline accuracy that won't
  hold up in production — this is label leakage, and it's the exact bug
  point-in-time joins exist to prevent.

### **Phase 2: Online Store and Materialization**

* **A low-latency online store:** A simple in-memory dict keyed by
  `(entity_id, feature_name) → latest_value`, meant for millisecond-scale
  reads at prediction time (a real model server can't wait on a table
  scan per request).
* **Materialization job:** Periodically copy the *latest* feature values
  from the offline `mini_iceberg` table into the online store — this is
  a batch job with the exact same "how fresh does this need to be"
  tradeoff as `mini-data-observability`'s freshness monitoring (group 04).
* **Online/offline skew check:** Compare a feature's online value against
  what the offline point-in-time join would have returned for "now" —
  these should agree; a mismatch here is training/serving skew, a classic
  and hard-to-detect ML production bug.

### **Phase 3: Serving and Feature Freshness**

* **A prediction-time lookup API:** Given an entity id, fetch all its
  current feature values from the online store in one call — the
  interface a real model server actually calls.
* **Staleness-aware serving:** Reject or flag a prediction request if a
  required feature's online value is older than an acceptable threshold
  (the materialization job hasn't run recently enough) — surfacing a
  pipeline problem as a serving-time signal instead of silently serving
  stale features.

### **What this exposes about real tools**

Feature stores exist almost entirely to solve one problem — point-in-time
correctness — and everything else (online store, materialization jobs) is
plumbing in service of that. Having built the naive, leaky version first
in Phase 1 and watched it produce falsely great offline metrics is what
makes "our model's offline accuracy doesn't match production" a
diagnosable, expected failure mode instead of a mystery you discover after
shipping.
