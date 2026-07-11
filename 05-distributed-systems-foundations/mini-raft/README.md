### **Project Scope: Real Raft (etcd/ZooKeeper's ZAB) vs. Mini-Raft**

| Feature | Real Raft Implementations | Mini-Raft (Python) |
| --- | --- | --- |
| **Transport** | gRPC/custom binary RPC | HTTP or plain sockets between local processes |
| **Log compaction** | Snapshotting to bound log growth | Basic snapshotting |
| **Membership changes** | Joint consensus for safe cluster resizing | Fixed cluster size (no live reconfiguration) |
| **Client interaction** | Linearizable reads via leader lease or read-index | Reads always go through the leader |

The foundation `mini-coordination-service` and, indirectly, `mini-object-store`
(both this group) are built on — this is the primitive underneath
ZooKeeper/etcd/Kafka's controller quorum.

---

### **Phase 1: Leader Election**

* **Terms and votes:** Each node has a "term" counter and can vote once
  per term; a node becomes leader by getting votes from a majority.
* **Election timeout:** A follower that hasn't heard from a leader within
  a randomized timeout starts an election — the randomization is load-
  bearing (fixed timeouts cause repeated split votes when multiple nodes
  time out simultaneously; prove this to yourself by disabling the
  randomization and watching elections fail to converge).
* **Heartbeats:** A leader periodically pings followers to suppress their
  election timeouts, asserting "I'm still here."

### **Phase 2: Log Replication**

* **Append entries:** A leader appends a client command to its own log,
  then replicates it to followers; once a majority have it, it's
  "committed" and safe to apply to a state machine.
* **Log consistency check:** Before accepting a new entry, a follower
  verifies its log agrees with the leader's up to that point — reject
  and force the leader to send earlier entries if not (this is what
  repairs a follower that fell behind or diverged).
* **Kill and restart nodes mid-replication:** Verify committed entries
  survive a leader crash and a new leader (elected from the remaining
  majority) has every committed entry — this is the actual safety
  property Raft exists to guarantee; test it by deliberately breaking it
  first (disable the log consistency check) and watching data loss occur.

### **Phase 3: Snapshotting**

* **Log compaction:** Once entries are applied to the state machine, they
  don't need to stay in the log forever — periodically snapshot the state
  machine and truncate the log up to that point.
* **Follower catch-up via snapshot:** A follower too far behind to catch
  up via log replay instead receives a full snapshot — implement this
  path and test it against a follower down long enough that its needed
  log entries have already been compacted away.

### **What this exposes about real tools**

Every "why does my ZooKeeper/etcd cluster need an odd number of nodes" and
"why did we lose data during a network partition despite replication"
question resolves to the exact mechanics you build here: majority quorums,
term numbers preventing stale leaders from re-asserting themselves, and
the randomized-timeout trick that keeps elections from livelocking.
Consensus is the one piece of distributed-systems folklore genuinely worth
building from scratch, because every "just use ZooKeeper for coordination"
recommendation is implicitly leaning on these exact guarantees.
