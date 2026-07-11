"""Phase 2 (part 1): Manifest files — tracking individual physical data files.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
A manifest is the lowest level of Iceberg's metadata tree. It answers one
question: "of the Parquet files that make up this table, which ones exist,
and what do they contain?" Each entry records:
  - file-path: where the actual Parquet file lives
  - record-count / file-size-bytes: cheap facts used for read planning
    (e.g. "do I even need to open this file?") and, in Phase 4, for deciding
    which files are "small" and worth compacting
  - column-stats (min/max per column): this is what lets a real query engine
    skip entire files without reading them — if you're filtering `WHERE id >
    1000` and a file's manifest entry says id ranges [1, 50], the engine never
    opens that file. We compute and store these stats even though our mini
    reader (table.py) won't actually use them to prune — recording them is
    the point of this phase; using them for pruning would be a natural
    follow-up extension.

Why manifests are their own file, separate from the snapshot (snapshot.py):
appends should be cheap. Appending 100 rows should not require rewriting the
stats for every file the table has ever had. So each append writes ONE new
manifest containing ONLY the new file's entry, and the new snapshot's
manifest list = [...all previous manifests, this new one]. Old manifests are
never edited — same immutability rule as metadata.py, one level down. This is
also exactly why small files accumulate over time (many appends -> many
manifests, each pointing at one small file) and why Phase 4's compaction is
needed: it's the operation that collapses many manifests into one.
"""

import json
import os
import uuid


def make_entry(file_path: str, record_count: int, file_size_bytes: int, column_stats: dict) -> dict:
    """Build a single manifest entry dict for one data file.

    Example:
        make_entry("warehouse/users/data/abc.parquet", 2, 1234, {"id": {"min": 1, "max": 2}})
        # -> {"status": "added", "file-path": "warehouse/users/data/abc.parquet",
        #     "record-count": 2, "file-size-bytes": 1234,
        #     "column-stats": {"id": {"min": 1, "max": 2}}}

    "status" is always "added" in this mini version — real Iceberg also has
    "existing" (carried forward unchanged) and "deleted" statuses to support
    incremental manifest rewrites; we don't need those distinctions since
    compaction.py (Phase 4) just omits entries it doesn't want to carry
    forward rather than marking them deleted (see the README's Phase 4 note).
    """
    return {
        "status": "added",
        "file-path": file_path,
        "record-count": record_count,
        "file-size-bytes": file_size_bytes,
        "column-stats": column_stats,
    }


def write_manifest(metadata_dir: str, entries: list) -> str:
    """Write a new manifest file containing the given entries; returns its path.

    Example:
        write_manifest("warehouse/users/metadata", [entry])
        # -> "warehouse/users/metadata/manifest-9f2a1b....json"
        # that file on disk now contains: {"entries": [entry]}

    Steps:
      - path = os.path.join(metadata_dir, f"manifest-{uuid.uuid4().hex}.json")
        (a random name, not a version number — unlike vN.metadata.json,
        manifests aren't a linear sequence; a snapshot can reference several
        of them at once, so there's no single "next number")
      - write {"entries": entries} as JSON to that path
      - return path
    """
    manifest_path = os.path.join(metadata_dir, f"manifest-{uuid.uuid4().hex}.json")
    with open(manifest_path, "w") as f:
        json.dump({"entries": entries}, f, indent=4)
    return manifest_path

def read_manifest(path: str) -> list:
    """Read a manifest file back into its list of entries.

    Example:
        read_manifest("warehouse/users/metadata/manifest-9f2a1b....json")
        # -> [{"status": "added", "file-path": "...", "record-count": 2, ...}]

    Steps: open `path`, json.load it, return the `"entries"` list.
    """
    with open(path, "r") as f:
        manifest_dict = json.load(f)
    return manifest_dict["entries"]
