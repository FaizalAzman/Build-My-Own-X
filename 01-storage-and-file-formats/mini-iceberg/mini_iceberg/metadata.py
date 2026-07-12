"""Table metadata: the root JSON tracking schema, snapshot history, and current state.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
In real Apache Iceberg, "table metadata" is the single source of truth for a
table's entire state: its schema, its partition spec, and — critically — the
full list of every snapshot (commit) that has ever happened to the table, plus
a pointer to which one is "current".

The one rule that makes the whole format work: **a metadata file, once
written, is never edited again.** Every commit (an append, a delete, a
compaction — anything) writes a brand-new file: v1.metadata.json,
v2.metadata.json, v3.metadata.json, etc. Nothing is ever mutated in place.

Why immutability matters:
  - A reader that opens v2.metadata.json and starts scanning snapshots is
    guaranteed to see a complete, consistent view — there is no way to observe
    a "half-written" commit, because half-written files are never the ones
    catalog.json points at (see catalog.py's _commit/_save — the pointer only
    moves *after* the file is fully on disk).
  - It's what makes time travel possible at the metadata level: you can open
    v1.metadata.json directly and see exactly what the table looked like
    right after the first commit, even though v5 exists now.
  - It's the foundation real Iceberg builds optimistic concurrency on: two
    writers can both read v2, both try to write v3 — whoever's atomic
    swap of the catalog pointer lands first wins, and the loser detects the
    conflict and retries against the new v3. (We're single-threaded here, so
    you won't implement the retry loop, but this is *why* the "write new file,
    then swap a pointer" shape exists instead of "open file, edit, save".)

Phase 1 only ever writes the initial version (empty snapshot history, no
current snapshot yet — there's nothing to append to yet). Phase 2 will call
this again each time a new snapshot is committed.
"""

import json
import os


def write_metadata(
    metadata_dir: str,
    version: int,
    schema_json: list,
    snapshots: list,
    current_snapshot_id,
) -> str:
    """Write a new immutable vN.metadata.json file; returns its path.

    On-disk shape (this *is* the table's entire tracked history):
        {
          "format-version": 1,
          "schema": schema_json,
          "current-snapshot-id": current_snapshot_id,
          "snapshots": snapshots
        }

    Note "snapshots" is the *whole list so far*, not just the new one — each
    version file is a complete standalone record, not a diff against the
    previous version. That's what lets you delete every version file except
    the latest and still have a fully working table (real Iceberg does exactly
    this during "metadata expiry" cleanup).

    Steps:
      1. path = os.path.join(metadata_dir, f"v{version}.metadata.json")
      2. write the dict above as JSON to that path
      3. return path

    Do NOT ever open an existing vN file and rewrite it — always a new version
    number, matching the immutability rule described in the module docstring.
    """
    path  = os.path.join(metadata_dir, f"v{version}.metadata.json")
    metadata = {
        "format-version": 1,
        "schema": schema_json,
        "current-snapshot-id": current_snapshot_id,
        "snapshots": snapshots
    }

    with open(path, 'w') as f:
        json.dump(metadata, f, indent=4)

    return path

def read_metadata(path: str) -> dict:
    """Read a vN.metadata.json file back into a dict.

    Steps: open `path`, json.load it, return the dict.
    """
    with open(path, 'r') as f:
        return json.load(f)
