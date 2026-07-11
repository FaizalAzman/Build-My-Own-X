"""Thin CLI wrapper over the mini_iceberg library.

This file is pure plumbing (argparse -> library calls) — there's no new
Iceberg concept here, it just exists so you can poke at the library from a
terminal instead of writing a Python script every time. Fill it in last,
after catalog.py / table.py / compaction.py all work — it's the easiest way
to sanity-check them interactively.
"""

import argparse

import pandas as pd

from .catalog import Catalog
from .compaction import compact
from .types import parse_schema_spec


def _load_dataframe(path: str) -> pd.DataFrame:
    """Load a CSV or Parquet file into a DataFrame based on its extension.

    Example:
        _load_dataframe("new_users.csv")
        # -> DataFrame built from new_users.csv's rows/columns

    TODO: if path.endswith(".parquet"), use pd.read_parquet; else pd.read_csv.
    """
    raise NotImplementedError


def cmd_create_table(args):
    """Handle: create-table warehouse users --schema id:int64,name:string

    Example:
        args.warehouse = "warehouse"; args.name = "users"; args.schema = "id:int64,name:string"
        cmd_create_table(args)
        # -> prints: Created table 'users' with schema id:int64,name:string
        # -> on disk: warehouse/users/data/, warehouse/users/metadata/v1.metadata.json

    TODO: Catalog(args.warehouse).create_table(args.name, parse_schema_spec(args.schema));
    print a confirmation.
    """
    raise NotImplementedError


def cmd_append(args):
    """Handle: append warehouse users new_users.csv

    Example:
        args.warehouse = "warehouse"; args.name = "users"; args.data_file = "new_users.csv"
        cmd_append(args)
        # -> prints: Appended 2 rows to 'users' as snapshot 1

    TODO: load_table, _load_dataframe(args.data_file), table.append(df);
    print the resulting snapshot id.
    """
    raise NotImplementedError


def cmd_read(args):
    """Handle: read warehouse users [--snapshot-id 1]

    Example:
        args.warehouse = "warehouse"; args.name = "users"; args.snapshot_id = None
        cmd_read(args)
        # -> prints the current table as a text table, e.g.:
        #     id   name
        #      1  alice
        #      2    bob

        args.snapshot_id = 1
        cmd_read(args)
        # -> prints only the rows that existed as of snapshot 1

    TODO: load_table, table.read(snapshot_id=args.snapshot_id), print the DataFrame.
    """
    raise NotImplementedError


def cmd_history(args):
    """Handle: history warehouse users

    Example:
        cmd_history(args)
        # -> prints one line per commit, e.g.:
        #    snapshot    1  append      ts=1700000000000
        #    snapshot    2  append      ts=1700000005000
        #    snapshot    3  compaction  ts=1700000009000

    TODO: load_table, iterate table.history(), print snapshot id/operation/timestamp per line.
    """
    raise NotImplementedError


def cmd_compact(args):
    """Handle: compact warehouse users [--threshold-bytes 1048576]

    Example:
        cmd_compact(args)
        # -> prints: Compacted 5 files into warehouse/users/data/9f2a....parquet as snapshot 6
        # or, if there was nothing worth compacting:
        # -> prints: Nothing to compact (fewer than 2 small files).

    TODO: load_table, compact(table, small_file_threshold_bytes=args.threshold_bytes);
    print the result dict in a readable form.
    """
    raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    """Wire up subcommands: create-table, append, read, history, compact.

    Example:
        parser = build_parser()
        args = parser.parse_args(["read", "warehouse", "users", "--snapshot-id", "1"])
        # -> args.warehouse == "warehouse", args.name == "users", args.snapshot_id == 1,
        #    args.func == cmd_read

    TODO: for each subcommand below, add the listed positional/optional
    arguments and set_defaults(func=<the matching cmd_* function>).

      create-table <warehouse> <name> --schema id:int64,name:string
      append       <warehouse> <name> <data_file>
      read         <warehouse> <name> [--snapshot-id N]
      history      <warehouse> <name>
      compact      <warehouse> <name> [--threshold-bytes N (default 1_048_576)]
    """
    raise NotImplementedError


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
