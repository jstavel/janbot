"""Versioned lexicon for the deterministic output guard.

This module is data, not logic. It is reviewed like any other data and changed only with a
reason; adding a marker or subject token is a behaviour change and needs a test. The guard
matches case-insensitively.

A marker is a capability/experience/commitment phrase. ``answer_phrase`` is the form the
model may write; ``chunk_phrase`` is the grounded form a cited chunk must contain for the
claim to count as supported. The split lets an answer say "I am interested in working for X"
while a chunk says "interested in working for X", without treating the pronoun as content.
"""

from __future__ import annotations

from typing import NamedTuple

LEXICON_VERSION = "2026-10-20.2"


class Marker(NamedTuple):
    answer_phrase: str
    chunk_phrase: str


MARKERS: tuple[Marker, ...] = (
    Marker("strong foundation in", "strong foundation"),
    Marker("strong background in", "strong background"),
    Marker("professional in", "professional"),
    Marker("expert in", "expert"),
    Marker("proficient in", "proficient"),
    Marker("skilled in", "skilled"),
    Marker("experienced in", "experienced"),
    Marker("deep experience in", "deep experience"),
    Marker("deep knowledge of", "deep knowledge"),
    Marker("i am interested in working for", "interested in working for"),
    Marker("i want to work for", "want to work for"),
    Marker("i am available", "available"),
    Marker("i can start", "can start"),
    Marker("i accept", "accept"),
    Marker("my expertise", "expertise"),
    Marker("i have expertise", "expertise"),
)

SUBJECT_FORMS: tuple[str, ...] = ("I", "I'm", "I am", "I'd", "I would", "I can")


class CommitmentPredicate(NamedTuple):
    """One commitment/interest predicate on the published predicate axis.

    ``lead`` is the human form used by the generated sweep; ``pattern`` is the
    structural regex the guard matches; ``chunk_phrase`` is the grounded form a
    cited chunk must contain. ``bare`` predicates (interest/availability) are a
    commitment even without a prospect reference.
    """

    lead: str
    pattern: str
    chunk_phrase: str
    bare: bool = False


COMMITMENT_PREDICATES: tuple[CommitmentPredicate, ...] = (
    CommitmentPredicate("glad to", r"glad\s+to\b", "glad to"),
    CommitmentPredicate("keen to", r"keen\s+to\b", "keen to"),
    CommitmentPredicate("happy to", r"happy\s+to\b", "happy to"),
    CommitmentPredicate("eager to", r"eager\s+to\b", "eager to"),
    CommitmentPredicate("delighted to", r"delighted\s+to\b", "delighted to"),
    CommitmentPredicate("thrilled to", r"thrilled\s+to\b", "thrilled to"),
    CommitmentPredicate("love to", r"love\s+to\b", "love to"),
    CommitmentPredicate("want to", r"want\s+to\b", "want to"),
    CommitmentPredicate("interested in", r"interested\s+in\b", "interested in"),
    CommitmentPredicate("open to", r"open\s+to\b", "open to"),
    CommitmentPredicate(
        "look forward to", r"look(?:ing)?\s+forward\s+to\b", "look forward to"
    ),
    CommitmentPredicate(
        "jump at the chance to",
        r"jump\s+at\s+the\s+chance\s+to\b",
        "jump at the chance to",
    ),
    CommitmentPredicate("gladly accept", r"gladly\s+accept\b", "gladly accept", True),
    CommitmentPredicate("available for", r"available\s+for\b", "available for"),
    CommitmentPredicate("can start", r"can\s+start\b", "can start", True),
    CommitmentPredicate("drawn to", r"drawn\s+to\b", "drawn to"),
    CommitmentPredicate("attracted to", r"attracted\s+to\b", "attracted to"),
    CommitmentPredicate("excited about", r"excited\s+about\b", "excited about"),
    CommitmentPredicate("excited to", r"excited\s+to\b", "excited to"),
    CommitmentPredicate("like to", r"like\s+to\b", "like to"),
    CommitmentPredicate("be part of", r"be\s+part\s+of\b", "be part of"),
    CommitmentPredicate("join", r"join(?:ing)?\b", "join"),
    CommitmentPredicate("work for", r"work(?:ing)?\s+for\b", "work for"),
    CommitmentPredicate("work with", r"work(?:ing)?\s+with\b", "work with"),
    CommitmentPredicate("apply for", r"apply(?:ing)?\s+for\b", "apply for"),
    CommitmentPredicate(
        "be considered for", r"be\s+considered\s+for\b", "be considered for"
    ),
    CommitmentPredicate("accept", r"accept\b", "accept the offer", True),
    CommitmentPredicate(
        "interested", r"interested\b(?!\s+in\b)", "interested in working", True
    ),
    CommitmentPredicate("available", r"available\b(?!\s+for\b)", "available", True),
)


class ProspectReference(NamedTuple):
    """A named or deictic reference to the prospect on the reference axis."""

    phrase: str
    pattern: str


# Named, role, mission, deictic and verb-bearing references. The bare ``you`` /
# ``there`` forms match only at the end of a clause (so "what you do" is a topic,
# not a party reference).
PROSPECT_REFERENCES: tuple[ProspectReference, ...] = (
    ProspectReference("your company", r"your\s+company\b"),
    ProspectReference("your team", r"your\s+team\b"),
    ProspectReference("your organisation", r"your\s+organi[sz]ation\b"),
    ProspectReference("your mission", r"your\s+mission\b"),
    ProspectReference("your offer", r"your\s+offer\b"),
    ProspectReference("the role", r"the\s+role\b"),
    ProspectReference("this role", r"this\s+role\b"),
    ProspectReference("the position", r"the\s+position\b"),
    ProspectReference("this position", r"this\s+position\b"),
    ProspectReference("the job", r"the\s+job\b"),
    ProspectReference("this job", r"this\s+job\b"),
    ProspectReference("the offer", r"the\s+offer\b"),
    ProspectReference("this offer", r"this\s+offer\b"),
    ProspectReference("workplace", r"workplaces?\b"),
    ProspectReference("come aboard", r"com(?:e|ing)\s+aboard\b"),
    ProspectReference("join you", r"join(?:ing)?\s+you\b"),
    ProspectReference("work with you", r"work(?:ing)?\s+with\s+you\b"),
    ProspectReference("there", r"\bthere\b(?=\s*[.!?,;]|$)"),
    ProspectReference("you", r"\byou\b(?=\s*[.!?,;]|$)"),
)


SUBJECT_TOKENS: tuple[str, ...] = (
    # languages / stacks
    "typescript",
    "python",
    "perl",
    "javascript",
    "js",
    "clojure",
    "rust",
    "java",
    "golang",
    "c++",
    "c#",
    "php",
    "sql",
    "postgresql",
    "postgres",
    "django",
    "react",
    "linux",
    # platforms / tools
    "kubernetes",
    "openshift",
    "terraform",
    "ansible",
    "jenkins",
    "rabbitmq",
    "kafka",
    "prometheus",
    "grafana",
    "nagios",
    "openssl",
    "pki",
    "smartcard",
    "edeposit",
    "janbot",
    "krakatoa",
    "red hat",
    "aws",
    "gcp",
    "azure",
    # employment / commitments
    "full-time",
    "part-time",
    "remote",
    "on-site",
    "onsite",
    "hybrid",
    "relocate",
    "relocation",
    "notice period",
    "salary",
    "start date",
    "employment",
    "job offer",
    "contract",
)


# Declared clause connectors for D2 (regex patterns). These are the only boundaries the
# guard may split a sentence on. A version number such as "Python 3.12" contains none of
# them and is never split. The ", and" connector only splits when a clause starter follows:
# in "Python, Perl, Clojure, and TypeScript" it is a list conjunction; in
# "... TypeScript, and I focus ..." it is a clause boundary.
CLAUSE_CONNECTORS: tuple[str, ...] = (
    r", and (?=(?:I|we|you|he|she|it|they|the|this|that|these|those|a|an|can|will|would|should|could|may|might|must|is|are|was|were|has|have|do|does|did)\b)",
    r"; ",
    r", but ",
    r" but ",
    r", so ",
    r" so ",
)
