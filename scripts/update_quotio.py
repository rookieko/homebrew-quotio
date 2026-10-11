#!/usr/bin/env python3
"""Update the cask from Quotio's latest stable GitHub release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request


RELEASE_API = "https://api.github.com/repos/nguyenphutrong/quotio/releases/latest"
RELEASE_BASE = "https://github.com/nguyenphutrong/quotio/releases/download"
VERSION_PATTERN = r'^(\s*version ")([0-9]+\.[0-9]+\.[0-9]+)("\s*)$'
SHA_PATTERN = r'^(\s*sha256 ")([a-f0-9]{64})("\s*)$'


def latest_release():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rookieko-homebrew-quotio-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(RELEASE_API, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def release_asset(release):
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Refusing a draft or prerelease")
    tag = release.get("tag_name", "")
    # The cask's URL uses v#{version}, so reject incompatible tag conventions.
    match = re.fullmatch(r"v([0-9]+\.[0-9]+\.[0-9]+)", tag)
    if not match:
        raise ValueError(f"Unexpected stable release tag: {tag!r}")
    version = match.group(1)
    name = f"Quotio-{version}.dmg"
    assets = [asset for asset in release.get("assets", []) if asset.get("name") == name]
    if len(assets) != 1:
        raise ValueError(f"Expected exactly one {name} asset")
    asset = assets[0]
    expected_url = f"{RELEASE_BASE}/{tag}/{name}"
    if asset.get("browser_download_url") != expected_url:
        raise ValueError("Unexpected DMG download URL")
    if asset.get("state") != "uploaded" or not isinstance(asset.get("size"), int) or asset["size"] <= 0:
        raise ValueError("DMG upload is incomplete")
    digest = asset.get("digest")
    if digest is not None and not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("Unexpected GitHub asset digest")
    return version, asset


def download_sha256(asset):
    # Do not send the API token to the public asset URL or its redirect hosts.
    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "rookieko-homebrew-quotio-updater"},
    )
    checksum = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        while chunk := response.read(1024 * 1024):
            checksum.update(chunk)
            size += len(chunk)
    if size != asset["size"]:
        raise ValueError(f"DMG size mismatch: expected {asset['size']}, got {size}")
    digest = checksum.hexdigest()
    if asset.get("digest") and asset["digest"] != f"sha256:{digest}":
        raise ValueError("Downloaded DMG does not match GitHub's SHA256 digest")
    return digest


def update_cask(path, release):
    text = path.read_text()
    versions = re.findall(VERSION_PATTERN, text, re.MULTILINE)
    checksums = re.findall(SHA_PATTERN, text, re.MULTILINE)
    if len(versions) != 1 or len(checksums) != 1:
        raise ValueError("Expected one version and one SHA256 in the cask")
    current_version, current_sha = versions[0][1], checksums[0][1]
    version, asset = release_asset(release)
    if tuple(map(int, version.split("."))) < tuple(map(int, current_version.split("."))):
        print(f"Keeping {current_version}; upstream latest is older ({version})")
        return False, current_version
    if version == current_version and asset.get("digest") == f"sha256:{current_sha}":
        print(f"Quotio {version} is already up to date")
        return False, version
    digest = download_sha256(asset)
    if version == current_version and digest == current_sha:
        print(f"Quotio {version} is already up to date")
        return False, version
    updated = re.sub(VERSION_PATTERN, lambda m: m[1] + version + m[3], text, flags=re.MULTILINE)
    updated = re.sub(SHA_PATTERN, lambda m: m[1] + digest + m[3], updated, flags=re.MULTILINE)
    path.write_text(updated)
    print(f"Updated Quotio {current_version} -> {version}; sha256 {digest}")
    return True, version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cask", type=Path, default=Path(__file__).resolve().parents[1] / "Casks/quotio.rb")
    args = parser.parse_args()
    changed, version = update_cask(args.cask, latest_release())
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as stream:
            stream.write(f"changed={str(changed).lower()}\nversion={version}\n")


if __name__ == "__main__":
    main()
