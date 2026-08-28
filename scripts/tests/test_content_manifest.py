import json
import tempfile
import unittest
from pathlib import Path

from scripts.content_manifest import ManifestError, collect_manifest, compare_manifests


class ContentManifestTest(unittest.TestCase):
    def test_collects_literal_registration_ids_and_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = root / "src/main/java/example/Registration.java"
            registration.parent.mkdir(parents=True)
            registration.write_text(
                '''
                class Registration {
                    Object a = new BlockEntry<>("machine_block", props, Maker::new);
                    Object b = register("tool", Maker::new);
                    Object c = FluidEntry.make("steam", 0, still, flowing, props, 0);
                    Object d = metal(new Logic(), "turbine").build();
                    Object e = registerSound("running");
                    Object f = registerArg("machine_menu", server, client);
                }
                ''',
                encoding="utf-8",
            )
            resource = root / "src/main/resources/assets/immersivetechnology/models/item/tool.json"
            resource.parent.mkdir(parents=True)
            resource.write_text("{}", encoding="utf-8")

            manifest = collect_manifest(root)

            self.assertEqual(["machine_block", "steam_fluid_block", "turbine"], manifest["blocks"])
            self.assertEqual(["steam"], manifest["fluids"])
            self.assertEqual(["turbine"], manifest["multiblocks"])
            self.assertEqual(["running"], manifest["sounds"])
            self.assertEqual(["machine_menu"], manifest["menus"])
            self.assertIn("assets/immersivetechnology/models/item/tool.json", manifest["resource_paths"])

    def test_reports_removed_content_by_category(self):
        baseline = {"blocks": ["a", "b"], "resource_paths": ["assets/x.json"]}
        current = {"blocks": ["b"], "resource_paths": []}

        differences = compare_manifests(baseline, current)

        self.assertEqual(["a"], differences["blocks"]["removed"])
        self.assertEqual(["assets/x.json"], differences["resource_paths"]["removed"])

    def test_rejects_duplicate_explicit_registrations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = root / "src/main/java/example/ModItems.java"
            registration.parent.mkdir(parents=True)
            registration.write_text(
                'register("duplicate", Maker::new); register("duplicate", Maker::new);',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ManifestError, "items:duplicate"):
                collect_manifest(root)

    def test_hashes_all_production_sources_and_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/main/java/example/Entry.java"
            source.parent.mkdir(parents=True)
            source.write_text("package example; class Entry {}\n", encoding="utf-8")
            resource = root / "src/generated/resources/data/immersivetechnology/recipes/test.json"
            resource.parent.mkdir(parents=True)
            resource.write_text('{"type":"example"}\n', encoding="utf-8")
            cache = root / "src/generated/resources/.cache/generated-hash"
            cache.parent.mkdir(parents=True)
            cache.write_text("ephemeral", encoding="utf-8")

            manifest = collect_manifest(root)

            self.assertIn("src/main/java/example/Entry.java", manifest["java_sources"])
            self.assertIn("data/immersivetechnology/recipes/test.json", manifest["resource_hashes"])
            self.assertNotIn(".cache/generated-hash", manifest["resource_hashes"])
            self.assertEqual(64, len(manifest["java_sources"]["src/main/java/example/Entry.java"]))

    def test_real_manifest_covers_extended_content_surfaces(self):
        root = Path(__file__).resolve().parents[2]
        manifest = collect_manifest(root)

        for category in (
            "config_keys",
            "creative_tabs",
            "loot_entries",
            "network_messages",
            "integrations",
            "java_sources",
            "resource_hashes",
        ):
            self.assertTrue(manifest[category], category)


if __name__ == "__main__":
    unittest.main()
