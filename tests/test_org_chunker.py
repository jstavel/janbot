"""Full org subtree chunker tests.

One chunk is expected per non-root node at any depth, plus one for the file root
when that root carries a PROPERTIES drawer or text of its own; each chunk carries
the heading, tags, PROPERTIES, body/LOGBOOK and descendant text, with a full
heading-path breadcrumb and a per-file unique id.
"""

from __future__ import annotations

from pathlib import Path

from janbot.ingest import read_org_file


def _chunks(tmp_path: Path, text: str):
    source = tmp_path / "sample.org"
    source.write_text(text)
    return read_org_file(source)


def test_nested_chunk_has_breadcrumb_properties_tags_and_child(tmp_path: Path) -> None:
    chunks = _chunks(
        tmp_path,
        "* Parent\n** Child :focus:\n"
        ":PROPERTIES:\n:KEY: value\n:END:\n"
        "Child body text.\n"
        "*** Grandchild\nGrandchild body text.\n",
    )

    child = next(chunk for chunk in chunks if chunk.breadcrumb == "Parent > Child")
    assert ":focus:" in child.text
    assert "value" in child.text
    assert "Child body text." in child.text
    assert "Grandchild" in child.text
    assert "Grandchild body text." in child.text


def test_every_level_produces_one_chunk(tmp_path: Path) -> None:
    chunks = _chunks(
        tmp_path,
        "* One\n** Two\n*** Three\nDeep body.\n",
    )

    assert len(chunks) == 3
    assert {chunk.breadcrumb for chunk in chunks} == {"One", "One > Two", "One > Two > Three"}


def test_duplicate_sibling_headings_get_unique_ids(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* Notes\nFirst.\n* Notes\nSecond.\n")

    assert len(chunks) == 2
    assert {chunk.breadcrumb for chunk in chunks} == {"Notes"}
    assert len({chunk.id for chunk in chunks}) == 2


def test_identical_sibling_subtrees_get_distinct_ids(tmp_path: Path) -> None:
    """Exact-duplicate siblings (same heading and body) still get distinct ids."""
    chunks = _chunks(tmp_path, "* Notes\nSame body.\n* Notes\nSame body.\n")

    assert len(chunks) == 2
    assert len({chunk.id for chunk in chunks}) == 2


def test_empty_node_still_yields_heading_text(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* Empty\n* Full\nBody.\n")

    empty = next(chunk for chunk in chunks if chunk.breadcrumb == "Empty")
    assert empty.text == "Empty"


def test_properties_and_logbook_are_retained(tmp_path: Path) -> None:
    chunks = _chunks(
        tmp_path,
        "* Entry\n"
        ":PROPERTIES:\n:ID: abc-123\n:END:\n"
        ":LOGBOOK:\nCLOCK: [2026-01-01 Thu]\n:END:\n"
        "Some body.\n",
    )

    entry = chunks[0]
    assert "abc-123" in entry.text
    assert "LOGBOOK" in entry.text
    assert "CLOCK: [2026-01-01 Thu]" in entry.text
    assert "Some body." in entry.text


def test_untitled_tagged_heading_yields_a_chunk(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* :work:\nBody.\n")

    assert len(chunks) == 1
    assert ":work:" in chunks[0].text


def test_descendant_inherits_parent_tag(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* Parent :work:\n** Child\nKid.\n")

    child = next(chunk for chunk in chunks if chunk.breadcrumb == "Parent > Child")
    assert ":work:" in child.text


def test_ancestor_chunk_contains_descendant_text(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* Parent\n** Child\nChild only text.\n")

    parent = next(chunk for chunk in chunks if chunk.breadcrumb == "Parent")
    assert "Child only text." in parent.text


def test_file_root_chunk_carries_drawer_and_lede(tmp_path: Path) -> None:
    """The approved :SYNOPSIS: and the text above the first heading are retrievable."""
    chunks = _chunks(
        tmp_path,
        ":PROPERTIES:\n"
        ":TITLE: Sample object\n"
        ":SYNOPSIS: A one-sentence summary of the whole document.\n"
        ":END:\n"
        "\n"
        "# Sample object — the human title line\n"
        "\n"
        "A lede paragraph that sits above the first heading.\n"
        "\n"
        "* Section\nBody.\n",
    )

    root_chunk = next(chunk for chunk in chunks if chunk.breadcrumb == "(file)")
    assert root_chunk is chunks[0]
    assert ":SYNOPSIS: A one-sentence summary of the whole document." in root_chunk.text
    assert "A lede paragraph that sits above the first heading." in root_chunk.text
    assert {chunk.breadcrumb for chunk in chunks} == {"(file)", "Section"}


def test_keyword_only_root_yields_no_root_chunk(tmp_path: Path) -> None:
    """Org keywords are metadata: they neither create a root chunk nor appear in one."""
    chunks = _chunks(tmp_path, "#+TITLE: Public Profile\n\n* About\nBody.\n")

    assert [chunk.breadcrumb for chunk in chunks] == ["About"]
    assert all("#+TITLE" not in chunk.text for chunk in chunks)


def test_root_chunk_excludes_keyword_lines(tmp_path: Path) -> None:
    chunks = _chunks(
        tmp_path,
        "#+TITLE: Sample\n"
        ":PROPERTIES:\n:SYNOPSIS: Summary.\n:END:\n"
        "Lede text.\n"
        "* Section\nBody.\n",
    )

    root_chunk = next(chunk for chunk in chunks if chunk.breadcrumb == "(file)")
    assert "#+TITLE" not in root_chunk.text
    assert "Lede text." in root_chunk.text


def test_root_chunk_absent_without_drawer_or_text(tmp_path: Path) -> None:
    chunks = _chunks(tmp_path, "* Only heading\nBody.\n")

    assert [chunk.breadcrumb for chunk in chunks] == ["Only heading"]
