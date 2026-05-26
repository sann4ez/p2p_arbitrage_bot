import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.migrations import add_p2p_filter_columns


if __name__ == "__main__":
    asyncio.run(add_p2p_filter_columns())
