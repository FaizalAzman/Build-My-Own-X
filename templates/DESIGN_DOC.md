# Template: Design Doc

Every exercise in group 10 is answered with a design doc in this shape. It's
also the shape most companies use for design docs, RFCs and architecture
reviews, so practising it here pays off directly at work.

A design doc exists so a reviewer can **disagree with you precisely**. That
only works if your assumptions, numbers and rejected alternatives are written
down. A doc that is merely persuasive gives the reviewer nothing to push on.
Aim for 4–8 pages. If it's longer, you're probably describing the
implementation instead of the decisions.

Draw diagrams in [Mermaid](https://mermaid.js.org/) inside fenced code blocks;
GitHub renders them, and they stay diffable.

---

## 1. Context and problem

Two or three paragraphs. What's broken or missing, who it hurts, and why it
needs solving now rather than next year.

## 2. Goals and non-goals

- **Goals:** outcomes you can check, not activities.
- **Non-goals:** things a reasonable reader might expect this design to do,
  which it deliberately doesn't. This list prevents most scope arguments.

## 3. Requirements

**Functional:** what the system must do.

**Non-functional:** numbers only.

| Requirement | Target | Source / assumption |
|---|---|---|
| Data volume (now / in 2 years) | | |
| Throughput (average / peak) | | |
| Latency (p50 / p99) | | |
| Freshness (event to queryable) | | |
| Availability | | |
| Durability: RPO / RTO | | |
| Retention | | |
| Consistency | | |

**Constraints:** budget, team size and skills, deadline, compliance, and
existing technology you must keep or integrate with.

## 4. Back-of-envelope estimates

Show the arithmetic so a reviewer can check it. Cover storage, throughput,
state size, network transfer and cost. Round aggressively. The goal is the
right order of magnitude, plus knowing which number dominates.

## 5. Proposed architecture

- **Diagram** of components and data flow.
- **Components and responsibilities:** one or two lines each.
- **Main path walkthrough:** follow one record or one query end to end.
- **Data model,** where it matters: grain, keys, partitioning, history.

## 6. Alternatives considered

At least two real alternatives. One of them must be **the simplest thing that
could possibly work**. Compare every alternative against the requirements in
§3, and reject each one by naming the requirement it fails. "It's worse" is
not a reason.

| Requirement | Proposed | Alternative A | Alternative B (simplest) |
|---|---|---|---|
| | | | |

## 7. Key decisions (ADR style)

Repeat this block for each significant decision:

> **Decision:** …
> **Context:** the forces in play.
> **Options:** …
> **Choice and why:** …
> **Consequences:** what becomes easier, what becomes harder, and whether
> this is a one-way or two-way door.

## 8. Failure modes

| Component | Failure | How detected | Impact / blast radius | Mitigation | Recovery |
|---|---|---|---|---|---|
| | | | | | |

Include human and process failures, such as a bad deploy, a wrong backfill or
a schema change nobody announced. Not just machines dying.

## 9. Security and compliance

Who can access what, how access is enforced and audited, where PII lives, and
how data is retained and deleted.

## 10. Cost estimate

Monthly cost at launch and at 10× scale. Name the single biggest cost driver
and the lever that controls it.

## 11. Operations

SLOs and the SLIs that measure them, monitoring and alerting, on-call
ownership, and the runbooks that need to exist before launch.

## 12. Rollout and migration

The phases, how you validate each one, and the rollback plan for each.

## 13. Evolution

What breaks first at 10×? What would you change then? Which decisions in §7
are hardest to reverse?

## 14. Open questions and risks

What you don't know yet, and how and when you'll find out.

## Appendix: Constraint-change round

For each constraint change given in the exercise, answer in one paragraph:
**what changes in the design, what stays the same, and why.** Being able to
tell which parts of a design are load-bearing for which requirement is the
core skill this whole group trains.

---

## Review checklist

Use this when reviewing your own doc, or ask a peer to use it:

- [ ] Every number in §3–§4 has a source or is labelled as an assumption.
- [ ] Every requirement in §3 maps to a component or decision that meets it.
- [ ] The simplest alternative was considered honestly, not set up to lose.
- [ ] Failure modes include human and process failures.
- [ ] Cost is estimated at 10×, not just at launch.
- [ ] Each key decision says whether it's reversible.
- [ ] A reader could predict how the design changes if one requirement moves.
