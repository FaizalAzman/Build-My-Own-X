# Template: The Decision Section of a Case Study

Every `CASE_STUDY.md` in groups 01–09 ends with this section. The rest of the
case study explains how the real system works and where your mini version
differs. This section asks the question you'll actually face as an architect:
**should we use this, something else, or nothing, and what would make that
answer change?**

Nobody will ask you to implement Kafka. You will be asked whether to adopt it,
what it will cost, what will page someone at 3am, and how hard it would be to
back out of. Your answer has to hold up in a design review.

**Rules for writing it:**

- **Numbers, not adjectives.** Don't write "small tables"; write "under ~1 TB,
  under ~50 commits/hour". Rough is fine; vague is not.
- **Every recommendation names the constraint that would flip it.** If you
  can't say what would change your mind, you don't understand the decision yet.
- **Ground claims in evidence.** Cite what you built or measured (link the
  section), or label the claim as an assumption. Vendor marketing isn't evidence.
- **Include "don't use anything" as an option.** It wins more often than people
  expect, and it's the option teams most often forget to consider.

Copy everything below the line into the end of the case study and fill it in.
Delete prompts that don't apply rather than padding them.

---

## N. Decision: when to choose `<System>` (and when not to)

### The decision space

| Option | What it is | Who typically picks it |
|---|---|---|
| `<the real system>` (self-managed) | | |
| `<managed / commercial equivalent>` | | |
| `<simpler alternative that covers ~80%>` | | |
| Nothing (an existing tool, a file, a cron job, a database table) | | |

### The forces that decide it

Keep only the forces that matter for this system. Each one needs a
threshold: the point where the answer changes.

| Force | Why it matters here | Threshold where the answer changes |
|---|---|---|
| Data volume and growth rate | | |
| Read/write ratio, latency targets (p50/p99) | | |
| Concurrency (writers, readers, engines) | | |
| Consistency/correctness requirements | | |
| Freshness | | |
| Team size, skills, capacity to run it | | |
| Budget and cost model | | |
| Ecosystem fit and lock-in | | |
| Compliance and security | | |

### Decision table

| If… | Choose | Because | The cost you accept |
|---|---|---|---|
| | | | |

### Cost shape

What dominates cost as this scales: storage, compute, network, or people?
Which of those grows linearly and which grows faster than linear? Do one
back-of-envelope calculation with the arithmetic shown.

### Operational burden

What has to be run, upgraded, tuned and monitored? Which failures page a
human? What skills does the team need that it might not have?

### Failure modes and blast radius

List the top three ways this fails in production. For each, say what else
breaks when it does and how you'd find out (ideally before a consumer does).

### Reversibility

Is this a one-way door or a two-way door? What would it cost to leave in two
years (data migration, rewrites, retraining people)? What can you do now to
keep that exit cheap?

### Signals you chose wrong

What would you observe 6–12 months in that means this decision should be
revisited? Name the metric or the symptom.

### Recommendation for a concrete scenario

Pick one realistic scenario and state its numbers. Then write a single
paragraph recommending an option, the way you would in a design review.
End with what you'd monitor to know the decision is still right.
