### **Project Scope: Real Data Access Control (Snowflake/BigQuery row/column security, Apache Ranger) vs. Mini-RBAC-Data-Access**

| Feature | Real Systems | Mini-RBAC-Data-Access (Python) |
| --- | --- | --- |
| **Roles** | Hierarchical roles, role inheritance | Flat roles with explicit grants |
| **Row-level security** | Policy predicates injected into query plans | Predicate injected into `mini-query-engine`'s (group 02) `WHERE` clause |
| **Column masking** | Dynamic masking (full, partial, hash) based on role | Full mask, partial mask (e.g. last-4-digits), and hash |
| **Audit** | Every access logged with the effective policy applied | A log entry per query: user, role, policy applied |

The governance layer over `mini-query-engine` (group 02) — every query it
executes should pass through this project's policy layer first.

---

### **Phase 1: Roles and Grants**

* **Roles and permissions:** Define roles (e.g. `analyst`, `finance`,
  `admin`) and grant table/column-level `SELECT` permissions per role.
* **Deny by default:** A role with no explicit grant on a table can't
  query it at all — implement this as the default, not an opt-in, matching
  how real access-control systems fail closed rather than open.
* **Effective permission resolution:** Given a user's role(s), compute
  which tables and columns they can actually see — this becomes the input
  to Phases 2 and 3.

### **Phase 2: Row-Level Security**

* **Policy predicates:** Attach a predicate to a table per role — e.g.
  `region = current_user_region()` — so an `analyst` in the EU region
  querying `orders` transparently only ever sees EU rows.
* **Injection into query execution:** Rewrite an incoming query from
  `mini-query-engine` (group 02) to `AND` the relevant policy predicate
  onto its `WHERE` clause before execution — the user's query text never
  changes, but the *rows returned* differ by role, without the user
  needing to know the policy exists.
* **Prove it can't be bypassed:** Try to write a query that evades the
  injected predicate (e.g. via a subquery or a `UNION`) and confirm your
  rewrite step catches it at every entry point, not just the top-level
  `WHERE`.

### **Phase 3: Column Masking**

* **Masking functions:** Full mask (`***`), partial mask (show last 4
  characters of a credit-card-shaped string), and one-way hash — applied
  per column, per role, at read time.
* **Mask at the right layer:** Apply masking *after* row-level security
  filtering but *before* returning results to the client — get this order
  wrong (mask before filtering) and reason about what information could
  leak through row-count side channels even with masked values.
* **Audit log:** Record every query with the user, role, and exactly which
  policies (row filters + column masks) were applied — the artifact a real
  compliance audit actually asks for.

### **What this exposes about real tools**

Row-level security and column masking are usually sold as simple checkbox
features, but the actual hard part — proven in Phase 2 — is guaranteeing
the policy applies at *every* query shape a user could construct (nested
subqueries, `UNION`s, CTEs), not just the obvious top-level case. Having
tried to bypass your own policy layer and found (or failed to find) a hole
is the only way to actually trust that a production access-control layer
is doing what it claims.
