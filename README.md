# Build-My-Own-X: A Staff-Level Data Engineering Curriculum

Each folder is a from-scratch, pure-Python reimplementation of a real data
infrastructure system — not to replace the real thing, but to force contact
with the design decisions the real thing's authors had to make. The goal
isn't "can I build a toy Kafka" — it's "having built one, I now know exactly
*why* Kafka's partition model looks the way it does, and what it costs you."

And the real point, which everything above serves: **being able to reason
about data systems architecturally.** That means deciding when to use Kafka,
something else or nothing at all, at what scale the answer changes, and
defending that decision in writing. Building teaches how a system works. The
decision sections and the design exercises in group 10 turn that into
judgment. The repo has two tracks:

- **Build track (groups 01–09):** take a real system apart by rebuilding it,
  then write a case study that ends in a *decision* section.
- **Design track (group 10):** write design docs for realistic platform
  problems, using the case studies as evidence. No code.

Every project README follows the same shape as
[`mini-iceberg/README.md`](01-storage-and-file-formats/mini-iceberg/README.md):
a scope table (what the mini version deliberately drops vs. the real system,
and why), then a phased build plan, then a closing note on what building it
actually exposes about the real tool's strengths and weaknesses. There's no
fixed order requirement — the grouping is thematic — but within a group,
earlier projects generally make later ones easier, and group 09 (Capstones)
explicitly assumes most of what comes before it.

This list isn't meant to be completed quickly. It's meant to be complete.

## 01 — Storage & File Formats

The layer underneath everything else: how bytes on disk trade off write
speed, read speed, and space. `mini-iceberg` used PyArrow's Parquet
reader/writer as a black box — these fill in what's inside that box, and
what the alternatives (row-based, write-optimized, read-optimized) actually
cost.

| Project | Teaches |
|---|---|
| ✅ [`mini-iceberg`](01-storage-and-file-formats/mini-iceberg/) | **Done.** Apache Iceberg's table format: catalog, metadata tree, snapshots/manifests, time travel, compaction — see [`CASE_STUDY.md`](01-storage-and-file-formats/mini-iceberg/CASE_STUDY.md) for where it matches real Iceberg, where it simplifies and why, plus anti-patterns and performance notes |
| [`mini-parquet`](01-storage-and-file-formats/mini-parquet/) | What's inside a columnar file format: row groups, encoding, stats, pruning |
| [`mini-avro`](01-storage-and-file-formats/mini-avro/) | Row-based serialization and schema resolution — the direct contrast to Parquet, and what real Iceberg manifests actually use |
| [`mini-lsm`](01-storage-and-file-formats/mini-lsm/) | Write-optimized storage: memtable, WAL, SSTables, compaction strategies |
| [`mini-btree-kv`](01-storage-and-file-formats/mini-btree-kv/) | Read-optimized storage: B-trees, in-place updates — the direct contrast to LSM |

## 02 — Query Engines & Compute

The layer that reads storage and answers questions. This is where
`mini-iceberg`'s unused column stats (flagged in its case study) finally get
put to work, and where "just add an index" stops being an incantation.

| Project | Teaches |
|---|---|
| [`mini-query-engine`](02-query-engines-and-compute/mini-query-engine/) | SQL over `mini-iceberg` tables: predicate pushdown via manifest stats, join strategies |
| [`mini-vectorized-exec`](02-query-engines-and-compute/mini-vectorized-exec/) | Batch-at-a-time (vectorized) execution vs. row-at-a-time — why DuckDB is fast, and where vectorization doesn't help |
| [`mini-cbo`](02-query-engines-and-compute/mini-cbo/) | Cost-based optimization: cardinality estimation, join reordering, and where estimation lies to you |
| [`mini-materialized-views`](02-query-engines-and-compute/mini-materialized-views/) | Incremental view maintenance, staleness tracking, and which aggregates can't be incrementally computed at all |

## 03 — Streaming & Messaging

A genuinely different set of tradeoffs from batch storage: ordering,
delivery guarantees, and schema evolution under continuous write load.

| Project | Teaches |
|---|---|
| [`mini-kafka`](03-streaming-and-messaging/mini-kafka/) | Log-based brokers: partitions, offsets, consumer groups, leader/follower replication |
| [`mini-stream-processor`](03-streaming-and-messaging/mini-stream-processor/) | Windowing, watermarks, exactly-once vs. at-least-once semantics |
| [`mini-cdc`](03-streaming-and-messaging/mini-cdc/) | Turning a database's write-ahead log into a stream of change events |
| [`mini-schema-registry`](03-streaming-and-messaging/mini-schema-registry/) | Compatibility-checked schema evolution for streaming payloads — the runtime enforcement `mini-data-contracts` mirrors at CI time |

## 04 — Orchestration & Workflow

The tool category every data org argues about most, and the one whose
failure modes are least visible from the outside — plus the observability
layer that watches everything else in this curriculum for you.

| Project | Teaches |
|---|---|
| [`mini-airflow`](04-orchestration-and-workflow/mini-airflow/) | DAG scheduling, retries/backoff, backfills, idempotency |
| [`mini-dbt`](04-orchestration-and-workflow/mini-dbt/) | SQL dependency graphs, materializations, compile-time vs. run-time |
| [`mini-data-observability`](04-orchestration-and-workflow/mini-data-observability/) | Freshness/volume/schema-drift monitoring, and why naive anomaly detection cries wolf every weekend |

## 05 — Distributed Systems Foundations

The primitives underneath almost everything above: how multiple machines
agree on anything at all, how data physically moves between them, and how
storage survives a machine dying.

| Project | Teaches |
|---|---|
| [`mini-raft`](05-distributed-systems-foundations/mini-raft/) | Leader election + log replication — what's underneath ZooKeeper/etcd |
| [`mini-object-store`](05-distributed-systems-foundations/mini-object-store/) | S3/HDFS-shaped storage: chunking, replication, a `mini-raft`-backed metadata service |
| [`mini-coordination-service`](05-distributed-systems-foundations/mini-coordination-service/) | ZooKeeper-shaped: ephemeral nodes, watches, and the single primitive underneath locks/leader-election/service-discovery |
| [`mini-shuffle`](05-distributed-systems-foundations/mini-shuffle/) | Spark-shaped shuffle: partitioning, spill-to-disk, sort-merge, lineage-based recovery |

## 06 — Data Quality & Governance

The layer that decides whether anyone can trust the data the rest of this
stack produces, and who's allowed to see what.

| Project | Teaches |
|---|---|
| [`mini-data-catalog`](06-data-quality-and-governance/mini-data-catalog/) | Metadata search + lineage-integrated browsing (Amundsen/DataHub-shaped) |
| [`mini-lineage`](06-data-quality-and-governance/mini-lineage/) | Parsing SQL into table- and column-level lineage, and where column-level tracking breaks |
| [`mini-great-expectations`](06-data-quality-and-governance/mini-great-expectations/) | A data quality assertion engine, wired to actually block a pipeline on failure |
| [`mini-data-contracts`](06-data-quality-and-governance/mini-data-contracts/) | CI-time breaking-change enforcement between producers and consumers |
| [`mini-rbac-data-access`](06-data-quality-and-governance/mini-rbac-data-access/) | Row-level security and column masking injected into query execution |

## 07 — Modern & ML Data Infra

Where "data engineering" and "ML infra" overlap — the newest, least
standardized category, and the one with the least agreement on right
answers.

| Project | Teaches |
|---|---|
| [`mini-feature-store`](07-modern-and-ml-data-infra/mini-feature-store/) | Point-in-time-correct joins — and what happens to your model's offline accuracy when you skip them |
| [`mini-vector-db`](07-modern-and-ml-data-infra/mini-vector-db/) | Embedding storage + approximate nearest neighbor search (HNSW vs. IVF-Flat), and where each wins |

## 08 — Data Integration & Migration

Getting data (and whole databases) from one system to another without
losing rows, breaking types, or requiring meaningful downtime.

| Project | Teaches |
|---|---|
| [`mini-dms`](08-data-integration-and-migration/mini-dms/) | Full-load + CDC-based database migration across engines: type mapping, lag tracking, cutover validation |
| [`mini-elt-connector`](08-data-integration-and-migration/mini-elt-connector/) | A Fivetran/Airbyte-shaped extract-load framework: incremental cursors, checkpointing, schema drift |

## 09 — Capstones

Not new theory — pure integration. Each of these assumes most of the
projects above already exist and combines them into something with the
shape of a real production system.

| Project | Teaches |
|---|---|
| [`mini-spark-core`](09-capstones/mini-spark-core/) | Driver/executor architecture, DAG-of-stages scheduling, lineage-based fault tolerance — built on `mini-shuffle` |
| [`mini-distributed-warehouse`](09-capstones/mini-distributed-warehouse/) | A full MPP query engine across `mini-object-store` + `mini-coordination-service` + `mini-query-engine` + `mini-shuffle` — where distributed scaling actually stops paying off |

## 10 — Architecture & Design

The track the rest of the repo exists for. Groups 01–09 teach how systems
work. This group teaches **choosing and combining them under real
constraints**: volume, latency, budget, team size, deadlines and regulation.
Each exercise is a realistic platform problem answered with a design doc in
the shape of [`templates/DESIGN_DOC.md`](templates/DESIGN_DOC.md). There's no
code. The evidence is the case studies you've already written.

Every exercise ends with a **constraint-change round**: three changes to the
requirements, and for each one you explain what changes in your design and
what doesn't. That round is the actual test. Knowing which parts of a design
are load-bearing for which requirement is what separates architectural
reasoning from naming the right tools.

**Do these as you go, not at the end.** Write a first version (v1) of an
exercise as soon as you've built one or two of the projects it draws on.
Write v2 after building the rest. The difference between v1 and v2 shows you
what the builds actually taught you. Then get v2 reviewed by someone else,
because judgment only improves when it's challenged.

| Exercise | The core decision | Draws on |
|---|---|---|
| [`design-analytics-data-model`](10-architecture-and-design/design-analytics-data-model/) | Grain, history (SCD), and where metric definitions live: Kimball vs. Data Vault vs. one big table | `mini-dbt`, `mini-query-engine`, `mini-materialized-views`, `mini-lineage` |
| [`design-realtime-fraud-pipeline`](10-architecture-and-design/design-realtime-fraud-pipeline/) | Working back from a 60 ms latency budget: what's precomputed vs. computed at request time, and how it degrades | `mini-kafka`, `mini-stream-processor`, `mini-feature-store`, `mini-lsm` |
| [`design-customer-facing-analytics`](10-architecture-and-design/design-customer-facing-analytics/) | Serving engine and tenant isolation for many small queries with a hard latency target | `mini-query-engine`, `mini-vectorized-exec`, `mini-materialized-views`, `mini-rbac-data-access` |
| [`design-warehouse-to-lakehouse-migration`](10-architecture-and-design/design-warehouse-to-lakehouse-migration/) | Target platform, migration order by lineage, and proving the numbers match before cutover | `mini-dms`, `mini-iceberg`, `mini-lineage`, `mini-airflow` |
| [`design-gdpr-event-lake`](10-architecture-and-design/design-gdpr-event-lake/) | Erasure and data residency in immutable storage: physical deletes vs. crypto-shredding vs. pseudonymisation | `mini-iceberg`, `mini-rbac-data-access`, `mini-data-catalog`, `mini-lineage` |
| [`design-platform-cost-reduction`](10-architecture-and-design/design-platform-cost-reduction/) | Reading a cloud bill back to the design decisions that caused it, and cutting 40% without breaking SLAs | `mini-parquet`, `mini-iceberg`, `mini-cbo`, `mini-dbt` |
| [`design-data-reliability-and-dr`](10-architecture-and-design/design-data-reliability-and-dr/) | Data SLOs by tier, write-audit-publish, and RPO/RTO that include metadata | `mini-airflow`, `mini-data-observability`, `mini-great-expectations`, `mini-iceberg` |
| [`design-platform-ownership-model`](10-architecture-and-design/design-platform-ownership-model/) | Who owns what: centralised vs. data mesh vs. platform-as-product, and the contracts between teams | `mini-data-contracts`, `mini-data-catalog`, `mini-schema-registry`, `mini-elt-connector` |

## How to use this repo

For each project: read its scope table first — the "Real System" column is
the thing you're studying, the "Mini" column is what you're actually going
to type. Build it, then (as we did for `mini-iceberg`) write a `CASE_STUDY.md`
comparing your design's decisions against the real system's, with a
particular eye toward: what would break at 100x the scale, 10x the
concurrent writers, or under a failure this project never tests. That last
step is where "I built a toy" turns into "I understand the tradeoff" —
it's not optional, and it's the actual deliverable, not the code.

Every case study then ends with a **decision section** following
[`templates/CASE_STUDY_DECISION.md`](templates/CASE_STUDY_DECISION.md): when
you'd choose the real system, a managed equivalent, a simpler alternative or
nothing at all, with the numbers at which that answer changes, plus the cost
shape, operational burden, reversibility, and the signals that you chose
wrong. The [`mini-iceberg` case study](01-storage-and-file-formats/mini-iceberg/CASE_STUDY.md#13-decision-when-to-choose-iceberg-and-when-not-to)
has a worked example.

The full loop for each project is:

1. **Build** the mini version.
2. **Case study:** how the real system works and what changes at scale.
3. **Decision:** when you'd choose it, and what would change your mind.
4. **Design:** use that decision as evidence in a group 10 design doc, and
   revise the doc when a later project changes your mind.

Steps 1–2 build understanding. Steps 3–4 build judgment. Working as an
architect needs both, but it's judgment that gets tested.

## Playgrounds

Finished projects also run in the browser: see [`playground/`](playground/).
Each playground loads the project's unmodified source into Pyodide, then walks
through the build phases and runs experiments that test claims from the case
study. For example, the [`mini-iceberg` playground](playground/mini-iceberg/)
measures what committing too often costs, and shows a commit being silently
lost when two writers have no compare-and-swap. Once a project's case study
is written, give it a playground (see
[`playground/README.md`](playground/README.md)). Measurements you take
yourself make better evidence for design docs than vendor benchmarks.

If a new tool or concept isn't on this list and it can be built and taken
apart, it belongs here — add a group or a project rather than treating this
as closed.
