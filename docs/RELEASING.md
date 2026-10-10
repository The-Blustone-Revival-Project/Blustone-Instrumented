# Instrumented release convention

Tag/version: **2.8.0.1+N**, continuing the existing increment. Title: **2.8.0.1+N: Short descriptive summary**. The historical releases keep their original tags and APK assets. Do not invent missing historical build numbers or retag/rebuild an old APK to rename a release.

All releases are published regular public releases. Never use draft/prerelease flags set to true. The highest published build is explicitly Latest; all older builds remain public historical releases. A regular release designation does not erase known defects: the broken +6 build retains its DO NOT INSTALL warning and can never become the recommended Latest.

Current source/release line: **2.8.0.1+15**. VERSION tracks the instrumented build tag, separate from the game's native app version. A metadata-only title/status normalization does not create a new APK build number.

## New build release

1. Preserve originals and the signing identity; build only the side-by-side instrumented package.
2. Increment VERSION, prepare the matching notes and validate the native patches and focused host tests.
3. Verify APK identity/signature and the intended native behavior before publication. Retain honest limits; a regular release is not a claim of full game revival.
4. Review/commit/push public source only. Keep signing keys, account captures and toolchains ignored.
5. Publish with `python tools/release.py --summary "Short summary" --notes-file <notes> --apk <APK> --metadata <BUILD-METADATA.json> --checksums <SHA256SUMS.txt>`.

The publisher verifies VERSION, title format, side-by-side package metadata, APK/checksum parity, clean/pushed source and immutable tag use. It has no prerelease/draft option. Do not use the old upload helper to create a release; it now only uploads to an already-published regular release.

Existing release titles/statuses were normalized in October2026. Their exact previous metadata and unchanged asset fingerprints were retained privately during the audit; public history is indexed in releases/index.json.
