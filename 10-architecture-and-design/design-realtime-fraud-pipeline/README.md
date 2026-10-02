### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Volume** | 5,000 card transactions/s on average, 25,000/s at seasonal peak, ~80M active cards | How state is partitioned and sized |
| **Latency** | The fraud check gets **60 ms p99** of the card authorization's latency budget | What runs synchronously on the request path, and what runs ahead of time |
| **Features** | Counts and sums per card, device and merchant over 1-minute, 1-hour and 24-hour windows, plus 90-day aggregates | Where each feature is computed (stream, batch, or at request time) |
| **Model** | Retrained weekly on historical data | How training features match serving features exactly (no skew) |
| **Correctness** | No transaction may be lost; audit must be able to reproduce the exact features any past decision used | Where exactly-once actually matters, and where at-least-once is fine |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md).

**Draws on:** `mini-kafka` (partitioning, consumer groups), `mini-stream-processor`
(windows, watermarks, delivery semantics), `mini-feature-store` (point-in-time
correctness, online/offline split), `mini-lsm` (what a stream processor's state
store is underneath), `mini-cdc`.

This is the canonical "do we need streaming?" problem. The tempting answer
is "Kafka plus Flink plus a feature store". The useful answer explains which
parts of the latency budget each component spends, and what happens to an
authorization when one of them is slow.

---

### **Phase 1: Requirements and Back-of-Envelope**

* **Latency budget:** Split the 60 ms p99 into network, feature lookup, model
  inference and slack. That split immediately rules out some architectures,
  for example any synchronous scan over 90 days of history.
* **State size:** Estimate how much state you hold: cards × features ×
  windows × bytes, plus how much detail each window type needs (a
  sliding-window count needs more than a single counter). Decide whether it
  fits in memory on one node, on N nodes, or needs a disk-backed store.
* **Time semantics:** Transactions arrive out of order from many acquirers.
  Decide whether "transactions in the last hour" means event time or
  processing time, and what each choice costs in correctness and latency.

### **Phase 2: Architecture and Alternatives**

* **Compare at least three designs:**
  * a stream processor precomputes features into an online key-value store,
    and the scoring service only does lookups;
  * counters are incremented on a fast database at request time (no stream
    processor at all);
  * micro-batch features every few minutes, plus a small set of real-time
    counters.

  For each, state which features it can serve within budget and how fresh
  they are.
* **Training/serving skew:** Show how the weekly training set gets *exactly*
  the feature values the online path would have seen at each transaction's
  timestamp. This is the point-in-time join from `mini-feature-store`.
* **Partitioning:** Choose the Kafka and processor partition key. Then deal
  with the fact that one very large merchant produces 3% of all traffic
  (a hot key).

### **Phase 3: Failure, Replay, and Audit**

* **Degraded mode:** The stream processor falls 2 minutes behind. Does scoring
  use stale features, fall back to a rules engine, approve the transaction
  (fail open) or decline it (fail closed)? Note that the right answer differs
  by transaction amount. Design that policy explicitly.
* **New feature backfill:** Data science wants a new 90-day feature tomorrow.
  How do you compute it historically for training *and* warm the online store,
  without the two disagreeing?
* **Audit:** A regulator asks why transaction X was declined 14 months ago.
  What did you log at decision time so the answer doesn't depend on
  recomputing anything?

### **Constraint-change round**

1. The latency budget drops to **15 ms p99**.
2. Volume grows 10× after a partnership with a large card issuer.
3. Regulation now requires decisions to be explainable and reproducible for
   7 years.

### **What this trains**

Reasoning from a latency budget down to an architecture, instead of from a
technology list up to one. It also trains you to make degradation policy a
designed, reviewed decision rather than whatever happens when a timeout fires.
