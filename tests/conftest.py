import os
from pathlib import Path


TEST_DB_PATH = Path(__file__).resolve().parents[1] / "output" / "test_buybee.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("BUYBEE_DB_PATH", str(TEST_DB_PATH))
