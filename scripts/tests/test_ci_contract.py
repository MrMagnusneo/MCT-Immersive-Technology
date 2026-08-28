from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CiContractTest(unittest.TestCase):
    def test_ci_runs_datagen_and_dedicated_server_smoke(self):
        workflow = (ROOT / ".github/workflows/neoforge-1.21.1-build.yml").read_text()
        self.assertIn("./gradlew runData", workflow)
        self.assertIn("scripts/ci/server_smoke.sh", workflow)
        self.assertIn("scripts/verify_jar.py", workflow)
        self.assertGreaterEqual(workflow.count("content_manifest.py --check"), 2)
        self.assertNotIn("if: always()", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("cmp version.properties", workflow)

        smoke = ROOT / "scripts/ci/server_smoke.sh"
        self.assertTrue(smoke.is_file())
        script = smoke.read_text()
        self.assertIn("./gradlew runServer", script)
        self.assertIn("Done (", script)
        self.assertIn("printf 'stop\\n'", script)
        self.assertIn("server_exit", script)
        self.assertIn("post-ready", script)

    def test_prepare_tasks_are_configuration_cache_safe(self):
        build_script = (ROOT / "build.gradle").read_text()
        self.assertNotIn(
            "doFirst {\n        layout.buildDirectory.dir('classes/java/gametest')",
            build_script,
        )
        self.assertNotIn(
            "doFirst {\n        layout.buildDirectory.dir('classes/java/datagen')",
            build_script,
        )

    def test_client_only_wayfix_is_not_on_the_server_classpath(self):
        build_script = (ROOT / "build.gradle").read_text()
        self.assertIn(
            'clientRuntimeOnly "curse.maven:${version_wayfix_curse}"',
            build_script,
        )
        self.assertNotIn(
            'runtimeOnly "curse.maven:${version_wayfix_curse}"',
            build_script,
        )
        self.assertIn(
            "getAdditionalRuntimeClasspathConfiguration().extendsFrom(configurations.maybeCreate('clientRuntimeOnly'))",
            build_script,
        )

    def test_normal_builds_do_not_mutate_the_committed_version(self):
        build_script = (ROOT / "build.gradle").read_text()
        self.assertIn('def newVersion = "${baseVersion}-b${currentBuild}-${stage}"', build_script)
        self.assertNotRegex(build_script, r"(?m)^\s*(?:processResources|jar|datagenJar|sourcesJar|build)\.dependsOn bumpVersion$")

    def test_server_run_accepts_a_graceful_stop_command(self):
        build_script = (ROOT / "build.gradle").read_text()
        self.assertIn("tasks.named('runServer').configure", build_script)
        self.assertIn("standardInput = System.in", build_script)


if __name__ == "__main__":
    unittest.main()
