#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path


class JarVerificationError(RuntimeError):
    pass


def _source_resource(root: Path, jar_path: str) -> Path:
    candidates = [
        root / "src/main/resources" / jar_path,
        root / "src/generated/resources" / jar_path,
    ]
    matches = [path for path in candidates if path.is_file()]
    if len(matches) != 1:
        raise JarVerificationError(f"Expected one source for {jar_path}, found {len(matches)}")
    return matches[0]


def verify_jar(root: Path, baseline_path: Path, jar_path: Path) -> dict:
    root = Path(root)
    jar_path = Path(jar_path)
    if not re.fullmatch(
        r"MCT-ImmersiveTechnology-1\.21\.1-\d+\.\d+\.\d+-b\d+-[A-Za-z0-9_.-]+\.jar",
        jar_path.name,
    ):
        raise JarVerificationError(f"Unexpected gameplay JAR filename: {jar_path.name}")

    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    with zipfile.ZipFile(jar_path) as archive:
        names = set(archive.namelist())

        required_entries = {"META-INF/neoforge.mods.toml", "mixins.immersivetechnology.json"}
        missing_entries = sorted(required_entries - names)
        if missing_entries:
            raise JarVerificationError("Missing required JAR entries: " + ", ".join(missing_entries))
        if "META-INF/mods.toml" in names:
            raise JarVerificationError("Legacy Forge META-INF/mods.toml must not be packaged")

        missing_resources = sorted(set(baseline["resource_paths"]) - names)
        if missing_resources:
            raise JarVerificationError("Missing baseline resources: " + ", ".join(missing_resources[:20]))

        missing_classes = []
        for source_path in baseline["java_sources"]:
            class_path = source_path.removeprefix("src/main/java/").removesuffix(".java") + ".class"
            if class_path not in names:
                missing_classes.append(class_path)
        if missing_classes:
            raise JarVerificationError("Missing compiled top-level classes: " + ", ".join(missing_classes[:20]))

        content_mismatches = []
        for resource_path in baseline["resource_paths"]:
            if resource_path == "META-INF/neoforge.mods.toml":
                # This template is intentionally expanded by processResources;
                # its required static and substituted fields are checked below.
                continue
            source = _source_resource(root, resource_path)
            packaged = archive.read(resource_path)
            if source.suffix in {".json", ".mcmeta"}:
                try:
                    same = json.loads(source.read_text(encoding="utf-8")) == json.loads(packaged.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    same = source.read_bytes() == packaged
            else:
                same = source.read_bytes() == packaged
            if not same:
                content_mismatches.append(resource_path)
        if content_mismatches:
            raise JarVerificationError("Packaged resource content differs: " + ", ".join(content_mismatches[:20]))

        metadata = archive.read("META-INF/neoforge.mods.toml").decode("utf-8")
        required_metadata = (
            r'modLoader\s*=\s*"javafml"',
            r'modId\s*=\s*"immersivetechnology"',
            r'modId\s*=\s*"neoforge"',
            r'modId\s*=\s*"minecraft"',
            r'modId\s*=\s*"immersiveengineering"',
            r'modId\s*=\s*"immersiveconvergence"',
            r'versionRange\s*=\s*"\[1\.21\.1\]"',
            r'config\s*=\s*"mixins\.immersivetechnology\.json"',
        )
        missing_metadata = [pattern for pattern in required_metadata if not re.search(pattern, metadata)]
        if missing_metadata:
            raise JarVerificationError("NeoForge metadata is incomplete: " + ", ".join(missing_metadata))
        if "${" in metadata:
            raise JarVerificationError("NeoForge metadata contains unexpanded placeholders")

        report = {
            "jar": jar_path.name,
            "sha256": hashlib.sha256(jar_path.read_bytes()).hexdigest(),
            "classes": sum(name.endswith(".class") for name in names),
            "resources": len(baseline["resource_paths"]),
            "java_sources": len(baseline["java_sources"]),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the packaged Immersive Technology gameplay JAR")
    parser.add_argument("jar", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src/test/resources/baseline-content-manifest.json",
    )
    args = parser.parse_args()
    try:
        report = verify_jar(args.root, args.baseline, args.jar)
    except (JarVerificationError, OSError, zipfile.BadZipFile) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
