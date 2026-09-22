# Markov for Windows

The Windows build is a self-contained, 64-bit `Markov.exe`. Copy that one file
where you want to keep the app, then double-click it. Python does not need to be
installed. Markov starts the personal service and opens its PWA in your default
browser. Keep its console window open; Ctrl+C stops the service. This version
does not install a Windows Service, tray app, or automatic startup entry.

The generated executable is at `dist/windows/Markov.exe`, alongside its SHA-256
checksum. It contains the Markov icon, product version, Python runtime, web
templates, styles, fonts, and extraction dependencies. It is an unsigned local
build; code signing and an installer are separate release steps. macOS and Linux
packaging are deferred.

## Your archive and phone

New installations keep the archive and service configuration in
`%LOCALAPPDATA%\Markov`. If `%USERPROFILE%\.markov\service.json` already exists,
the executable reuses that personal-service directory. Moving or replacing the
executable leaves the archive in place. Do not run multiple service processes
against the same archive. A second launch on an occupied port reports an error.

To configure the phone address, run this from a terminal beside the executable:

```powershell
.\Markov.exe --name "My Markov" --url https://YOUR-SERVICE-HOST
```

Use your actual trusted HTTPS address, then open **You → Your service** on the
computer to create the QR invitation. See [private HTTPS and QR pairing](local-service.md).
The executable does not create that network connection automatically.

The existing service flags remain available: `--data-dir`, `--database`,
`--owner`, `--port`, and `--check`. Use `--no-browser` for unattended launches.
Model settings can live in a `.env` file inside the selected data directory;
the executable intentionally ignores unrelated `.env` files beside itself.
Without configured providers it starts with heuristic processing and keyword
indexing. Model weights and FFmpeg are not included; advanced transcription
and external model runtimes still need their usual setup. The optional
in-process `llama-cpp-python` provider is not bundled; an Ollama or compatible
local HTTP endpoint remains supported.

## Build from source

On Windows with 64-bit Python 3.11, run:

```powershell
.\scripts\build_windows.ps1
```

Use `-Python C:\path\to\python.exe` to select the build interpreter. The script
creates an isolated environment under `build/windows-env`, installs constrained
dependencies, generates the icon from Markov's existing SVG, packages the app,
runs the executable's configuration check, and writes its SHA-256 checksum.
The build downloads dependencies but never bundles your `.env` or archive.
Generated binaries and temporary build files stay out of Git.

Executable verification covers startup without Python on PATH, bundled PWA
assets, QR generation, saving a bookmark, and persistence after restarting.
This is not a clean-VM installer or signed-release validation.
