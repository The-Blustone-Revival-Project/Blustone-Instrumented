# Publication handoff — 2026-10-10

The user authorized pushes and release publication after the copy-only migration. All three main branches now contain the reviewed migrated source/docs/data. Private archives, saves, signing keys, raw telemetry and toolchains remain ignored and local; the original folder is retained.

- Server: [Blustone Server 1.0.0](https://github.com/The-Blustone-Revival-Project/Blustone-Server/releases/tag/v1.0.0), with Added/Improved/Fixed notes, verified resource ZIP, resource manifest and checksums.
- DataDump: [Blustone DataDump 2026-10-10](https://github.com/The-Blustone-Revival-Project/Blustone-DataDump/releases/tag/2026-10-10), with two readable stats/evidence documents, the JSON snapshot, manifest and checksums. Same-day future snapshots use .2, .3, etc.
- Instrumented: [2.8.0.1+15](https://github.com/The-Blustone-Revival-Project/Blustone-Instrumented/releases/tag/2.8.0.1%2B15) is Latest. All14 existing releases have consistent titles and regular public status; no drafts/prereleases remain. APK asset IDs, sizes, digests and download URLs are unchanged. +6 retains its broken-build/DO NOT INSTALL warning.

Every new release uses the repo-specific policy in docs/RELEASING.md and is regular/public/Latest when published. GitHub retains one Latest pointer per repository; older versions remain public historical releases.

Server48-script tests/build/resource verification and compiled encrypted protocol/restart checks passed. The public/CI fixture path was also exercised without private snapshots. Instrumented31 host tests/build-input checks passed. DataDump8 dataset validators, source hashes and snapshot increment/immutability tests passed. Remote release-asset hashes match prepared artifacts. Recovered source bytes were verified against committed Git blobs.

No APK rebuilt or installed, no device actions or new battle, no Docker operation and no original-folder deletion. The battle goal remains paused; E7 stays inactive. Read the release policy before the next publication. Historical migration reports describe the earlier copy-only milestone; this document supersedes their no-push continuation instruction.
