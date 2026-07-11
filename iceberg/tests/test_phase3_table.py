import pandas as pd
import pyarrow as pa

from mini_iceberg.catalog import Catalog

SCHEMA = pa.schema([("id", pa.int64()), ("name", pa.string())])


def test_append_creates_snapshot_and_updates_read(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("users", SCHEMA)

    assert table.current_snapshot_id is None
    assert len(table.read()) == 0

    snap1 = table.append(pd.DataFrame({"id": [1, 2], "name": ["alice", "bob"]}))
    assert snap1 == 1
    assert table.current_snapshot_id == 1
    assert len(table.read()) == 2

    snap2 = table.append(pd.DataFrame({"id": [3], "name": ["carol"]}))
    assert snap2 == 2
    assert len(table.read()) == 3
    assert set(table.read()["id"]) == {1, 2, 3}


def test_time_travel_reads_old_snapshot(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("users", SCHEMA)

    snap1 = table.append(pd.DataFrame({"id": [1, 2], "name": ["alice", "bob"]}))
    table.append(pd.DataFrame({"id": [3], "name": ["carol"]}))

    assert len(table.read(snapshot_id=snap1)) == 2
    assert set(table.read(snapshot_id=snap1)["id"]) == {1, 2}
    # current read is unaffected by asking for an old snapshot
    assert len(table.read()) == 3


def test_history_lists_snapshots_in_order(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    table = catalog.create_table("users", SCHEMA)

    snap1 = table.append(pd.DataFrame({"id": [1], "name": ["alice"]}))
    snap2 = table.append(pd.DataFrame({"id": [2], "name": ["bob"]}))

    history = table.history()
    assert [s["snapshot-id"] for s in history] == [snap1, snap2]
    assert history[0]["summary"]["operation"] == "append"


def test_reloading_table_through_catalog_sees_latest_state(tmp_path):
    warehouse = str(tmp_path / "warehouse")
    catalog = Catalog(warehouse)
    table = catalog.create_table("users", SCHEMA)
    table.append(pd.DataFrame({"id": [1], "name": ["alice"]}))

    reloaded = Catalog(warehouse).load_table("users")
    assert len(reloaded.read()) == 1
    assert reloaded.current_snapshot_id == table.current_snapshot_id
