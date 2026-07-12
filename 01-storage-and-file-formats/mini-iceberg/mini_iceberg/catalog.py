"""Phase 1: storage layout + catalog.

What this is: Catalog("warehouse") is a folder called "warehouse" that holds
every table. Inside it there's one file, catalog.json, which is just a dict:

    {"tables": {"users": "warehouse/users/metadata/v3.metadata.json"}}

That's it. The catalog doesn't know anything about schemas or data — for each
table name it just remembers "which metadata file is the current one right
now". Anyone who wants to read a table asks the catalog for that path first,
then opens that file to find out everything else.

Why write-to-temp-then-rename in _save(): if you write catalog.json directly
and the process dies halfway through, the file is left corrupted (half a
JSON object). Writing to a ".tmp" file and then renaming it over the real one
is a single atomic filesystem operation — the file you can see is always
either fully-old or fully-new, never half-written.

create_table/load_table return a `Table` (mini_iceberg/table.py, Phase 3),
not just a path, so callers don't have to re-figure-out data_dir/metadata_dir
themselves every time.
"""

import json
import os

import pyarrow as pa

from . import metadata as metadata_io
from . import types
from .table import Table

import json
from pathlib import Path
from typing import Union


class Catalog:
    def __init__(self, root_dir: str):
        """
        Initializes the warehouse catalog.
        
        Creates the warehouse directory if it does not exist. 
        If a catalog file already exists, it loads the data. 
        Otherwise, it creates a new, empty catalog file.
        """

        # Convert to an absolute Path object
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

        self.catalog_path = self.root_dir / "catalog.json"

        # Load existing catalog or initialize a new one
        if self.catalog_path.exists():
            with self.catalog_path.open('r') as f:
                self._data = json.load(f)
        else:
            self._data = {"tables": {}}
            self._save()

    def _save(self):
        """Saves the current catalog data to disk.

        Uses a temporary file and an atomic rename to ensure the
        catalog.json file is never left in a corrupted, half-written state.
        """
        temp_path = self.catalog_path.with_name(self.catalog_path.name + ".tmp")
        # Write data to the temporary file
        with temp_path.open('w') as f:
            json.dump(self._data, f, indent=4)

        # Atomically replace the old catalog with the new temporary file
        temp_path.replace(self.catalog_path)

    def _commit(self, name: str, metadata_path: str):
        """Update which metadata file `name` currently points to, and save.

        Table.append() and compact() call this every time they finish writing
        a new metadata version — this is the one line that actually makes the
        new version "the current one".

        TODO: self._data["tables"][name] = metadata_path; self._save()
        """
        self._data["tables"][name] = metadata_path
        self._save()

    def create_table(self, name: str, schema: pa.Schema) -> Table:
        """Make a brand-new, empty table: folders + an initial metadata file + a catalog entry.

        Example:
            schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
            table = catalog.create_table("users", schema)
            # -> Table with table.current_snapshot_id == None, table.read() == 0 rows
            # on disk: warehouse/users/data/ (empty), warehouse/users/metadata/v1.metadata.json
            # warehouse/catalog.json now has "users": ".../users/metadata/v1.metadata.json"

        TODO:
          - if name already in self._data["tables"]: raise ValueError
          - table_dir = <root>/<name>
          - data_dir = <table_dir>/data, metadata_dir = <table_dir>/metadata
          - os.makedirs both of those
          - metadata_path = metadata_io.write_metadata(metadata_dir, version=1,
                schema_json=types.schema_to_json(schema), snapshots=[],
                current_snapshot_id=None)
            (empty snapshots, no current snapshot — table exists, no rows yet)
          - self._commit(name, metadata_path)
          - return Table(self, name, table_dir, metadata_path)
        """
        if name in self._data['tables']:
            raise ValueError(f"Table '{name}' already exists in the catalog.")
        
        table_dir = self.root_dir / name
        data_dir = table_dir / "data"
        metadata_dir = table_dir / "metadata"
        data_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = metadata_io.write_metadata(
            str(metadata_dir),
            version=1,
            schema_json=types.schema_to_json(schema),
            snapshots=[],
            current_snapshot_id=None
        )

        self._commit(name, str(metadata_path))

        return Table(self, name, str(table_dir), str(metadata_path))

    def load_table(self, name: str) -> Table:
        """Look up a table that was already created, by name.

        Example:
            catalog2 = Catalog("warehouse")   # fresh Catalog instance, same folder
            table = catalog2.load_table("users")
            table.read()   # -> whatever rows "users" currently has, same as before

            catalog2.load_table("does-not-exist")  # -> raises KeyError

        TODO:
          - if name not in self._data["tables"]: raise KeyError
          - metadata_path = self._data["tables"][name]
          - table_dir = os.path.dirname(os.path.dirname(metadata_path))
            (metadata_path's folder is metadata_dir; metadata_dir's parent is table_dir)
          - return Table(self, name, table_dir, metadata_path)
        """
        if name not in self._data['tables']:
            raise KeyError(f"Table '{name}' does not exist in the catalog.")
        
        metadata_path = self._data['tables'][name]
        table_dir = Path(metadata_path).parent.parent

        return Table(self, name, str(table_dir), metadata_path)
