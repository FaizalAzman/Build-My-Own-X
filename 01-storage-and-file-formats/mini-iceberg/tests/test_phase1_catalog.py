import json
import os

import pyarrow as pa

from mini_iceberg.catalog import Catalog

SCHEMA = pa.schema([("id", pa.int64()), ("name", pa.string())])


def test_create_table_makes_directory_layout(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    handle = catalog.create_table("users", SCHEMA)

    assert os.path.isdir(handle.data_dir)
    assert os.path.isdir(handle.metadata_dir)
    assert os.path.isfile(handle.metadata_path)
    assert os.path.basename(handle.metadata_path) == "v1.metadata.json"


def test_catalog_json_points_at_latest_metadata(tmp_path):
    warehouse = str(tmp_path / "warehouse")
    catalog = Catalog(warehouse)
    handle = catalog.create_table("users", SCHEMA)

    with open(os.path.join(warehouse, "catalog.json")) as f:
        catalog_json = json.load(f)

    assert catalog_json["tables"]["users"] == handle.metadata_path


def test_load_table_round_trips_schema(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    catalog.create_table("users", SCHEMA)

    reloaded_catalog = Catalog(str(tmp_path / "warehouse"))
    handle = reloaded_catalog.load_table("users")

    assert handle.schema == SCHEMA


def test_create_table_rejects_duplicate_name(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))
    catalog.create_table("users", SCHEMA)

    try:
        catalog.create_table("users", SCHEMA)
        assert False, "expected ValueError for duplicate table name"
    except ValueError:
        pass


def test_load_missing_table_raises_key_error(tmp_path):
    catalog = Catalog(str(tmp_path / "warehouse"))

    try:
        catalog.load_table("does-not-exist")
        assert False, "expected KeyError for missing table"
    except KeyError:
        pass
