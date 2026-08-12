import tempfile
import unittest
from pathlib import Path

from app import JobAgent, Profile, Store, DEMO_JOBS


class ShiftScoutTests(unittest.TestCase):
    def setUp(self):
        self.profile = Profile("Sam", "sam@example.com", "Berlin", "Python Developer", "Python, SQL, Git", "Built Flask apps", False)

    def test_agent_ranks_relevant_job_first(self):
        ranked = JobAgent().rank(self.profile, DEMO_JOBS)
        self.assertEqual(ranked[0]["title"], "Junior Python Developer")
        self.assertGreater(ranked[0]["score"], 0)

    def test_profile_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.db")
            store.save_profile(self.profile)
            self.assertEqual(store.load_profile(), self.profile)

    def test_note_contains_identity_and_job(self):
        note = JobAgent().application_note(self.profile, DEMO_JOBS[0])
        self.assertIn("Sam", note)
        self.assertIn("Junior Python Developer", note)


if __name__ == "__main__":
    unittest.main()
