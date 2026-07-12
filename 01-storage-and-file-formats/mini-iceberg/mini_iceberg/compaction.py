"""Phase 4 (the capstone): compaction — rewrite many small files into one large file.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
This is the "small file problem" real data lakes hit constantly: every append
(Phase 3) writes one new Parquet file. Frequent small appends (streaming
ingestion, micro-batches, etc.) mean a table can end up backed by thousands of
tiny files. Each file costs a fixed amount of overhead to open/read regardless
of how little data it holds, and each has its own manifest entry, so query
planning also gets slower as file count grows. Compaction is offline
maintenance that fixes the PHYSICAL layout without changing the LOGICAL
data — after compaction, `table.read()` must return exactly the same rows as
before, just sourced from fewer, larger files.

The critical design point (this is the "architectural win" the README refers
to): compaction is committed as a NEW SNAPSHOT, not an in-place rewrite.

  - The old small Parquet files are left on disk, untouched.
  - The old manifests that reference them are left on disk, untouched.
  - A brand new manifest is written that OMITS the small files' entries and
    ADDS one entry for the new large file. Carried-forward files (ones that
    were already active but weren't part of this compaction pass, e.g.
    because they were already big enough) get their entries copied into the
    new manifest as-is.
  - A new snapshot is committed pointing ONLY at this new manifest (unlike
    append, which keeps accumulating the manifest list — compaction's whole
    point is to collapse it back down to one).

Because nothing old is deleted, `table.read(snapshot_id=<pre-compaction id>)`
keeps working after compaction runs — time travel to before the compaction
still resolves to the original small files, which are still sitting right
where they were. This is exactly why append() never rewrites old manifests
and why metadata.py never rewrites old metadata versions: that same
discipline is what makes compaction "just another commit" instead of a
special destructive operation you have to be careful about.

(A production system would eventually need a separate "expire old snapshots /
delete orphaned files" maintenance job to reclaim the disk space the
untouched old files are using — deliberately out of scope here, since it
would undo the time-travel guarantee this phase is demonstrating.)
"""

import os
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

from . import manifest as manifest_io
from . import types


def compact(table, small_file_threshold_bytes: int) -> dict:
    """Rewrite files under `small_file_threshold_bytes` into a single new file.

    Example:
        # table has 5 small appended files, each a few bytes, current snapshot is 5
        compact(table, small_file_threshold_bytes=1_048_576)
        # -> {"compacted": True, "files-rewritten": 5,
        #     "new-file": "warehouse/events/data/9f2a....parquet", "snapshot-id": 6}
        # table.read() still returns the same rows as before, just from 1 file now.

        # table has only 1 file total, nothing worth merging
        compact(table, small_file_threshold_bytes=1_048_576)
        # -> {"compacted": False, "files-rewritten": 0}

    TODO:
      1. entries = table.active_entries() — reuse Table's own resolver (see
         table.py) so compaction can never disagree with read() about what
         "currently active" means.
      2. small = {path: entry for path, entry in entries.items()
                  if entry["file-size-bytes"] < small_file_threshold_bytes}
      3. If len(small) < 2: return {"compacted": False, "files-rewritten": 0}
         (compacting a single file, or zero files, has nothing to gain — don't
         churn out a no-op snapshot)
      4. Load every small file with pq.read_table(path) and combine them:
         combined = pa.concat_tables([...])
      5. Write combined out as one new file:
         new_file_path = os.path.join(table.data_dir, f"{uuid.uuid4().hex}.parquet")
         pq.write_table(combined, new_file_path)
      6. Build its manifest entry via manifest_io.make_entry(...), using
         combined.num_rows, os.path.getsize(new_file_path), and
         types.column_stats(combined.to_pandas()) for the stats.
      7. carried_forward = [entry for path, entry in entries.items() if path not in small]
         (everything that was active but NOT part of this compaction pass —
         copied into the new manifest unchanged)
      8. Write ONE new manifest containing carried_forward + [new_entry] via
         manifest_io.write_manifest(table.metadata_dir, ...).
      9. Commit it as a new snapshot: table._commit_snapshot(
             [new_manifest_path], table.current_snapshot_id, operation="compaction")
         (manifest list = just this one manifest — not appended to the parent's
         list, unlike Table.append(); see the module docstring for why)
     10. Return {"compacted": True, "files-rewritten": len(small),
                 "new-file": new_file_path, "snapshot-id": <id from step 9>}
    """
    entries = table.active_entries()
    small = {
        path: entry
        for path, entry in entries.items()
        if entry["file-size-bytes"] < small_file_threshold_bytes
    }

    if len(small) < 2:
        return {"compacted": False, "files-rewritten": 0}

    small_tables = [pq.read_table(path) for path in small]
    combined = pa.concat_tables(small_tables)

    new_file_path = os.path.join(table.data_dir, f"{uuid.uuid4().hex}.parquet")
    pq.write_table(combined, new_file_path)

    new_entry = manifest_io.make_entry(
        file_path=new_file_path,
        record_count=combined.num_rows,
        file_size_bytes=os.path.getsize(new_file_path),
        column_stats=types.column_stats(combined.to_pandas()),
    )

    carried_forward = [entry for path, entry in entries.items() if path not in small]
    new_manifest_path = manifest_io.write_manifest(
        table.metadata_dir, carried_forward + [new_entry]
    )

    new_snapshot_id = table._commit_snapshot(
        [new_manifest_path], table.current_snapshot_id, operation="compaction"
    )

    return {
        "compacted": True,
        "files-rewritten": len(small),
        "new-file": new_file_path,
        "snapshot-id": new_snapshot_id,
    }
