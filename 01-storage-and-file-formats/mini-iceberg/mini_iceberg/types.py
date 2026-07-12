"""Schema (de)serialization between pyarrow.Schema and the JSON stored in table metadata.

WHY THIS FILE EXISTS (the concept)
-----------------------------------
Iceberg's headline feature is schema evolution: you can rename a column, add
a column, drop a column, or widen a type (int32 -> int64) *without rewriting
any existing data files*. That's only possible because Iceberg never trusts a
column's position or name at read time — every column has a permanent integer
**field ID**, assigned once when the column is created, that never changes
even if the column is renamed. Old Parquet files (written under an old
schema) get their columns matched up to the current schema by field ID, not
by name or position.

We are deliberately NOT implementing field IDs in this mini version — matching
by column name is enough to learn manifests/snapshots/compaction. But keep in
mind as you build this: the moment you'd want to support `RENAME COLUMN`, the
name-based approach here breaks (rename "id" to "user_id" and every old
manifest's stats, keyed by name, silently stop matching). That's precisely the
bug field IDs exist to prevent. Real Iceberg's schema JSON looks like
`{"id": 1, "name": "id", "type": "long", "required": false}` — the `"id": 1`
is the field ID this file is skipping.

The functions below are the boundary between two type systems:
  - pyarrow.Schema: what your Python code and Parquet files actually use
  - JSON: what gets persisted in table metadata (JSON can't represent a
    pyarrow.DataType object directly, so we round-trip through type *names*)
"""

import numbers

import pyarrow as pa

# TODO: extend as needed. Keep _NAME_TO_TYPE derived from this one so they can't drift.
_TYPE_TO_NAME = {
    pa.int32(): "int32",
    pa.int64(): "int64",
    pa.float32(): "float32",
    pa.float64(): "float64",
    pa.string(): "string",
    pa.bool_(): "bool",
    pa.date32(): "date32",
}

_NAME_TO_TYPE = {name: type_ for type_, name in _TYPE_TO_NAME.items()}


def schema_to_json(schema: pa.Schema) -> list:
    """Serialize a pyarrow Schema to the JSON list stored in table metadata.

    Example:
        schema_to_json(pa.schema([("id", pa.int64()), ("name", pa.string())]))
        # -> [{"name": "id", "type": "int64"}, {"name": "name", "type": "string"}]

    Steps:
      - iterate `schema` (iterating a pa.Schema yields pa.Field objects, each
        with .name and .type)
      - look up each field's `.type` in _TYPE_TO_NAME to get the string name
      - raise ValueError for any type not in the map (fail loud — a silently
        dropped/mismatched column is exactly the kind of bug field IDs exist
        to prevent in real Iceberg; don't reintroduce it here via a fallback)
    """
    json_list = []
    for field in schema:
        type_name = _TYPE_TO_NAME.get(field.type)
        if type_name is None:
            raise ValueError(f"Unsupported type: {field.type}. Supported types: {list(_TYPE_TO_NAME.keys())}")
        json_list.append({"name": field.name, "type": type_name})
    return json_list


def schema_from_json(fields: list) -> pa.Schema:
    """Rebuild a pyarrow Schema from the JSON list produced by schema_to_json.

    Example:
        schema_from_json([{"name": "id", "type": "int64"}, {"name": "name", "type": "string"}])
        # -> pa.schema([("id", pa.int64()), ("name", pa.string())])

    Steps:
      - map each {"name", "type"} dict back to a (name, pa.DataType) tuple via
        _NAME_TO_TYPE
      - build and return a pa.schema(...) from the list of tuples
    """
    fields_list = []
    for field in fields:
        type_ = _NAME_TO_TYPE.get(field["type"])
        if type_ is None:
            raise ValueError(f"Unsupported type: {field['type']}. Supported types: {list(_NAME_TO_TYPE.keys())}")
        fields_list.append((field["name"], type_))
    return pa.schema(fields_list)


def parse_schema_spec(spec: str) -> pa.Schema:
    """Parse a CLI-friendly schema spec like 'id:int64,name:string' into a pyarrow Schema.

    This exists purely so a human can define a table's schema from the command
    line (Phase 1's README bullet: "establishing a rigid baseline is required
    before you can mutate it"). It has nothing to do with the persisted format.

    Example:
        parse_schema_spec("id:int64,name:string")
        # -> pa.schema([("id", pa.int64()), ("name", pa.string())])

    Steps:
      - split on "," for fields, then on ":" for name/type within each field
      - validate the type name is in _NAME_TO_TYPE (raise ValueError with a
        helpful message listing supported types if not)
      - build and return a pa.schema(...)
    """
    fields_list = []
    for field_spec in spec.split(","):
        name, type_name = field_spec.split(":")
        type_ = _NAME_TO_TYPE.get(type_name)
        if type_ is None:
            raise ValueError(f"Unsupported type: {type_name}. Supported types: {list(_NAME_TO_TYPE.keys())}")
        fields_list.append((name, type_))
    return pa.schema(fields_list)


# ---------------------------------------------------------------------------
# Phase 2: column statistics for manifest entries (see manifest.py)
# ---------------------------------------------------------------------------
#
# WHY THIS FUNCTION EXISTS
# A manifest entry's min/max stats are what a real query engine uses to skip
# files entirely during a scan (file pruning) instead of opening every
# Parquet file on every query. We compute these at append time — once, when
# we already have the DataFrame in memory — rather than re-scanning files
# later, because computing stats is cheap now and expensive later (it would
# mean re-reading every data file just to answer "what's the min of this
# column across the whole table").


def _to_native(value):
    """Convert a numpy/pandas scalar to a plain JSON-serializable Python value.

    Example:
        _to_native(numpy.int64(5))       # -> 5           (plain Python int)
        _to_native(pandas.Timestamp(...)) # -> "2026-01-01 00:00:00" (string fallback)

    TODO:
      - if `value` has an `.item()` method (numpy scalars do), call it first
      - if the result is a number, str, or bool, return it as-is
      - otherwise fall back to str(value) (e.g. for pandas Timestamp/date
        objects, which json.dump can't serialize directly)
    """
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (numbers.Number, str, bool)):
        return value
    return str(value)


def column_stats(df) -> dict:
    """Compute per-column {min, max} stats for a DataFrame.

    Example:
        column_stats(pd.DataFrame({"id": [3, 1, 2], "name": ["carol", "alice", "bob"]}))
        # -> {"id": {"min": 1, "max": 3}, "name": {"min": "alice", "max": "carol"}}

    TODO:
      - for each column in df.columns:
          - drop nulls (series.dropna()) — nulls shouldn't affect min/max
          - skip the column entirely if it's empty after dropping nulls
          - try series.min() / series.max(), converting each through
            _to_native(); wrap in try/except TypeError and skip columns whose
            values aren't orderable (e.g. nested/list columns) rather than
            crashing the whole append
    """
    stats = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
        try:
            min_val = _to_native(series.min())
            max_val = _to_native(series.max())
            stats[col] = {"min": min_val, "max": max_val}
        except TypeError:
            continue
    return stats
