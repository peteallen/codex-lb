"""Preview/apply current token prices to explicitly selected retained models.

Run from the repository root: python -m scripts.repair_cost_estimates --model gpt-6-astra
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone

from app.db.session import SessionLocal, engine
from app.modules.request_logs.cost_repair import repair_cost_estimates


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", required=True, help="Exact stored model ID; repeat as needed")
    parser.add_argument("--since", type=_utc_datetime, help="Inclusive UTC timestamp")
    parser.add_argument("--until", type=_utc_datetime, help="Exclusive UTC timestamp")
    parser.add_argument("--apply", action="store_true", help="Commit the previewed repair; back up the database first")
    args = parser.parse_args()
    try:
        async with SessionLocal() as session:
            summary = await repair_cost_estimates(
                session,
                models=args.model,
                since=args.since,
                until=args.until,
                apply=args.apply,
            )
        print(json.dumps({"applied": args.apply, **asdict(summary)}, indent=2))
        if summary.missing_cache_write_counts:
            print("Historical cache-write counts were not retained; those estimates exclude unreported write premiums.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
