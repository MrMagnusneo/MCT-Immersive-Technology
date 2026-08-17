from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CiContractTest(unittest.TestCase):
    def test_ci_runs_datagen_and_dedicated_server_smoke(self):
        workflow = (ROOT / ".github/workflows/neoforge-1.21.1-build.yml").read_text()
        self.assertIn("./gradlew runData", workflow)
        self.assertIn("scripts/ci/server_smoke.sh", workflow)

        smoke = ROOT / "scripts/ci/server_smoke.sh"
        self.assertTrue(smoke.is_file())
        script = smoke.read_text()
        self.assertIn("./gradlew runServer", script)
        self.assertIn("Done (", script)


if __name__ == "__main__":
    unittest.main()
