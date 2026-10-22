#!/usr/bin/env python3
"""Extract ``public_profile_org/`` from the org corpus view — deterministically.

The extract is a *derived* artifact: ``public_profile_org/`` is regenerated from
``~/org`` (the SSOT), never edited in place. This script is the procedure; before
it existed, the only trace of a re-extract was a commit message.

What it does, per the re-baseline round plan (2026-10-22):

1. Reads the work-profile view ``corpus/views/work-profile/index.org`` **at the
   pinned commit** and parses its ``[[id:...]]`` selection (the view decides what
   is public — a second place that decides would be a second source of truth).
2. Per selected object: byte-copy the object file at the pin (extract filename =
   the object's internal filename; ``:ID:`` preserved), or — for a Czech object —
   emit the versioned English translation from ``tools/extract_translations/``
   with the ``:SOURCE-ID:``/``:SOURCE-SHA256:`` pins **injected** (the sha256 of
   the object file at the pinned commit; the translation artifact never carries a
   hand-written pin — a pin is a mechanical function of (object, commit), and a
   hand-written one is a second place to drift).
3. Emits the two generated sections from the view: ``thesis-map.md`` (thesis
   blocks only, ``***`` → ``##``, ``[[id:X][label]]`` → label, ``[[id:X]]`` → X,
   fixed title line) and ``public-proof-map.org`` (fixed header template + the
   view's bullets with ``[[slug]]`` → "the slug" + fixed closing paragraph).
4. Emits ``MANIFEST``: the commit pin, a count line that must match reality,
   sorted per-file sha256; it does not list itself.

Czech detection is mechanical: an object's ``:TITLE:``/``:SYNOPSIS:`` is Czech
when it contains a lowercase Czech-only letter (``čďěňřšťůž``) — Czech orthography
puts diacritics on essentially every Czech sentence, and these letters do not
occur in English prose. Uppercase acronyms embedded in English text (``OSVČ``)
stay English. A Czech ``:TITLE:``/``:SYNOPSIS:`` without a translation artifact
is a **hard error** — no silent Czech in the extract.

Modes:

- ``--check`` (default): regenerate into a temp dir and require byte-equality
  with the target tree (``public_profile_org/``), file set included — an extract
  file outside the view's selection, or a selection item missing from the
  extract, is drift and fails. Any diff exits non-zero.
- ``--write``: materialize the emission into the target tree (adding, updating
  and removing files so the tree equals the emission exactly).

The pin comes from ``--commit``; without it, the pin recorded in the target
``MANIFEST`` is used (the extract declares what it was extracted from), falling
back to ``~/org`` HEAD when no MANIFEST exists.

Stdlib only, so the procedure runs anywhere the repo checks out.

Validation fixture: run with ``--check --commit 05b11a7…`` — the transforms must
reproduce the previous extract round byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ORG_DEFAULT = Path("~/org")
VIEW_PATH = "corpus/views/work-profile/index.org"
OBJECTS_PREFIX = "corpus/objects/"
MANIFEST_NAME = "MANIFEST"
THESIS_NAME = "thesis-map.md"
PROOF_NAME = "public-proof-map.org"
TRANSLATIONS_DEFAULT = Path(__file__).resolve().parent / "extract_translations"
CZECH_LETTERS = set("čďěňřšťůž")
SOURCE_ID_PLACEHOLDER = "@@SOURCE-ID@@"
SOURCE_SHA_PLACEHOLDER = "@@SOURCE-SHA256@@"

LINK_ID_LABEL = re.compile(r"\[\[id:([0-9A-Za-z\-]+)\]\[([^\]]*)\]\]")
LINK_ID = re.compile(r"\[\[id:([0-9A-Za-z\-]+)\]\]")
LINK_ANY = re.compile(r"\[\[id:([0-9A-Za-z\-]+)\](?:\[[^\]]*\])?\]")
LINK_SLUG = re.compile(r"\[\[([0-9A-Za-z\-]+)\]\]")

THESIS_TITLE = "# Thesis map — five claims, their evidence, and the gap that would falsify each\n"

PROOF_HEADER = """:PROPERTIES:
:ID:       20261014-public-proof-map
:TITLE:    Public proof map — what a recruiter can inspect, and what stays private
:DOMAIN:   way-of-working
:TAGS:     proof public references github allow-list recruiter verifiability
:SYNOPSIS: Maps every project to the public reference (GitHub URL or live site) that proves it, and names honestly which work has no public proof because it is internal, client-gated, or never published.
:END:

# Public proof map — what a recruiter can inspect, and what stays private

Public references a recruiter (or their AI agent) can open, by project:

"""

PROOF_CLOSING = """
Everything else has no public reference — internal, client-gated, or unpublished.
That is normal: an answer should say so rather than invent a link.
"""


class ExtractError(Exception):
    """A hard error: the emission is refused, nothing is written."""


def git_bytes(org: Path, *args: str) -> bytes:
    """Run git in the org repo and return raw stdout bytes (no newline translation)."""
    result = subprocess.run(
        ["git", "-C", str(org), *args], capture_output=True
    )
    if result.returncode != 0:
        raise ExtractError(
            f"git {' '.join(args)} failed in {org}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def resolve_commit(org: Path, commit: str) -> str:
    """Resolve a (possibly short) commit to the full 40-hex sha the MANIFEST pins."""
    out = git_bytes(org, "rev-parse", "--verify", f"{commit}^{{commit}}")
    sha = out.decode("utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ExtractError(f"{commit!r} did not resolve to a commit sha: {sha!r}")
    return sha


def view_text_at(org: Path, commit: str) -> str:
    return git_bytes(org, "show", f"{commit}:{VIEW_PATH}").decode("utf-8")


def selection(view: str) -> list[str]:
    """The view's ``[[id:...]]`` selection, deduplicated in first-appearance order.

    Both link shapes count: ``[[id:X]]`` and ``[[id:X][label]]``.
    """
    return list(dict.fromkeys(LINK_ANY.findall(view)))


def org_section(text: str, title: str) -> str:
    """The body of the ``** <title>`` section, without its heading, leading blanks stripped."""
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("** ") and line[3:].strip() == title:
            start = i + 1
            break
    if start is None:
        raise ExtractError(f"view has no '** {title}' section")
    end = next(
        (j for j in range(start, len(lines)) if lines[j].startswith("** ")),
        len(lines),
    )
    body = "\n".join(lines[start:end])
    return body.lstrip("\n")


def transform_links(text: str) -> str:
    text = LINK_ID_LABEL.sub(r"\2", text)
    text = LINK_ID.sub(r"\1", text)
    return text


def emit_thesis_map(view: str) -> bytes:
    """Thesis blocks only: the frame paragraph + the ``***`` blocks, trailing prose dropped."""
    body = org_section(view, "Thesis map")
    blocks = re.findall(r"^\*\*\* .*$", body, re.M)
    if not blocks:
        raise ExtractError("the Thesis map section has no '***' thesis blocks")
    last = body.rfind(blocks[-1])
    tail = body[last:]
    blank = re.search(r"\n\n", tail)
    body = body[: last + blank.start()] if blank else body
    body = transform_links(body)
    body = re.sub(r"^\*\*\* ", "## ", body, flags=re.M)
    return (THESIS_TITLE + "\n" + body + "\n").encode("utf-8")


def emit_proof_map(view: str) -> bytes:
    """Fixed header template + the view's bullets (``[[slug]]`` → "the slug") + fixed closing."""
    body = org_section(view, "Public proof map")
    bullets = [
        LINK_SLUG.sub(r"the \1", line)
        for line in body.split("\n")
        if line.startswith("- ")
    ]
    if not bullets:
        raise ExtractError("the Public proof map section has no bullets")
    return (PROOF_HEADER + "\n".join(bullets) + "\n" + PROOF_CLOSING).encode("utf-8")


def parse_drawer(text: str) -> dict[str, str]:
    """Top-level ``:KEY: value`` drawer properties; indented continuation lines append."""
    lines = text.split("\n")
    end = next((i for i, l in enumerate(lines) if l.strip() == ":END:"), None)
    if end is None:
        raise ExtractError("object has no :PROPERTIES:/:END: drawer")
    properties: dict[str, str] = {}
    key = None
    for line in lines[:end]:
        match = re.match(r"^:([A-Z0-9-]+):\s?(.*)$", line)
        if match:
            key = match.group(1)
            properties[key] = match.group(2).strip()
        elif key is not None and line.startswith((" ", "\t")) and line.strip():
            properties[key] += " " + line.strip()
    return properties


def is_czech(properties: dict[str, str]) -> bool:
    """A Czech ``:TITLE:``/``:SYNOPSIS:`` — lowercase Czech-only diacritics present."""
    probe = properties.get("TITLE", "") + "\n" + properties.get("SYNOPSIS", "")
    return any(char in CZECH_LETTERS for char in probe)


def object_file_at(org: Path, commit: str, object_id: str) -> tuple[str, bytes]:
    """The object's single ``.org`` file (internal filename, bytes) at the pinned commit."""
    listing = git_bytes(
        org, "ls-tree", "--name-only", f"{commit}:{OBJECTS_PREFIX}{object_id}"
    ).decode("utf-8").split()
    names = [name.split("/")[-1] for name in listing if name.endswith(".org")]
    if len(names) != 1:
        raise ExtractError(
            f"object {object_id} must contain exactly one .org file at {commit[:7]}; "
            f"found {listing!r}"
        )
    name = names[0]
    data = git_bytes(org, "show", f"{commit}:{OBJECTS_PREFIX}{object_id}/{name}")
    return name, data


def load_translation(
    translations: Path, name: str, object_id: str, object_sha256: str
) -> bytes:
    """The versioned English translation with the source pins injected.

    The artifact carries placeholders, never a hand-written pin: the sha256 is a
    mechanical function of (object file, pinned commit) and is injected here.
    """
    path = translations / name
    if not path.is_file():
        raise ExtractError(
            f"object {object_id} has a Czech :TITLE:/:SYNOPSIS: but no translation "
            f"artifact at {path} — no silent Czech in the extract"
        )
    text = path.read_bytes().decode("utf-8")
    properties = parse_drawer(text)
    recorded = properties.get("ID")
    if recorded != object_id:
        raise ExtractError(
            f"translation artifact {path} carries :ID: {recorded!r}, "
            f"expected the object's {object_id!r} — wrong object or drift"
        )
    for key in ("SOURCE-ID", "SOURCE-SHA256"):
        value = properties.get(key)
        if value is not None and value not in (
            SOURCE_ID_PLACEHOLDER,
            SOURCE_SHA_PLACEHOLDER,
        ):
            raise ExtractError(
                f"translation artifact {path} carries a hand-written :{key}: "
                f"({value!r}) — pins are injected, never hand-written"
            )
    if text.count(SOURCE_ID_PLACEHOLDER) != 1 or text.count(SOURCE_SHA_PLACEHOLDER) != 1:
        raise ExtractError(
            f"translation artifact {path} must carry exactly one "
            f"{SOURCE_ID_PLACEHOLDER} and one {SOURCE_SHA_PLACEHOLDER} placeholder"
        )
    text = text.replace(SOURCE_ID_PLACEHOLDER, object_id)
    text = text.replace(SOURCE_SHA_PLACEHOLDER, object_sha256)
    return text.encode("utf-8")


def emit(
    org: Path, commit: str, translations: Path
) -> tuple[dict[str, bytes], list[str]]:
    """The full extract emission: {extract filename: bytes} + the note log."""
    view = view_text_at(org, commit)
    notes: list[str] = []
    files: dict[str, bytes] = {}
    for object_id in selection(view):
        name, data = object_file_at(org, commit, object_id)
        if name in files:
            raise ExtractError(
                f"extract filename collision: {name!r} is the internal filename of "
                f"more than one selected object"
            )
        properties = parse_drawer(data.decode("utf-8"))
        if is_czech(properties):
            files[name] = load_translation(
                translations, name, object_id, hashlib.sha256(data).hexdigest()
            )
            notes.append(f"translation: {object_id} -> {name}")
        else:
            files[name] = data
    files[THESIS_NAME] = emit_thesis_map(view)
    files[PROOF_NAME] = emit_proof_map(view)

    manifest_lines = [
        "# public_profile_org extract manifest",
        f"# source: ~/org @ {commit} (corpus/)",
        f"# files: {len(files)} — {len(files) - 2} objects + {PROOF_NAME} + {THESIS_NAME}",
        "# format: sha256sum, sorted by filename; MANIFEST does not list itself",
    ]
    for name in sorted(files):
        digest = hashlib.sha256(files[name]).hexdigest()
        manifest_lines.append(f"{digest}  {name}")
    files[MANIFEST_NAME] = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    return files, notes


def read_target_tree(target: Path) -> dict[str, bytes]:
    tree: dict[str, bytes] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            tree[str(path.relative_to(target))] = path.read_bytes()
    return tree


def diff_report(emission: dict[str, bytes], tree: dict[str, bytes]) -> list[str]:
    report: list[str] = []
    for name in sorted(set(emission) - set(tree)):
        report.append(f"missing from target: {name}")
    for name in sorted(set(tree) - set(emission)):
        report.append(f"orphan in target (not in the view's selection): {name}")
    for name in sorted(set(emission) & set(tree)):
        if emission[name] != tree[name]:
            report.append(f"differs: {name}")
    return report


def check(
    target: Path, emission: dict[str, bytes]
) -> int:
    tree = read_target_tree(target)
    differences = diff_report(emission, tree)
    if differences:
        for line in differences:
            print(f"extract-check: {line}")
        print(
            f"extract-check: FAIL — {len(differences)} difference(s) between the "
            f"emission and {target}"
        )
        return 1
    print(
        f"extract-check: OK — {len(emission)} files byte-equal between the "
        f"emission and {target}"
    )
    return 0


def write(target: Path, emission: dict[str, bytes]) -> int:
    target.mkdir(parents=True, exist_ok=True)
    tree = read_target_tree(target)
    for name in sorted(set(tree) - set(emission)):
        if not (name == MANIFEST_NAME or name.endswith((".org", ".md"))):
            raise ExtractError(
                f"refusing to remove {name!r} from {target}: not an extract file"
            )
        (target / name).unlink()
    for name, data in sorted(emission.items()):
        out = target / name
        existed = out.is_file()
        if existed and out.read_bytes() == data:
            continue
        out.write_bytes(data)
        print(f"extract-write: {'updated' if existed else 'added'} {name}")
    print(f"extract-write: {target} now equals the emission ({len(emission)} files)")
    return 0


def pin_from_manifest(target: Path) -> str | None:
    manifest = target / MANIFEST_NAME
    if not manifest.is_file():
        return None
    match = re.search(
        r"^# source: ~/org @ ([0-9a-f]{40}) \(corpus/\)$",
        manifest.read_text(encoding="utf-8"),
        re.M,
    )
    return match.group(1) if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools/extract_public_profile.py",
        description="Regenerate public_profile_org/ from the org corpus view.",
    )
    parser.add_argument(
        "--org",
        type=Path,
        default=ORG_DEFAULT,
        help=f"the org SSOT repo (default: {ORG_DEFAULT})",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help=(
            "the ~/org commit the extract pins (default: the pin recorded in the "
            "target MANIFEST, else ~/org HEAD)"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "public_profile_org",
        help="the extract tree to check against or write (default: public_profile_org)",
    )
    parser.add_argument(
        "--translations",
        type=Path,
        default=TRANSLATIONS_DEFAULT,
        help=f"versioned English translations (default: {TRANSLATIONS_DEFAULT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the emission byte-equals --out (the default; kept explicit)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="materialize the emission into --out (default: check only)",
    )
    args = parser.parse_args(argv)

    org = args.org.expanduser()
    if not org.is_dir():
        print(f"extract: org repo not found: {org}", file=sys.stderr)
        return 2
    target = args.out

    commit = args.commit
    if commit is None:
        commit = pin_from_manifest(target)
    if commit is None:
        head = subprocess.run(
            ["git", "-C", str(org), "rev-parse", "HEAD"], capture_output=True
        )
        if head.returncode != 0:
            print("extract: no --commit, no MANIFEST pin, no ~/org HEAD", file=sys.stderr)
            return 2
        commit = head.stdout.decode("utf-8").strip()
        print(f"extract: no pin recorded; using ~/org HEAD {commit[:7]}")

    try:
        full = resolve_commit(org, commit)
        files, notes = emit(org, full, args.translations)
    except ExtractError as exc:
        print(f"extract: {exc}", file=sys.stderr)
        return 1

    for note in notes:
        print(f"extract: {note}")
    print(
        f"extract: pin {full[:7]} — {len(files) - 3} objects + {PROOF_NAME} + "
        f"{THESIS_NAME} + {MANIFEST_NAME}"
    )
    if args.write:
        try:
            return write(target, files)
        except ExtractError as exc:
            print(f"extract: {exc}", file=sys.stderr)
            return 1
    return check(target, files)


if __name__ == "__main__":
    raise SystemExit(main())
