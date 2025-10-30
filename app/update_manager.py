"""
Update Manager for XUI Manager
Handles checking for updates, downloading, and applying them safely
"""

import asyncio
import aiohttp
import subprocess
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path

from app.version import (
    CURRENT_VERSION,
    Version,
    GITHUB_API_URL,
    GITHUB_REPO,
    parse_changelog
)

logger = logging.getLogger(__name__)

# Update check configuration
UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
LAST_CHECK_FILE = "/opt/xui-manager/last_update_check.json"
UPDATE_LOCK_FILE = "/opt/xui-manager/.update_lock"


class UpdateManager:
    """Manages software updates from GitHub releases"""

    def __init__(self):
        self.current_version = Version(CURRENT_VERSION)
        self.last_check_data = self._load_last_check()

    def _load_last_check(self) -> Dict:
        """Load last update check data from file"""
        try:
            if os.path.exists(LAST_CHECK_FILE):
                with open(LAST_CHECK_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading last check data: {e}")
        return {
            "last_check": None,
            "latest_version": None,
            "update_available": False
        }

    def _save_last_check(self, data: Dict):
        """Save update check data to file"""
        try:
            with open(LAST_CHECK_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving last check data: {e}")

    async def check_for_updates(self, force: bool = False) -> Dict:
        """
        Check GitHub for latest release

        Args:
            force: Force check even if checked recently

        Returns:
            Dict with update information
        """
        # Check if we need to update (avoid too frequent checks)
        if not force and self.last_check_data.get("last_check"):
            last_check = datetime.fromisoformat(self.last_check_data["last_check"])
            if datetime.now() - last_check < timedelta(hours=1):
                logger.info("Using cached update check data")
                return {
                    "current_version": CURRENT_VERSION,
                    "latest_version": self.last_check_data.get("latest_version"),
                    "update_available": self.last_check_data.get("update_available", False),
                    "cached": True,
                    "last_check": self.last_check_data["last_check"]
                }

        try:
            logger.info(f"Checking for updates from {GITHUB_API_URL}")

            async with aiohttp.ClientSession() as session:
                async with session.get(GITHUB_API_URL, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"GitHub API returned status {response.status}")

                    data = await response.json()

                    latest_tag = data.get("tag_name", "").lstrip('v')
                    latest_version = Version(latest_tag)

                    update_available = latest_version > self.current_version

                    changelog = parse_changelog(data.get("body", ""))

                    result = {
                        "current_version": str(self.current_version),
                        "latest_version": str(latest_version),
                        "update_available": update_available,
                        "release_name": data.get("name"),
                        "release_date": data.get("published_at"),
                        "release_url": data.get("html_url"),
                        "changelog": changelog,
                        "download_url": data.get("tarball_url"),
                        "cached": False,
                        "last_check": datetime.now().isoformat()
                    }

                    # Save check data
                    self._save_last_check({
                        "last_check": result["last_check"],
                        "latest_version": str(latest_version),
                        "update_available": update_available
                    })

                    self.last_check_data = {
                        "last_check": result["last_check"],
                        "latest_version": str(latest_version),
                        "update_available": update_available
                    }

                    return result

        except asyncio.TimeoutError:
            logger.error("Timeout while checking for updates")
            return {
                "error": "Timeout connecting to GitHub",
                "current_version": CURRENT_VERSION,
                "cached": False
            }
        except Exception as e:
            logger.error(f"Error checking for updates: {e}", exc_info=True)
            return {
                "error": str(e),
                "current_version": CURRENT_VERSION,
                "cached": False
            }

    def is_update_in_progress(self) -> bool:
        """Check if update is currently in progress"""
        return os.path.exists(UPDATE_LOCK_FILE)

    def _create_update_lock(self):
        """Create lock file to prevent concurrent updates"""
        Path(UPDATE_LOCK_FILE).touch()

    def _remove_update_lock(self):
        """Remove update lock file"""
        try:
            os.remove(UPDATE_LOCK_FILE)
        except:
            pass

    async def perform_update(self) -> Dict:
        """
        Perform system update using git pull

        Returns:
            Dict with update result
        """
        if self.is_update_in_progress():
            return {
                "success": False,
                "error": "Update already in progress"
            }

        try:
            self._create_update_lock()

            # Check if update is available
            update_info = await self.check_for_updates(force=True)
            if not update_info.get("update_available"):
                self._remove_update_lock()
                return {
                    "success": False,
                    "error": "No update available",
                    "current_version": CURRENT_VERSION
                }

            logger.info(f"Starting update from {CURRENT_VERSION} to {update_info['latest_version']}")

            # Create backup before update
            backup_result = self._create_backup()
            if not backup_result["success"]:
                self._remove_update_lock()
                return {
                    "success": False,
                    "error": f"Backup failed: {backup_result['error']}"
                }

            # Perform git pull
            update_result = self._git_pull_update()

            if update_result["success"]:
                # Restart service
                restart_result = self._restart_service()

                self._remove_update_lock()

                return {
                    "success": True,
                    "message": "Update completed successfully",
                    "previous_version": CURRENT_VERSION,
                    "new_version": update_info["latest_version"],
                    "backup_file": backup_result.get("backup_file"),
                    "service_restarted": restart_result["success"],
                    "changes": update_result.get("changes", [])
                }
            else:
                self._remove_update_lock()
                return {
                    "success": False,
                    "error": update_result.get("error", "Unknown error"),
                    "backup_file": backup_result.get("backup_file")
                }

        except Exception as e:
            logger.error(f"Error during update: {e}", exc_info=True)
            self._remove_update_lock()
            return {
                "success": False,
                "error": str(e)
            }

    def _create_backup(self) -> Dict:
        """Create backup of current installation"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"/opt/xui-manager/backups/backup_{timestamp}.tar.gz"

            os.makedirs("/opt/xui-manager/backups", exist_ok=True)

            # Create tar archive of important files
            result = subprocess.run(
                [
                    "tar", "-czf", backup_file,
                    "-C", "/opt/xui-manager",
                    "--exclude=venv",
                    "--exclude=.git",
                    "--exclude=__pycache__",
                    "--exclude=*.pyc",
                    "."
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Backup created: {backup_file}")
                return {
                    "success": True,
                    "backup_file": backup_file
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }

        except Exception as e:
            logger.error(f"Backup error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _git_pull_update(self) -> Dict:
        """Pull latest changes from git repository"""
        try:
            # Fetch latest changes
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd="/opt/xui-manager",
                capture_output=True,
                text=True,
                timeout=30
            )

            if fetch_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Git fetch failed: {fetch_result.stderr}"
                }

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd="/opt/xui-manager",
                capture_output=True,
                text=True,
                timeout=10
            )

            current_branch = branch_result.stdout.strip()

            # Pull changes
            pull_result = subprocess.run(
                ["git", "pull", "origin", current_branch],
                cwd="/opt/xui-manager",
                capture_output=True,
                text=True,
                timeout=30
            )

            if pull_result.returncode == 0:
                # Get list of changed files
                changes = pull_result.stdout.strip().split('\n')

                return {
                    "success": True,
                    "branch": current_branch,
                    "changes": changes
                }
            else:
                return {
                    "success": False,
                    "error": pull_result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Git operation timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _restart_service(self) -> Dict:
        """Restart xui-manager service using sudo"""
        try:
            # Try with sudo first (requires sudoers configuration)
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "xui-manager"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": "Service restarted successfully",
                    "method": "sudo"
                }

            # If sudo failed, try without sudo (for development)
            logger.warning("Sudo restart failed, trying without sudo")
            result = subprocess.run(
                ["systemctl", "restart", "xui-manager"],
                capture_output=True,
                text=True,
                timeout=10
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr,
                "method": "direct",
                "warning": "Restart may require sudo privileges"
            }

        except subprocess.TimeoutExpired:
            logger.error("Service restart timed out")
            return {
                "success": False,
                "error": "Service restart timed out"
            }
        except Exception as e:
            logger.error(f"Service restart error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
update_manager = UpdateManager()
