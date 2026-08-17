#!/usr/bin/env python3
import argparse
from collections import Counter
import hashlib
import json
import re
import sys
from pathlib import Path


LIST_CATEGORIES = (
    "blocks", "items", "fluids", "fluid_types", "block_entities", "menus",
    "particles", "recipe_types", "recipe_serializers", "multiblocks", "sounds",
    "creative_tabs", "loot_entries", "config_keys", "network_messages",
    "integrations", "resource_paths",
)
HASH_CATEGORIES = ("java_sources", "resource_hashes")
CATEGORIES = LIST_CATEGORIES + HASH_CATEGORIES
DUPLICATE_REGISTRATION_CATEGORIES = (
    "blocks", "items", "fluids", "block_entities", "menus", "particles",
    "recipe_types", "recipe_serializers", "multiblocks", "sounds",
    "creative_tabs", "loot_entries",
)


class ManifestError(RuntimeError):
    pass


def _literals(pattern: str, text: str) -> list[str]:
    return re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_manifest(root: Path) -> dict:
    root = Path(root)
    values: dict[str, set[str]] = {category: set() for category in LIST_CATEGORIES}
    explicit: dict[str, list[str]] = {category: [] for category in LIST_CATEGORIES}
    java_sources: dict[str, str] = {}
    resource_hashes: dict[str, str] = {}
    resource_occurrences: list[str] = []
    java_root = root / "src/main/java"

    def record(category: str, matches: list[str]) -> None:
        explicit[category].extend(matches)
        values[category].update(matches)

    for path in sorted(java_root.rglob("*.java")) if java_root.exists() else []:
        text = path.read_text(encoding="utf-8")
        name = path.name
        relative_source = path.relative_to(root).as_posix()
        java_sources[relative_source] = _sha256(path)

        record("blocks", _literals(r'new\s+(?:ModBlocks\.)?BlockEntry\s*<.*?>?\s*\(\s*"([a-z0-9_]+)"', text))
        record("fluids", _literals(r'FluidEntry\.make\s*\(\s*"([a-z0-9_]+)"', text))
        record("multiblocks", _literals(r'(?:stone|stoneNoMirror|metal|metalNoMirror|metalNoMirrorWithActive)\s*\([^;]*?"([a-z0-9_]+)"\s*\)', text))
        record("sounds", _literals(r'registerSound\s*\(\s*"([a-z0-9_]+)"', text))

        registrations = _literals(r'\.register\s*\(\s*"([a-z0-9_]+)"', text)
        direct_registrations = _literals(r'(?<!\.)\bregister\s*\(\s*"([a-z0-9_]+)"', text)
        if name == "ModItems.java":
            record("items", direct_registrations)
        elif name == "BlockEntities.java":
            record("block_entities", registrations)
        elif name == "MenuTypes.java":
            record("menus", registrations)
            record("menus", _literals(r'register(?:Arg|Multiblock)\s*\(\s*"([a-z0-9_]+)"', text))
        elif name == "Particles.java":
            record("particles", registrations)
        elif name == "RecipeTypes.java":
            record("recipe_types", direct_registrations)
            record("recipe_serializers", registrations)
        elif name == "CreativeTab.java":
            record("creative_tabs", registrations)
        elif name == "LootFunctions.java":
            record("loot_entries", _literals(r'registerEntry\s*\(\s*"([a-z0-9_]+)"', text))

        # Controlled fixtures intentionally use a neutral file name.
        if name != "MenuTypes.java":
            record("menus", _literals(r'register(?:Arg|Multiblock)\s*\(\s*"([a-z0-9_]+)"', text))

        if name.endswith("Config.java"):
            record("config_keys", _literals(r'\.(?:define|defineInRange|defineEnum|defineListAllowEmpty)\s*\(\s*"([A-Za-z0-9_.-]+)"', text))

        relative_java = path.relative_to(java_root).as_posix()
        if "/core/network/" in f"/{relative_java}" and name != "PacketHandler.java":
            values["network_messages"].add(relative_java.removesuffix(".java"))
        if "/core/integration/" in f"/{relative_java}":
            values["integrations"].add(relative_java.removesuffix(".java"))

    duplicates = []
    for category in DUPLICATE_REGISTRATION_CATEGORIES:
        identifiers = explicit[category]
        duplicates.extend(f"{category}:{identifier}" for identifier, count in Counter(identifiers).items() if count > 1)
    if duplicates:
        raise ManifestError("Duplicate explicit registrations: " + ", ".join(sorted(duplicates)))

    # These entries are created programmatically by the registration helpers.
    values["blocks"].update(values["multiblocks"])
    values["items"].update(values["blocks"])
    for fluid in values["fluids"]:
        values["fluid_types"].add(fluid)
        values["items"].add(f"{fluid}_bucket")
        values["blocks"].add(f"{fluid}_fluid_block")

    for base in (root / "src/main/resources", root / "src/generated/resources"):
        for namespace_root in (base / "assets/immersivetechnology", base / "data/immersivetechnology"):
            if not namespace_root.exists():
                continue
            for path in sorted(namespace_root.rglob("*")):
                if path.is_file():
                    jar_path = path.relative_to(base).as_posix()
                    resource_occurrences.append(jar_path)
                    values["resource_paths"].add(jar_path)
                    resource_hashes[jar_path] = _sha256(path)

    duplicate_resources = sorted(path for path, count in Counter(resource_occurrences).items() if count > 1)
    if duplicate_resources:
        raise ManifestError("Duplicate resource paths: " + ", ".join(duplicate_resources))

    manifest = {category: sorted(values[category]) for category in LIST_CATEGORIES}
    manifest["java_sources"] = dict(sorted(java_sources.items()))
    manifest["resource_hashes"] = dict(sorted(resource_hashes.items()))
    return manifest


def compare_manifests(baseline: dict, current: dict) -> dict:
    differences = {}
    for category in sorted(set(baseline) | set(current)):
        before = baseline.get(category, {})
        after = current.get(category, {})
        if isinstance(before, dict) or isinstance(after, dict):
            before = before if isinstance(before, dict) else {}
            after = after if isinstance(after, dict) else {}
            added = sorted(set(after) - set(before))
            removed = sorted(set(before) - set(after))
            changed = sorted(key for key in set(before) & set(after) if before[key] != after[key])
            if added or removed or changed:
                differences[category] = {"added": added, "removed": removed, "changed": changed}
        else:
            before_set = set(before)
            after_set = set(after)
            added = sorted(after_set - before_set)
            removed = sorted(before_set - after_set)
            if added or removed:
                differences[category] = {"added": added, "removed": removed}
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the Immersive Technology content manifest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", type=Path, metavar="PATH")
    mode.add_argument("--check", type=Path, metavar="PATH")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    try:
        current = collect_manifest(args.root)
    except ManifestError as error:
        print(error, file=sys.stderr)
        return 1

    target = args.write or args.check
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0

    baseline = json.loads(target.read_text(encoding="utf-8"))
    differences = compare_manifests(baseline, current)
    if differences:
        print(json.dumps(differences, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
