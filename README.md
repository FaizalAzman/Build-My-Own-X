# Build-My-Own-X: A Staff-Level Data Engineering Curriculum

Each folder is a from-scratch, pure-Python reimplementation of a real data
infrastructure system — not to replace the real thing, but to force contact
with the design decisions the real thing's authors had to make. The goal
isn't "can I build a toy Kafka" — it's "having built one, I now know exactly
*why* Kafka's partition model looks the way it does, and what it costs you."

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

## How to use this repo

For each project: read its scope table first — the "Real System" column is
the thing you're studying, the "Mini" column is what you're actually going
to type. Build it, then (as we did for `mini-iceberg`) write a `CASE_STUDY.md`
comparing your design's decisions against the real system's, with a
particular eye toward: what would break at 100x the scale, 10x the
concurrent writers, or under a failure this project never tests. That last
step is where "I built a toy" turns into "I understand the tradeoff" —
it's not optional, and it's the actual deliverable, not the code.

If a new tool or concept isn't on this list and it can be built and taken
apart, it belongs here — add a group or a project rather than treating this
as closed.
