import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.verify_jar import JarVerificationError, verify_jar


class VerifyJarTest(unittest.TestCase):
    def test_accepts_neoforge_jar_with_matching_class_and_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resource = root / "src/main/resources/assets/immersivetechnology/required.json"
            resource.parent.mkdir(parents=True)
            resource.write_text('{"value": 1}\n', encoding="utf-8")
            manifest = {
                "resource_paths": ["assets/immersivetechnology/required.json"],
                "resource_hashes": {"assets/immersivetechnology/required.json": "00" * 32},
                "java_sources": {"src/main/java/example/Entry.java": "00" * 32},
            }
            baseline = root / "baseline.json"
            baseline.write_text(json.dumps(manifest), encoding="utf-8")
            jar = root / "MCT-ImmersiveTechnology-1.21.1-3.0.0-b1-alpha.jar"
            metadata = '''
                modLoader = "javafml"
                modId = "immersivetechnology"
                modId = "neoforge"
                modId = "minecraft"
                modId = "immersiveengineering"
                modId = "immersiveconvergence"
                versionRange = "[1.21.1]"
                config = "mixins.immersivetechnology.json"
            '''
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/neoforge.mods.toml", metadata)
                archive.writestr("mixins.immersivetechnology.json", "{}")
                archive.writestr("example/Entry.class", b"class")
                archive.writestr("assets/immersivetechnology/required.json", '{"value":1}')

            report = verify_jar(root, baseline, jar)

            self.assertEqual(1, report["classes"])
            self.assertEqual(1, report["resources"])

    def test_rejects_jar_missing_baseline_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/main/resources/assets/immersivetechnology").mkdir(parents=True)
            resource = root / "src/main/resources/assets/immersivetechnology/required.txt"
            resource.write_text("required", encoding="utf-8")
            source = root / "src/main/java/example/Entry.java"
            source.parent.mkdir(parents=True)
            source.write_text("package example; class Entry {}", encoding="utf-8")
            manifest = {
                "resource_paths": ["assets/immersivetechnology/required.txt"],
                "resource_hashes": {
                    "assets/immersivetechnology/required.txt": "00" * 32,
                },
                "java_sources": {"src/main/java/example/Entry.java": "00" * 32},
            }
            baseline = root / "baseline.json"
            baseline.write_text(json.dumps(manifest), encoding="utf-8")
            jar = root / "MCT-ImmersiveTechnology-1.21.1-3.0.0-b1-alpha.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/neoforge.mods.toml", 'modId = "immersivetechnology"')
                archive.writestr("mixins.immersivetechnology.json", "{}")
                archive.writestr("example/Entry.class", b"class")

            with self.assertRaisesRegex(JarVerificationError, "required.txt"):
                verify_jar(root, baseline, jar)


if __name__ == "__main__":
    unittest.main()
