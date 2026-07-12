# Mini-Iceberg vs. Apache Iceberg: A Case Study

This documents where `mini_iceberg` (the project in this folder) matches real Apache
Iceberg's design, and where it deliberately simplifies — with the specific
production problem each simplification would need to solve if this were real.

---

## 1. The core idea: both got this part right

The central mechanism you built is *not* a toy version of Iceberg's design — it's
the real one:

- **Catalog → metadata pointer → snapshot (manifest list) → manifests → data files**,
  a strict tree, one direction only.
- **Nothing is ever mutated in place.** Every commit writes new files; a pointer
  (`catalog.json`'s entry, in your case) is swapped only once the new state is
  fully written.
- **Time travel is a side effect of immutability, not a bolted-on feature.** Because
  old snapshots/manifests/files are never touched, an old `snapshot_id` just... still
  resolves.
- **Compaction is a commit, not a special destructive operation.** It creates a new
  snapshot; it never deletes anything.

Real Iceberg's [table spec](https://iceberg.apache.org/spec/) is built on exactly this
shape. Everything below is about what gets added *on top* of it in production, not a
different foundation.

---

## 2. Physical format: JSON vs. Avro

| | mini_iceberg | Apache Iceberg |
|---|---|---|
| Manifest files | JSON | **Avro** (binary, schema'd, splittable) |
| Manifest list (snapshot) | JSON | **Avro** |
| Table metadata | JSON | JSON (real Iceberg *does* use JSON here — you matched this one exactly) |
| Data files | Parquet | Parquet, ORC, or Avro |

Why Avro for manifests specifically: manifest files can get large (thousands of entries
per manifest in big tables), and Avro is a compact binary row format with an embedded
schema — cheaper to store and faster to scan than JSON at that scale. Table metadata
stays JSON in real Iceberg because it's read in full on every query anyway and is
usually small (a list of snapshots, not a list of files), so JSON's readability wins
there with no real cost. Your project mirrors that distinction correctly in spirit
(reusing JSON for `vN.metadata.json` was the right call) — the only place you diverge
is manifests/snapshots, where you used JSON for simplicity instead of learning Avro.

---

## 3. Schema evolution: field IDs vs. names

This is the one you flagged yourself while building `types.py`, and it's real:

- **mini_iceberg** matches columns by **name**. `schema_to_json`/`schema_from_json`
  round-trip a list of `{"name", "type"}`.
- **Apache Iceberg** assigns every column a permanent integer **field ID** at creation
  time, e.g. `{"id": 1, "name": "id", "type": "long"}`. Every manifest entry's stats
  and every Parquet file's column mapping are keyed by that ID, not by name or
  position.

Concretely, this means in mini_iceberg: `RENAME COLUMN id TO user_id` would silently
break every old manifest's stats (they're keyed `"id"`, and the new schema has no `"id"`
anymore). In real Iceberg, the field ID for that column stays `1` forever regardless of
what it's currently named, so old manifests, old Parquet files, and the current schema
all still agree on what column `1` means.

This is *the* feature that makes Iceberg's headline promise ("evolve your schema
without rewriting data") actually safe. mini_iceberg gets everything else about
snapshots/manifests right, but doesn't attempt this part.

---

## 4. Column stats: recorded vs. *used*

Both systems compute per-file min/max stats at write time (`column_stats()` in your
project). The difference is what happens with them at **read** time:

- **mini_iceberg's `read()`** ignores stats entirely — it opens every active file, every
  time, unconditionally.
- **Real Iceberg** (via Spark/Trino/etc.) uses those same stats for **file pruning**:
  if a query filters `WHERE id > 1000` and a file's manifest entry says `id` ranges
  `[1, 50]`, the engine never opens that file at all. Real Iceberg also tracks
  **null-count** and **NaN-count** per column (not just min/max), and pushes this
  pruning down to the *manifest* level too — each manifest itself carries a summary
  of the partition ranges its files span, so an engine can sometimes skip whole
  manifests without opening any of the files inside them.

You built the data structure real pruning is built on; the actual pruning logic
(comparing a query's filter against stored ranges before deciding to open a file) is
the natural next extension if you wanted to keep going.

---

## 5. Partitioning: none vs. hidden partitioning

mini_iceberg has no concept of partitions — every file in a table is just "a file."

Real Iceberg tables have a **partition spec**: a declared transform of one or more
columns (e.g. `days(event_time)`, `bucket(16, user_id)`) that determines which
directory/prefix a file's data logically belongs to. Two things make this different
from older formats like Hive:

- It's **hidden** — queries don't need to know the partition scheme; `WHERE event_time
  > '2026-01-01'` gets partition-pruned automatically, without the user writing
  `WHERE partition_day > '2026-01-01'`.
- Partition specs can **evolve** — you can repartition a table going forward without
  rewriting old data, because (again) each manifest records which partition spec was
  in effect for the files it lists.

This is a genuinely separate axis of complexity from everything else in this case
study — it would be a substantial Phase 5 on its own.

---

## 6. Concurrency: single-threaded vs. optimistic concurrency control

Your `Catalog._commit()` just overwrites the pointer. That's correct and sufficient
*because your whole project is single-threaded* — nothing else is trying to commit at
the same time.

Real Iceberg catalogs (REST, Hive Metastore, AWS Glue) implement **compare-and-swap**:
a writer reads the current metadata pointer, builds a new metadata file assuming that
pointer is still current, then asks the catalog "swap to my new file, but *only* if
the pointer is still what I read." If another writer committed in between, the swap
is rejected, and the loser must reread the new current state and retry (Iceberg calls
this the *"refresh-and-retry"* loop). This is what lets two Spark jobs append to the
same table concurrently without corrupting it — whoever's swap lands first wins, and
the second one just redoes its commit against the new base.

You already noted this in your own docstrings — it's the reason `_commit()` is
structured as "write full new state, then flip one pointer" instead of "edit in place,"
even in a single-threaded project. That shape is required infrastructure for
concurrency control, even though you never needed the retry loop itself.

---

## 7. Snapshot ordering: timestamps vs. sequence numbers

mini_iceberg orders snapshots by incrementing `snapshot-id` (`1 + max existing id`).
Real Iceberg tracks a separate monotonic **sequence number** per snapshot, distinct
from both the snapshot ID and the wall-clock timestamp.

Why a third number is needed: under concurrent writers, wall-clock timestamps can be
skewed or arrive out of order (two commits landing within the same millisecond, or a
writer's clock being slightly wrong), and snapshot IDs alone don't tell you which
manifest entries are newer when merging manifests from concurrent branches. The
sequence number is assigned centrally by the catalog at commit time specifically to
give an unambiguous global ordering that doesn't depend on clocks. Your project's
`timestamp-ms` + incrementing ID is fine precisely because there's only ever one
writer.

---

## 8. Deletes and updates: append-only vs. row-level mutation

mini_iceberg only supports `append()`. There is no way to delete or update a row short
of rewriting the whole table.

Real Iceberg supports row-level `DELETE`/`UPDATE`/`MERGE` via two mechanisms:

- **Copy-on-write**: rewrite the affected data files entirely (simple, expensive per
  write, cheap to read).
- **Merge-on-read**: write a small **delete file** (position deletes, referencing
  `(file_path, row_offset)`, or equality deletes, referencing column values to match)
  alongside the existing data files, without touching them. A read merges the delete
  file against the data files on the fly. This is the same "write something new,
  don't touch what exists" philosophy you used for compaction — extended to deletions
  instead of just additions.

This is arguably the most complex missing piece — it's also exactly why compaction
in real Iceberg is more involved than yours: `rewrite_data_files` also has to account
for reconciling any pending delete files against the data files it's merging.

---

## 9. Maintenance operations: nothing vs. expiry/orphan cleanup

You already identified this one directly: mini_iceberg never deletes anything, ever —
disk usage only grows.

Real Iceberg has two separate maintenance procedures for this, deliberately kept apart
from compaction:

- **`expire_snapshots`**: removes old snapshot *metadata* (and the manifests/manifest
  lists only *that* snapshot referenced) once they're older than a retention window,
  so `catalog.json`-equivalent state doesn't grow forever and time travel has a
  bounded horizon.
- **`remove_orphan_files`**: physically deletes data files no longer referenced by
  *any* remaining snapshot, after `expire_snapshots` has run.

These are deliberately separate, occasional, explicit operations — not something that
happens automatically on every commit — because running them too aggressively is
exactly what would break time travel, which is the whole feature this project is
demonstrating.

---

## 10. Multi-engine access: one Python process vs. many engines, one truth

mini_iceberg is a library one Python process imports. Real Iceberg's entire design
goal is that the *same table*, sitting on S3/GCS/HDFS with one REST/Glue/Hive catalog
entry, can be read and written by Spark, Trino, Flink, DuckDB, and PyIceberg
simultaneously, with all of them agreeing on what "current" means — because "current"
is defined entirely by the catalog pointer and immutable files, not by anything
engine-specific. This is really a restatement of point 6 (concurrency) and point 1
(the core mechanism), but it's worth naming as the actual business reason all of this
complexity exists: Iceberg's format is the interchange contract between engines that
otherwise share nothing.

---

## 11. Anti-patterns to avoid (learned from decisions this project actually made)

These are mistakes that are easy to make when extending a system shaped like this one
— each tied to a specific choice `mini_iceberg` got right, and what breaks if you
later "simplify" it away.

**Editing a manifest/metadata/snapshot file in place instead of writing a new one.**
Every read path (`active_entries`, `read`, `history`) trusts that once a `vN.metadata.json`
or `manifest-*.json` exists, its contents never change again. The moment any code
opens an existing one and rewrites it — even to fix a typo, even "just this once" —
every snapshot that referenced it silently changes retroactively, and time travel
stops meaning what it claims to mean. The fix is always "write a new file, then repoint
the thing above it," never "edit in place." You followed this correctly everywhere;
the anti-pattern is caving to it under time pressure later.

**Rebuilding the full manifest list from scratch on every append, instead of
accumulating.** It would be tempting to "clean up" `Table.append()` by having each
commit regenerate one manifest containing *every* active file, rather than one new
manifest listing only the new file. That reads as simpler, but it turns every append
into O(existing table size) work instead of O(new data) — the exact opposite of the
property that makes Iceberg-style appends cheap. (This *is* the correct thing to do
during compaction — the difference is compaction is an explicit, occasional operation,
not something that happens on every write.)

**Deleting old data files right after compaction "to save space."** We confirmed
directly that compaction leaves old files on disk untouched. The anti-pattern is
adding a `os.remove()` call at the end of `compact()` because the old files "aren't
needed anymore" — they're needed by exactly one thing: any snapshot ID older than the
compaction. Deleting them the moment they're compacted away silently breaks every
older `read(snapshot_id=...)` call, with no error until someone actually tries it.
Cleanup, if you ever add it, has to be its own explicit step that reasons about *every*
still-reachable snapshot first (see §9) — never a side effect of compaction.

**Reordering `_commit_snapshot()`'s steps.** The method writes the manifest → writes
the snapshot → writes the new metadata version → *then* calls `catalog._commit()` last.
This order isn't arbitrary: `catalog._commit()` is the single moment a new state
becomes visible to any other reader, so everything it points to (transitively, all the
way down to the data files) must already be fully and successfully written *before*
that call. Flip the order — say, update the catalog pointer first, then write the
metadata file — and a crash or concurrent read in between leaves the catalog pointing
at a metadata file that doesn't exist yet.

**Tracking version/snapshot-id counters separately from what's on disk.** `_version()`
parses the version number back out of `self.metadata_path`'s filename rather than
incrementing a stored counter; `_commit_snapshot()` computes the next snapshot id as
`1 + max(existing ids)` rather than tracking one. This was a deliberate choice: a
separate in-memory counter can drift from reality (e.g. if a previous process crashed
after writing a file but before updating its counter), while the filename/metadata
list can't — they're the actual state. The anti-pattern is adding a `self._next_version`
or `self._next_snapshot_id` field "for efficiency" — it reintroduces exactly the kind
of drift this design was built to avoid.

**Silently coercing or dropping unsupported schema types.** `schema_to_json` raises
`ValueError` on a `pyarrow` type it doesn't recognize, rather than skipping the column
or guessing a fallback type. A silently dropped or mis-typed column is invisible until
someone notices missing data much later — much worse than a loud failure at write time.
Any future extension to `_TYPE_TO_NAME` should keep this fail-loud behavior rather than
adding a permissive fallback branch.

**Storing absolute filesystem paths inside persisted metadata.** Every manifest entry,
snapshot, and catalog pointer in this project stores an absolute Windows path
(`C:\Data\...`). That's what makes the `warehouse/` folder non-portable — copy or move
it anywhere else and every stored path breaks. This wasn't a wrong choice for a
single-machine learning project, but it's worth naming as something to fix before
reusing any of this code somewhere paths might change (store paths relative to the
warehouse root instead, and resolve them against `root_dir` at read time).

---

## 12. Where performance would actually break down, and how to fix it

None of this matters at the scale you've been testing (a handful of rows, a handful of
files) — these are the things that would start to hurt as the table grows, and the
concrete fix for each, grounded in the actual code:

**`active_entries()` re-reads and re-parses every manifest from disk on every call.**
`read()` and `compact()` both call it, and it always walks the full manifest list for
the given snapshot from scratch — even if you just called it a second ago for the same
snapshot. This is safe to cache: because manifests and snapshots are immutable once
written, `active_entries(snapshot_id=5)`'s result can **never** change for as long as
that file exists. A simple `functools.lru_cache`-style cache keyed by `snapshot_id` (or
even a plain dict on the `Table` instance) would eliminate almost all of this repeated
I/O with zero risk of returning stale data — a rare case where caching is entirely free
of the usual invalidation headache, precisely *because* of the immutability this whole
project builds around.

**Compaction always merges every small file into exactly one output file, with no
target size.** If a table accumulated 10,000 tiny files, `compact()` as written loads
all 10,000 into memory at once (`pq.read_table` for each, then `pa.concat_tables`) and
writes one potentially huge output file. Real Iceberg's `rewrite_data_files` instead
**bin-packs**: it groups small files into batches targeting a configured output size
(e.g. 512 MB each), producing several right-sized files instead of one unbounded one,
and can bound how much it loads into memory per batch. The concrete fix here: add a
`target_file_size_bytes` parameter, sort/group `small` by size into bins that sum close
to that target, and call the merge-and-write step once per bin instead of once total.

**`compaction.py` converts the merged PyArrow table to pandas just to compute stats.**
`compact()` calls `types.column_stats(combined.to_pandas())` — for a large compacted
table, that's a second full copy of the data in memory (once as a PyArrow `Table`, once
as a pandas `DataFrame`) purely to compute a min/max. `append()` doesn't have this
problem, since its caller already hands it a DataFrame. The fix: compute stats directly
on the PyArrow table via `pyarrow.compute.min`/`max` per column, avoiding the conversion
entirely — same result, half the peak memory during compaction specifically.

**No client-side batching before appends.** Every `append()` call writes one Parquet
file, no matter how small. If callers append one row at a time (a very plausible
real-world pattern — e.g. streaming ingestion), that's the small-file problem
compounding as fast as possible. Real ingestion pipelines usually buffer rows
client-side and flush a batch (by row count, byte size, or time interval) before ever
calling the equivalent of `append()`, treating compaction as a periodic backstop rather
than the primary mitigation. Nothing prevents you from doing this on top of the
existing `Table.append()` unchanged — it's a caller-side discipline, not a library
change.

**Manifests can only be compacted together with the data files they describe.**
Right now, the only way to reduce manifest count is `compact()`, which requires
physically rewriting the underlying data files too — even if those files are already
comfortably large and only the *metadata* has fragmented (e.g. after many appends of
already-reasonably-sized files). Real Iceberg has a separate `rewrite_manifests`
action for exactly this: consolidate manifests without touching any data files. A
natural extension here would be a `compact_manifests_only(table)` that merges
`active_entries()`'s underlying manifests into one, keeping every existing entry
unchanged, and commits it as a new snapshot the same way `compact()` does — just
skipping the "load and rewrite Parquet" step entirely.

---

## Summary table

| Concept | mini_iceberg | Apache Iceberg | Complexity driver |
|---|---|---|---|
| Catalog → metadata → snapshot → manifest → file | ✅ same shape | ✅ | — |
| Immutability + pointer-swap commits | ✅ same shape | ✅ | — |
| Time travel by snapshot id | ✅ | ✅ (+ as-of-timestamp, branches/tags) | — |
| Manifest/snapshot file format | JSON | Avro | scale (large manifests) |
| Schema evolution | name-based | field-ID based | rename-safety, real evolution |
| Column stats | recorded, unused | recorded + used for pruning | query performance |
| Partitioning | none | hidden, evolvable partition specs | query performance at scale |
| Concurrency | single-threaded | optimistic concurrency + retry | multiple concurrent writers |
| Snapshot ordering | id + timestamp | id + timestamp + **sequence number** | clock skew, concurrent commits |
| Row-level mutation | append-only | delete files (COW/MOR) | UPDATE/DELETE/MERGE support |
| Old-file cleanup | never (by design) | `expire_snapshots` / `remove_orphan_files` | bounded storage growth |
| Access model | one Python process | many engines, one shared catalog | interchange across tools |

Every row in the "complexity driver" column is a *production concern this project
never had to face* (concurrent writers, huge tables, multiple query engines, storage
cost at scale) — not a flaw in the design you built. The mechanism is the same; real
Iceberg is this mechanism plus the answers to "what happens when this runs for years,
at petabyte scale, with a dozen engines and writers hitting it at once."
