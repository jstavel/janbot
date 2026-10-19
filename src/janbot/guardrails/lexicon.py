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

LEXICON_VERSION = "2026-10-19.2"


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
