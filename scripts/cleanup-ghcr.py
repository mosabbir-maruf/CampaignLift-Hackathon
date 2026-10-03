#!/usr/bin/env python3
"""GHCR Container Image Retention and Cleanup Script for CampaignLift.

Retains the newest TWO versions for each target application package:
  - campaignlift-frontend
  - campaignlift-backend
and prunes older versions.

Uses standard Python library (urllib) only — no external dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

TARGET_PACKAGES = [
    "campaignlift-frontend",
    "campaignlift-backend",
]


def github_request(
    url: str,
    token: str,
    method: str = "GET",
) -> Tuple[int, Any]:
    """Execute authenticated GitHub REST API request."""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "CampaignLift-GHCR-Retention/1.0")

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            if body:
                return status, json.loads(body)
            return status, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed


def get_package_versions(
    owner: str,
    package_name: str,
    token: str,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Fetch package versions, trying org endpoint first and falling back to user endpoint."""
    # 1. Try organization endpoint
    org_url = f"https://api.github.com/orgs/{owner}/packages/container/{package_name}/versions?per_page=100"
    status, data = github_request(org_url, token)

    if status == 200 and isinstance(data, list):
        return "org", data

    # 2. Try user endpoint
    user_url = f"https://api.github.com/users/{owner}/packages/container/{package_name}/versions?per_page=100"
    status, data = github_request(user_url, token)

    if status == 200 and isinstance(data, list):
        return "user", data

    # If package doesn't exist yet (e.g. initial run)
    if status == 404:
        print(f"Package '{package_name}' not found under owner '{owner}' (status 404). It may not be published yet.")
        return None, []

    print(f"Warning: Could not fetch versions for '{package_name}': status {status}, response: {data}")
    return None, []


def delete_package_version(
    entity_type: str,
    owner: str,
    package_name: str,
    version_id: int,
    token: str,
) -> bool:
    """Delete a specific package version by ID."""
    if entity_type == "org":
        url = f"https://api.github.com/orgs/{owner}/packages/container/{package_name}/versions/{version_id}"
    else:
        url = f"https://api.github.com/users/{owner}/packages/container/{package_name}/versions/{version_id}"

    status, resp = github_request(url, token, method="DELETE")
    if status in (204, 200):
        return True

    print(f"Warning: Failed to delete version {version_id} ({status}): {resp}")
    if status in (403, 401):
        print(
            "Note: Package deletion requires admin / packages:delete scope. "
            "Default GITHUB_TOKEN may lack permission to delete packages on some runners."
        )
    return False


def clean_package(
    owner: str,
    package_name: str,
    token: str,
    retain_count: int = 2,
    dry_run: bool = False,
) -> None:
    """Clean up older versions of a single container package."""
    print(f"\n=======================================================")
    print(f"Evaluating package: {package_name} (owner: {owner})")
    print(f"=======================================================")

    entity_type, versions = get_package_versions(owner, package_name, token)
    if not entity_type or not versions:
        print(f"No active versions to clean for '{package_name}'.")
        return

    # Sort versions by created_at descending (newest first)
    versions.sort(key=lambda v: v.get("created_at", ""), reverse=True)
    total_versions = len(versions)
    print(f"Total published versions found: {total_versions}")

    for idx, v in enumerate(versions):
        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
        created = v.get("created_at", "unknown")
        vid = v.get("id")
        print(f"  [{idx + 1}] ID: {vid} | Created: {created} | Tags: {tags}")

    if total_versions <= retain_count:
        print(f"Package has {total_versions} versions (<= retain threshold {retain_count}). No cleanup required.")
        return

    keep_versions = versions[:retain_count]
    candidate_deletions = versions[retain_count:]

    print(f"\nRetaining {len(keep_versions)} newest versions:")
    for v in keep_versions:
        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
        print(f"  ✓ KEEP: ID {v.get('id')} (Tags: {tags})")

    to_delete: List[Dict[str, Any]] = []
    for v in candidate_deletions:
        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
        # Critical multi-arch safety: never delete untagged versions (these are platform sub-manifests)
        if not tags:
            print(f"  ✓ PRESERVE: ID {v.get('id')} has no tags (multi-arch child manifest). Skipping deletion.")
            continue
        # Safety guarantee: never delete if tagged with 'latest'
        if "latest" in tags:
            print(f"  ✓ PRESERVE: ID {v.get('id')} has 'latest' tag. Skipping deletion.")
            continue
        to_delete.append(v)

    if not to_delete:
        print("No older versions eligible for deletion after safety checks.")
        return

    print(f"\nEligible for deletion ({len(to_delete)} versions):")
    for v in to_delete:
        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
        vid = v.get("id")
        if dry_run:
            print(f"  [DRY-RUN] Would delete version ID {vid} (Tags: {tags})")
        else:
            print(f"  Deleting version ID {vid} (Tags: {tags})...")
            success = delete_package_version(entity_type, owner, package_name, vid, token)
            if success:
                print(f"    ✓ Successfully deleted version ID {vid}")
            else:
                print(f"    ✗ Deletion skipped or failed for version ID {vid}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean up old GHCR package versions, retaining the newest 2.")
    parser.add_argument("--owner", required=True, help="GitHub organization or user owner name")
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub Personal Access Token or GITHUB_TOKEN (defaults to GITHUB_TOKEN env)",
    )
    parser.add_argument("--retain", type=int, default=2, help="Number of newest versions to retain (default: 2)")
    parser.add_argument(
        "--packages",
        nargs="+",
        default=TARGET_PACKAGES,
        help="Target packages to inspect and clean (default: campaignlift-frontend campaignlift-backend)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate cleanup without deleting packages")
    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("Notice: No GITHUB_TOKEN provided. Skipping GHCR package retention cleanup.")
        return 0

    owner = args.owner.lower()
    print(f"Starting GHCR retention cleanup for owner: {owner} (Retain newest: {args.retain})")
    if args.dry_run:
        print("[MODE] DRY-RUN enabled: No package versions will actually be deleted.")

    for pkg in args.packages:
        try:
            clean_package(
                owner=owner,
                package_name=pkg,
                token=token,
                retain_count=args.retain,
                dry_run=args.dry_run,
            )
        except Exception as e:
            print(f"Non-fatal error cleaning package '{pkg}': {e}")

    print("\nGHCR retention cleanup evaluation completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
