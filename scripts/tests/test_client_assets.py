import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESOURCE_ROOTS = [ROOT / "src" / "main" / "resources", ROOT / "src" / "generated" / "resources"]
NAMESPACE = "immersivetechnology"
RESOURCE_LOCATION = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")


def _location(value, default_namespace="minecraft"):
    return value if ":" in value else f"{default_namespace}:{value}"


def _asset(location, kind, suffix):
    namespace, path = location.split(":", 1)
    for root in RESOURCE_ROOTS:
        candidate = root / "assets" / namespace / kind / f"{path}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _paletted_textures():
    textures = set()
    for root in RESOURCE_ROOTS:
        for atlas in root.glob("assets/*/atlases/*.json"):
            for source in json.loads(atlas.read_text(encoding="utf-8"))["sources"]:
                if not source["type"].endswith("paletted_permutations"):
                    continue
                separator = source.get("separator", "_")
                for texture in source["textures"]:
                    for key in source["permutations"]:
                        textures.add(f"{texture}{separator}{key}")
    return textures


def _model_files():
    for root in RESOURCE_ROOTS:
        yield from (root / "assets" / NAMESPACE / "models").rglob("*.json")


def _used_obj_files():
    used = set()

    def visit(key, value):
        if key in ("model", "modelLocation") and isinstance(value, str) and value.endswith(".obj"):
            namespace, path = _location(value).split(":", 1)
            for root in RESOURCE_ROOTS:
                obj = root / "assets" / namespace / path
                if namespace == NAMESPACE and obj.exists():
                    used.add(obj)

    for model in _model_files():
        _walk(json.loads(model.read_text(encoding="utf-8")), visit)
    return sorted(used)


def _walk(element, visit):
    if isinstance(element, dict):
        for key, value in element.items():
            visit(key, value)
            _walk(value, visit)
    elif isinstance(element, list):
        for value in element:
            _walk(value, visit)


class ClientAssetTest(unittest.TestCase):
    """Missing Immersive Technology assets render as the purple/black placeholder in game."""

    def test_model_textures_parents_and_obj_files_exist(self):
        paletted = _paletted_textures()
        problems = []
        for model in _model_files():
            owner = model.relative_to(ROOT)

            def visit(key, value):
                if key == "textures" and isinstance(value, dict):
                    for texture in value.values():
                        if not isinstance(texture, str) or texture.startswith("#"):
                            continue
                        location = _location(texture)
                        if location.startswith(NAMESPACE + ":") and location not in paletted \
                                and _asset(location, "textures", ".png") is None:
                            problems.append(f"{owner}: missing texture {location}")
                elif key == "parent" and isinstance(value, str):
                    location = _location(value)
                    if location.startswith(NAMESPACE + ":") and _asset(location, "models", ".json") is None:
                        problems.append(f"{owner}: missing parent {location}")
                elif key == "model" and isinstance(value, str) and value.endswith(".obj"):
                    namespace, path = _location(value).split(":", 1)
                    if namespace == NAMESPACE and not any(
                            (root / "assets" / namespace / path).exists() for root in RESOURCE_ROOTS):
                        problems.append(f"{owner}: missing OBJ {value}")

            _walk(json.loads(model.read_text(encoding="utf-8")), visit)
        self.assertEqual([], problems)

    def test_obj_materials_reference_existing_textures(self):
        problems = []
        for obj in _used_obj_files():
            lines = obj.read_text(encoding="utf-8", errors="replace").splitlines()
            defined = set()
            for line in lines:
                if not line.startswith("mtllib "):
                    continue
                material = obj.parent / line[len("mtllib "):].strip()
                if not material.exists():
                    problems.append(f"{obj.relative_to(ROOT)}: missing material library {material.name}")
                    continue
                for entry in material.read_text(encoding="utf-8", errors="replace").splitlines():
                    if entry.startswith("newmtl "):
                        defined.add(entry[len("newmtl "):].strip())
                    if not entry.startswith("map_Kd "):
                        continue
                    texture = entry[len("map_Kd "):].strip()
                    if texture.startswith("#"):
                        continue
                    if not RESOURCE_LOCATION.fullmatch(texture):
                        problems.append(f"{material.relative_to(ROOT)}: invalid texture location {texture}")
                    elif texture.startswith(NAMESPACE + ":") and _asset(texture, "textures", ".png") is None:
                        problems.append(f"{material.relative_to(ROOT)}: missing texture {texture}")
            for line in lines:
                if line.startswith("usemtl ") and line[len("usemtl "):].strip() not in defined:
                    problems.append(f"{obj.relative_to(ROOT)}: undefined material {line[len('usemtl '):].strip()}")
        self.assertEqual([], sorted(set(problems)))

    def test_obj_files_used_by_models_are_not_empty(self):
        problems = []
        for model in _model_files():
            def visit(key, value):
                if key == "model" and isinstance(value, str) and value.endswith(".obj"):
                    namespace, path = _location(value).split(":", 1)
                    for root in RESOURCE_ROOTS:
                        obj = root / "assets" / namespace / path
                        if obj.exists() and not any(line.startswith("f ") for line in
                                                    obj.read_text(encoding="utf-8", errors="replace").splitlines()):
                            problems.append(f"{model.relative_to(ROOT)}: {value} has no faces")

            _walk(json.loads(model.read_text(encoding="utf-8")), visit)
        self.assertEqual([], problems)

    def test_blockstates_reference_existing_models(self):
        problems = []
        for root in RESOURCE_ROOTS:
            for blockstate in (root / "assets" / NAMESPACE / "blockstates").glob("*.json"):
                def visit(key, value):
                    if key == "model" and isinstance(value, str):
                        location = _location(value)
                        if location.startswith(NAMESPACE + ":") and _asset(location, "models", ".json") is None:
                            problems.append(f"{blockstate.name}: missing model {location}")

                _walk(json.loads(blockstate.read_text(encoding="utf-8")), visit)
        self.assertEqual([], problems)

    def test_registered_blocks_and_items_have_assets(self):
        manifest = json.loads((ROOT / "src/test/resources/baseline-content-manifest.json").read_text(encoding="utf-8"))
        # "removal" is a false positive of the manifest's registration regex (@SuppressWarnings("removal"))
        blocks = [name for name in manifest["blocks"] if name != "removal"]
        items = [name for name in manifest["items"] if name != "removal"]
        missing = [f"blockstate {name}" for name in blocks
                   if _asset(f"{NAMESPACE}:{name}", "blockstates", ".json") is None]
        missing += [f"item model {name}" for name in items
                    if _asset(f"{NAMESPACE}:item/{name}", "models", ".json") is None]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
