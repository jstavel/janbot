"""Public-reference allow-list for the eval harness.

The owner's rule: an answer surfaces the full public URL when a project has one,
and never invents one. This module is the single source of truth for *which*
public URLs are real. The allow-list is generated from the public corpus — every
``:PUBLIC:`` drawer, every explicit reference link (an org ``[[url]]`` link or a
reference-list bullet that leads with the URL) and the generated proof map —
into ``eval/public_urls.yaml``, so it can never drift from the corpus by hand.
Prose mentions, filenames, internal git remotes and malformed ``:PUBLIC:`` lines
are not references and stay out of the list.

References are compared in a normalized form (scheme and ``www.`` stripped,
trailing ``.git``/``#fragment``/``?query``/punctuation removed, host and path
lower-cased, trailing slash dropped), so a full URL and the bare
``github.com/jstavel/janbot`` the golden answers use resolve to the same key.

On-list is deliberately asymmetric (see ``is_public_reference``): a candidate is
valid when it equals a listed entry, is a *deeper path under* a listed entry
(``github.com/jstavel/janbot/tree/main`` under ``github.com/jstavel/janbot``), or
is a listed *pathless* host (``brailcom.cz`` for ``brailcom.cz/projects``). A
pathless candidate never verifies as a prefix of a listed path — ``github.com``
is **not** a valid reference for every ``github.com/...`` repo, because that host
is shared by many entries rather than being a reference of its own.

This module is import-isolated: it walks ``.org`` files locally and imports
neither ``janbot.ingest`` nor ``janbot.store`` (no chromadb on the eval path).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml

from janbot.config import PROJECT_ROOT

__all__ = [
    "DEFAULT_ALLOW_LIST_PATH",
    "DEFAULT_CORPUS_ROOT",
    "extract_urls",
    "generate_allow_list",
    "harvest_public_urls",
    "is_public_reference",
    "load_public_urls",
    "missing_references",
    "normalize_reference",
]

DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "public_profile_org"
DEFAULT_ALLOW_LIST_PATH = PROJECT_ROOT / "eval" / "public_urls.yaml"

_HEADER = (
    "# Public URL allow-list for the JanBot eval harness.\n"
    "#\n"
    "# Generated from the public corpus (public_profile_org/): every :PUBLIC:\n"
    "# drawer, every explicit reference link and the public proof map. Do not\n"
    "# edit by hand; regenerate with `uv run python -m janbot.eval.public_urls`.\n"
)

_PROOF_MAP_NAME = "public-proof-map.org"

_TRAILING = ".,;:!?'\"`)]}>"

# A bare (scheme-less, non-``www.``) candidate must end in a real top-level
# domain, so prose tokens such as ``WebDriver.io``, ``test-clj.testng``,
# ``amqp.pdfbox`` or ``gnome.ldtp`` (library names) are never mistaken for URLs.
_COMMON_TLDS = frozenset(
    {
        "ai", "app", "at", "au", "be", "biz", "blog", "br", "ca", "ch", "cloud",
        "cn", "co", "com", "cz", "de", "dev", "dk", "edu", "es", "eu", "fi",
        "fr", "gd", "gov", "gr", "hk", "ie", "il", "in", "info", "int", "io",
        "it", "jp", "kr", "live", "me", "mil", "mx", "name", "net", "nl", "no",
        "nz", "one", "online", "org", "page", "pl", "pro", "pt", "run", "se",
        "sg", "sh", "shop", "site", "store", "tech", "top", "tw", "uk", "us",
        "world", "xyz", "za",
    }
)

# A URL body never contains whitespace, brackets/quotes, or the glue characters
# (``,`` ``;`` ``:``) that can abut a URL in prose.
_BODY = r"[^\s<>\[\](){}'\"|,;:]+"
_URL_RE = re.compile(
    r"(?:https?://|www\.)" + _BODY
    + r"|(?<![\w@./-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?:/" + _BODY + r")?",
    re.IGNORECASE,
)

_PUBLIC_LINE = re.compile(r"^\s*:PUBLIC:\s*(?P<value>.*)$", re.MULTILINE)
_ORG_LINK = re.compile(r"\[\[(?P<target>[^\]\[]+)")
_BULLET_LINE = re.compile(r"^\s*-\s+(?P<rest>\S.*)$", re.MULTILINE)


def normalize_reference(raw: str) -> str:
    """Return the comparison form of ``raw``.

    Strips a scheme and a leading ``www.``, a trailing ``#fragment``, ``?query``,
    ``.git``, punctuation and ``/``; lower-cases host and path.
    """
    reference = raw.strip().strip(_TRAILING)
    reference = re.sub(r"^https?://", "", reference, flags=re.IGNORECASE)
    reference = re.sub(r"^www\.", "", reference, flags=re.IGNORECASE)
    reference = reference.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    if reference.lower().endswith(".git"):
        reference = reference[:-4]
    return reference.rstrip("/").lower()


def _host_and_path(reference: str) -> tuple[str, str]:
    host, _, path = reference.partition("/")
    return host, path


def _iter_candidates(text: str) -> Iterator[str]:
    """Yield the raw URL-shaped candidates in ``text``.

    A scheme'd or ``www.`` URL always qualifies; a bare candidate must end in a
    real top-level domain so prose tokens never qualify.
    """
    for match in _URL_RE.finditer(text):
        candidate = match.group(0)
        if not candidate.lower().startswith(("http://", "https://", "www.")):
            host = candidate.split("/", 1)[0]
            if host.rsplit(".", 1)[-1].lower() not in _COMMON_TLDS:
                continue
        yield candidate


def _reference_sources(text: str, *, proof_map: bool) -> Iterator[str]:
    """Yield the raw reference candidates of one corpus file.

    The proof map is a curated reference list, so every URL it carries counts.
    Every other file contributes only from explicit reference contexts: a
    ``:PUBLIC:`` drawer, an org ``[[url]]`` link, or a bullet that leads with the
    URL. That keeps prose mentions and filenames out of the allow-list.
    """
    if proof_map:
        yield from _iter_candidates(text)
        return
    for match in _PUBLIC_LINE.finditer(text):
        yield from _iter_candidates(match.group("value"))
    for match in _ORG_LINK.finditer(text):
        yield from _iter_candidates(match.group("target"))
    for match in _BULLET_LINE.finditer(text):
        rest = match.group("rest")
        if rest.lower().startswith(("http://", "https://", "www.")):
            yield from _iter_candidates(rest)


def _listed_hosts(allow_list: Iterable[str] | None) -> frozenset[str]:
    """The set of hosts named by ``allow_list`` (used to keep bare expected hosts)."""
    if allow_list is None:
        return frozenset()
    return frozenset(_host_and_path(normalize_reference(entry))[0] for entry in allow_list)


def extract_urls(text: str, allow_list: Iterable[str] | None = None) -> list[str]:
    """Return the normalized references in ``text``, order-preserving and de-duplicated.

    A scheme'd or ``www.`` URL always counts; a bare domain counts when it carries
    a path, or when its host is named by ``allow_list`` — so an expected pathless
    reference such as ``bazar-cd.cz`` is still checked while prose tokens
    (``WebDriver.io``, ``test-clj.testng``) are ignored.
    """
    listed = _listed_hosts(allow_list)
    seen: dict[str, None] = {}
    for raw in _iter_candidates(text):
        reference = normalize_reference(raw)
        if not reference:
            continue
        host, path = _host_and_path(reference)
        has_scheme = raw.lower().startswith(("http://", "https://", "www."))
        if not has_scheme and not path and host not in listed:
            continue
        seen.setdefault(reference, None)
    return list(seen)


def _dedicated_hosts(allow_list: Iterable[str]) -> frozenset[str]:
    """Hosts named by exactly one listed entry — a project's own site, not a shared code host."""
    counts: dict[str, int] = {}
    for entry in allow_list:
        host = _host_and_path(normalize_reference(entry))[0]
        counts[host] = counts.get(host, 0) + 1
    return frozenset(host for host, count in counts.items() if count == 1)


def is_public_reference(reference: str, allow_list: Iterable[str]) -> bool:
    """Return ``True`` only when ``reference`` is a valid public URL for the corpus.

    Valid means it equals a listed entry, is a deeper path under a listed entry
    (or under a listed pathless dedicated host), or is a pathless listed host. A
    pathless candidate is never a prefix of a listed path, so ``github.com`` does
    not verify against a repo under it.
    """
    ref = normalize_reference(reference)
    if not ref:
        return False
    host, path = _host_and_path(ref)
    normalized = [normalize_reference(entry) for entry in allow_list]
    if ref in normalized:
        return True
    dedicated = _dedicated_hosts(normalized)
    if path:
        for allowed in normalized:
            allowed_host, allowed_path = _host_and_path(allowed)
            if allowed_host != host:
                continue
            if not allowed_path:
                if allowed_host in dedicated:
                    return True
                continue
            if path == allowed_path or path.startswith(allowed_path + "/"):
                return True
        return False
    return host in dedicated


def _covers(shorter: str, longer: str) -> bool:
    """Return ``True`` when ``shorter`` names the same host and at most ``longer``'s path."""
    host_s, path_s = _host_and_path(shorter)
    host_l, path_l = _host_and_path(longer)
    if host_s != host_l:
        return False
    if not path_s:
        return True
    return path_l == path_s or path_l.startswith(path_s + "/")


def missing_references(expected: Iterable[str], actual: Iterable[str]) -> list[str]:
    """Return every expected reference the actual references do not surface."""
    actual_list = list(actual)
    return [ref for ref in expected if not any(_covers(ref, seen) for seen in actual_list)]


def load_public_urls(path: str | Path = DEFAULT_ALLOW_LIST_PATH) -> frozenset[str]:
    """Load and normalize the allow-list at ``path``.

    Raises:
        FileNotFoundError: if ``path`` does not exist, naming it.
        ValueError: if the document is not a mapping with a ``urls`` list, or an
            entry is blank or non-string, naming the offending path.
    """
    allow_path = Path(path)
    if not allow_path.exists():
        raise FileNotFoundError(f"public URL allow-list not found: {allow_path}")

    document = yaml.safe_load(allow_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("urls"), list):
        raise ValueError(
            f"public URL allow-list {allow_path} must be a mapping with a 'urls' list"
        )
    references: set[str] = set()
    for entry in document["urls"]:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(
                f"public URL allow-list {allow_path} has a blank or non-string entry"
            )
        references.add(normalize_reference(entry))
    return frozenset(references)


def _iter_org_files(corpus_root: str | Path) -> Iterator[Path]:
    """Yield every ``.org`` file under ``corpus_root`` in deterministic order.

    A local walker, deliberately not ``janbot.ingest.scope``: the eval package
    must stay free of the ingestion/chromadb import chain. A missing or
    non-directory root yields nothing (never raises).
    """
    try:
        root = Path(corpus_root).resolve()
    except (OSError, RuntimeError):
        return
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.org")):
        if path.is_file():
            yield path


def harvest_public_urls(corpus_root: str | Path = DEFAULT_CORPUS_ROOT) -> list[str]:
    """Return the de-duplicated public URLs found across the corpus, sorted by key.

    Every ``.org`` file under ``corpus_root`` is scanned, so ``:PUBLIC:`` drawers,
    inline reference links and the proof map all contribute — the corpus stays
    the one source. The first spelling seen for a normalized key is kept.
    """
    originals: dict[str, str] = {}
    for path in _iter_org_files(corpus_root):
        text = path.read_text(encoding="utf-8")
        for raw in _reference_sources(text, proof_map=path.name == _PROOF_MAP_NAME):
            key = normalize_reference(raw)
            if not key:
                continue
            originals.setdefault(key, raw.strip().strip(_TRAILING).rstrip("/"))
    return [originals[key] for key in sorted(originals)]


def generate_allow_list(
    corpus_root: str | Path = DEFAULT_CORPUS_ROOT,
    path: str | Path = DEFAULT_ALLOW_LIST_PATH,
) -> list[str]:
    """Regenerate ``eval/public_urls.yaml`` from the corpus and return the URLs written."""
    urls = harvest_public_urls(corpus_root)
    body = yaml.safe_dump({"urls": urls}, sort_keys=False, default_flow_style=False)
    Path(path).write_text(_HEADER + body, encoding="utf-8")
    return urls


def main(argv: list[str] | None = None) -> int:
    """CLI: regenerate the allow-list from the corpus."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m janbot.eval.public_urls")
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS_ROOT),
        help=f"corpus root to harvest (default: {DEFAULT_CORPUS_ROOT})",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_ALLOW_LIST_PATH),
        help=f"allow-list path to write (default: {DEFAULT_ALLOW_LIST_PATH})",
    )
    args = parser.parse_args(argv)

    urls = generate_allow_list(args.corpus, args.out)
    print(f"wrote {len(urls)} public URLs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
