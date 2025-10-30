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
import tarfile
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable
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
UPDATE_STATUS_FILE = "/opt/xui-manager/.update_status.json"

# Files/directories to update (only code, not config or data)
FILES_TO_UPDATE = [
    "app/",
    "templates/",
    "requirements.txt",
    "README.md"
]

# Files/directories to NEVER touch
FILES_TO_SKIP = [
    "config.json",
    "xui.db",
    ".env",
    "venv/",
    "__pycache__/",
    "*.pyc",
    "backups/",
    ".git/",
    "last_update_check.json",
    ".update_lock",
    ".update_status.json"
]


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
            # Ensure directory exists
            os.makedirs(os.path.dirname(LAST_CHECK_FILE), exist_ok=True)
            with open(LAST_CHECK_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving last check data: {e}", exc_info=True)

    def _update_status(self, status: str, progress: int = 0, message: str = "", details: Dict = None):
        """Update and save current update status for progress tracking"""
        try:
            status_data = {
                "status": status,  # downloading, extracting, installing, restarting, completed, failed
                "progress": progress,  # 0-100
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "details": details or {}
            }

            os.makedirs(os.path.dirname(UPDATE_STATUS_FILE), exist_ok=True)
            with open(UPDATE_STATUS_FILE, 'w') as f:
                json.dump(status_data, f, indent=2)

            logger.info(f"Update status: {status} - {progress}% - {message}")
        except Exception as e:
            logger.error(f"Error saving update status: {e}", exc_info=True)

    def get_update_status(self) -> Dict:
        """Get current update status"""
        try:
            if os.path.exists(UPDATE_STATUS_FILE):
                with open(UPDATE_STATUS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading update status: {e}")

        return {
            "status": "idle",
            "progress": 0,
            "message": "",
            "timestamp": None,
            "details": {}
        }

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

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(GITHUB_API_URL) as response:
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
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(UPDATE_LOCK_FILE), exist_ok=True)
            Path(UPDATE_LOCK_FILE).touch()
        except Exception as e:
            logger.error(f"Error creating lock file: {e}", exc_info=True)
            raise

    def _remove_update_lock(self):
        """Remove update lock file"""
        try:
            os.remove(UPDATE_LOCK_FILE)
        except:
            pass

    async def perform_update(self) -> Dict:
        """
        Perform system update by downloading from GitHub release

        Process:
        1. Check for updates
        2. Create backup
        3. Download tarball from GitHub
        4. Extract only code files (app/, templates/, requirements.txt)
        5. Install dependencies if requirements.txt changed
        6. Restart service

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
            self._update_status("checking", 5, "Проверка обновлений...")

            # Check if update is available
            update_info = await self.check_for_updates(force=True)
            if not update_info.get("update_available"):
                self._remove_update_lock()
                self._update_status("failed", 0, "Обновления не найдены")
                return {
                    "success": False,
                    "error": "No update available",
                    "current_version": CURRENT_VERSION
                }

            logger.info(f"Starting update from {CURRENT_VERSION} to {update_info['latest_version']}")
            self._update_status("backup", 10, "Создание резервной копии...")

            # Create backup before update
            backup_result = self._create_backup()
            if not backup_result["success"]:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка бэкапа: {backup_result['error']}")
                return {
                    "success": False,
                    "error": f"Backup failed: {backup_result['error']}"
                }

            self._update_status("downloading", 20, "Скачивание обновления с GitHub...")

            # Download update from GitHub
            download_result = await self._download_update(update_info["download_url"])
            if not download_result["success"]:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка загрузки: {download_result['error']}")
                return {
                    "success": False,
                    "error": f"Download failed: {download_result['error']}",
                    "backup_file": backup_result.get("backup_file")
                }

            self._update_status("extracting", 50, "Распаковка файлов...")

            # Extract and install files
            install_result = await self._install_update(download_result["temp_dir"])
            if not install_result["success"]:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка установки: {install_result['error']}")
                return {
                    "success": False,
                    "error": f"Installation failed: {install_result['error']}",
                    "backup_file": backup_result.get("backup_file")
                }

            self._update_status("dependencies", 80, "Установка зависимостей...")

            # Install dependencies if requirements changed
            if install_result.get("requirements_changed"):
                deps_result = self._install_dependencies()
                if not deps_result["success"]:
                    logger.warning(f"Dependencies installation warning: {deps_result.get('error')}")

            self._update_status("restarting", 90, "Перезапуск сервиса...")

            # Restart service
            restart_result = self._restart_service()

            self._remove_update_lock()
            self._update_status("completed", 100, "Обновление завершено!")

            return {
                "success": True,
                "message": "Update completed successfully",
                "previous_version": CURRENT_VERSION,
                "new_version": update_info["latest_version"],
                "backup_file": backup_result.get("backup_file"),
                "service_restarted": restart_result["success"],
                "files_updated": install_result.get("files_updated", []),
                "requirements_changed": install_result.get("requirements_changed", False)
            }

        except Exception as e:
            logger.error(f"Error during update: {e}", exc_info=True)
            self._remove_update_lock()
            self._update_status("failed", 0, f"Ошибка: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _create_backup(self) -> Dict:
        """Create backup of current installation

        Excludes temporary files, logs, and backups directory to avoid conflicts
        tar exit code 1 (file changed as we read it) is considered success
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"/opt/xui-manager/backups/backup_{timestamp}.tar.gz"

            os.makedirs("/opt/xui-manager/backups", exist_ok=True)

            # Create tar archive of important files
            # Exclude changing files to prevent "file changed as we read it" errors
            result = subprocess.run(
                [
                    "tar", "-czf", backup_file,
                    "-C", "/opt/xui-manager",
                    "--exclude=venv",
                    "--exclude=.git",
                    "--exclude=__pycache__",
                    "--exclude=*.pyc",
                    "--exclude=*.log",
                    "--exclude=backups",  # Don't backup backups!
                    "--exclude=.update_status.json",
                    "--exclude=.update_lock",
                    "--exclude=last_update_check.json",
                    "--exclude=queues.json",
                    "--exclude=*.db-journal",
                    "--exclude=*.db-wal",
                    "--exclude=*.db-shm",
                    "."
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            # tar exit codes:
            # 0 = success
            # 1 = some files changed during archival (acceptable)
            # 2+ = critical error
            if result.returncode == 0 or result.returncode == 1:
                logger.info(f"Backup created: {backup_file} (exit code: {result.returncode})")
                if result.returncode == 1:
                    logger.info("Some files changed during backup (expected for active system)")
                return {
                    "success": True,
                    "backup_file": backup_file
                }
            else:
                logger.error(f"Backup failed with exit code {result.returncode}: {result.stderr}")
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

    async def _download_update(self, tarball_url: str) -> Dict:
        """Download release tarball from GitHub"""
        try:
            temp_dir = tempfile.mkdtemp(prefix="xui-update-")
            tarball_path = os.path.join(temp_dir, "release.tar.gz")

            logger.info(f"Downloading from {tarball_url}")

            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(tarball_url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")

                    # Download with progress tracking
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    with open(tarball_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0:
                                progress = 20 + int(30 * downloaded / total_size)  # 20-50%
                                self._update_status("downloading", progress,
                                                  f"Скачано {downloaded // 1024} KB из {total_size // 1024} KB")

            logger.info(f"Downloaded to {tarball_path}")

            # Extract tarball
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with tarfile.open(tarball_path, 'r:gz') as tar:
                tar.extractall(extract_dir)

            # GitHub tarballs have a root directory, find it
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1:
                source_dir = os.path.join(extract_dir, extracted_items[0])
            else:
                source_dir = extract_dir

            return {
                "success": True,
                "temp_dir": source_dir,
                "tarball_path": tarball_path
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Download timeout"
            }
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def _install_update(self, source_dir: str) -> Dict:
        """Install update by copying only code files"""
        try:
            install_dir = "/opt/xui-manager"
            files_updated = []
            requirements_changed = False

            # Check if requirements.txt will change
            old_req = os.path.join(install_dir, "requirements.txt")
            new_req = os.path.join(source_dir, "requirements.txt")
            if os.path.exists(old_req) and os.path.exists(new_req):
                with open(old_req, 'r') as f1, open(new_req, 'r') as f2:
                    requirements_changed = (f1.read() != f2.read())

            # Update only code files
            for item in FILES_TO_UPDATE:
                source_path = os.path.join(source_dir, item)
                dest_path = os.path.join(install_dir, item)

                if not os.path.exists(source_path):
                    logger.warning(f"Source path not found: {source_path}")
                    continue

                # If it's a directory, copy recursively
                if item.endswith('/'):
                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)
                    shutil.copytree(source_path, dest_path)
                    files_updated.append(item)
                    logger.info(f"Updated directory: {item}")
                else:
                    # Copy file
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    files_updated.append(item)
                    logger.info(f"Updated file: {item}")

            # Clean up temp directory
            try:
                shutil.rmtree(os.path.dirname(os.path.dirname(source_dir)))
            except:
                pass

            return {
                "success": True,
                "files_updated": files_updated,
                "requirements_changed": requirements_changed
            }

        except Exception as e:
            logger.error(f"Installation error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _install_dependencies(self) -> Dict:
        """Install Python dependencies from requirements.txt"""
        try:
            venv_python = "/opt/xui-manager/venv/bin/python"
            requirements_file = "/opt/xui-manager/requirements.txt"

            # Check if venv exists
            if not os.path.exists(venv_python):
                venv_python = "python3"  # Fallback to system python

            logger.info("Installing dependencies...")

            result = subprocess.run(
                [venv_python, "-m", "pip", "install", "-r", requirements_file, "--no-cache-dir"],
                capture_output=True,
                text=True,
                timeout=180  # 3 minutes
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Pip install timeout"
            }
        except Exception as e:
            logger.error(f"Dependencies installation error: {e}")
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
