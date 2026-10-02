### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Company** | ~600 people, 8 product domains, each with 1–3 analysts or engineers of mixed skill | The ownership model: who owns which data and pipelines |
| **Central team** | 15 data engineers. Request backlog of **9 weeks**, and they are the bottleneck for every new dataset. | What the central team stops doing, keeps doing and starts doing |
| **Proposal** | A VP has proposed "adopting data mesh" | Whether to adopt it, and which parts are worth taking |
| **Pain** | Three different definitions of "active user"; nobody knows who owns half the tables; domains build shadow pipelines to escape the queue | The interfaces between teams, and how they are enforced |
| **Regulated domain** | Payments data falls under financial regulation | Where self-service stops |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md).
Here the "architecture" is teams, ownership boundaries and the platform
interfaces between them, as well as the systems.

**Draws on:** `mini-data-contracts` + `mini-schema-registry` (interfaces
between teams), `mini-data-catalog` + `mini-lineage` (discoverability and
ownership), `mini-elt-connector` + `mini-dbt` (what self-service ingestion and
modeling would have to provide), `mini-rbac-data-access`.

Conway's law applies to data platforms more strongly than almost anywhere
else: the pipelines end up mirroring the team structure. At staff level and
above, the question is often not which tool to use but **who owns what and
what the contract between them is**. That's an architecture decision with
the same tradeoff structure as any technical one.

---

### **Phase 1: Map the Current System, Including the People**

* **Where the queue forms:** Trace three typical requests from asking to
  delivery. Where does the time go: waiting, building, or clarifying
  requirements?
* **Cross-domain data:** Which datasets are produced by one domain and
  consumed by others? These are where the contracts will have to be.
* **Capability per domain:** Rate each domain's realistic ability to own
  pipelines. A plan that assumes every domain can do it will fail in the
  domains that can't.

### **Phase 2: Ownership Model and Alternatives**

* **Compare models:**
  * fully centralised (fix the bottleneck with more people and prioritisation);
  * hub-and-spoke (embedded engineers who report centrally);
  * full data mesh (domains own data products end to end);
  * **platform as a product**: a central team builds the "paved road"
    (ingestion templates, contract checks, catalog registration, cost
    visibility) and domains build on it.

  Mixing models per domain is allowed, and probably correct.
* **Interfaces:** Define what a "data product" must provide: an owner, a
  contract, SLOs, documentation and access policy. Then decide how each of
  those is checked automatically, rather than by review meetings.
* **Shared definitions:** Decide where "active user" lives under your model,
  who can change it, and how consumers are protected from that change.

### **Phase 3: Failure Modes and Migration**

* **How decentralisation fails:** domains without data skills ship broken
  pipelines; definitions fragment further; spend explodes when nobody sees the
  bill; governance becomes 8 different policies. For each failure, name the
  platform guardrail that contains it.
* **Migration path:** Choose the first domain to move and say why. Define what
  "done" means for that pilot, and decide which central work gets handed over
  and which is kept.
* **Success metrics:** lead time for a new dataset, number of incidents per
  data product, duplicated definitions, and cost per domain.

### **Constraint-change round**

1. The company cuts staff by half, and domains lose their data people first.
2. The company acquires another company with its own data team and platform.
3. A regulator requires a single accountable owner for all customer data.

### **What this trains**

Seeing team boundaries and interfaces as architecture, and evaluating
organisational patterns (data mesh included) by the same tradeoffs as
technical ones: what each one enables, what it costs, and when it breaks.
