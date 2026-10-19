# Offline replay of T6 through guard + normalizer (2026-10-19)

**Run replayed:** `c967e50ddaa64da38741907b83648a74` (`run-c967e50d-output.txt`).
**Method:** for every val question, retrieval was recomputed from the pinned index (`hybrid`,
`chunks`, k=4) — no model call. Recomputed source labels were compared exactly (order and
duplicates) with the recorded `retrieved:` line; the recorded `raw-answer`/`raw-citations` were
then replayed through guard + normalizer using the recomputed chunk texts.

## Exactness labels

- **Exact:** retrieval recomputation and the recorded raw answer/citations. The guard is
  deterministic, so its output is exact for that input.
- **Proxy / prediction:** the `spurious_refusal_rate` is a replay prediction, not a measured
  run. Judge metrics for the recovered items are unmeasured until T5.
- **Not exact acceptance evidence:** any aggregate metric inferred from this replay.

## Retrieval cross-check

| check | result |
|---|---|
| val items | 59 |
| recomputed source-label mismatches | **0** |
| raw-answer items replayed | 49 |
| pre-model declines (θ gate) | 10 |

## Guard + normalizer actions

| action | count |
|---|---|
| `none` | 47 |
| `repaired: D2` | 1 (item 19) |
| `declined: uncited` | 1 (item 41) |
| pre-model decline | 10 |

## The acceptance items

| item | T6 final | replay result | exact/proxy |
|---|---|---|---|
| **4** — spec-first end to end | decline | **answered**; normalized 2 aliases; no D1/D2 drop | raw exact; guard exact; judge unmeasured |
| **23** — inspectable projects | decline | **answered**; normalized 1 alias; no D1/D2 drop | raw exact; guard exact; judge unmeasured |
| **63** — Linux arc | decline | **answered**; normalized 2 aliases; no D1/D2 drop | raw exact; guard exact; judge unmeasured |
| **41** — fired from Red Hat | `declined: D1` | **`declined: uncited`**; no citations existed | exact |
| **19** — Tell me about yourself | `repaired: D2` | unchanged; grounded clause kept, technology clause gone | exact |

The answers for items 4, 23 and 63 are the recorded raw model predictions, not new generations.
The normalizer resolves their org-roam IDs from the retrieved file-root chunks' own `:ID:`
properties; the raw citations become `reactive-testing-project.org` + `janbot-ai-agent.org`
(item 4), `public-proof-map.org` (23), and `linux-from-scratch.org` + `linux-origins-vut.org`
(63).

## Byte-identity of every other item

Every item outside {4, 23, 63} reproduces its T6 final answer **byte-identically** (including
item 19's repaired answer and item 41's fixed decline line). No other answer changed.

## Predicted spurious refusal

Replaying the 49 in-corpus items gives **one** declined in-corpus item: item 41
(`declined: uncited`). The predicted `spurious_refusal_rate` is therefore **1/49 = 0.0204**;
this is a **prediction** from the recorded text, not a measured run.

## Cross-link trap — unit test

`test_cross_link_is_not_an_alias_of_another_objects_id` passes. It constructs
`linux-from-scratch.org` with `:ID: 20261007-linux-from-scratch` and
`filesystem-recovery.org` with a `[[id:20261007-linux-from-scratch]]` cross-link; citing the ID
resolves only to `linux-from-scratch.org`, never to `filesystem-recovery.org`.

## Label taxonomy (closed set)

`none`; `repaired: D1-partial`; `repaired: D2`; `repaired: D1-partial + D2`;
`declined: uncited`; `declined: D1-all-invalid`; `declined: D2-empty`;
`declined: guard-error`; `disabled`.

## What this does not prove

Judge metrics (`faithfulness`, `citation_correctness`) for items 4/23/63, and the measured
`spurious_refusal_rate`, require a fresh run on freshly generated text. T5 is that run and is
not registered until the owner says go.
