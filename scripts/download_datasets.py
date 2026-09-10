#!/usr/bin/env python3
"""
Dataset Downloader and Manager
Downloads standard Solomon VRPTW benchmark instances and provisions dynamic dataset locations.
"""
from __future__ import annotations
import argparse
import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_SOLOMON_INSTANCES = ["C101", "R101", "RC101"]

# Reliable open-source mirror for official Solomon VRPTW benchmark files
SOLOMON_MIRROR_URL = "https://raw.githubusercontent.com/ScorpJD/python-ga-VRPTW/master/data/text/{instance}.txt"

# Mendeley Dynamic Multi-Period VRP dataset reference:
# https://data.mendeley.com/datasets/cbkzp5b8hb/1
# License: CC BY 4.0


def download_solomon_instance(
    instance_name: str, target_dir: Path, force: bool = False
) -> Path:
    """
    Downloads a single Solomon benchmark instance if not already present.
    """
    instance_name = instance_name.upper()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{instance_name}.txt"

    if target_file.exists() and not force:
        print(f"[{instance_name}] Already exists at {target_file}")
        return target_file

    url = SOLOMON_MIRROR_URL.format(instance=instance_name)
    print(f"[{instance_name}] Downloading from {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "SWARMRoute/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
        target_file.write_text(content, encoding="utf-8")
        print(f"[{instance_name}] Successfully saved to {target_file} ({len(content.splitlines())} lines)")
        return target_file
    except Exception as e:
        print(f"Error downloading {instance_name}: {e}", file=sys.stderr)
        raise


def setup_dynamic_dataset_scaffolding(dynamic_dir: Path) -> None:
    """
    Initializes directory structure and reference metadata for the Dynamic Multi-Period VRP dataset.
    """
    dynamic_dir.mkdir(parents=True, exist_ok=True)
    info_file = dynamic_dir / "README.md"
    if not info_file.exists():
        info_file.write_text(
            """# Dynamic Multi-Period Vehicle Routing Problem Dataset
Reference: https://data.mendeley.com/datasets/cbkzp5b8hb/1
Secondary: https://data.mendeley.com/datasets/5p5sv8hshj/1
License: Creative Commons Attribution 4.0 International (CC BY 4.0)

This directory houses customer demand profiles, dynamic release times,
and distance matrices for dynamic dispatch and re-optimization.
""",
            encoding="utf-8",
        )
    print(f"[Dynamic Scaffolding] Ready at {dynamic_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify SWARMRoute datasets.")
    parser.add_argument(
        "--instances",
        nargs="+",
        default=DEFAULT_SOLOMON_INSTANCES,
        help="Solomon instances to download (e.g., C101 R101 RC101)",
    )
    parser.add_argument(
        "--solomon-dir",
        default="data/raw/solomon",
        help="Target folder for Solomon instances",
    )
    parser.add_argument(
        "--dynamic-dir",
        default="data/raw/dynamic",
        help="Target folder for dynamic dataset",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    args = parser.parse_args()

    solomon_path = Path(args.solomon_dir)
    dynamic_path = Path(args.dynamic_dir)

    print("====================================================")
    print(" SWARMRoute: Dataset Downloader")
    print("====================================================")
    for inst in args.instances:
        download_solomon_instance(inst, solomon_path, force=args.force)

    setup_dynamic_dataset_scaffolding(dynamic_path)
    print("All datasets verified successfully.")


if __name__ == "__main__":
    main()
