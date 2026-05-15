from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO = "ggml-org/llama.cpp"
GITHUB_LATEST_RELEASE = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_SUFFIX = "win-vulkan-x64.zip"
DEFAULT_HISTORY_FILENAME = ".llama_cpp_vulkan_fetcher_history.json"

logger = logging.getLogger("llama_cpp_vulkan_fetcher")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_history() -> dict:
    return {
        "repo": REPO,
        "asset_suffix": ASSET_SUFFIX,
        "processed_releases": [],
    }


def load_history(path: Path) -> dict:
    if not path.exists():
        return default_history()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("History root must be a JSON object")
        data.setdefault("repo", REPO)
        data.setdefault("asset_suffix", ASSET_SUFFIX)
        data.setdefault("processed_releases", [])
        return data
    except Exception as e:
        logger.warning("Invalid history file at %s: %s", path, e)
        return default_history()


def save_history(path: Path, history: dict) -> None:
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def github_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "llama-cpp-vulkan-fetcher/0.1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_latest_release() -> dict:
    response = requests.get(
        GITHUB_LATEST_RELEASE,
        headers=github_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def find_asset(release_json: dict) -> dict:
    for asset in release_json.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(ASSET_SUFFIX):
            return asset
    raise RuntimeError(f"No asset ending with '{ASSET_SUFFIX}' found in latest release")


def find_processed_release(history: dict, release_id: int, asset_name: str) -> dict | None:
    for item in reversed(history.get("processed_releases", [])):
        if item.get("release_id") == release_id and item.get("asset_name") == asset_name:
            return item
    return None


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def download_file(url: str, dest: Path) -> None:
    with requests.get(url, headers=github_headers(), stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract_zip(zip_path: Path, output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = (output_dir / member.filename).resolve()
            if output_dir not in member_path.parents and member_path != output_dir:
                raise RuntimeError(f"Unsafe ZIP entry detected: {member.filename}")
        zf.extractall(output_dir)


def append_history_entry(history: dict, entry: dict) -> None:
    history.setdefault("processed_releases", []).append(entry)


def build_history_entry(
    release_json: dict,
    asset: dict,
    output_dir: Path,
    status: str,
    downloaded_at: str | None = None,
    extracted_at: str | None = None,
    sha256: str | None = None,
    zip_path: Path | None = None,
) -> dict:
    return {
        "release_id": release_json.get("id"),
        "tag_name": release_json.get("tag_name"),
        "release_name": release_json.get("name"),
        "asset_name": asset.get("name"),
        "asset_size": asset.get("size"),
        "download_url": asset.get("browser_download_url"),
        "extract_dir": str(output_dir),
        "zip_path": str(zip_path) if zip_path else None,
        "downloaded_at": downloaded_at,
        "extracted_at": extracted_at,
        "sha256": sha256,
        "status": status,
    }


def cmd_fetch(args: argparse.Namespace) -> int:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    history_path = Path(args.history_file).resolve()
    history = load_history(history_path)

    release_json = None
    asset = None
    zip_path = None
    downloaded_at = None
    extracted_at = None
    sha256 = None

    try:
        logger.info("Fetching latest release metadata")
        release_json = get_latest_release()
        asset = find_asset(release_json)

        release_id = release_json.get("id")
        tag_name = release_json.get("tag_name")
        asset_name = asset.get("name")
        asset_url = asset.get("browser_download_url")

        logger.info("Latest release: %s | asset: %s", tag_name, asset_name)

        processed = find_processed_release(history, release_id, asset_name)
        if processed and not args.force:
            logger.info(
                "Release already processed | extracted_at=%s | extract_dir=%s",
                processed.get("extracted_at"),
                processed.get("extract_dir"),
            )
            proceed = ask_yes_no(
                f"Release {tag_name} was already processed. Download and extract again?",
                default=False,
            )
            if not proceed:
                logger.info("Operation cancelled by user")
                return 0

        zip_path = output_dir / asset_name

        logger.info("Downloading %s", asset_url)
        download_file(asset_url, zip_path)
        downloaded_at = utc_now_iso()

        if args.compute_sha256:
            logger.info("Computing SHA-256")
            sha256 = compute_sha256(zip_path)

        logger.info("Extracting %s to %s", zip_path.name, output_dir)
        safe_extract_zip(zip_path, output_dir)
        extracted_at = utc_now_iso()

        if not args.keep_zip and zip_path.exists():
            zip_path.unlink()
            logger.info("Removed ZIP file after extraction")

        entry = build_history_entry(
            release_json=release_json,
            asset=asset,
            output_dir=output_dir,
            status="success",
            downloaded_at=downloaded_at,
            extracted_at=extracted_at,
            sha256=sha256,
            zip_path=zip_path if args.keep_zip else None,
        )
        append_history_entry(history, entry)
        save_history(history_path, history)

        logger.info("History updated: %s", history_path)
        logger.info("Done")
        return 0

    except requests.HTTPError as e:
        logger.exception("HTTP error")
        if release_json and asset:
            entry = build_history_entry(
                release_json=release_json,
                asset=asset,
                output_dir=output_dir,
                status=f"http_error: {e}",
                downloaded_at=downloaded_at,
                extracted_at=extracted_at,
                sha256=sha256,
                zip_path=zip_path,
            )
            append_history_entry(history, entry)
            save_history(history_path, history)
        return 1

    except Exception as e:
        logger.exception("Unexpected error")
        if release_json and asset:
            entry = build_history_entry(
                release_json=release_json,
                asset=asset,
                output_dir=output_dir,
                status=f"error: {e}",
                downloaded_at=downloaded_at,
                extracted_at=extracted_at,
                sha256=sha256,
                zip_path=zip_path,
            )
            append_history_entry(history, entry)
            save_history(history_path, history)
        return 1


def cmd_history(args: argparse.Namespace) -> int:
    history_path = Path(args.history_file).resolve()
    history = load_history(history_path)
    items = history.get("processed_releases", [])

    if not items:
        if args.json:
            print("[]")
        else:
            print("No processed releases found.")
        return 0

    selected = items if args.limit == 0 else items[-args.limit:]

    if args.json:
        print(json.dumps(selected, indent=2, ensure_ascii=False))
        return 0

    for item in selected:
        print(
            f"{item.get('tag_name')} | {item.get('asset_name')} | "
            f"status={item.get('status')} | "
            f"downloaded_at={item.get('downloaded_at')} | "
            f"extracted_at={item.get('extracted_at')} | "
            f"sha256={item.get('sha256') or '-'} | "
            f"dir={item.get('extract_dir')}"
        )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    history_path = Path(args.history_file).resolve()
    history = load_history(history_path)

    release_json = get_latest_release()
    asset = find_asset(release_json)

    processed = find_processed_release(
        history,
        release_json.get("id"),
        asset.get("name"),
    )

    if processed:
        message = {
            "status": "already_processed",
            "tag_name": release_json.get("tag_name"),
            "asset_name": asset.get("name"),
            "extracted_at": processed.get("extracted_at"),
            "extract_dir": processed.get("extract_dir"),
        }
        if args.json:
            print(json.dumps(message, indent=2, ensure_ascii=False))
        else:
            print(
                f"Already processed: {message['tag_name']} | "
                f"{message['asset_name']} | extracted_at={message['extracted_at']}"
            )
        return 0

    message = {
        "status": "new_release_available",
        "tag_name": release_json.get("tag_name"),
        "asset_name": asset.get("name"),
    }
    if args.json:
        print(json.dumps(message, indent=2, ensure_ascii=False))
    else:
        print(f"New release available: {message['tag_name']} | {message['asset_name']}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download and extract the latest llama.cpp Windows Vulkan x64 binaries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--history-file",
        default=DEFAULT_HISTORY_FILENAME,
        help="Path to the history JSON file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Available commands",
    )

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Download and extract latest release",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    fetch_parser.add_argument(
        "-o", "--output", default=".",
        help="Directory where the ZIP will be extracted",
    )
    fetch_parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if the latest release was already processed",
    )
    fetch_parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded ZIP after extraction",
    )
    fetch_parser.add_argument(
        "--compute-sha256",
        action="store_true",
        help="Compute SHA-256 for the downloaded ZIP and save it in history",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    history_parser = subparsers.add_parser(
        "history",
        help="Show processed release history",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of entries to show (0 = all)",
    )
    history_parser.add_argument(
        "--json",
        action="store_true",
        help="Output history entries as JSON",
    )
    history_parser.set_defaults(func=cmd_history)

    check_parser = subparsers.add_parser(
        "check",
        help="Check whether the latest release has already been processed",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Output check result as JSON",
    )
    check_parser.set_defaults(func=cmd_check)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())