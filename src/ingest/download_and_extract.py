"""
Data Ingestion & Extraction Utility.
Downloads and extracts the October 2026 DTC GPS archive from the official Cloudflare R2 bucket:
https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import requests
import py7zr
import sqlite3
from src.config import GPS_RAW_DIR, PROCESSED_DATA_DIR

ARCHIVE_URL = "https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z"
ARCHIVE_PATH = GPS_RAW_DIR / "delhi-dtc-bus-gtfs-rt-2026-10.7z"


def download_archive(url: str = ARCHIVE_URL, dest_path: Path = ARCHIVE_PATH, chunk_size: int = 1024 * 1024):
    """Downloads the historical GPS archive with progress streaming."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        print(f"Archive already exists at {dest_path}. Skipping download.")
        return

    print(f"Connecting to {url}...")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        print(f"Downloading archive ({total_size / (1024*1024):.1f} MB)...")

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100.0
                        sys.stdout.write(f"\rProgress: {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({pct:.1f}%)")
                        sys.stdout.flush()

    print("\nDownload complete.")


def extract_days(archive_path: Path = ARCHIVE_PATH, target_dir: Path = GPS_RAW_DIR, specific_files: list = None):
    """
    Extracts SQLite database files from the 7z archive.
    Optionally extracts only specific days (e.g. ['bus_movements_2026_10_15.db']).
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found at {archive_path}")

    print(f"Opening archive {archive_path.name}...")
    with py7zr.SevenZipFile(archive_path, mode='r') as z:
        all_names = z.getnames()
        print(f"Found {len(all_names)} daily databases in archive.")
        
        targets = specific_files if specific_files else all_names
        print(f"Extracting {len(targets)} files to {target_dir}...")
        z.extract(path=target_dir, targets=targets)
        print("Extraction complete.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download and extract DTC GPS dataset")
    parser.add_argument("--download", action="store_true", help="Download the archive from R2")
    parser.add_argument("--extract-sample", action="store_true", help="Extract sample days for fast pipeline build")
    parser.add_argument("--extract-all", action="store_true", help="Extract all 31 days")
    args = parser.parse_args()

    if args.download:
        download_archive()

    if args.extract_sample:
        # Extract 2 weekdays and 1 weekend day
        sample_days = [
            "bus_movements_2026_10_15.db", # Thursday (weekday)
            "bus_movements_2026_10_16.db", # Friday (weekday)
            "bus_movements_2026_10_18.db", # Sunday (weekend)
        ]
        extract_days(specific_files=sample_days)
    elif args.extract_all:
        extract_days()
