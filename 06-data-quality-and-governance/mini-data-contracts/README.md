### **Project Scope: Real Data Contracts (dbt contracts, buf/Protobuf-style CI checks) vs. Mini-Data-Contracts**

| Feature | Real Data Contracts | Mini-Data-Contracts (Python) |
| --- | --- | --- |
| **Definition** | Declared schema + SLAs (freshness, quality) per producer table | Declared schema + a breaking-change policy |
| **Enforcement point** | CI, before a producer's change merges | A `check_contract()` call, runnable in CI |
| **Breaking-change rules** | Same family as schema-registry compatibility rules | Reuses `mini-schema-registry`'s (group 03) compatibility logic |
| **Consumer visibility** | Contract violations block the producer's deploy, not just alert | Same: a failing check exits non-zero |

The organizational sibling of `mini-schema-registry` (group 03) — that
project enforces compatibility at publish time (runtime); this one enforces
it at merge time (CI), before code ever ships.

---

### **Phase 1: Declaring a Contract**

* **A contract file:** For a table (could be a `mini_iceberg` table or a
  `mini-dbt` model's output), declare its expected schema, plus simple
  SLAs — expected freshness cadence, a minimum row count.
* **Ownership metadata:** Who owns this table, and who consumes it
  (declared consumers, even if just a list of names/teams) — a contract
  without a known consumer list can't warn anyone before a breaking
  change ships.

### **Phase 2: Breaking-Change Detection in CI**

* **Diff against the previous contract:** Given a proposed schema change
  (e.g. a modified `mini-dbt` model), compute whether it's compatible with
  the declared contract — reuse `mini-schema-registry`'s backward/forward
  compatibility logic directly rather than reimplementing it.
* **Fail the build:** Wire this check into a CI step that exits non-zero
  on a breaking, un-acknowledged change — the entire point is that this
  runs *before* merge, catching what `mini-schema-registry`'s runtime
  check would otherwise only catch at publish time, after the code has
  already shipped.
* **An explicit override path:** Sometimes a breaking change is
  intentional and coordinated — implement a way to acknowledge/version-bump
  a contract deliberately, distinct from an accidental violation slipping
  through.

### **Phase 3: SLA Verification**

* **Freshness SLA check:** Verify a table actually updated within its
  contract's declared cadence — same mechanism as `mini-data-observability`
  (group 04)'s freshness monitor, but framed as a contractual obligation
  rather than a passive alert.
* **Consumer notification:** When a contract change is proposed, look up
  its declared consumers and simulate a notification — the organizational
  step that turns "I changed my table" into "the three teams who depend on
  it knew in advance," which is the actual problem data contracts exist to
  solve.

### **What this exposes about real tools**

Data contracts and schema registries solve the *same* technical problem
(is this schema change compatible) at two different points in the
lifecycle — CI/merge-time vs. publish/runtime — and real organizations
usually need both, because CI-time checks require every producer to
actually run this CI job, and there's always a change that bypasses it.
Building both projects side by side is what makes visible that "data
contracts" isn't a new technology, it's schema-registry-style
compatibility checking, moved earlier and wrapped in a process.
