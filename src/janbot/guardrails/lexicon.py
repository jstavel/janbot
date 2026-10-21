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

LEXICON_VERSION = "2026-10-21.1"


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
    """One predicate on the actionable or company-interest axis.

    ``lead`` is the human form used by the generated regression; ``pattern`` is
    the structural regex the guard matches; ``chunk_phrase`` is the grounded form
    a cited chunk must contain.
    """

    lead: str
    pattern: str
    chunk_phrase: str


ACTIONABLE_COMMITMENTS: tuple[CommitmentPredicate, ...] = (
    CommitmentPredicate("available", r"available\b", "available"),
    CommitmentPredicate("available to start", r"available\s+to\s+start\b", "available to start"),
    CommitmentPredicate(
        "available immediately", r"available\s+immediately\b", "available immediately"
    ),
    CommitmentPredicate(
        "available for work",
        r"available\s+for\s+(?:work|the\s+role|this\s+role|a\s+role)\b",
        "available for",
    ),
    CommitmentPredicate("can start", r"can\s+start\b", "can start"),
    CommitmentPredicate("could start", r"could\s+start\b", "could start"),
    CommitmentPredicate(
        "start next month",
        r"start\s+(?:next|on|immediately|from|in|at)\b",
        "start next",
    ),
    CommitmentPredicate("start date", r"start\s+date\b", "start date"),
    CommitmentPredicate("notice period", r"notice\s+period\b", "notice period"),
    CommitmentPredicate(
        "salary expectation",
        r"salary\s+(?:expectation|requirement|range)\b",
        "salary expectation",
    ),
    CommitmentPredicate(
        "compensation expectation",
        r"compensation\s+(?:expectation|requirement|range)\b",
        "compensation expectation",
    ),
    CommitmentPredicate("pay expectation", r"pay\s+expectation\b", "pay expectation"),
    CommitmentPredicate(
        "expect a salary", r"expect(?:ing)?\s+(?:a\s+)?salary\b", "salary"
    ),
    CommitmentPredicate("my rate is", r"my\s+rate\s+is\b", "my rate is"),
    CommitmentPredicate(
        "accept the offer", r"accept\s+(?:the|an|your)\s+offer\b", "accept the offer"
    ),
    CommitmentPredicate("accept", r"accept\s*(?:[.!]|$)", "accept"),
    CommitmentPredicate(
        "willing to relocate",
        r"(?:willing|able|open)\s+to\s+relocat(?:e|ing)\b",
        "willing to relocate",
    ),
    CommitmentPredicate("can relocate", r"can\s+relocat(?:e|ing)\b", "can relocate"),
    CommitmentPredicate("relocation", r"relocat(?:e|ion)\b", "relocation"),
    CommitmentPredicate(
        "willing to travel",
        r"(?:willing|able|open)\s+to\s+travel\b",
        "willing to travel",
    ),
    CommitmentPredicate("can travel", r"can\s+travel\b", "can travel"),
    CommitmentPredicate(
        "available for interview",
        r"available\s+for\s+(?:an\s+)?interview\b",
        "available for interview",
    ),
)

COMPANY_INTEREST_PREDICATES: tuple[CommitmentPredicate, ...] = (
    CommitmentPredicate("interested in", r"interested\s+in\b", "interested in"),
    CommitmentPredicate("drawn to", r"drawn\s+to\b", "drawn to"),
    CommitmentPredicate("attracted to", r"attracted\s+to\b", "attracted to"),
    CommitmentPredicate("excited about", r"excited\s+about\b", "excited about"),
    CommitmentPredicate(
        "excited to join", r"excited\s+to\s+join\b", "excited to join"
    ),
    CommitmentPredicate("keen to join", r"keen\s+to\s+join\b", "keen to join"),
    CommitmentPredicate(
        "want to work for", r"want\s+to\s+work\s+(?:for|at)\b", "want to work for"
    ),
    CommitmentPredicate(
        "would like to work for",
        r"(?:would\s+)?like\s+to\s+work\s+(?:for|at)\b",
        "like to work for",
    ),
    CommitmentPredicate(
        "love to work for", r"love\s+to\s+work\s+(?:for|at)\b", "love to work for"
    ),
    CommitmentPredicate(
        "open to joining", r"open\s+to\s+(?:joining|working)\b", "open to joining"
    ),
    CommitmentPredicate(
        "look forward to joining",
        r"look(?:ing)?\s+forward\s+to\s+(?:joining|working)\b",
        "look forward to joining",
    ),
    CommitmentPredicate(
        "jump at the chance to join",
        r"jump\s+at\s+the\s+chance\s+to\s+(?:join|work)\b",
        "jump at the chance to join",
    ),
    CommitmentPredicate("join", r"join(?:ing)?\b", "join"),
    CommitmentPredicate("work for", r"work(?:ing)?\s+(?:for|at)\b", "work for"),
    CommitmentPredicate("work with", r"work(?:ing)?\s+with\b", "work with"),
    CommitmentPredicate("work there", r"work(?:ing)?\s+there\b", "work there"),
    CommitmentPredicate("be part of", r"be\s+part\s+of\b", "be part of"),
    CommitmentPredicate("apply for", r"apply(?:ing)?\s+(?:for|to)\b", "apply for"),
    CommitmentPredicate(
        "be considered for", r"be\s+considered\s+for\b", "be considered for"
    ),
    CommitmentPredicate("come aboard", r"com(?:e|ing)\s+aboard\b", "come aboard"),
    CommitmentPredicate(
        "move forward with", r"move\s+forward\s+with\b", "move forward with"
    ),
)


class ProspectReference(NamedTuple):
    """A named or deictic reference to the prospect's company/team."""

    phrase: str
    pattern: str


COMPANY_REFERENCES: tuple[ProspectReference, ...] = (
    ProspectReference("your company", r"your\s+company\b"),
    ProspectReference("your team", r"your\s+team\b"),
    ProspectReference("your organisation", r"your\s+organi[sz]ation\b"),
    ProspectReference("your mission", r"your\s+mission\b"),
    ProspectReference("your offer", r"your\s+offer\b"),
    ProspectReference("the company", r"the\s+company\b"),
    ProspectReference("the team", r"the\s+team\b"),
    ProspectReference("join you", r"join(?:ing)?\s+you\b"),
    ProspectReference("work with you", r"work(?:ing)?\s+with\s+you\b"),
    ProspectReference("come aboard", r"com(?:e|ing)\s+aboard\b"),
    ProspectReference("part of what you do", r"part\s+of\s+what\s+you\s+do\b"),
    ProspectReference("there", r"\bthere\b(?=\s*[.!?,;]|$)"),
    ProspectReference("you", r"\byou\b(?=\s*[.!?,;]|$)"),
)

NAMED_COMPANIES: tuple[str, ...] = (
    "Acme",
    "Globex",
    "Initech",
    "Umbrella",
    "Hooli",
)

# Proper nouns that are technologies/products/topics, not companies. Company
# names (Red Hat, AWS, JanBot, …) stay eligible; a cited chunk can ground them.
NON_COMPANY_PROPER_NOUNS = frozenset(
    {
        "i",
        "i'm",
        "i am",
        "i'd",
        "i would",
        "i can",
        "my",
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "we",
        "you",
        "it",
        "yes",
        "no",
        "and",
        "but",
        "if",
        "when",
        "where",
        "what",
        "how",
        "why",
        "while",
        "sounds",
        "count",
        "python",
        "perl",
        "clojure",
        "typescript",
        "javascript",
        "js",
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
    }
)

NAMED_COMPANY_PATTERN = r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,2}\b"


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
