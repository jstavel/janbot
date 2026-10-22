"""Daily served/declined usage counters over the guardrail Firestore store.

One document per UTC day — ``usage_<YYYY-MM-DD>`` in the shared
``janbot_guardrails`` collection — with two fields, ``served`` and ``declined``,
each an atomic ``firestore.Increment`` applied by a set-merge, so concurrent
requests never lose a count and the reader needs no transaction.

Fail-open: a counter error is logged as one closed-set JSON line and never
denies a request. The counter is called with nothing but the outcome class —
it records no IP and no question or answer text.

The read side is operator-side only (no new public surface):

.. code-block:: sh

   uv run python -m janbot.guardrails.usage --date 2026-10-22
   uv run python -m janbot.guardrails.usage --days 7

The CLI reads the same store over Application Default Credentials and fails
with a clear message when ``JANBOT_FIRESTORE_PROJECT`` is unset or no ADC is
available; it never touches the service. ``google-cloud-firestore`` is imported
lazily, so the module stays importable without it.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from janbot.config import Config, load_config
from janbot.guardrails.limits import COLLECTION

USAGE_DOC_PREFIX = "usage_"
SERVED_FIELD = "served"
DECLINED_FIELD = "declined"

logger = logging.getLogger("janbot.usage")


def usage_doc_id(day: str) -> str:
    return f"{USAGE_DOC_PREFIX}{day}"


class UsageCounter:
    """The fail-open daily counter: ``served``/``declined`` per UTC date."""

    def __init__(
        self, client: Any, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))
        self._collection = client.collection(COLLECTION)

    @classmethod
    def from_config(cls, config: Any) -> UsageCounter | None:
        """Build from config, or return ``None`` when no Firestore project is set.

        Same store conditions as :meth:`FirestoreLimits.from_config`: production
        mode already refuses to start without a project; outside it, an unset
        project means the local/eval run has no shared store and nothing counts.
        """
        if not config.firestore_project:
            return None
        from google.cloud import firestore

        client = firestore.Client(
            project=config.firestore_project, database=config.firestore_database
        )
        return cls(client)

    def record_served(self) -> None:
        """Count one answered reply (live or cache hit). Never raises."""
        self._increment(SERVED_FIELD)

    def record_declined(self) -> None:
        """Count one insufficient reply or route-level guardrail refusal."""
        self._increment(DECLINED_FIELD)

    def _increment(self, field: str) -> None:
        try:
            from google.cloud import firestore

            now = self._clock()
            ref = self._collection.document(usage_doc_id(now.date().isoformat()))
            ref.set(
                {
                    field: firestore.Increment(1),
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
        except Exception:
            # Fail-open: visibility is never a denial — the import, the clock,
            # the document resolution and the write all sit inside this try.
            # One closed-set line; no text, no IP, no reason detail.
            logger.warning(
                json.dumps(
                    {"event": "usage-counter-error", "counter": field},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )


def read_day(client: Any, day: str) -> tuple[int, int]:
    """Read one UTC day's ``(served, declined)`` totals; a missing day is 0/0."""
    snapshot = client.collection(COLLECTION).document(usage_doc_id(day)).get()
    if not snapshot.exists:
        return 0, 0
    served = int(snapshot.get(SERVED_FIELD) or 0)
    declined = int(snapshot.get(DECLINED_FIELD) or 0)
    return served, declined


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m janbot.guardrails.usage",
        description="Print daily served/declined totals from the guardrail store.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--date", metavar="YYYY-MM-DD", help="read one UTC date's totals"
    )
    group.add_argument(
        "--days",
        type=int,
        metavar="N",
        help="read the last N UTC days, ending today (oldest first)",
    )
    return parser.parse_args(argv)


def _days_to_read(args: argparse.Namespace) -> list[str]:
    today = datetime.now(UTC).date()
    if args.date is not None:
        try:
            day = date.fromisoformat(args.date)
        except ValueError as exc:
            raise ValueError(f"--date {args.date!r} is not a YYYY-MM-DD date") from exc
        return [day.isoformat()]
    if args.days < 1:
        raise ValueError(f"--days {args.days!r} must be a positive integer")
    return [
        (today - timedelta(days=offset)).isoformat() for offset in range(args.days - 1, -1, -1)
    ]


def main(argv: Sequence[str] | None = None, *, config: Config | None = None) -> int:
    """Read and print the totals. Returns a process exit code, never raises."""
    args = parse_args(argv)
    try:
        days = _days_to_read(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    resolved = config if config is not None else load_config()
    if not resolved.firestore_project:
        print(
            "error: JANBOT_FIRESTORE_PROJECT is unset; there is no guardrail "
            "store to read (set it to the deployed project id)",
            file=sys.stderr,
        )
        return 2

    try:
        from google.cloud import firestore

        client = firestore.Client(
            project=resolved.firestore_project, database=resolved.firestore_database
        )
        rows = [(day, *read_day(client, day)) for day in days]
    except Exception as exc:
        print(f"error: the usage store could not be read: {exc}", file=sys.stderr)
        return 1

    print(f"{'date':<10}  {'served':>6}  {'declined':>8}")
    for day, served, declined in rows:
        print(f"{day:<10}  {served:>6}  {declined:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
