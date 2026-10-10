# Blustone JET Workshop

This is a local, read-only browser viewer for the recovered Blustone `.jet`
resources. It does not upload files, modify the corpus, or run the game.

## Start it on Windows

From the repository root:

```powershell
.\tools\jet-viewer\start-jet-viewer.ps1
```

Or double-click `tools\jet-viewer\start-jet-viewer.cmd` in Explorer.

The launcher uses the repository's bundled Python environment when available,
starts a loopback-only server, and opens the browser at
`http://127.0.0.1:8765/`. Stop it with `Ctrl+C`.

If PowerShell blocks `.ps1` execution, run the same program directly:

```powershell
& .\tools\python-venv\Scripts\python.exe .\tools\jet-viewer\jet_viewer.py
```

You can inspect another evidence directory without changing the code:

```powershell
.\tools\jet-viewer\start-jet-viewer.ps1 -Root .\recovered-assets\phone-2026-09-18
```

## What it decodes

The viewer currently recognizes the confirmed payload shapes in this corpus:

- embedded MP4/MP3/PNG/JPEG/WebP/WAV/Ogg payloads, served to the browser as
  their normal media type;
- concatenated zlib/JET chunks, including multi-resource `CUT*` files and the
  repository's `E_DEFALT.jet` spelling;
- readable `RW`/`RWM` resources after inflation, including GLSL shader source
  and LEVELING JSON records;
- `I2` custom texture atlases reconstructed as PNG images;
- RW-wrapped TrueType/OpenType fonts with in-browser font previews; and
- character bundles such as `C001.jet`, including PNG atlases, atlas-region
  text, and Spine 3.6 binary skeleton/animation metadata; and
- original/inflated/media bytes as separate downloads.

The `.jet` format is not one uniform public archive format. The native game
loader still owns some custom texture and resource-record semantics, so those
layers are shown honestly as binary/metadata until their format is verified.

## Tests

```powershell
& .\tools\python-venv\Scripts\python.exe -m unittest discover .\tools\jet-viewer -p 'test_*.py' -v
```

For the full canonical APK corpus, run the exhaustive audit:

```powershell
& .\tools\python-venv\Scripts\python.exe .\tools\jet-viewer\audit_corpus.py
```

The audit walks every outer chunk and logical resource, validates all decoded
media payloads, checks font tables, parses full MP3 frame streams and MP4 box
tables, and reports unconsumed bytes. `S2`/`AT` tails are retained as explicit
auxiliary-record layers rather than discarded.
