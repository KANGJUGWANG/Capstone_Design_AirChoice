from __future__ import annotations

import argparse
import asyncio
from datetime import date

from src.crawler.collector import run_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Flights 수집기")
    parser.add_argument(
        "--dep-date",
        type=str,
        default=None,
        help="테스트용 특정 출발일 (예: 2026-05-11). 생략 시 DPD 1~120 전체 실행.",
    )
    args = parser.parse_args()

    dep_date = None
    if args.dep_date:
        dep_date = date.fromisoformat(args.dep_date)

    asyncio.run(run_collection(dep_date=dep_date))


if __name__ == "__main__":
    main()
