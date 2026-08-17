#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


CATEGORIES = (
    "blocks",
    "items",
    "fluids",
    "fluid_types",
    "block_entities",
    "menus",
    "particles",
    "recipe_types",
    "recipe_serializers",
    "multiblocks",
    "sounds",
    "resource_paths",
)


def _literals(pattern: str, text: str) -> set[str]:
    return set(re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL))


def collect_manifest(root: Path) -> dict[str, list[str]]:
    root = Path(root)
    values: dict[str, set[str]] = {category: set() for category in CATEGORIES}
    java_root = root / "src/main/java"

    for path in sorted(java_root.rglob("*.java")) if java_root.exists() else []:
        text = path.read_text(encoding="utf-8")
        name = path.name

        values["blocks"].update(_literals(r'new\s+(?:ModBlocks\.)?BlockEntry\s*<.*?>?\s*\(\s*"([a-z0-9_]+)"', text))
        values["fluids"].update(_literals(r'FluidEntry\.make\s*\(\s*"([a-z0-9_]+)"', text))
        values["multiblocks"].update(
            _literals(r'(?:stone|stoneNoMirror|metal|metalNoMirror|metalNoMirrorWithActive)\s*\([^;]*?"([a-z0-9_]+)"\s*\)', text)
        )
        values["sounds"].update(_literals(r'registerSound\s*\(\s*"([a-z0-9_]+)"', text))

        registrations = _literals(r'\.register\s*\(\s*"([a-z0-9_]+)"', text)
        direct_registrations = _literals(r'(?<!\.)\bregister\s*\(\s*"([a-z0-9_]+)"', text)
        if name == "ModItems.java":
            values["items"].update(direct_registrations)
        elif name == "BlockEntities.java":
            values["block_entities"].update(registrations)
        elif name == "MenuTypes.java":
            values["menus"].update(registrations)
            values["menus"].update(_literals(r'register(?:Arg|Multiblock)\s*\(\s*"([a-z0-9_]+)"', text))
        elif name == "Particles.java":
            values["particles"].update(registrations)
        elif name == "RecipeTypes.java":
            values["recipe_types"].update(direct_registrations)
            values["recipe_serializers"].update(registrations)

        # Controlled fixtures intentionally use a neutral file name.
        values["menus"].update(_literals(r'register(?:Arg|Multiblock)\s*\(\s*"([a-z0-9_]+)"', text))

    # These entries are created programmatically by the registration helpers.
    values["blocks"].update(values["multiblocks"])
    values["items"].update(values["blocks"])
    for fluid in values["fluids"]:
        values["fluid_types"].add(fluid)
        values["items"].add(f"{fluid}_bucket")
        values["blocks"].add(f"{fluid}_fluid_block")

    for base in (root / "src/main/resources", root / "src/generated/resources"):
        namespace_roots = (base / "assets/immersivetechnology", base / "data/immersivetechnology")
        for namespace_root in namespace_roots:
            if not namespace_root.exists():
                continue
            for path in namespace_root.rglob("*"):
                if path.is_file():
                    values["resource_paths"].add(path.relative_to(base).as_posix())

    return {category: sorted(values[category]) for category in CATEGORIES}


def compare_manifests(baseline: dict, current: dict) -> dict[str, dict[str, list[str]]]:
    differences = {}
    for category in sorted(set(baseline) | set(current)):
        before = set(baseline.get(category, []))
        after = set(current.get(category, []))
        added = sorted(after - before)
        removed = sorted(before - after)
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

    current = collect_manifest(args.root)
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
