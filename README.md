# llama-cpp-vulkan-fetcher

A Python CLI that downloads the latest **Windows Vulkan x64** binary release of [`llama.cpp`](https://github.com/ggml-org/llama.cpp), extracts it into a target directory, and keeps a local history of processed releases.

## Features

- Downloads the latest `llama.cpp` release from GitHub
- Selects the `win-vulkan-x64.zip` asset automatically
- Extracts the ZIP into the chosen output directory
- Stores a local JSON history of processed releases
- Warns when the latest release was already processed
- Supports forced re-download with `--force`
- Can compute SHA-256 for downloaded archives
- Includes `fetch`, `history`, and `check` subcommands
- Supports built-in `-h` / `--help`

## Why this project

Keeping a local `llama.cpp` setup updated on Windows is simple in theory, but repetitive in practice. This tool automates the boring part:

1. Query the latest upstream release
2. Find the correct Vulkan x64 Windows binary
3. Download it
4. Extract it
5. Record what happened locally

The project uses a standard Python package structure with a `src/` layout and a console script entry point, which is a robust and widely used way to package command-line tools.

## Project structure

```text
llama-cpp-vulkan-fetcher/
├─ pyproject.toml
├─ README.md
└─ src/
   └─ llama_cpp_vulkan_fetcher/
      ├─ __init__.py
      └─ __main__.py
```

## Requirements

- Python 3.9+
- Internet access
- Windows, if you want to use the downloaded binaries directly

## Installation

Clone the repository and install it locally.

### Regular install

```bash
git clone https://github.com/yourusername/llama-cpp-vulkan-fetcher.git
cd llama-cpp-vulkan-fetcher
python -m pip install -U pip
python -m pip install .
```

### Editable install

For development, use an editable install:

```bash
python -m pip install -e .
```

## Usage

### Show help

```bash
llama-cpp-vulkan-fetcher --help
```

### Download and extract the latest release

```bash
llama-cpp-vulkan-fetcher fetch
```

### Extract into a specific directory

```bash
llama-cpp-vulkan-fetcher fetch --output ./llama-bin
```

### Force processing even if already downloaded before

```bash
llama-cpp-vulkan-fetcher fetch --force
```

### Keep the downloaded ZIP file

```bash
llama-cpp-vulkan-fetcher fetch --keep-zip
```

### Compute SHA-256 for the ZIP

```bash
llama-cpp-vulkan-fetcher fetch --compute-sha256
```

### Show release history

```bash
llama-cpp-vulkan-fetcher history
```

### Show full history as JSON

```bash
llama-cpp-vulkan-fetcher history --limit 0 --json
```

### Check if the latest release was already processed

```bash
llama-cpp-vulkan-fetcher check
```

### Check status as JSON

```bash
llama-cpp-vulkan-fetcher check --json
```

## Commands

### `fetch`

Downloads the latest `llama.cpp` Windows Vulkan x64 ZIP, extracts it, and records the operation in the history file.

Common options:

- `-o, --output` — extraction target directory
- `--force` — skip confirmation if the release was already processed
- `--keep-zip` — do not delete the ZIP after extraction
- `--compute-sha256` — calculate and store the archive hash

### `history`

Prints the local history of processed releases.

Common options:

- `--limit` — number of entries to show, `0` means all
- `--json` — machine-readable JSON output

### `check`

Checks whether the latest upstream release has already been processed locally.

Common options:

- `--json` — machine-readable JSON output

## History file

The tool stores release activity in a JSON file named:

```text
.llama_cpp_vulkan_fetcher_history.json
```

A typical entry looks like this:

```json
{
  "release_id": 210001234,
  "tag_name": "b9142",
  "release_name": "b9142",
  "asset_name": "llama-b9142-bin-win-vulkan-x64.zip",
  "asset_size": 123456789,
  "download_url": "https://github.com/ggml-org/llama.cpp/releases/download/b9142/llama-b9142-bin-win-vulkan-x64.zip",
  "extract_dir": "C:\\tools\\llama.cpp",
  "zip_path": null,
  "downloaded_at": "2026-05-15T09:00:00Z",
  "extracted_at": "2026-05-15T09:00:07Z",
  "sha256": "abc123...",
  "status": "success"
}
```

This makes it easy to audit what was downloaded, when it was processed, and where it was extracted.

## Optional GitHub token

GitHub API access works without authentication for public releases, but using a token can reduce the chance of rate-limit issues.

### Windows CMD

```cmd
set GITHUB_TOKEN=your_token_here
```

### PowerShell

```powershell
$env:GITHUB_TOKEN="your_token_here"
```

## Exit codes

The CLI returns standard process exit codes:

- `0` for success
- `1` for errors

The `check` command also uses exit codes intentionally:

- `0` if the latest release was already processed
- `1` if a new release is available or if an error occurs

This makes it easy to integrate into scripts, scheduled tasks, or CI workflows.

## Development notes

This project uses:

- `requests` for GitHub API calls and asset downloads
- `argparse` for the CLI interface
- `setuptools` with `pyproject.toml`
- `src/` layout for robust packaging

## Troubleshooting

### Command installs but does not run

If the CLI command exists but raises an import error, reinstall the package:

```bash
python -m pip uninstall llama-cpp-vulkan-fetcher
python -m pip install -e .
```

### Verify import manually

```bash
python -c "import llama_cpp_vulkan_fetcher; print(llama_cpp_vulkan_fetcher.__file__)"
```

### Verify the command was installed in the current Python environment

```bash
python -m pip show llama-cpp-vulkan-fetcher
```

## Roadmap

Possible future improvements:

- Download progress bar
- Config file support
- Support for other `llama.cpp` binary variants
- Cleanup command for old archives
- Optional non-interactive mode for automation
- Release notes display before download

## Contributing

Issues, suggestions, and pull requests are welcome.

Suggested workflow:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the CLI
5. Open a pull request

## License

Choose a license before publishing, for example MIT.

## Acknowledgments

This tool depends on the excellent [`ggml-org/llama.cpp`](https://github.com/ggml-org/llama.cpp) project and its published release assets.