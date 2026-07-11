### **Project Scope: Real Data Catalogs (Amundsen/DataHub) vs. Mini-Data-Catalog**

| Feature | Real Data Catalogs | Mini-Data-Catalog (Python) |
| --- | --- | --- |
| **Ingestion** | Scrapers/connectors for many source systems (warehouses, BI tools, orchestrators) | Ingests directly from `mini_iceberg`'s `Catalog` |
| **Search** | Full-text + ranked search (Elasticsearch-backed) | Simple substring + tag-based search |
| **Lineage** | Ingested from query logs or explicit integrations | Ingested from `mini-lineage`'s graph (same group) |
| **Metadata model** | Rich: owners, descriptions, tags, usage stats, popularity | Table/column names, types, tags, owner field |

Ties together `mini_iceberg` (its data source), `mini-lineage`, and
`mini-data-contracts` (all this group) into one browsable, searchable
index — the "front door" to everything else in this curriculum.

---

### **Phase 1: Metadata Ingestion**

* **A connector for `mini_iceberg`:** Walk every table in a
  `mini_iceberg.Catalog`, extracting name, schema, current snapshot id,
  and row/file counts, and store it in the catalog's own metadata store.
* **Manual annotations:** Let a human attach an owner, a free-text
  description, and tags to a table — this human-entered layer is what
  turns raw metadata into something a catalog is actually useful for
  (nobody searches a data catalog for a table's PyArrow schema; they
  search for "who owns this" and "what is this for").

### **Phase 2: Search**

* **Indexing:** Build a simple inverted index over table names,
  descriptions, tags, and column names.
* **Ranking:** A search for a term should rank exact table-name matches
  above description matches above column-name matches — implement even a
  crude scoring function and notice how much search quality depends on
  this ordering, not just on matching at all.

### **Phase 3: Lineage and Usage Integration**

* **Pull in `mini-lineage`'s graph:** Show, for any table, its upstream
  sources and downstream consumers directly in the catalog entry.
* **Usage stats:** Track how often each table is queried (hook into
  `mini-query-engine`'s execution path) and surface "most-used tables" —
  the signal real catalogs use to help users find the *trusted* version
  of a metric when five similarly-named tables exist.

### **What this exposes about real tools**

A data catalog's actual hard problem isn't storage or search — it's
getting anyone to keep the human-entered metadata (owners, descriptions)
up to date, which is a social/incentive problem, not a technical one. That
insight only becomes visible once you've built the technical parts
yourself and realized how empty and useless a catalog is without that
layer — the exact reason catalog adoption efforts fail more often on
process than on tooling.
