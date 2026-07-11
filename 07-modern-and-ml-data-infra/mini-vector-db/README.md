### **Project Scope: Real Vector Databases (Pinecone/pgvector/FAISS) vs. Mini-Vector-DB**

| Feature | Real Vector Databases | Mini-Vector-DB (Python) |
| --- | --- | --- |
| **Index structure** | HNSW, IVF-Flat, or hybrid | Both: implement HNSW and IVF-Flat, compare them |
| **Distance metrics** | Cosine, dot product, Euclidean | All three, as pluggable functions |
| **Filtering** | Metadata pre/post-filtering alongside vector search | A simple metadata pre-filter |
| **Updates** | Incremental insert/delete without full rebuild | Insert supported; delete via tombstone (same idea as `mini-lsm`) |

The most recently relevant category in this whole curriculum (RAG,
embeddings search) — and a good demonstration that "approximate" is a
deliberate, tunable trade against exactness, not a compromise you're stuck
with.

---

### **Phase 1: Brute-Force Baseline**

* **Exact k-NN:** Given a query vector, compute distance to *every* stored
  vector and return the top-k closest — correct, and your ground truth for
  measuring approximate methods' recall in later phases.
* **Distance metrics:** Implement cosine similarity, dot product, and
  Euclidean distance, and confirm (empirically, not just by formula) that
  they can rank the same set of vectors differently for the same query.

### **Phase 2: IVF-Flat (Inverted File Index)**

* **Clustering:** Run k-means to partition all stored vectors into N
  clusters, each with a centroid.
* **Search only nearby clusters:** For a query, find the closest few
  centroids and only brute-force search *those* clusters' vectors, not the
  whole dataset — trading a small recall loss for a large speedup.
* **Measure the recall/speed tradeoff:** Vary how many clusters you probe
  and plot recall (vs. Phase 1's exact answer) against query latency —
  this curve *is* the actual product decision every vector DB user makes
  when picking an index's tuning parameters.

### **Phase 3: HNSW (Hierarchical Navigable Small World)**

* **Build a multi-layer graph:** Insert vectors into a graph structure
  with multiple layers, sparser at the top, denser at the bottom — each
  node connected to its approximate nearest neighbors within its layer.
* **Greedy search:** Starting from the top (sparse) layer, greedily walk
  toward the query vector, then descend a layer and repeat — this is what
  gives HNSW its logarithmic-ish search complexity.
* **Compare against IVF-Flat directly:** Same dataset, same recall target
  — measure build time, memory usage, and query latency for both index
  types. They win in different regimes; find where the crossover is on
  your own data rather than trusting a benchmark blog post.

### **What this exposes about real tools**

"Vector search is approximate" is usually stated as if it's one setting,
but Phase 2 and Phase 3 make clear it's actually a family of *different*
approximations with different cost curves — IVF-Flat trades recall for
lower memory and simpler updates, HNSW trades build time and memory for
much faster queries at high recall. Choosing between Pinecone's index
options (or pgvector's `ivfflat` vs. `hnsw`) stops being a coin flip once
you've built both and watched where each one actually wins.
