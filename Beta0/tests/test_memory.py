import tempfile
import unittest
from pathlib import Path

from memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_experience_survives_restart_and_old_history_remains(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.db"

            with MemoryStore(db) as memory:
                first_id = memory.add_experience("red box", "User said this object is a red box")
                memory.add_belief("red box", "This is a red box", 0.70, first_id)

            with MemoryStore(db) as memory:
                self.assertEqual(len(memory.experiences_for("red box")), 1)
                self.assertEqual(memory.latest_belief("red box").statement, "This is a red box")

                second_id = memory.add_experience(
                    "red box", "Later observation: object appears orange under daylight"
                )
                memory.add_belief(
                    "red box",
                    "Object may be orange rather than red",
                    0.55,
                    second_id,
                    status="uncertain",
                )

                experiences = memory.experiences_for("red box")
                beliefs = memory.belief_history("red box")

                self.assertEqual(len(experiences), 2)
                self.assertEqual(len(beliefs), 2)
                self.assertIn("red box", experiences[0].observation)
                self.assertEqual(memory.latest_belief("red box").status, "uncertain")


if __name__ == "__main__":
    unittest.main()
