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

LEXICON_VERSION = "2026-10-20.1"


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

class CommitmentMarker(NamedTuple):
    """A first-person commitment/interest phrase about the prospect.

    ``party_required`` distinguishes an interest/join/role claim, which needs a
    party noun in the forward window, from a commitment that stands on its own
    (availability, start date, acceptance). ``chunk_phrase`` is the grounded form
    a cited chunk must contain (with a party noun, when required).
    """

    answer_phrase: str
    chunk_phrase: str
    party_required: bool = True


COMMITMENT_MARKERS: tuple[CommitmentMarker, ...] = (
    # Interest in the prospect (party noun required)
    CommitmentMarker("interested in", "interested in"),
    CommitmentMarker("drawn to", "drawn to"),
    CommitmentMarker("attracted to", "attracted to"),
    CommitmentMarker("excited about", "excited about"),
    CommitmentMarker("keen on", "keen on"),
    CommitmentMarker("open to", "open to"),
    # Join / role / working-for (party noun required)
    CommitmentMarker("excited to join", "excited to join"),
    CommitmentMarker("eager to join", "eager to join"),
    CommitmentMarker("keen to join", "keen to join"),
    CommitmentMarker("happy to join", "happy to join"),
    CommitmentMarker("glad to join", "glad to join"),
    CommitmentMarker("looking forward to joining", "looking forward to joining"),
    CommitmentMarker("join your", "join your"),
    CommitmentMarker("joining your", "joining your"),
    CommitmentMarker("join the", "join the"),
    CommitmentMarker("joining the", "joining the"),
    CommitmentMarker("be part of your", "be part of your"),
    CommitmentMarker("be part of the", "be part of the"),
    CommitmentMarker("part of your team", "part of your team"),
    CommitmentMarker("work for your", "work for your"),
    CommitmentMarker("working for your", "working for your"),
    CommitmentMarker("want to work for", "want to work for"),
    CommitmentMarker("would like to work for", "would like to work for"),
    CommitmentMarker("like to work for", "like to work for"),
    CommitmentMarker("be considered for", "be considered for"),
    CommitmentMarker("want to apply for", "want to apply for"),
    CommitmentMarker("like to apply for", "like to apply for"),
    # Standalone commitments (no party noun)
    CommitmentMarker("working for you", "working for you", False),
    CommitmentMarker("available to start", "available to start", False),
    CommitmentMarker("available immediately", "available immediately", False),
    CommitmentMarker("can start next month", "can start next month", False),
    CommitmentMarker("can start immediately", "can start immediately", False),
    CommitmentMarker("start next month", "start next month", False),
    CommitmentMarker("start immediately", "start immediately", False),
    CommitmentMarker("accept the offer", "accept the offer", False),
    CommitmentMarker("accept an offer", "accept an offer", False),
    CommitmentMarker("i accept", "accept", False),
    CommitmentMarker("take the role", "take the role", False),
    CommitmentMarker("take the job", "take the job", False),
    CommitmentMarker("sign me up", "sign me up", False),
    CommitmentMarker("come aboard", "come aboard", False),
)

PARTY_TOKENS: tuple[str, ...] = (
    "company",
    "companies",
    "team",
    "teams",
    "role",
    "roles",
    "position",
    "positions",
    "job",
    "jobs",
    "offer",
    "offers",
    "workplace",
    "workplaces",
    "organization",
    "organizations",
    "organisation",
    "organisations",
    "employer",
    "employers",
    "your company",
    "your team",
    "your role",
    "your organisation",
    "your organization",
    "your workplace",
    "this role",
    "the role",
    "this position",
    "the position",
    "this job",
    "the job",
    "the offer",
    "this offer",
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
