"""
Version Management System for XUI Manager
Handles version checking, comparison, and update information
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import re

# Current application version (Semantic Versioning: MAJOR.MINOR.PATCH)
CURRENT_VERSION = "2.5.0"
VERSION_NAME = "Presets & Enhanced UI"
GITHUB_REPO = "khiziresmars/xmanager"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class Version:
    """Semantic version parser and comparator"""

    def __init__(self, version_string: str):
        """
        Parse semantic version string (e.g., "1.2.3", "v1.2.3")

        Args:
            version_string: Version in format "MAJOR.MINOR.PATCH" or "vMAJOR.MINOR.PATCH"
        """
        # Remove 'v' prefix if present
        clean_version = version_string.lstrip('v')

        # Parse version parts
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$', clean_version)
        if not match:
            raise ValueError(f"Invalid version format: {version_string}")

        self.major = int(match.group(1))
        self.minor = int(match.group(2))
        self.patch = int(match.group(3))
        self.prerelease = match.group(4)  # e.g., "beta", "rc1"

    def __str__(self) -> str:
        """Return version as string"""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version

    def __eq__(self, other: 'Version') -> bool:
        """Check if versions are equal"""
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: 'Version') -> bool:
        """Check if this version is less than other"""
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: 'Version') -> bool:
        """Check if this version is less than or equal to other"""
        return self < other or self == other

    def __gt__(self, other: 'Version') -> bool:
        """Check if this version is greater than other"""
        return not self <= other

    def __ge__(self, other: 'Version') -> bool:
        """Check if this version is greater than or equal to other"""
        return not self < other


def get_current_version() -> Dict:
    """
    Get current application version information

    Returns:
        Dict with version details
    """
    return {
        "version": CURRENT_VERSION,
        "name": VERSION_NAME,
        "repository": GITHUB_REPO,
        "timestamp": datetime.now().isoformat()
    }


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two semantic versions

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = Version(version1)
    v2 = Version(version2)

    if v1 < v2:
        return -1
    elif v1 == v2:
        return 0
    else:
        return 1


def parse_changelog(changelog_text: str) -> Dict:
    """
    Parse changelog text from GitHub release notes

    Args:
        changelog_text: Raw changelog text

    Returns:
        Parsed changelog with features, fixes, and breaking changes
    """
    lines = changelog_text.split('\n')

    changelog = {
        "features": [],
        "fixes": [],
        "breaking_changes": [],
        "other": []
    }

    current_section = "other"

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Detect section headers
        if 'feature' in line.lower() or 'new' in line.lower():
            current_section = "features"
            continue
        elif 'fix' in line.lower() or 'bug' in line.lower():
            current_section = "fixes"
            continue
        elif 'breaking' in line.lower():
            current_section = "breaking_changes"
            continue

        # Add line to current section
        if line.startswith('-') or line.startswith('*'):
            line = line.lstrip('-*').strip()
            changelog[current_section].append(line)

    return changelog


def get_version_info() -> Dict:
    """
    Get comprehensive version information

    Returns:
        Dict with current version, build date, and metadata
    """
    current = Version(CURRENT_VERSION)

    return {
        "current_version": str(current),
        "version_name": VERSION_NAME,
        "major": current.major,
        "minor": current.minor,
        "patch": current.patch,
        "is_prerelease": bool(current.prerelease),
        "prerelease_tag": current.prerelease,
        "repository": GITHUB_REPO,
        "github_url": f"https://github.com/{GITHUB_REPO}",
        "releases_url": f"https://github.com/{GITHUB_REPO}/releases",
        "api_url": GITHUB_API_URL
    }
