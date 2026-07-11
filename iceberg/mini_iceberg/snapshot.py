"""Phase 2 (part 2): Snapshots (manifest lists) — the commit record.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
A snapshot is what "a commit" means in Iceberg. It doesn't contain any data
itself — it's a manifest LIST: the set of manifest files (manifest.py) that
were active at the moment this commit happened, plus a bit of bookkeeping:

  - snapshot-id: a unique identifier a reader can pass to time-travel back to
    exactly this state (this is the id table.py's read(snapshot_id=...) takes)
  - timestamp-ms: when the commit happened (real Iceberg also supports
    "as-of-time" travel using this; we only require the id-based version)
  - parent-snapshot-id: the snapshot this one was committed on top of, which
    turns the snapshot history into a linked list — you can walk backwards
    from "current" to see the whole lineage of the table (that's exactly what
    table.py's history() exposes)
  - manifests: the list of manifest file paths active in this snapshot

Why manifests accumulate across snapshots instead of each snapshot only
listing its own new manifest: a snapshot must be a COMPLETE description of
the table's state on its own — a reader time-traveling to snapshot 2 should
never need to also consult snapshot 1's manifest list to find files that are
still live. So an append's new snapshot manifest list = parent's manifest
list + [new manifest]. A compaction's new snapshot manifest list is a fresh,
collapsed list (see compaction.py) — because compaction's entire point is to
replace many manifests referencing many small files with one manifest
referencing one big file.
"""

import json
import os


def write_snapshot(
    metadata_dir: str,
    snapshot_id: int,
    timestamp_ms: int,
    parent_snapshot_id,
    manifests: list,
) -> str:
    """Write a manifest-list JSON file for this snapshot; returns its path.

    Example:
        write_snapshot("warehouse/users/metadata", 2, 1_700_000_000_000, 1,
                        ["warehouse/users/metadata/manifest-a.json",
                         "warehouse/users/metadata/manifest-b.json"])
        # -> "warehouse/users/metadata/snap-2.json"
        # that file on disk now contains:
        #   {"snapshot-id": 2, "timestamp-ms": 1700000000000, "parent-snapshot-id": 1,
        #    "manifests": ["warehouse/users/metadata/manifest-a.json",
        #                  "warehouse/users/metadata/manifest-b.json"]}

    Steps:
      - path = os.path.join(metadata_dir, f"snap-{snapshot_id}.json")
      - write the dict above as JSON to that path
      - return path
    """
    snapshot_dict = {
        "snapshot-id": snapshot_id,
        "timestamp-ms": timestamp_ms,
        "parent-snapshot-id": parent_snapshot_id,
        "manifests": manifests,
    }
    path = os.path.join(metadata_dir, f"snap-{snapshot_id}.json")
    with open(path, 'w') as f:
        json.dump(snapshot_dict, f, indent=2)
    return path


def read_snapshot(path: str) -> dict:
    """Read a snapshot (manifest-list) file back into a dict.

    Example:
        read_snapshot("warehouse/users/metadata/snap-2.json")
        # -> {"snapshot-id": 2, "timestamp-ms": 1700000000000, "parent-snapshot-id": 1,
        #     "manifests": ["warehouse/users/metadata/manifest-a.json", ...]}

    Steps: open `path`, json.load it, return the dict.
    """
    with open(path, 'r') as f:
        return json.load(f)
