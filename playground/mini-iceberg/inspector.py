"""Reads a mini_iceberg warehouse straight from disk and describes its metadata tree.

Deliberately uses only json + os, not the mini_iceberg library: the inspector
shows what is actually on disk, so it still tells the truth when the library
gets something wrong (see the two-writers experiment).
"""

import json
import os


def _load(path):
    with open(path) as f:
        return json.load(f)


def describe(root):
    catalog_path = os.path.join(root, "catalog.json")
    if not os.path.exists(catalog_path):
        return json.dumps({"tables": []})

    rel = lambda p: os.path.relpath(p, root)
    tables = []
    for name, metadata_path in _load(catalog_path)["tables"].items():
        table_dir = os.path.dirname(os.path.dirname(metadata_path))
        metadata = _load(metadata_path)
        reachable = {os.path.normpath(metadata_path)}
        snapshots = []

        for summary in metadata["snapshots"]:
            snap_path = summary["manifest-list"]
            reachable.add(os.path.normpath(snap_path))
            snap = _load(snap_path) if os.path.exists(snap_path) else {"manifests": []}
            manifests, active = [], []
            for manifest_path in snap["manifests"]:
                reachable.add(os.path.normpath(manifest_path))
                entries = _load(manifest_path)["entries"] if os.path.exists(manifest_path) else []
                files = []
                for entry in entries:
                    reachable.add(os.path.normpath(entry["file-path"]))
                    files.append({
                        "path": rel(entry["file-path"]),
                        "rows": entry["record-count"],
                        "bytes": entry["file-size-bytes"],
                        "missing": not os.path.exists(entry["file-path"]),
                    })
                active.extend(f["path"] for f in files)
                manifests.append({
                    "path": rel(manifest_path),
                    "missing": not os.path.exists(manifest_path),
                    "files": files,
                })
            snapshots.append({
                "id": summary["snapshot-id"],
                "parent": snap.get("parent-snapshot-id"),
                "operation": summary["summary"]["operation"],
                "timestamp_ms": summary["timestamp-ms"],
                "manifest_list": rel(snap_path),
                "missing": not os.path.exists(snap_path),
                "manifests": manifests,
                "active_files": active,
                "rows": sum(f["rows"] for m in manifests for f in m["files"]),
            })

        on_disk = []
        for dirpath, _, filenames in os.walk(table_dir):
            on_disk.extend(os.path.normpath(os.path.join(dirpath, n)) for n in filenames)
        versions = sorted(
            (p for p in on_disk if p.endswith(".metadata.json")),
            key=lambda p: int(os.path.basename(p)[1:-14]),
        )
        orphans = [
            rel(p) for p in on_disk
            if p not in reachable and not p.endswith(".metadata.json")
        ]

        tables.append({
            "name": name,
            "current_metadata": rel(metadata_path),
            "metadata_versions": [rel(p) for p in versions],
            "current_snapshot_id": metadata["current-snapshot-id"],
            "schema": metadata["schema"],
            "snapshots": snapshots,
            "orphans": sorted(orphans),
            "counts": {
                "data_files": sum(p.endswith(".parquet") for p in on_disk),
                "manifests": sum(os.path.basename(p).startswith("manifest-") for p in on_disk),
                "snapshots": sum(os.path.basename(p).startswith("snap-") for p in on_disk),
                "metadata_versions": len(versions),
                "bytes": sum(os.path.getsize(p) for p in on_disk),
            },
        })
    return json.dumps({"tables": tables})
