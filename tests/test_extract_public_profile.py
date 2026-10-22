"""Tests for the deterministic public-profile extract procedure.

Covers the mechanical rows of the re-baseline round's I/O & edge-case matrix:
determinism, the Czech guard, injected source pins, orphan detection and the
MANIFEST contract. The operational rows (gate freeze, reference, cache, plan,
cold start) are covered by their own commands and records, not here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "extract_public_profile.py"

VIEW = """\
:PROPERTIES:
:ID:       view-work-profile
:TITLE:    Work Profile
:END:

# Work Profile View

** Thesis map

*** A thesis
- Claim: a claim.
- Evidence: [[id:20260101-alpha][alpha label]] · [[id:20260102-beta]]

Statuses are honest by design.

** Public proof map

Public references:

- Alpha — https://example.com/alpha — [[alpharepo]] org

Everything else in this view has no public reference.

** Way of working

- [[id:20260101-alpha][Alpha]]
"""

ALPHA = """\
:PROPERTIES:
:ID:       20260101-alpha
:TITLE:    Alpha — public proof
:DOMAIN:   way-of-working
:SYNOPSIS: An English object with no Czech letters.
:END:

# Alpha

Body of alpha.
"""

BETA = """\
:PROPERTIES:
:ID:       20260102-beta
:TITLE:    Beta — Czech object
:DOMAIN:   attitudes
:SYNOPSIS: Tohle je český objekt s diakritikou.
:END:

# Beta

Tělo objektu.
"""

TRANSLATION = """\
:PROPERTIES:
:ID:       20260102-beta
:TITLE:    Beta — translated
:DOMAIN:   attitudes
:SYNOPSIS: This is a Czech object with an English translation.
:SOURCE-ID: @@SOURCE-ID@@
:SOURCE-SHA256: @@SOURCE-SHA256@@
:END:

# Beta

The body, translated.
"""


@pytest.fixture()
def extract_module():
    spec = importlib.util.spec_from_file_location("extract_public_profile", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def org_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "org"
    view = repo / "corpus" / "views" / "work-profile" / "index.org"
    view.parent.mkdir(parents=True)
    view.write_text(VIEW, encoding="utf-8")
    for object_id, name, body in (
        ("20260101-alpha", "alpha.org", ALPHA),
        ("20260102-beta", "beta.org", BETA),
    ):
        path = repo / "corpus" / "objects" / object_id / name
        path.parent.mkdir(parents=True)
        path.write_text(body, encoding="utf-8")
    _git(repo, "init", "-q")
    commit = _commit(repo, "fixture")
    return repo, commit


@pytest.fixture()
def translations(tmp_path: Path, org_repo: tuple[Path, str]) -> Path:
    root = tmp_path / "extract_translations"
    root.mkdir()
    (root / "beta.org").write_text(TRANSLATION, encoding="utf-8")
    return root


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    return tmp_path / "public_profile_org"


def test_emission_is_deterministic_and_check_is_byte_green(
    extract_module, org_repo, translations, target
):
    repo, commit = org_repo
    files, notes = extract_module.emit(repo, commit, translations)
    assert extract_module.write(target, files) == 0
    assert extract_module.check(target, files) == 0
    assert notes == ["translation: 20260102-beta -> beta.org"]

    same, _ = extract_module.emit(repo, commit, translations)
    assert same == files

    (target / "alpha.org").write_text("tampered\n", encoding="utf-8")
    assert extract_module.check(target, files) == 1

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--org",
            str(repo),
            "--commit",
            commit,
            "--out",
            str(target),
            "--check",
        ],
        check=False,
        capture_output=True,
    )
    assert result.returncode == 1


def test_czech_title_without_translation_is_a_hard_error(
    extract_module, org_repo, tmp_path
):
    repo, commit = org_repo
    empty = tmp_path / "empty_translations"
    empty.mkdir()
    with pytest.raises(extract_module.ExtractError, match="20260102-beta"):
        extract_module.emit(repo, commit, empty)


def test_source_pins_are_injected_from_the_object_bytes(
    extract_module, org_repo, translations
):
    repo, commit = org_repo
    files, _ = extract_module.emit(repo, commit, translations)
    emitted = files["beta.org"].decode("utf-8")
    object_bytes = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:corpus/objects/20260102-beta/beta.org"],
        check=True,
        capture_output=True,
    ).stdout
    expected = hashlib.sha256(object_bytes).hexdigest()
    assert f":SOURCE-ID: 20260102-beta" in emitted
    assert f":SOURCE-SHA256: {expected}" in emitted
    assert "@@SOURCE" not in emitted


def test_hand_written_pin_is_refused(extract_module, org_repo, translations):
    repo, commit = org_repo
    artifact = translations / "beta.org"
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            ":SOURCE-SHA256: @@SOURCE-SHA256@@",
            ":SOURCE-SHA256: " + "0" * 64,
        ),
        encoding="utf-8",
    )
    with pytest.raises(extract_module.ExtractError, match="hand-written"):
        extract_module.emit(repo, commit, translations)


def test_orphan_in_target_fails_check(extract_module, org_repo, translations, target):
    repo, commit = org_repo
    files, _ = extract_module.emit(repo, commit, translations)
    extract_module.write(target, files)
    (target / "orphan.org").write_text("not in the view\n", encoding="utf-8")
    assert extract_module.check(target, files) == 1


def test_manifest_count_matches_reality_and_excludes_itself(
    extract_module, org_repo, translations
):
    repo, commit = org_repo
    files, _ = extract_module.emit(repo, commit, translations)
    manifest = files["MANIFEST"].decode("utf-8")
    assert f"# source: ~/org @ {commit} (corpus/)" in manifest
    assert "# files: 4 — 2 objects + public-proof-map.org + thesis-map.md" in manifest
    listed = [
        line.split("  ", 1)[1]
        for line in manifest.splitlines()
        if line and not line.startswith("#")
    ]
    assert listed == sorted(listed)
    assert "MANIFEST" not in listed
    assert len(listed) == len(files) - 1
    assert "alpha.org" in listed and "beta.org" in listed
