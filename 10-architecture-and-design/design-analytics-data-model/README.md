### **Exercise Scope: The Scenario vs. What You Decide**

| Dimension | Given | You decide |
| --- | --- | --- |
| **Business** | Two-sided marketplace: buyers, sellers, listings, orders, payments, refunds | Which business processes become fact tables, and at what grain |
| **Sources** | Postgres OLTP (~30 tables, CDC available), clickstream (~200M events/day), payment provider (daily settlement files + webhooks) | How raw data is landed and layered before anyone models it |
| **Consumers** | Finance (monthly close, must reconcile to the cent), product analysts (funnels, ad hoc), ML (seller-churn features), exec dashboard | Where business metric definitions live, and who owns them |
| **History** | Sellers change category, tier and region; finance attributes revenue to the seller's tier *at the time of the order* | Which attributes keep history (SCD2) and which are overwritten |
| **Late data** | Refunds and chargebacks arrive up to 90 days after the order | How late facts flow into periods that have already been reported |

**Deliverable:** a design doc following [`templates/DESIGN_DOC.md`](../../templates/DESIGN_DOC.md),
including an entity-relationship diagram. No code.

**Draws on:** `mini-dbt` (materializations, the model DAG), `mini-query-engine` +
`mini-cbo` (what joins and scans actually cost), `mini-materialized-views` (which
aggregates can be maintained incrementally), `mini-lineage` (what a model change
breaks downstream).

Data modeling is where most data platforms first go wrong, and it's the
mistake they pay for longest. A wrong engine choice can be migrated away from
in a quarter. A wrong grain becomes part of every dashboard, ML feature and
finance report built on top of it.

---

### **Phase 1: Requirements and Grain**

* **Business process inventory:** List each process (order placed, payment
  captured, refund issued, listing viewed, and so on) and, for each one, the
  questions consumers actually ask of it.
* **Declare the grain of every fact table in one sentence.** For example,
  "one row per order line per status change" vs. "one row per order line,
  current status only". Most modeling bugs are grain bugs: two facts at
  different grains get joined, rows silently fan out, and revenue doubles.
* **Back-of-envelope:** Estimate rows per day and three-year size for each
  fact, and the size of the seller dimension under SCD2 if sellers change tier
  about four times a year. Then decide whether the clickstream belongs in the
  same model at all.

### **Phase 2: Modeling Approach and Alternatives**

* **Compare four approaches** against the consumers above:
  * a Kimball star schema with conformed dimensions;
  * Data Vault (hubs, links and satellites) with marts on top;
  * one big table (OBT) per use case;
  * plain normalized replicas of the source.

  Note that "medallion" (bronze/silver/gold) is a *layering* convention, not a
  modeling technique. State which modeling approach lives in which layer.
* **Where metric definitions live:** in dbt models, in a semantic/metrics
  layer, or in the BI tool. "GMV" is currently defined four different ways by
  four teams. Your design has to make that impossible, and has to say who
  approves a change to the definition.
* **Physical design:** For your chosen model on a columnar engine, choose the
  partitioning and clustering for the largest fact table. Then decide whether
  the exec dashboard reads the star schema directly or a pre-aggregated table.
  Reason with what `mini-query-engine` showed you about join and scan cost.

### **Phase 3: Change, Late Data, and Correctness**

* **Late refunds:** Trace a refund that arrives 60 days after its order through
  your model. Does last quarter's revenue change? Finance says closed months
  must not change; product says the numbers must be accurate. Design for both,
  for example with restated views next to frozen snapshots, or with adjustment
  facts.
* **Source schema change:** The OLTP team adds an order status
  `partially_refunded`. What breaks, who finds out, and how? Connect this to
  `mini-data-contracts`.
* **Identity:** Two seller accounts are merged into one. How is history
  re-attributed, and what does that do to SCD2 rows and to reports that were
  already published?

### **Constraint-change round**

For each change, answer in one paragraph: what changes in your design, what
stays the same, and why.

1. The company acquires a competitor whose orders can contain items from
   several sellers. You now have two source systems for "order", with
   different shapes.
2. Analysts start asking questions through a text-to-SQL assistant instead of
   writing SQL. What do the model and its metadata need to look like for the
   assistant's answers to be correct?
3. Finance requires every monthly close to be reproducible exactly, two years
   later, for audit.

### **What this trains**

Three decisions get much harder to reverse with every consumer built on them:
the grain, how history is kept, and where metric definitions live. Every
other design exercise in this group assumes you can make those three
decisions deliberately, and explain the choice to a finance lead and an ML
engineer in the same meeting.
