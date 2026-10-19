# ADR-010 — deterministic output-level guard against fabricated citations and over-claiming

**Status:** Accepted (implementation in this change).
**Date:** 2026-10-19.
**Context:** ADR-009 condition (option (c)) requires a deterministic output-level guard
before the `/chat` core, with no model call, so the benchmark stays valid. Runs A
(`e7110d58`, `chunks`) and B (`f9ae28f2`, `sources`) were both refused registration; the
remaining failures are generation-side, not retrieval-side (`rebaseline-brief-20261018.md`
§5.8, §6.7/§6.8). Five items are the acceptance target: 4, 19, 74, 83, 97.

## Decision

Add a deterministic filter between the program's raw prediction and the response. It runs
inside the guardrail layer, before the existing citation validation; it uses only
request-local data. It never calls a model, the network, the dataset, or `expected_sources`.

**Inputs**

- the generated answer text;
- the source labels the model cited;
- the retrieved chunks for this request: source label plus chunk text.

**Outputs**

- a repaired `(answer, citations)` pair, or
- a decline. The existing uncited/decline path builds the contract-compliant
  `insufficient` reply; the `ChatResponse` shape and the `/chat` contract do not change.

**Fail closed.** If the guard itself raises, the request declines. No unguarded text is
emitted.

## D1 — fabricated citation

A cited label is **fabricated** when it is not in the retrieved source set.

**Action:** drop that label, keep the answer. If no valid label remains, the existing
uncited rule turns the response into a decline — no new mechanism is needed. A valid label
is never dropped; the answer is not rewritten by D1.

## D2 — over-claim

A sentence is an **over-claim** when it contains both:

1. a **capability/experience/commitment marker** from the declared lexicon (e.g.
   “strong foundation in”, “professional in”, “expert in”, “interested in working for”);
2. a **subject token** from the declared lexicon (technologies, employers, commitments).

The sentence is kept only when the claim is **grounded in a cited chunk**: the marker's
head phrase and the subject token must co-occur in the same sentence of at least one cited
chunk. The subject must sit in the marker's **forward claim window** — the text following
the marker (up to 120 characters). A subject token earlier in the sentence is not
necessarily the marker's object; ignoring it prevents dropping a grounded sentence such as
“…expertise in Python and Perl … with a strong foundation in asynchronous systems”. Merely
finding the subject token somewhere in a cited chunk is **not** grounding —
`personal-intro.org` says “TypeScript with agents”, which grounds that wording but not
“a strong foundation in TypeScript”. If the window names several subject tokens, **all** of
them must be grounded; one ungrounded token drops the sentence.

**Action:** drop the ungrounded sentence, keep the other sentences. If the answer becomes
empty, decline.

**Why this is stricter than “token not present”:** the acceptance item 19 is exactly the
case where the subject token is present but the capability claim is not. A token-presence
test would keep the over-claim. The co-occurrence test is mechanical and catches it.

## Decision table

| failure | action | reason |
|---|---|---|
| cited label not retrieved | drop label, keep answer | the answer may still be grounded in the remaining cited chunks |
| no valid label remains | decline | the existing uncited rule |
| sentence: marker + ungrounded subject | drop sentence | a thinner answer is better than a false capability claim |
| all sentences dropped | decline | no grounded answer remains |
| guard internal error | decline | fail closed; never emit unguarded text |
| clean answer and labels | byte-identical pass-through | the guard must not perturb valid output |

Repair is the default over refusal: a fabricated label is an error, but a slightly thinner
answer is still useful. Refusal is reserved for an answer with no valid grounding left.

## Lexicon

The markers, their head phrases, and the subject tokens live in a dedicated, versioned data
module (`src/janbot/guardrails/lexicon.py`), not inline in the matching code. It is
reviewed like any other data and changed only with a reason. It contains no model call and
no network access.

## What this guard cannot catch

- paraphrase (“I know TypeScript well”, “TypeScript is second nature”);
- implication and hedged claims;
- capability claims without a lexicon marker;
- a subject token that does not match the lexicon's spelling or aliases;
- a claim whose subject is phrased **before** the marker (word-order paraphrase);
- a claim whose marker and subject sit in different sentences;
- over-claiming spread across several sentences that are each individually grounded.

The guard is a deterministic floor, not a semantic judge. A guard that overstates its own
coverage would reproduce the defect it exists to prevent.

## Contract and evidence

- `/chat` contract, `ChatResponse`, citations shape and error envelope unchanged.
- No change to the DSPy signature, prompts or retrieval path.
- Evidence: unit tests for D1, D2, no-op, empty-after-drop and fail-closed; the offline
  replay of recorded runs; and (after owner approval) one confirmation run.
- The confirmation run is the first run whose per-item artifact carries the raw answer and
  cited labels the guard needs; the earlier run outputs contain answer text only for
  answered items and no per-item citations, so they cannot fully replay D1.
