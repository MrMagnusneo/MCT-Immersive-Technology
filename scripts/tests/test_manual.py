import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "immersivetechnology"
RESOURCE_ROOTS = [ROOT / "src" / "main" / "resources", ROOT / "src" / "generated" / "resources"]
MANUAL = ROOT / "src" / "main" / "resources" / "assets" / NAMESPACE / "manual"
# Special element types registered by Immersive Engineering's manual (plus this mod's own)
KNOWN_TYPES = {
    "crafting", "image", "item_display", "table", "entity", "blueprint", "bottling", "mixer", "multiblock",
    "dynamic_table", 
}


def _location(value, default_namespace="immersiveengineering"):
    return value if ":" in value else f"{default_namespace}:{value}"


def _entries():
    for data in sorted(MANUAL.glob("*.json")):
        yield data.stem, json.loads(data.read_text(encoding="utf-8"))


def _elements(entry):
    for anchor, value in entry.items():
        if anchor == "require_advancement":
            continue
        for element in value if isinstance(value, list) else [value]:
            yield anchor, element


def _registered(kind):
    found = set()
    for root in RESOURCE_ROOTS:
        base = root / "assets" / NAMESPACE / kind
        found |= {path.stem for path in base.glob("*.json")}
    return found


class ManualTest(unittest.TestCase):
    """Any failing entry makes Immersive Engineering refuse to open the whole Engineer's Manual."""

    def test_special_elements_are_valid(self):
        multiblocks = {
            f"{NAMESPACE}:multiblocks/{name}" for name in json.loads(
                (ROOT / "src/test/resources/baseline-content-manifest.json").read_text(encoding="utf-8"))["multiblocks"]
        }
        recipes = set()
        for root in RESOURCE_ROOTS:
            for recipe in root.glob("data/*/recipe/**/*.json"):
                relative = recipe.relative_to(root / "data")
                recipes.add(f"{relative.parts[0]}:{'/'.join(relative.parts[2:])[:-5]}")
        items = _registered("models/item")
        problems = []

        def check_stack(stack, where):
            if isinstance(stack, dict):
                if "item" in stack:
                    problems.append(f"{where}: ItemStack uses the pre-1.21 'item' field instead of 'id'")
                stack = stack.get("id")
            if isinstance(stack, str):
                location = _location(stack, "minecraft")
                if location.startswith(NAMESPACE + ":") and location.split(":", 1)[1] not in items:
                    problems.append(f"{where}: unknown item {location}")

        for name, entry in _entries():
            for anchor, element in _elements(entry):
                where = f"{name}/{anchor}"
                kind = element.get("type")
                if _location(kind) .split(":", 1)[1] not in KNOWN_TYPES and kind not in KNOWN_TYPES:
                    problems.append(f"{where}: unknown special element type {kind}")
                elif kind == "multiblock":
                    if _location(element["name"]) not in multiblocks:
                        problems.append(f"{where}: unknown multiblock {element['name']}")
                elif kind == "crafting":
                    for row in element.get("recipes", [element]):
                        for ref in row if isinstance(row, list) else [row]:
                            if isinstance(ref, dict) and "recipe" in ref:
                                if _location(ref["recipe"]) not in recipes:
                                    problems.append(f"{where}: unknown recipe {ref['recipe']}")
                            else:
                                check_stack(ref, where)
                elif kind == "item_display":
                    for stack in ([element["id"]] if "id" in element else element["items"]):
                        check_stack(stack, where)
        self.assertEqual([], problems)

    def test_texts_have_title_and_subtitle(self):
        problems = []
        for text in sorted(MANUAL.glob("*/*.txt")):
            content = text.read_text(encoding="utf-8")
            if content.count("\n") < 2:
                problems.append(str(text.relative_to(MANUAL)))
        self.assertEqual([], problems)

    def test_every_entry_has_english_text(self):
        missing = [name for name, _ in _entries() if not (MANUAL / "en_us" / f"{name}.txt").exists()]
        self.assertEqual([], missing)

    def test_config_placeholders_have_getters(self):
        proxy = (ROOT / "src/main/java/mctmods/immersivetechnology/core/proxy/ClientProxy.java").read_text(encoding="utf-8")
        handled = set(re.findall(r'case "([a-z0-9_.]+)"', proxy))
        used = set()
        for text in MANUAL.glob("*/*.txt"):
            used |= set(re.findall(r"<config;[a-zA-Z]+;([a-z0-9_.]+)", text.read_text(encoding="utf-8")))
        # IE throws "Config key ... does not exist" and the manual stops loading
        self.assertEqual(set(), used - handled)


if __name__ == "__main__":
    unittest.main()
