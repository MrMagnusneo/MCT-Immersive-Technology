# NeoForge 1.21.1 validation

## Branch and loader

- Target branch: `1.21.1-3.0-Dev`.
- Validation branch: `codex/neoforge-1.21.1-build`.
- Loader: NeoForge (`net.neoforged.moddev`, `neoForge {}`, and `META-INF/neoforge.mods.toml`).
- Runtime: Minecraft 1.21.1, NeoForge 21.1.234, and Java 21.

## Preserved content baseline

The baseline manifest records both logical registrations and SHA-256 hashes for every production Java source and namespaced resource. CI rejects removed, added, changed, or duplicate content before building and repeats the check after datagen.

| Surface | Count |
| --- | ---: |
| Blocks | 47 |
| Items | 49 |
| Fluids / fluid types | 12 / 12 |
| Block entities | 13 |
| Menus | 14 |
| Particles | 2 |
| Recipe types / serializers | 13 / 13 |
| Multiblocks | 18 |
| Sounds | 21 |
| Creative tabs | 1 |
| Loot entries | 2 |
| Config keys | 70 |
| Network messages | 6 |
| Integration entry points | 23 |
| Production Java sources | 350 |
| Production resources (all namespaces and root metadata) | 841 |

## Automated acceptance gates

The GitHub Actions workflow performs these checks in order:

1. Run all manifest, CI-contract, and JAR-verifier regression tests.
2. Compare the source tree with the content/hash baseline and reject duplicate registrations or resource paths.
3. Run NeoForge datagen and repeat the manifest/hash check, including a clean Git diff for production and generated resources.
4. Run a clean Gradle build with an immutable committed version.
5. Select exactly one gameplay JAR and verify its filename, expanded NeoForge metadata, required dependencies, mixin config, all 350 compiled top-level classes, and the semantic or byte-exact content of all 841 production resources.
6. Start the dedicated server, observe it after the ready state, reject fatal markers, send `stop`, and require exit code 0.
7. Confirm `version.properties` was not changed and upload the exact verified JAR only when all preceding gates succeed.

The workflow is rerun three times on the final code revision before the deliverable JAR is accepted.
