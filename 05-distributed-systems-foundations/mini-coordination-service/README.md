### **Project Scope: Real ZooKeeper vs. Mini-Coordination-Service**

| Feature | Real ZooKeeper | Mini-Coordination-Service (Python) |
| --- | --- | --- |
| **Consensus** | ZAB (ZooKeeper Atomic Broadcast, Raft-like) | `mini-raft` (same group) |
| **Data model** | Hierarchical znodes, like a filesystem | Hierarchical key tree, same shape |
| **Ephemeral nodes** | Tied to a client session, auto-deleted on disconnect | Same, tied to a heartbeat-based session |
| **Watches** | One-time-fire notifications on znode changes | Same, one-time-fire semantics |

Uses `mini-raft` (same group) as its consensus core — this project is where
that consensus primitive gets turned into the specific API real systems
actually build on: locks, leader election, and service discovery.

---

### **Phase 1: The Znode Tree**

* **Hierarchical namespace:** Paths like `/services/worker-1`, each node
  holding a small value and having children — implement `create`, `get`,
  `set`, `delete`, `list_children`.
* **Sequential nodes:** A `create` flag that appends a monotonically
  increasing suffix (`/locks/lock-0000000007`) — the primitive that makes
  the locking recipe in Phase 3 possible.
* **Consistency via `mini-raft`:** Every mutation goes through your Raft
  log, so every node in the coordination service cluster agrees on the
  znode tree's state, even across a leader change.

### **Phase 2: Ephemeral Nodes and Watches**

* **Sessions:** A client maintains a session via periodic heartbeats; if
  the session times out (client crashed or network partitioned), the
  server closes it.
* **Ephemeral nodes:** A znode created as "ephemeral" is automatically
  deleted when its owning session ends — this is the exact mechanism
  service discovery and "who's currently the leader" both rely on (a
  crashed service's registration disappears without anyone needing to
  notice the crash directly).
* **One-time watches:** A client can watch a znode and get notified
  exactly once on its next change — deliberately *not* a continuous
  subscription (this is a real ZooKeeper design choice, not an oversight;
  implement it faithfully and feel why "watches are one-shot" pushes
  client code toward re-registering after every fire).

### **Phase 3: Building Recipes on Top**

* **Distributed lock:** Using sequential ephemeral nodes — each client
  creates one, the client holding the lowest-numbered node holds the
  lock, everyone else watches the node just below theirs.
* **Leader election:** The same recipe as the lock, semantically renamed —
  this is genuinely the same mechanism, which is worth confirming for
  yourself rather than taking on faith.
* **Service discovery:** Services register themselves as ephemeral
  children under `/services/<name>/`; clients watch that path and always
  see a live, current membership list — kill a service process and watch
  its entry disappear without any explicit deregistration call.

### **What this exposes about real tools**

Locks, leader election, and service discovery look like three unrelated
features in ZooKeeper's docs — building all three on the exact same
ephemeral-sequential-node primitive is what reveals they're one mechanism
with three names. That's also precisely why a ZooKeeper/etcd outage takes
down service discovery *and* leader election *and* distributed locks
simultaneously in real incidents: they were never independent systems.
