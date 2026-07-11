import os

import pandas as pd

from mini_iceberg import manifest, snapshot, types


def test_manifest_round_trip(tmp_path):
    entry = manifest.make_entry(
        file_path="data/abc.parquet",
        record_count=10,
        file_size_bytes=2048,
        column_stats={"id": {"min": 1, "max": 10}},
    )
    assert entry["status"] == "added"
    assert entry["file-path"] == "data/abc.parquet"

    path = manifest.write_manifest(str(tmp_path), [entry])
    assert os.path.isfile(path)
    assert os.path.basename(path).startswith("manifest-")

    entries = manifest.read_manifest(path)
    assert entries == [entry]


def test_snapshot_round_trip(tmp_path):
    path = snapshot.write_snapshot(
        str(tmp_path),
        snapshot_id=1,
        timestamp_ms=1_700_000_000_000,
        parent_snapshot_id=None,
        manifests=["metadata/manifest-a.json"],
    )
    assert os.path.basename(path) == "snap-1.json"

    snap = snapshot.read_snapshot(path)
    assert snap["snapshot-id"] == 1
    assert snap["parent-snapshot-id"] is None
    assert snap["manifests"] == ["metadata/manifest-a.json"]


def test_column_stats_numeric_and_string():
    df = pd.DataFrame({"id": [3, 1, 2], "name": ["carol", "alice", "bob"]})
    stats = types.column_stats(df)
    assert stats["id"] == {"min": 1, "max": 3}
    assert stats["name"] == {"min": "alice", "max": "carol"}


def test_column_stats_skips_all_null_column():
    df = pd.DataFrame({"id": [1, 2], "empty": [None, None]})
    stats = types.column_stats(df)
    assert "id" in stats
    assert "empty" not in stats
