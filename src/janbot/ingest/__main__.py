"""CLI: ``python -m janbot.ingest [--index PATH]``.

Indexes every ``.org`` file under the configured public corpus root and prints
the number of chunks stored. The corpus root always comes from configuration
(``JANBOT_CORPUS_PATH``); there is no positional override, so private notes
outside the public root can never be indexed. ``--index`` defaults to the
configured ``JANBOT_INDEX_PATH``.
"""

from __future__ import annotations

import argparse

from janbot.config import load_config
from janbot.ingest import index_corpus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janbot.ingest")
    parser.add_argument(
        "--index",
        default=None,
        help="index location (default: JANBOT_INDEX_PATH)",
    )
    args = parser.parse_args(argv)

    config = load_config()
    index_path = args.index if args.index is not None else config.index_path
    count = index_corpus(config.corpus_path, index_path)
    print(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
