"""Phase 3: the Table — append() and read(), including time travel.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
Everything in Phase 1 (catalog) and Phase 2 (manifests/snapshots) exists to
support two operations a user actually cares about:

  - append(df): add new rows, producing a new immutable snapshot
  - read(snapshot_id=None): materialize a DataFrame as of some point in time

The whole design so far pays off here. An append is cheap (Phase 2's docstring
explains why: one new data file, one new manifest, one new snapshot — nothing
existing is rewritten). A read at an OLD snapshot_id works for free, with zero
special-casing, because nothing is ever deleted or mutated: the old snapshot's
manifest-list file still exists, still lists manifests that still exist,
which still point at Parquet files that still exist. Time travel isn't a
separate mechanism bolted on — it's a side effect of never overwriting
anything.

`active_entries()` is written as its own method (rather than being inlined
into read()) specifically because Phase 4's compact() needs the exact same
"resolve a snapshot to its currently-live files" logic to decide what to
rewrite. Sharing it means compaction and reads can never disagree about what
"the current files" are.
"""

import os
import time
import uuid

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import manifest as manifest_io
from . import metadata as metadata_io
from . import snapshot as snapshot_io
from . import types


class Table:
    def __init__(self, catalog, name: str, table_dir: str, metadata_path: str):
        """Bind this Table to a catalog + on-disk location, then load its state.

        Example:
            Table(catalog, "users", "warehouse/users", "warehouse/users/metadata/v1.metadata.json")
            # -> table.data_dir == "warehouse/users/data"
            #    table.metadata_dir == "warehouse/users/metadata"
            #    table.schema == pa.schema([("id", pa.int64()), ("name", pa.string())])
            #    table.current_snapshot_id == None   (fresh table, no appends yet)

        TODO:
          - store catalog, name, table_dir
          - derive self.data_dir = <table_dir>/data and
            self.metadata_dir = <table_dir>/metadata (same derivation the
            catalog uses — a Table should be constructible from nothing more
            than table_dir + metadata_path)
          - store self.metadata_path = metadata_path
          - call self._reload() to actually load the metadata/schema (don't
            duplicate that loading logic here — every commit will need to
            re-run it too, so it belongs in one place)
        """
        self.catalog = catalog
        self.name = name
        self.table_dir = table_dir
        self.data_dir = os.path.join(table_dir, "data")
        self.metadata_dir = os.path.join(table_dir, "metadata")
        self.metadata_path = metadata_path
        self._reload()

    def _reload(self):
        """(Re)load self._metadata and self.schema from self.metadata_path.

        Example:
            # self.metadata_path == "warehouse/users/metadata/v2.metadata.json", which contains
            # {"schema": [...], "current-snapshot-id": 2, "snapshots": [...]}
            self._reload()
            # -> self._metadata == that dict, self.schema == the rebuilt pa.Schema

        TODO:
          - self._metadata = metadata_io.read_metadata(self.metadata_path)
          - self.schema = types.schema_from_json(self._metadata["schema"])

        Called once from __init__, and again at the end of every commit (see
        _commit_snapshot) so the in-memory Table always reflects the
        metadata_path it currently points at — never let self._metadata drift
        out of sync with self.metadata_path.
        """
        self._metadata = metadata_io.read_metadata(self.metadata_path)
        self.schema = types.schema_from_json(self._metadata["schema"])

    @property
    def current_snapshot_id(self):
        """Return self._metadata["current-snapshot-id"] (may be None for a
        table that has never had an append).

        Example: a brand-new table -> None. After two appends -> 2.
        """
        return self._metadata["current-snapshot-id"]

    def history(self) -> list:
        """Return the full list of snapshot summary dicts, oldest first.

        Example (continuing from append()'s example, after both commits):
            table.history()
            # -> [{"snapshot-id": 1, "timestamp-ms": ..., "manifest-list": "...",
            #      "summary": {"operation": "append"}},
            #     {"snapshot-id": 2, "timestamp-ms": ..., "manifest-list": "...",
            #      "summary": {"operation": "append"}}]

        TODO: return list(self._metadata["snapshots"]) — a copy, so callers
        can't mutate the Table's internal state by mutating the list.
        """
        return list(self._metadata["snapshots"])

    def _version(self) -> int:
        """Parse the version number N out of self.metadata_path's "vN.metadata.json".

        Why derive it from the filename instead of tracking a separate
        counter: the file that exists on disk IS the source of truth for what
        version we're at — a separate counter could drift out of sync with
        reality (e.g. if a previous run crashed after writing the file but
        before updating an in-memory counter).

        Example:
            # self.metadata_path == "warehouse/users/metadata/v3.metadata.json"
            self._version()  # -> 3

        TODO: basename = os.path.basename(self.metadata_path); strip the
        leading "v" and trailing ".metadata.json"; int() the remainder.
        """
        basename = os.path.basename(self.metadata_path)
        return int(basename[1:-14])  # Strip "v" and ".metadata.json"

    def _snapshot_summary(self, snapshot_id: int) -> dict:
        """Find the snapshot summary dict for `snapshot_id` in self._metadata["snapshots"].

        Example:
            self._snapshot_summary(1)
            # -> {"snapshot-id": 1, "timestamp-ms": ..., "manifest-list": "...",
            #     "summary": {"operation": "append"}}
            self._snapshot_summary(999)  # -> raises KeyError

        TODO: linear-scan self._metadata["snapshots"] for a matching
        "snapshot-id"; raise KeyError if none matches.
        """
        for snapshot in self._metadata["snapshots"]:
            if snapshot["snapshot-id"] == snapshot_id:
                return snapshot
        raise KeyError(f"Snapshot ID {snapshot_id} not found in table '{self.name}'.")

    def active_entries(self, snapshot_id=None) -> dict:
        """Map file-path -> manifest entry for every file active as of `snapshot_id`.

        This is the shared "what files make up the table right now" resolver
        used by both read() and compaction.compact().

        Example:
            table.active_entries()
            # -> {"warehouse/users/data/abc123.parquet":
            #        {"status": "added", "file-path": "...", "record-count": 2,
            #         "file-size-bytes": 1234, "column-stats": {"id": {"min": 1, "max": 2}, ...}},
            #     "warehouse/users/data/def456.parquet": {...}}

        TODO:
          - snapshot_id = self.current_snapshot_id if snapshot_id is None else snapshot_id
          - if snapshot_id is None, return {} (a table with no snapshots yet
            has no data — don't treat this as an error)
          - look up the snapshot summary via self._snapshot_summary(snapshot_id)
          - load it with snapshot_io.read_snapshot(summary["manifest-list"])
          - for every manifest path in its "manifests" list, load its entries
            via manifest_io.read_manifest(...) and, for every entry whose
            "status" == "added", add entries[entry["file-path"]] = entry
          - return the accumulated dict
        """
        if snapshot_id is None:
            snapshot_id = self.current_snapshot_id

        if snapshot_id is None:
            return {}

        snapshot_summary = self._snapshot_summary(snapshot_id)
        manifest_list_path = snapshot_summary["manifest-list"]
        manifest_list = snapshot_io.read_snapshot(manifest_list_path)["manifests"]

        entries = {}
        for manifest_path in manifest_list:
            manifest_entries = manifest_io.read_manifest(manifest_path)
            for entry in manifest_entries:
                if entry["status"] == "added":
                    entries[entry["file-path"]] = entry
        return entries

    def append(self, df: pd.DataFrame) -> int:
        """Append `df` as a new data file, committing a new snapshot. Returns the new snapshot id.

        Example:
            df = pd.DataFrame({"id": [1, 2], "name": ["alice", "bob"]})
            table.append(df)   # -> 1   (first commit, so snapshot id 1)

            df2 = pd.DataFrame({"id": [3], "name": ["carol"]})
            table.append(df2)  # -> 2   (second commit)

        TODO:
          1. Cast/validate df against the schema:
             pa_table = pa.Table.from_pandas(df, schema=self.schema, preserve_index=False)
             (this is what makes the schema a "rigid baseline" — a DataFrame
             with the wrong types or an extra column fails here, loudly,
             instead of silently writing a bad file)
          2. Write it to a new Parquet file:
             file_path = os.path.join(self.data_dir, f"{uuid.uuid4().hex}.parquet")
             pq.write_table(pa_table, file_path)
          3. Build a manifest entry (manifest_io.make_entry) using
             pa_table.num_rows, os.path.getsize(file_path), and
             types.column_stats(df) — then write it as a brand-new manifest
             via manifest_io.write_manifest(self.metadata_dir, [entry])
             (only this one new entry — see manifest.py's docstring for why)
          4. Determine the parent snapshot's manifest list: if
             self.current_snapshot_id is None, that's [] (first-ever append);
             otherwise it's snapshot_io.read_snapshot(...)["manifests"] for
             the current snapshot.
          5. new_manifests = parent_manifests + [new_manifest_path]
          6. return self._commit_snapshot(new_manifests, self.current_snapshot_id, operation="append")
        """
        pa_table = pa.Table.from_pandas(df, schema=self.schema, preserve_index=False)
        file_path = os.path.join(self.data_dir, f"{uuid.uuid4().hex}.parquet")
        pq.write_table(pa_table, file_path)

        entry = manifest_io.make_entry(
            file_path=file_path,
            record_count=pa_table.num_rows,
            file_size_bytes=os.path.getsize(file_path),
            column_stats=types.column_stats(df)
        )

        new_manifest_path = manifest_io.write_manifest(self.metadata_dir, [entry])

        if self.current_snapshot_id is None:
            parent_manifests = []
        else:
            current_snapshot_summary = self._snapshot_summary(self.current_snapshot_id)
            parent_manifests = snapshot_io.read_snapshot(current_snapshot_summary["manifest-list"])["manifests"]

        new_manifests = parent_manifests + [new_manifest_path]
        return self._commit_snapshot(new_manifests, self.current_snapshot_id, operation="append")

    def _commit_snapshot(self, manifests: list, parent_id, operation: str) -> int:
        """Shared commit path used by both append() and compaction.compact().

        This is deliberately the ONE place that writes a snapshot + a new
        metadata version + updates the catalog pointer + reloads — append and
        compaction differ only in how they compute `manifests`, not in how a
        commit is actually recorded. Keeping this logic in one spot means
        there's only one place that can get the commit protocol wrong.

        Example:
            # called from append(), current version is v2, snapshot 2 is current
            self._commit_snapshot(["manifest-a.json", "manifest-b.json"], parent_id=2, operation="append")
            # -> writes warehouse/users/metadata/snap-3.json and v3.metadata.json,
            #    updates the catalog to point at v3, reloads, returns 3

        TODO:
          1. Compute the next snapshot id: 1 if self._metadata["snapshots"] is
             empty, else 1 + max existing "snapshot-id" (mirrors _version()'s
             "derive from what exists" philosophy — no separate counter)
          2. timestamp_ms = int(time.time() * 1000)
          3. Write the manifest list: snapshot_io.write_snapshot(
                 self.metadata_dir, new_snapshot_id, timestamp_ms, parent_id, manifests)
          4. Build the new snapshot summary dict:
                 {"snapshot-id": new_snapshot_id, "timestamp-ms": timestamp_ms,
                  "manifest-list": <path from step 3>,
                  "summary": {"operation": operation}}
             and append it to self._metadata["snapshots"] (a NEW list — don't
             mutate the old one in place, since the old vN.metadata.json's
             in-memory dict is what "the previous version" looked like)
          5. Write the new metadata version: metadata_io.write_metadata(
                 self.metadata_dir, self._version() + 1, self._metadata["schema"],
                 <new snapshots list>, new_snapshot_id)
          6. self.catalog._commit(self.name, <new metadata path>) — this is
             the moment the new state becomes visible to every other reader
          7. self.metadata_path = <new metadata path>; self._reload()
          8. return new_snapshot_id
        """
        if not self._metadata["snapshots"]:
            new_snapshot_id = 1
        else:
            new_snapshot_id = 1 + max(s["snapshot-id"] for s in self._metadata["snapshots"])

        timestamp_ms = int(time.time() * 1000)

        manifest_list_path = snapshot_io.write_snapshot(
            self.metadata_dir, new_snapshot_id, timestamp_ms, parent_id, manifests
        )

        new_snapshot_summary = {
            "snapshot-id": new_snapshot_id,
            "timestamp-ms": timestamp_ms,
            "manifest-list": manifest_list_path,
            "summary": {"operation": operation}
        }

        new_snapshots_list = list(self._metadata["snapshots"]) + [new_snapshot_summary]

        new_metadata_path = metadata_io.write_metadata(
            self.metadata_dir,
            version=self._version() + 1,
            schema_json=types.schema_to_json(self.schema),
            snapshots=new_snapshots_list,
            current_snapshot_id=new_snapshot_id
        )

        self.catalog._commit(self.name, new_metadata_path)

        self.metadata_path = new_metadata_path
        self._reload()

        return new_snapshot_id

    def read(self, snapshot_id=None) -> pd.DataFrame:
        """Materialize the table as a DataFrame, as of `snapshot_id` (default: current).

        Example (continuing from append()'s example, after both commits above):
            table.read()               # -> DataFrame with 3 rows: alice, bob, carol
            table.read(snapshot_id=1)  # -> DataFrame with 2 rows: alice, bob
                                        #    (carol didn't exist yet as of snapshot 1)

        TODO:
          - entries = self.active_entries(snapshot_id)
          - if entries is empty, return an empty DataFrame matching the
            schema (self.schema.empty_table().to_pandas()) rather than an
            untyped empty DataFrame — callers shouldn't have to special-case
            "no data yet" vs. "some data"
          - otherwise, pq.read_table(path) for every path in entries, then
            pa.concat_tables(...).to_pandas() and return it

        Passing an old snapshot_id here is the entire time-travel feature —
        there is no separate "time travel mode"; it's the same code path with
        a different snapshot_id resolved to a different (older) set of files.
        """
        entries = self.active_entries(snapshot_id)
        if not entries:
            return self.schema.empty_table().to_pandas()

        tables = [pq.read_table(entry["file-path"]) for entry in entries.values()]
        combined_table = pa.concat_tables(tables)
        return combined_table.to_pandas()
