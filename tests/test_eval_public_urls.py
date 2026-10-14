"""Unit tests for the public-reference allow-list and metric.

They prove the owner's matrix: an answer whose URLs are all allow-listed passes;
an invented or wrong-owner URL fails as unverifiable; an expected URL the model
answer omits fails as incomplete; and an item with no URLs passes. They also
prove the URL contract (normalization, deeper-path and pathless matching,
extraction, glued-separator splitting), that each failure is named per item, that
the committed allow-list still matches a fresh corpus harvest (no drift), and
that the metric is registered for the runner. No model, no network, no MLflow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from janbot.api.contract import ChatResponse, Citation
from janbot.eval.dataset import GoldenItem
from janbot.eval.metrics import (
    ItemOutcome,
    public_reference_failures,
    public_references_metric,
    registered_metrics,
)
from janbot.eval.public_urls import (
    DEFAULT_ALLOW_LIST_PATH,
    extract_urls,
    harvest_public_urls,
    is_public_reference,
    load_public_urls,
    normalize_reference,
)

ALLOW = frozenset(
    {
        "github.com/jstavel/janbot",
        "github.com/other/repo",
        "brailcom.cz/projects",
        "bazar-cd.cz",
    }
)


def _item(expected_answer: str) -> GoldenItem:
    return GoldenItem(
        question="q", expected_answer=expected_answer, expected_sources=["profile.org"]
    )


def _outcome(expected_answer: str, answer: str | None) -> ItemOutcome:
    response = (
        None
        if answer is None
        else ChatResponse(answer=answer, citations=[Citation(source="p.org")])
    )
    error = None if answer is not None else "boom"
    return ItemOutcome(item=_item(expected_answer), response=response, error=error)


def test_all_urls_allow_listed_passes() -> None:
    outcomes = [
        _outcome(
            "JanBot is https://github.com/jstavel/janbot.",
            "JanBot is live at https://github.com/jstavel/janbot",
        )
    ]

    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_invented_url_fails_as_unverifiable() -> None:
    outcomes = [_outcome("No link here.", "Read https://github.com/jstavel/evil")]

    assert public_references_metric(outcomes, ALLOW) == 0.0


def test_wrong_owner_url_fails_as_unverifiable() -> None:
    outcomes = [_outcome("JanBot.", "See https://github.com/attacker/janbot")]

    assert public_references_metric(outcomes, ALLOW) == 0.0


def test_expected_url_missing_fails_as_incomplete() -> None:
    outcomes = [_outcome("JanBot is https://github.com/jstavel/janbot.", "JanBot is a project.")]

    assert public_references_metric(outcomes, ALLOW) == 0.0


def test_no_urls_involved_passes() -> None:
    outcomes = [_outcome("A philosophy answer with no links.", "Spec-first, no links.")]

    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_error_outcome_with_no_expected_url_passes() -> None:
    outcomes = [_outcome("no link", None)]

    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_error_outcome_with_expected_url_fails_as_incomplete() -> None:
    outcomes = [_outcome("https://github.com/jstavel/janbot", None)]

    assert public_references_metric(outcomes, ALLOW) == 0.0


def test_bare_and_scheme_forms_are_the_same_reference() -> None:
    outcomes = [
        _outcome("github.com/jstavel/janbot", "https://www.github.com/jstavel/janbot/")
    ]

    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_coarser_expected_reference_is_satisfied_by_full_url() -> None:
    outcomes = [_outcome("live at bazar-cd.cz", "https://www.bazar-cd.cz/")]

    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_bare_host_without_path_is_not_a_reference() -> None:
    outcomes = [_outcome("No links.", "We evaluated WebDriver.io and Seznam.cz.")]

    assert extract_urls("We evaluated WebDriver.io and Seznam.cz.") == []
    assert public_references_metric(outcomes, ALLOW) == 1.0


def test_metric_averages_pass_and_fail() -> None:
    outcomes = [
        _outcome("https://github.com/jstavel/janbot", "https://github.com/jstavel/janbot"),
        _outcome("no url", "https://github.com/jstavel/evil"),
    ]

    assert public_references_metric(outcomes, ALLOW) == 0.5


def test_empty_outcomes_is_zero() -> None:
    assert public_references_metric([], ALLOW) == 0.0


def test_extract_urls_strips_trailing_punctuation_and_dedupes() -> None:
    text = "See (https://github.com/jstavel/janbot), and https://github.com/jstavel/janbot again."

    assert extract_urls(text) == ["github.com/jstavel/janbot"]


def test_extract_urls_splits_urls_glued_to_text() -> None:
    text = "Repos: https://github.com/jstavel/janbot,and https://github.com/jstavel/krakatoa;more"

    assert extract_urls(text) == [
        "github.com/jstavel/janbot",
        "github.com/jstavel/krakatoa",
    ]


def test_extract_urls_ignores_library_name_prose() -> None:
    text = "The libraries were test-clj.testng, verify-testng, bugzilla-testng, gnome.ldtp."

    assert extract_urls(text) == []


def test_extract_urls_keeps_a_listed_pathless_host() -> None:
    assert extract_urls("live bazar-cd.cz", ALLOW) == ["bazar-cd.cz"]
    assert extract_urls("live bazar-cd.cz") == []


def test_normalize_reference_strips_scheme_www_and_punctuation() -> None:
    assert normalize_reference("https://www.Bazar-CD.cz/") == "bazar-cd.cz"


def test_normalize_reference_strips_git_fragment_and_query() -> None:
    assert normalize_reference("https://github.com/jstavel/janbot.git") == "github.com/jstavel/janbot"
    assert normalize_reference("https://github.com/jstavel/janbot.git/") == "github.com/jstavel/janbot"
    assert normalize_reference("https://github.com/x/repo#readme") == "github.com/x/repo"
    assert normalize_reference("https://github.com/x/repo?tab=readme") == "github.com/x/repo"


def test_is_public_reference_accepts_listed_deeper_and_dedicated() -> None:
    assert is_public_reference("https://github.com/jstavel/janbot", ALLOW)
    assert is_public_reference("github.com/jstavel/janbot/tree/main", ALLOW)
    assert is_public_reference("brailcom.cz", ALLOW)
    assert is_public_reference("https://www.bazar-cd.cz/kniha", ALLOW)
    assert not is_public_reference("github.com/attacker/janbot", ALLOW)


def test_is_public_reference_rejects_a_shared_pathless_host() -> None:
    assert not is_public_reference("https://github.com", ALLOW)
    assert not is_public_reference("github.com", ALLOW)


def test_public_references_metric_is_registered() -> None:
    assert "public_references" in registered_metrics()


def test_failures_are_named_per_item() -> None:
    outcomes = [
        _outcome("JanBot is https://github.com/jstavel/janbot.", "JanBot is a project."),
        _outcome("No link here.", "Read https://github.com/jstavel/evil"),
    ]

    failures = public_reference_failures(outcomes, ALLOW)

    assert len(failures) == 2
    assert "missing expected reference(s): github.com/jstavel/janbot" in failures[0]
    assert "unverifiable reference(s): github.com/jstavel/evil" in failures[1]
    assert all(failure.startswith("q — ") for failure in failures)


def test_committed_allow_list_matches_a_fresh_corpus_harvest() -> None:
    harvested = frozenset(normalize_reference(url) for url in harvest_public_urls())
    committed = load_public_urls()

    assert harvested == committed
    assert committed


def test_committed_allow_list_holds_the_real_owners() -> None:
    committed = load_public_urls()

    assert "github.com/jstavel/janbot" in committed
    assert "github.com/edeposit/edeposit.amqp.pdfbox" in committed
    assert "github.com/redhatqe/rhsm-cockpit-qe" in committed
    assert "brailcom.cz/projects" in committed


def test_missing_allow_list_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"

    with pytest.raises(FileNotFoundError) as excinfo:
        load_public_urls(missing)

    assert str(missing) in str(excinfo.value)


def test_malformed_allow_list_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"urls": [""]}), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_public_urls(path)

    assert str(path) in str(excinfo.value)


def test_committed_allow_list_is_a_curated_reference_list() -> None:
    committed = load_public_urls()

    assert normalize_reference("https://github.com/jstavel/janbot") in committed
    assert "inbox.org" not in committed
    assert "transcribe-oldest.sh" not in committed
    assert "amqp.pdfbox" not in committed
    assert "gnome.ldtp" not in committed
    assert "gitlab.cee.redhat.com/rhsm-qe/rhsm-scenarios.git" not in committed
    assert DEFAULT_ALLOW_LIST_PATH.exists()


def test_shared_host_is_never_dedicated_even_as_a_single_entry() -> None:
    # A shared code host stays non-dedicated whatever the list size, so a small
    # corpus cannot make an invented path under it verify.
    single = ["https://github.com/jstavel/janbot"]

    assert is_public_reference("https://github.com/jstavel/janbot", single)
    assert not is_public_reference("https://github.com", single)
    assert not is_public_reference("https://github.com/someoneelse/other", single)


def test_dedicated_host_covers_its_own_paths_but_not_a_lookalike() -> None:
    single = ["https://www.bazar-cd.cz"]

    assert is_public_reference("https://www.bazar-cd.cz/kniha", single)
    assert not is_public_reference("https://www.bazar-cd.cz.evil.example/kniha", single)
