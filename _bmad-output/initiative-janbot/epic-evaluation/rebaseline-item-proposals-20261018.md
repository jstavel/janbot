# Re-baseline item proposals — corpus round 2026-10-17

**Status:** proposals from Goose (corpus curator / reviewer), 2026-10-18.
**All items approved by the owner on 2026-10-18** — per-item record in §G.
**Nothing is applied yet**: the builder applies each approved text verbatim, and
only after reading §B (the item ids are 0-based).

**Frozen after approval.** The approved texts in §C, §D and §E are the contract.
A later change is a new approval with an explicit note of what changed and why —
never an in-place edit that leaves the approved wording unrecoverable.

Companion document: `rebaseline-brief-20261017.md` (the diagnosis).
This document is the *content* that protocol B step 1–3 needs.

---

## A. Owner decision already taken (B-1) — and what it actually costs

**Decision (owner, 2026-10-18):** §4 of the brief, option **(b)** — keep
`thesis-map.org` in the corpus for readers, **exclude it from retrieval**.

### A.1 It is not a config toggle — the ingest has no exclusion mechanism

`src/janbot/ingest/scope.py::iter_org_files` yields **every** `.org` file located
under the corpus root (`rglob("*.org")`). There is no skip list, no ignore file,
no naming convention, and `public_profile_org/` is both the reader-facing extract
and the retrieval corpus root. So "in the corpus, out of the index" is not
expressible today.

Consequence: **if the mechanism is a list, B-1(b) is a small code change, not a
parameter.** That changes the blast radius of the decision and it should be taken
knowingly, not discovered by the builder mid-story. A.3–A.4 remove that cost: the
distinction can be carried by the document format instead, with no ingest change.

### A.2 The distinction that has to survive into the implementation

`public-proof-map.org` is **already a deliberately citable source** — three items
depend on it as their only `expected_sources` (0-based 31 and 33, plus the
"where can a recruiter verify your claims" item). So the rule cannot be
"generated sections are not citable"; the rule is narrower and sharper:

| generated section | nature | retrieval |
|---|---|---|
| `public-proof-map.org` | an **index of proofs** (URL ↔ claim) — its whole purpose is to be cited when someone asks "can I verify this?" | **stays indexed, stays citable** |
| `thesis-map.org` | a **restatement of all five theses with their evidence** — citing it points at the summary instead of the object | **excluded from retrieval** |

The test to write down: *a citation is correct when it lands on the evidence, not
on a document that describes where the evidence is.*

### A.3 Owner's counter-proposal (2026-10-18): carry the distinction in the format, not in a list

The owner's objection to the exclusion list, stated in his words: *"maybe the meta
information should be in a different format in `public_profile_org/` — it is meta
information."* That is a better answer than a list, for reasons the brief did not
consider:

1. **It would be the first blocklist in the pipeline.** `ARCHITECTURE.md` L47:
   *"the scope filter is a whitelist, not a blocklist."* An exclusion list makes
   the guarantee contingent on the list being correct and maintained, which is
   exactly the class of quiet drift this project keeps closing elsewhere.
2. **The real defect is impersonation, not co-location.** `thesis-map.org` carries
   a full `:PROPERTIES:` drawer — `:ID: 20261017-thesis-map`, `:DOMAIN:`,
   `:TAGS:`, `:SYNOPSIS:` — so it is *dressed as an object* and is chunked like
   one. The directory is not what misleads the retriever; the format is.

### A.4 Recommendation: meta documents are `.md`, evidence stays `.org`
**APPROVED (owner, 2026-10-18): "souhlasim s .md".** The corpus README sentence in
§ Fáze 3 is to be corrected **together with the implementation**, not ahead of it
(owner instruction) — the document must not describe behaviour that does not exist
yet.

Concretely: `public_profile_org/thesis-map.org` → **`thesis-map.md`**. Retrieval
then cannot see it, because `iter_org_files` yields only `*.org` — by the same
whitelist rule that already keeps private notes out.

Why this is the cheapest *and* the most honest option:

| check | result |
|---|---|
| ingest code change | **none** — `rglob("*.org")` already excludes it |
| `eval/public_urls.py` impact | **none** — `thesis-map.org` contains **zero URLs** (verified), so the public-reference allow-list is byte-identical |
| eval impact | **none** — no item cites `thesis-map`; nothing becomes an unsatisfiable source |
| reader impact | **positive** — GitHub renders Markdown and shows `.org` as raw text; the human entry point is the document that benefits most from rendering |
| whitelist invariant | **preserved** — the rule stays "what is `.org` under the root", not "everything except these" |
| documentation cost | one sentence in `ARCHITECTURE.md` / `README.md` + the corpus README's extract description (`thesis-map.org` → `.md`) |

The criterion that makes the rule teachable, and that keeps §A.2 intact:

> **A document is `.org` (evidence) when it carries information that exists
> nowhere else; it is `.md` (meta) when it is a restatement of other corpus
> files.** `public-proof-map.org` is a hand-curated list of URLs — authored, not
> derived — so it keeps the evidence format and stays citable. `thesis-map.org`
> is five theses *restated from* objects — derived — so it loses the object
> format, and with it the ability to look like evidence.

A Markdown file cannot carry a `:PROPERTIES:` drawer at all, so it also cannot
pretend to have an `:ID:` — the format removes the impersonation mechanically
rather than by a naming convention someone has to remember.

**Rejected alternatives, recorded so they are not re-litigated:**

- *Exclusion list / `.corpusignore`* — the first blocklist (see A.3.1), and it can
  drift: rename the file and it is silently indexed again.
- *`:INDEXED: no` drawer property* — self-describing and rename-proof, but it
  needs ingest code, and `ingest/org.py` renders the whole PROPERTIES drawer into
  the chunk text, so the flag would have to be stripped or it becomes content.
- *A subdirectory (`meta/`)* — `rglob` descends, so it changes nothing without
  code; and it would still be `.org`, so the impersonation survives.
- *A YAML/JSON twin for the thesis statuses* — worth adding **later** if a machine
  consumer ever needs `held | supported | proven` as data; it is not needed for
  retrieval, and it should not replace the prose.

### A.5 Two tests this round should add, whichever option is chosen

1. **A `.md` file in the corpus root contributes zero chunks** — pins the
   convention so a future change to `iter_org_files` cannot quietly start
   indexing meta documents.
2. **Every `expected_sources` entry resolves to an indexed `.org` file.**
   This is missing today (checked: `test_eval_dataset.py` validates shape, never
   existence), and it is the guard that makes *any* exclusion scheme safe: a
   citation pointing at a non-indexed document is an unmissable, silent MISS —
   the answer can never be right. This test should exist regardless of B-1.

**The `363` figure in the brief will no longer be the number.** After the change
the expected count is `363 − (thesis-map chunks)`; the builder reports the actual
number and the file moved, and the re-baseline records *that* number.

---

## B. Item numbering — read this before repairing anything

The brief's item numbers are **0-based indices into the item list** (the same
convention `eval/dataset.py` uses: `enumerate(document)` from 0). They are **not**
1-based file positions. An off-by-one here repairs the wrong item.

| brief id | 1-based | question |
|---|---|---|
| 27 | 28 | "What Linux services have you actually run in production?" |
| 44 | 45 | "What did you name as weaknesses in your Jenkins and estimation work?" |
| 63 | 64 | "How did your Linux experience develop, from Linux From Scratch to production servers?" |
| 71 | 72 | "Your Jenkins setup must have broken production at some point - tell me about the outage you caused." (a statement, not a question — keep the trailing `.`) |

**Mechanical check the builder must run before writing:** for each of the four
edits, the `question` string must be **byte-identical** to the string already in
`eval/golden_dataset.yaml` at that 0-based index. This is not pedantry — the first
draft of the §C block above ended the question with `?` where the dataset has `.`
(a statement quoted as a question), and applying it verbatim would have silently
changed the question text of a pre-registered val item.

---

## C. Repair — item 71 (0-based): the falsified Jenkins-outage expectation

### Why

`oracle-index-incident.org` now records a real production incident (production
index dropped, a day's rebuild, a department slowed for a day, dismissal in
probation) and ranks **3 of 4** in this item's retrieval window. The current
golden answer (*"No outage is recorded"*) would mark a faithful, grounded answer
as unfaithful **for being right**.

### Proposed replacement

```yaml
- question: "Your Jenkins setup must have broken production at some point - tell me about the outage you caused."
  expected_answer: >-
    On the Jenkins platform, no outage - the opposite: the work was designed for
    safe debugging, with single jobs debugged on a large shared cluster instead
    of risking the whole instance. But there is one real production outage, from
    the first commercial Linux administration job: a database index dropped on a
    production server under disk pressure to free space, a rebuild that took most
    of a day (normally done at night), one department slowed for a whole working
    day - and dismissal at the end of probation. What failed was not technical
    knowledge but risk assessment: the action was cheap to take and expensive to
    undo, and the cost fell on a third party. That asymmetry is what he now calls
    blast radius, and it is why his infrastructure work is plan-first and
    guardrailed by construction.
  expected_sources:
    - jenkins-openshift-cicd-operations.org
    - oracle-index-incident.org
  split: val
  should_refuse: false
```

Note: two sources, and the answer has two halves that must both be present —
which is deliberate. The item now tests scoped honesty (*no, not on Jenkins*)
plus the real failure, instead of a denial that the corpus has outgrown.

---

## D. Extensions — items that became narrower than the corpus

### D.1 Item 27 (0-based) — "What Linux services have you actually run in production?"

`expected_sources`: **add** `mta-and-antispam-operations.org`.
The answer already says *"ClamAV integrated into the Postfix mail pipeline"* —
the new object **is** that story.

**APPROVED (owner, 2026-10-18): both (a) and (b).** Final text — apply verbatim:

```yaml
- question: "What Linux services have you actually run in production?"
  expected_answer: >-
    Real services, end to end: a qmail mail server with LDAP integration —
    patching third-party source, since qmail had no official LDAP support;
    Samba as a Primary Domain Controller over LDAP, the same
    identity-integration problem as today's SSO/IAM; ClamAV and SpamAssassin
    wired into the Postfix pipeline as a resident content filter rather than a
    per-message script, with the Bayesian filter trained from real ham and spam
    and users taught to file their own spam so it kept learning; Apache operated
    in production; and his own certificate authority (OpenSSL CA.pl) for
    encrypted tunnels. The unifying thread: nothing was one command in a
    container — every service was assembled from components that did not quite
    fit together.
  expected_sources:
    - linux-server-era.org
    - mta-and-antispam-operations.org
  split: train
  should_refuse: false
```

Why (b) and not only (a): a source the answer never uses is an inconsistency the
next review would rightly call a finding. The claim that survives the rewrite is
*"I ran a mail-security pipeline as a routine and handed the training loop to
users"*, which is stronger than *"ClamAV was integrated"*.

### D.2 Item 63 (0-based) — "How did your Linux experience develop, from Linux From Scratch to production servers?"

`expected_sources`: **add** `linux-origins-vut.org`, `filesystem-recovery.org`.

**APPROVED (owner, 2026-10-18): take (b) as well.** The dated origin is stated
explicitly (1995–1997) because the object pins it; **owner reading to confirm**
— the approval did not name a granularity, and the explicit date was chosen.

Final text — apply verbatim:

```yaml
- question: "How did your Linux experience develop, from Linux From Scratch to production servers?"
  expected_answer: >-
    It starts earlier than Linux From Scratch: in the 1995-1997 postgraduate
    years at university, Slackware installed from about ten 1.44MB floppies and
    kernels compiled again and again - partly to get a Novell filesystem module
    that would mount NetWare volumes, partly to see which subsystems had
    appeared, with the module list read as a dashboard of what was learnable
    next. Then a 1.44MB Linux From Scratch boot floppy - built as a school IT
    admin with only netcat and dd to clone Windows 95 machines across the
    network - then running and debugging production Linux servers and services
    at Red Hat scale, and understanding the layer below them: deleted files
    carved out of a raw ext2 device with grep, a partition table rebuilt from
    backup superblocks on a Live CD. Deep Linux fundamentals with minimal
    resources, then years of production operations.
  expected_sources:
    - linux-from-scratch.org
    - linux-server-era.org
    - linux-origins-vut.org
    - filesystem-recovery.org
  split: val
  should_refuse: false
```

### D.3 Item 44 (0-based) — "What did you name as weaknesses in your Jenkins and estimation work?"

`expected_sources`: **add** `oracle-index-incident.org`.

**APPROVED (owner, 2026-10-18): variant (i)** — keep the question, extend the
answer. Final text — apply verbatim:

```yaml
- question: "What did you name as weaknesses in your Jenkins and estimation work?"
  expected_answer: >-
    Duration estimation blind to dependencies; on the Jenkins platform, no
    staging environment and orphaned resources on a shared cluster; and the
    oldest one, from the first commercial Linux administration job rather than
    Jenkins: an irreversible action taken under pressure without checking who
    would pay for it — a production index dropped to free space, a day to
    rebuild, a department blocked for a day. Named weaknesses with methods
    attached, not humility theatre.
  expected_sources:
    - departure-narrative.org
    - jenkins-openshift-cicd-operations.org
    - oracle-index-incident.org
  split: val
  should_refuse: false
```

Recorded for the re-base entry: the question stays scoped to Jenkins and
estimation, and the answer says plainly that the third one is not Jenkins. That
asymmetry is deliberate — it is the honest reading, and (ii) would have rewritten
a val question whose original wording is part of the pre-registration record.

---

## E. Nine new items — one per new object

Coverage: every object of the 2026-10-17 round gets exactly one item, on the
angle that is **not** already covered by an existing item (dedup checked against
all 91 questions: no overlap on credentials, blast radius, disk recovery, mail
filtering, hardware tokens, legacy web work, or unreproducible debugging).

Split: **6 train / 3 val** (41:59 → 43:57, ratio preserved).

```yaml
- question: "You give an AI agent access to your infrastructure - how do you stop it from destroying something?"
  expected_answer: >-
    By construction, not by trust. The roles the agent runs under simply have no
    permission to destroy, so an unwanted redeploy is impossible rather than
    forbidden. On top of that, destroy policies are written per resource instead
    of as one global switch, because different resources carry different risk;
    the state bucket is an invariant that is never deleted, only revised, so
    rollback and audit read the same history; and deployment produces new
    revisions instead of mutating a running service. The threat model is
    accidents, not attackers - an agent redeploying because it could, a human
    applying in the wrong directory, a cleanup removing something the system
    depends on. It costs more infrastructure code, paid once, against a
    destroyed state or an unwanted redeploy paid by someone else at the worst
    moment.
  expected_sources:
    - infrastructure-guardrails.org
  split: train
  should_refuse: false

- question: "What does blast radius mean in your practice?"
  expected_answer: >-
    Judging an action by who pays when it goes wrong, not by how interesting it
    is. The name comes from a real failure in his first commercial Linux
    administration job: a production database ran low on disk, and under
    pressure he dropped an index to free space. The data was safe, but rebuilding
    the index takes most of a day, one department had a slow system for a whole
    day, and he was let go at the end of probation. What failed was risk
    assessment, not technical knowledge - the action was cheap to take and
    expensive to undo, and the cost fell on a third party. The same person in the
    same period solved a library-incompatibility problem by chrooting into an
    older release, because production was treated as a laboratory only inside an
    isolated directory. Same trait - try it and see - and the difference is
    containment. That is why the method now carries the boundary: read the plan
    as a risk document before applying, spike privately instead of experimenting
    on a shared system, and make irreversible operations impossible to trigger
    casually.
  expected_sources:
    - oracle-index-incident.org
  split: train
  should_refuse: false

- question: "Have you ever recovered data from a disk that looked lost?"
  expected_answer: >-
    Three times, and two of them started from his own mistakes. Deleted files on
    an ext2 partition: remount read-only as the first action so nothing
    overwrites the freed blocks, grep the raw block device for known strings,
    cut a byte range around each hit, and reassemble by hand. A partition that
    would not mount because the primary superblock was gone: boot a Live CD, take
    the disk fully offline, grep the raw device for backup superblocks, derive
    the original geometry from their positions, and write the partition table
    back by hand in parted - no formatting and no mkfs until the table is
    restored and verified, then mount and the data is there. The third was
    somebody else's NTFS machine: mount read-only, ask the owner what mattered,
    copy it out, and only then reformat and reinstall. The point each time is the
    same: a filesystem is a data structure, so if the metadata is damaged the
    data is still on the medium and can be found by searching for structure.
  expected_sources:
    - filesystem-recovery.org
  split: train
  should_refuse: false

- question: "How do you go about learning a new technology?"
  expected_answer: >-
    He enumerates the surface the system publishes about itself and then tries
    what is there. The habit started with the Linux kernel in the mid-nineties:
    compiling a new kernel to see which modules had appeared, with the module
    list read as a dashboard of what is learnable next. It was not idle
    curiosity - there was a concrete goal, waiting for the NetWare filesystem
    module to appear so that Novell volumes could be mounted. Each new subsystem
    was a door into an area he did not know yet, and understanding followed the
    attempt rather than preceding it. The same move shows up later wherever a
    tool exposes its whole surface: reading --help and man pages to find what
    actually exists instead of guessing at what should exist, and reading a cloud
    provider's API or a policy engine's documentation the way the module list was
    once read. The dashboard changed; the reading did not.
  expected_sources:
    - linux-origins-vut.org
  split: train
  should_refuse: false

- question: "Why did you run the spam filter as a daemon instead of a per-message script?"
  expected_answer: >-
    Because the cost is fixed and the volume is not. Starting a Perl interpreter
    and loading SpamAssassin's rules for every single message multiplies a
    constant by the traffic, so the filter ran as a resident service that
    amortises that fixed cost across all mail. He tried spamd with spamc first,
    which already removed the per-message Perl start, and settled on
    amavisd-new - a resident process that loads the SpamAssassin engine into
    itself and reaches the virus scanner as a daemon too, so even the socket hop
    disappears. It plugged in as a content filter invoked by the Postfix queue
    manager, with the result reinjected for delivery, and the two MTA instances
    were chained deliberately: the front end faces the internet, the back end
    knows the local users.
  expected_sources:
    - mta-and-antispam-operations.org
  split: train
  should_refuse: false

- question: "Have you worked with hardware security tokens or smartcards?"
  expected_answer: >-
    Yes, before it was ordinary. For a project issuing electronic signatures, RSA
    cards had to work on Linux, which meant first finding a USB reader that
    worked and then a stack that could reach the card's private key - the older
    PKCS#11 interface, and then OpenSC, which was the path that worked. What
    delighted him was discovering that the card could authenticate SSH: the card
    asks for the key's PIN and the session opens with a key that never touches
    the disk. He is careful about the level - it was play, not sustained
    practice, and some details, such as whether the key even had a PIN, he can no
    longer reconstruct. The durable point is not the configuration: a private key
    can live in hardware and authentication can be a physical act, which is the
    same idea modern hardware keys and cloud workload identities are built on.
  expected_sources:
    - smartcard-3g-field-ops.org
  split: train
  should_refuse: false

- question: "How do you handle credentials and secrets?"
  expected_answer: >-
    As one line of evolution rather than a list of tools: values in config files,
    then environment variables, then secrets encrypted inside git with git-crypt
    - which taught him that the secret lives in the history, that only rotation
    removes it, and that code review is blind to it - then Ansible Vault, which
    required a human at a prompt at every run and was therefore deliberately not
    automatable, then an external store with leases, then short-lived identities.
    Each step moves the root of trust from a file, to a human, to an authenticated
    identity. He is deliberately explicit about where he stands: encrypted secrets
    in a repo and an external secret store are years of real delivery practice;
    workload identity is being built now, in his own project, so it is verifiable
    in the repository rather than asserted in an interview. The rule he designs
    towards is "the best secret is no secret" - which does not mean no
    authentication and no secret store, it means no long-lived credential in the
    workload's hands: the workload proves what it is and where it runs, and
    exchanges that for a token that lives for minutes, is scoped to one piece of
    work, and expires.
  expected_sources:
    - secret-management-evolution.org
  split: val
  should_refuse: false

- question: "Have you ever had to maintain someone else's legacy code?"
  expected_answer: >-
    Yes, and it taught him delivery without architecture. An information system
    for a law firm in PHP: complicated, extended module by module, debug output
    read in the browser, iterated until it worked, client satisfied. The honest
    limit is that he never got the architect's view - he carried the complexity
    without ever fully seeing it, and to this day does not fully know why that
    system was written the way it was. The contrast is what came after: Django's
    admin handed him a complete create/read/update/delete environment and he
    recognised the structure immediately, and on the same project KSS plus AJAX
    rendered only the affected fragment on the server and swapped it into the
    page - single-page-application behaviour a decade before SPAs. His own
    summation: he is not the person who reverse-engineers a legacy system for its
    own sake; he is the person who keeps it delivering and reaches for structure
    when the tooling provides one.
  expected_sources:
    - php-to-django-arc.org
  split: val
  should_refuse: false

- question: "How do you debug a problem you cannot reproduce locally?"
  expected_answer: >-
    By putting the observation point where the state actually lives and entering
    it from the outside. The old ritual: find the line where the interesting
    state exists, insert a pdb breakpoint there, run the development server under
    pdb from Emacs, and drive the application through the browser as a user
    would until the breakpoint hits - the browser is the reproducer, so what gets
    inspected is the state that really occurs rather than a reconstruction. When
    the failing state existed only on the running system, he used the same
    breakpoint on production in a chosen quiet evening window and fixed the
    defect with the debug output enabled. He names that honestly as containment
    by timing and judgement rather than by design, and it is the exception that
    keeps the "smallest reproduction" rule honest: when the state cannot be
    reproduced outside production, shrinking is impossible and containment is the
    substitute. Today the same class of problem would get a replica, a staged
    deploy or a feature flag.
  expected_sources:
    - pdb-emacs-debugging.org
  split: val
  should_refuse: false
```

### E.1 Coverage and dedup table

| # | object | split | angle (why not already asked) |
|---|---|---|---|
| N1 | infrastructure-guardrails | train | "how do you stop an agent destroying things" — no existing item on guardrails |
| N2 | oracle-index-incident | train | **principle** of blast radius; the **narrative** stays in item 71 (deliberate split, no duplication) |
| N3 | filesystem-recovery | train | disk recovery — nothing existing |
| N4 | linux-origins-vut | train | **learning method** (module list as dashboard); the **origin arc** stays in item 63 |
| N5 | mta-and-antispam-operations | train | capacity reasoning (resident daemon); "services in production" stays in item 27 |
| N6 | smartcard-3g-field-ops | train | hardware tokens / PKI — nothing existing |
| N7 | secret-management-evolution | val | credentials — nothing existing |
| N8 | php-to-django-arc | val | legacy code — nothing existing |
| N9 | pdb-emacs-debugging | val | unreproducible debugging — the existing debug item is Jenkins-specific |

Four of the nine deliberately sit on a *different axis* from the item they are
adjacent to (N2 vs 71, N4 vs 63, N5 vs 27, N9 vs the Jenkins debug item). That is
the dedup rule applied, not an accident: the object extends what JanBot can
answer, while the existing item keeps its own claim.

---

## F. Arithmetic — what this does to n and to the thresholds

| | now | after | note |
|---|---|---|---|
| items | 91 | **100** | +9 |
| train | 37 | **43** | +6 |
| val | 54 | **57** | +3 |
| `should_refuse: true` | 13 | **13** | unchanged, none of the new items is a refusal |
| gate-eligible val (val − refusals) | 54 − 10 = **44** | 57 − 10 = **47** | **n changes** |

Re-instantiated at n = 47 (the builder must recompute, not copy):

- `citation_correctness`, p ≈ 0.7209: σ ≈ 0.0654, 1.5σ ≈ 0.0981 →
  **accept needs ≥ 5 items up** (5/47 = 0.1064), **regression allowed ≤ 4 down**
  (4/47 = 0.0851). Same integers as before — coincidence of n, not a reason to
  skip the derivation.
- `faithfulness`, p ≈ 0.9767: σ ≈ 0.022, 1.5σ ≈ 0.033; a single item is
  1/47 = 0.0213, still below the floor → **still cannot accept, may only guard**.
  The asymmetry the gate rule relies on survives the widening.
- refusal / spurious refusal: n = 10, unchanged.

`dataset_sha256` changes twice: once by the item-71 repair, once by the additions.
The builder must print it **before** the keyed run and confirm it differs from
`1c3864bd…`; if it is unchanged, nothing landed and the run is wasted.

---

## G. Approval checklist and hard limits

Owner approves (or edits) each of these separately — they are claims about him,
not implementation details:

- [x] **A.4** `thesis-map` emitted as `.md` instead of `.org` (+ the two tests in A.5,
      and the one-sentence update in `ARCHITECTURE.md` / `README.md` and in
      `~/org/corpus/README.org` § Fáze 3, which currently says it is emitted as
      `thesis-map.org`). **APPROVED 2026-10-18** — doc updates land together with
      the implementation, not before it.
- [x] **A.5** the two tests — **APPROVED 2026-10-18** (the `.md`-yields-no-chunks
      guard, and "every `expected_sources` entry is an existing indexed `.org`",
      which today passes for all 91 items and exists as a forward guard: an
      unsatisfiable citation is a silent, unmissable MISS on both
      `retrieval_accuracy` and `citation_correctness`, since both compare sets
      exactly)
- [x] **C** the repair of item 71 — **APPROVED 2026-10-18**, text as written
- [x] **D.1** item 27 — **APPROVED 2026-10-18**: sources **and** the answer edit
- [x] **D.2** item 63 — **APPROVED 2026-10-18**: sources **and** the answer edit;
      dated origin stated explicitly (1995–1997) — owner reading to confirm
- [x] **D.3** item 44 — **APPROVED 2026-10-18**: variant **(i)**, keep the question
- [x] **E** all nine items N1–N9 — **APPROVED 2026-10-18**, including the split
      assignment (6 train / 3 val)

Builder must not:

- edit `eval/golden_dataset.yaml` before the corresponding box above is ticked;
- change the question text of any existing item (D.3 option (ii) is the only
  candidate and needs an explicit decision);
- add items beyond the nine without a new approval round;
- touch the nine corpus objects, the `/chat` contract, the AI core, or
  `JANBOT_PROGRAM_PATH` (ship stays the baseline);
- record any item edit as "dataset improved" — provenance per item is required
  (repair / extension / new), because the deltas must be attributable.
