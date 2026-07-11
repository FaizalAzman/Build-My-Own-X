### **Project Scope: Real Schema Registry (Confluent) vs. Mini-Schema-Registry**

| Feature | Real Schema Registry | Mini-Schema-Registry (Python) |
| --- | --- | --- |
| **Storage** | Backed by a Kafka topic itself (`_schemas`) | A local JSON file, versioned list per subject |
| **Compatibility modes** | Backward, forward, full, none — configurable per subject | All four modes, configurable per subject |
| **Schema formats** | Avro, Protobuf, JSON Schema | Avro (reuses `mini-avro`'s schema JSON) |
| **Enforcement** | Producer-side check before publish | Same: a `register()` call that can reject |

Directly downstream of `mini-avro` (group 01) and upstream of `mini-kafka`
(same group) — this is the piece that stops a bad schema change from ever
reaching the broker in the first place.

---

### **Phase 1: Subjects and Versions**

* **Register a schema:** For a given "subject" (typically `<topic>-value`),
  store a schema and assign it an incrementing version number.
* **Fetch by version or "latest":** A consumer or producer can ask for a
  subject's schema by explicit version, or just "the current one."
* **Immutable versions:** Once registered, a version's schema never
  changes — a schema *update* is always a new version, not an edit to an
  existing one (the same immutability discipline `mini_iceberg` uses for
  metadata files, one layer up in a different system).

### **Phase 2: Compatibility Checking**

* **Backward compatibility check:** Before accepting a new schema version,
  verify a reader using the *previous* version could still read data
  written with the *new* one (roughly: new fields must have defaults,
  no required field can be removed) — reuse `mini-avro`'s Phase 3 rules
  directly.
* **Forward compatibility check:** Verify a reader using the *new* version
  could read data written with the *previous* one.
* **Reject on violation:** A `register()` call that would violate the
  subject's configured compatibility mode fails with a clear error naming
  the specific incompatible change — not just "incompatible schema."

### **Phase 3: Producer/Consumer Integration**

* **Producer-side enforcement:** Before a producer (e.g. hooked into
  `mini-kafka`) publishes a message, it registers/validates its schema
  against the registry — a bad deploy that changes a field's type gets
  rejected *before* a single bad message reaches the topic, not after.
* **Consumer-side resolution:** A consumer fetches the schema version a
  message was written with (often embedded as a small ID prefix on the
  message) and uses `mini-avro`'s schema-resolution logic to decode it
  against its own expected schema.

### **What this exposes about real tools**

A schema registry's entire value is turning "someone changed a producer's
schema in a way that breaks fifty downstream consumers" from a Wednesday-
afternoon incident into a rejected pull request — the compatibility check
you implement in Phase 2 *is* that safety net. This is also the most
concrete illustration in this whole curriculum of why `iceberg/`'s
name-based schema matching (flagged in `CASE_STUDY.md` §3) is fragile: this
project makes rename-breaks-everything a check you can trigger and see
fail on purpose, not just a warning in a docstring.
