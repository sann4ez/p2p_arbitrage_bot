import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.seeders.reference_data import seed_reference_data


if __name__ == "__main__":
    asyncio.run(seed_reference_data())
