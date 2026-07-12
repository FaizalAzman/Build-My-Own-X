import os

import pandas as pd
import pyarrow as pa

from mini_iceberg.catalog import Catalog
from mini_iceberg.compaction import compact

SCHEMA = pa.schema([("id", pa.int64()), ("name", pa.string())])


def test_compaction_collapses_small_files_without_changing_data(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("events", SCHEMA)

    snap1 = table.append(pd.DataFrame({"id": [1], "name": ["a"]}))
    for i in range(2, 6):
        table.append(pd.DataFrame({"id": [i], "name": [f"row{i}"]}))

    assert len(table.active_entries()) == 5

    result = compact(table, small_file_threshold_bytes=1_048_576)
    assert result["compacted"] is True
    assert result["files-rewritten"] == 5

    assert len(table.active_entries()) == 1  # 5 small files -> 1 big file

    df = table.read()
    assert len(df) == 5
    assert set(df["id"]) == {1, 2, 3, 4, 5}

    # old snapshot is still readable after compaction
    assert len(table.read(snapshot_id=snap1)) == 1


def test_old_files_survive_compaction_on_disk(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("events", SCHEMA)

    snap1 = table.append(pd.DataFrame({"id": [1], "name": ["a"]}))
    for i in range(2, 4):
        table.append(pd.DataFrame({"id": [i], "name": [f"row{i}"]}))

    old_files = list(table.active_entries(snap1))
    compact(table, small_file_threshold_bytes=1_048_576)

    for path in old_files:
        assert os.path.exists(path)


def test_compact_is_noop_with_fewer_than_two_small_files(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("single", SCHEMA)
    table.append(pd.DataFrame({"id": [1], "name": ["a"]}))

    result = compact(table, small_file_threshold_bytes=1_048_576)
    assert result["compacted"] is False
    assert len(table.read()) == 1
