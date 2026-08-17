import json
import tempfile
import unittest
from pathlib import Path

from scripts.content_manifest import collect_manifest, compare_manifests


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


if __name__ == "__main__":
    unittest.main()
