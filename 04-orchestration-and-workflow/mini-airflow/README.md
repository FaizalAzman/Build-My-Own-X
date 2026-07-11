### **Project Scope: Real Airflow vs. Mini-Airflow**

| Feature | Real Airflow | Mini-Airflow (Python) |
| --- | --- | --- |
| **Scheduler** | Distributed, multiple schedulers with HA | Single-process scheduler loop |
| **Executor** | Celery/Kubernetes/local, parallel task execution | Local, threaded execution |
| **DAG definition** | Python DSL, dynamically parsed on an interval | Python DSL, same idea, simpler API |
| **Backfills** | Full CLI + UI support, catchup semantics | A `backfill(dag, start, end)` function |
| **State store** | Postgres/MySQL metadata database | SQLite or plain JSON |

The tool category with the most real-world disagreement about the right
approach (cron vs. DAG-based vs. event-driven) — build this to have an
informed opinion instead of a borrowed one.

---

### **Phase 1: DAG Definition and Topological Execution**

* **Task dependency graph:** Define tasks and `upstream >> downstream`
  relationships; validate the graph has no cycles (a real, common
  authoring mistake to guard against).
* **Topological execution:** Run tasks in an order that respects
  dependencies — parallelize independent branches, don't just run
  everything sequentially.
* **Task state machine:** Each task run has a state
  (`scheduled → running → success/failed`) — persist it, don't just track
  it in memory (a scheduler restart shouldn't lose track of what already
  ran).

### **Phase 2: Retries, Scheduling, and Idempotency**

* **Retries with backoff:** A failed task retries N times with increasing
  delay before being marked permanently failed.
* **A recurring schedule:** Run a DAG on an interval (e.g. every hour),
  creating a new "DAG run" each time, tracked independently of other runs.
* **Idempotency as a design requirement, not a nice-to-have:** Write a task
  that's *not* idempotent (e.g. `INSERT` without a dedup key) and
  deliberately trigger a retry-after-partial-success to produce duplicate
  data — then fix the task to be safely re-runnable, and understand why
  this is the task author's responsibility, not the scheduler's.

### **Phase 3: Backfills**

* **Historical DAG runs:** Given a DAG and a date range, create and
  execute one DAG run per interval in that range (e.g. one per day for 90
  days) — this is "backfill," and it's the same execution path as Phase 2's
  scheduled runs, just triggered for past intervals instead of the current
  one.
* **Catchup semantics:** Decide (and implement both) whether a DAG that
  was paused for a week automatically backfills every missed interval on
  resume, or only runs going forward — a real, consequential default that
  catches people off guard in production Airflow.

### **What this exposes about real tools**

Orchestrators get blamed for data quality incidents that are actually
*task design* failures — a non-idempotent task plus a scheduler retry is a
duplicate-data bug the orchestrator merely triggered, not caused. Having
built the retry mechanism yourself, and watched it create duplicates
against a task you wrote non-idempotently, makes that distinction concrete
instead of a talking point you repeat in a postmortem.
