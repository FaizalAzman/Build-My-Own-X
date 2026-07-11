### **Project Scope: Real Avro vs. Mini-Avro**

| Feature | Real Avro | Mini-Avro (Python) |
| --- | --- | --- |
| **Layout** | Row-based, schema embedded in the file header | Row-based, JSON schema embedded in the header |
| **Schema resolution** | Reader schema vs. writer schema reconciliation | Field-name-based resolution, with defaults for added fields |
| **Compression** | Per-block, Snappy/Deflate/Zstd | Optional per-block zlib |
| **Use case** | Kafka message payloads, Iceberg manifests/manifest lists | Same conceptual role, used to re-encode `mini_iceberg`'s manifests |

The direct row-based counterpart to `mini-parquet` (same group) — same
project, opposite layout. Real `iceberg/` manifests are Avro; `mini_iceberg`
used JSON instead (`CASE_STUDY.md` §2) — this project is where you go back
and actually build the thing that was skipped.

---

### **Phase 1: Row-Based Encoding**

* **Binary encoding:** Implement Avro's primitive encodings — variable-length
  zig-zag integers, length-prefixed strings/bytes — and write a sequence of
  records as one contiguous stream of bytes, record after record (the
  opposite layout choice from `mini-parquet`'s column-after-column).
* **Embedded schema:** Write the schema itself (as JSON) into the file's
  header, so the file is fully self-describing — a reader needs nothing
  external to decode it.
* **Re-encode `mini_iceberg`'s manifests:** Take an existing JSON manifest
  file from your `mini_iceberg` project and write an equivalent Avro-encoded
  version; compare file sizes.

### **Phase 2: Schema Resolution**

* **Writer schema vs. reader schema:** A file is always read using *both*
  the schema it was written with (embedded in the header) and the schema
  the reader currently expects — these can differ.
* **Field defaults:** If the reader's schema has a field the writer's
  schema didn't (a column added after this file was written), fall back
  to a declared default value instead of failing.
* **Dropped fields:** If the writer's schema has a field the reader's
  schema no longer has, skip it during decode without erroring — this
  two-sided reconciliation is Avro's actual schema evolution mechanism,
  distinct from (and older than) Iceberg's field-ID approach.

### **Phase 3: Compatibility Rules**

* **Backward compatibility:** A new reader schema can read data written
  with an old writer schema (this requires new fields to have defaults).
* **Forward compatibility:** An old reader schema can read data written
  with a new writer schema (this requires the reader to safely ignore
  fields it doesn't know about).
* **Break both, deliberately:** Remove a field's default and confirm
  backward compatibility now fails; this is exactly the check
  `mini-schema-registry` (group 03) automates.

### **What this exposes about real tools**

Row-based (Avro) vs. columnar (Parquet) isn't a stylistic choice — it's a
read-pattern bet. Avro wins when you almost always read whole records
(message queues, manifest files you read start-to-finish); Parquet wins
when you usually read a handful of columns out of many (analytical scans).
Having built both, "use Avro for streaming, Parquet for analytics" stops
being a rule you memorized and becomes a consequence of a tradeoff you can
re-derive.
