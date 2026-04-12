from __future__ import annotations

import asyncio

from src.crawler.collector import run_collection


def main() -> None:
    asyncio.run(run_collection())


if __name__ == "__main__":
    main()