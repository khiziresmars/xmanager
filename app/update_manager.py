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
from app.config import settings

logger = logging.getLogger(__name__)


def _get_github_headers() -> Dict:
    """Get headers for GitHub API requests, including auth token if configured"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "XUI-Manager"
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers

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
                # Recalculate update_available based on current version
                cached_latest = self.last_check_data.get("latest_version", CURRENT_VERSION)
                try:
                    update_available = Version(cached_latest) > self.current_version
                except:
                    update_available = False
                return {
                    "current_version": CURRENT_VERSION,
                    "latest_version": cached_latest,
                    "update_available": update_available,
                    "cached": True,
                    "last_check": self.last_check_data["last_check"]
                }

        try:
            logger.info(f"Checking for updates from {GITHUB_API_URL}")

            timeout = aiohttp.ClientTimeout(total=10)
            headers = _get_github_headers()
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
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
            headers = _get_github_headers()
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
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

    async def perform_update_to_version(self, version: str = None, force: bool = False, backup: bool = True) -> Dict:
        """
        Perform update to specific version or latest

        Args:
            version: Specific version to update to (e.g., "1.4.0") or None for latest
            force: Force update even if same version
            backup: Create backup before updating

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
            self._update_status("checking", 5, "Получение информации о версии...")

            # Get release info
            if version:
                release_info = await self._get_release_by_version(version)
            else:
                release_info = await self.check_for_updates(force=True)

            if "error" in release_info:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка: {release_info['error']}")
                return {
                    "success": False,
                    "error": release_info["error"]
                }

            target_version = release_info.get("latest_version") or release_info.get("version")
            download_url = release_info.get("download_url")

            if not download_url:
                self._remove_update_lock()
                return {"success": False, "error": "Download URL not found"}

            # Check if update needed
            if not force and target_version == CURRENT_VERSION:
                self._remove_update_lock()
                self._update_status("idle", 0, "Уже установлена актуальная версия")
                return {
                    "success": False,
                    "error": f"Already on version {CURRENT_VERSION}",
                    "current_version": CURRENT_VERSION
                }

            logger.info(f"Starting update from {CURRENT_VERSION} to {target_version}")

            # Backup
            backup_file = None
            if backup:
                self._update_status("backup", 10, "Создание резервной копии...")
                backup_result = self._create_backup()
                if not backup_result["success"]:
                    self._remove_update_lock()
                    self._update_status("failed", 0, f"Ошибка бэкапа: {backup_result['error']}")
                    return {
                        "success": False,
                        "error": f"Backup failed: {backup_result['error']}"
                    }
                backup_file = backup_result.get("backup_file")

            # Download
            self._update_status("downloading", 20, "Скачивание обновления...")
            download_result = await self._download_update(download_url)
            if not download_result["success"]:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка загрузки: {download_result['error']}")
                return {
                    "success": False,
                    "error": f"Download failed: {download_result['error']}",
                    "backup_file": backup_file
                }

            # Install
            self._update_status("extracting", 50, "Установка файлов...")
            install_result = await self._install_update(download_result["temp_dir"])
            if not install_result["success"]:
                self._remove_update_lock()
                self._update_status("failed", 0, f"Ошибка установки: {install_result['error']}")
                return {
                    "success": False,
                    "error": f"Installation failed: {install_result['error']}",
                    "backup_file": backup_file
                }

            # Dependencies
            self._update_status("dependencies", 80, "Установка зависимостей...")
            if install_result.get("requirements_changed"):
                deps_result = self._install_dependencies()
                if not deps_result["success"]:
                    logger.warning(f"Dependencies warning: {deps_result.get('error')}")

            # Restart
            self._update_status("restarting", 90, "Перезапуск сервиса...")
            restart_result = self._restart_service()

            self._remove_update_lock()
            self._update_status("completed", 100, "Обновление завершено!")

            return {
                "success": True,
                "message": "Update completed successfully",
                "old_version": CURRENT_VERSION,
                "new_version": target_version,
                "backup_path": backup_file,
                "restart_required": True,
                "service_restarted": restart_result["success"]
            }

        except Exception as e:
            logger.error(f"Error during update: {e}", exc_info=True)
            self._remove_update_lock()
            self._update_status("failed", 0, f"Ошибка: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_release_by_version(self, version: str) -> Dict:
        """Get specific release info from GitHub"""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/v{version}"

            timeout = aiohttp.ClientTimeout(total=10)
            headers = _get_github_headers()
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 404:
                        return {"error": f"Version {version} not found"}
                    if response.status != 200:
                        return {"error": f"GitHub API returned {response.status}"}

                    data = await response.json()

                    return {
                        "version": version,
                        "download_url": data.get("tarball_url"),
                        "release_name": data.get("name"),
                        "release_date": data.get("published_at"),
                        "changelog": parse_changelog(data.get("body", ""))
                    }

        except Exception as e:
            logger.error(f"Error getting release {version}: {e}")
            return {"error": str(e)}

    async def get_releases(self, limit: int = 10) -> Dict:
        """Get list of available releases from GitHub"""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page={limit}"

            timeout = aiohttp.ClientTimeout(total=10)
            headers = _get_github_headers()
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {"error": f"GitHub API returned {response.status}"}

                    data = await response.json()

                    releases = []
                    for release in data:
                        releases.append({
                            "version": release.get("tag_name", "").lstrip('v'),
                            "tag_name": release.get("tag_name"),
                            "name": release.get("name"),
                            "published_at": release.get("published_at"),
                            "download_url": release.get("tarball_url"),
                            "html_url": release.get("html_url"),
                            "prerelease": release.get("prerelease", False)
                        })

                    latest = releases[0]["version"] if releases else None

                    return {
                        "releases": releases,
                        "latest": latest,
                        "current_version": CURRENT_VERSION
                    }

        except Exception as e:
            logger.error(f"Error getting releases: {e}")
            return {"error": str(e), "releases": []}

    def list_backups(self) -> List[Dict]:
        """Get list of available backups"""
        backups = []
        backup_dir = "/opt/xui-manager/backups"

        try:
            if not os.path.exists(backup_dir):
                return []

            for filename in sorted(os.listdir(backup_dir), reverse=True):
                if filename.endswith('.tar.gz'):
                    filepath = os.path.join(backup_dir, filename)
                    stat = os.stat(filepath)

                    # Parse timestamp from filename
                    try:
                        timestamp_str = filename.replace('backup_', '').replace('.tar.gz', '')
                        created = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    except:
                        created = datetime.fromtimestamp(stat.st_mtime)

                    backups.append({
                        "filename": filename,
                        "path": filepath,
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created": created.isoformat()
                    })

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    def rollback(self, backup_path: str) -> Dict:
        """Rollback to a previous backup

        Args:
            backup_path: Path to backup file to restore

        Returns:
            Dict with rollback result
        """
        if not os.path.exists(backup_path):
            return {"success": False, "error": "Backup file not found"}

        if self.is_update_in_progress():
            return {"success": False, "error": "Update in progress, cannot rollback"}

        try:
            self._create_update_lock()
            self._update_status("rollback", 10, "Восстановление из резервной копии...")

            install_dir = "/opt/xui-manager"

            # Extract backup to temp directory first
            temp_dir = tempfile.mkdtemp(prefix="xui-rollback-")
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(temp_dir)

            self._update_status("rollback", 50, "Копирование файлов...")

            # Copy files from backup
            for item in FILES_TO_UPDATE:
                source_path = os.path.join(temp_dir, item)
                dest_path = os.path.join(install_dir, item)

                if not os.path.exists(source_path):
                    continue

                if item.endswith('/'):
                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)
                    shutil.copytree(source_path, dest_path)
                else:
                    shutil.copy2(source_path, dest_path)

                logger.info(f"Restored: {item}")

            # Clean up
            shutil.rmtree(temp_dir)

            self._update_status("rollback", 80, "Установка зависимостей...")

            # Reinstall dependencies
            self._install_dependencies()

            self._update_status("rollback", 90, "Перезапуск сервиса...")

            # Restart service
            restart_result = self._restart_service()

            self._remove_update_lock()
            self._update_status("completed", 100, "Откат завершён!")

            # Try to determine restored version
            restored_version = "unknown"
            version_file = os.path.join(install_dir, "app", "version.py")
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        restored_version = match.group(1)

            return {
                "success": True,
                "message": "Rollback completed successfully",
                "restored_version": restored_version,
                "backup_used": backup_path,
                "service_restarted": restart_result["success"]
            }

        except Exception as e:
            logger.error(f"Rollback error: {e}", exc_info=True)
            self._remove_update_lock()
            self._update_status("failed", 0, f"Ошибка отката: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def delete_backup(self, backup_path: str) -> Dict:
        """Delete a specific backup file"""
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "error": "Backup not found"}

            if not backup_path.startswith("/opt/xui-manager/backups/"):
                return {"success": False, "error": "Invalid backup path"}

            os.remove(backup_path)
            logger.info(f"Deleted backup: {backup_path}")

            return {"success": True, "message": f"Deleted {backup_path}"}

        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
            return {"success": False, "error": str(e)}


    # ============================================
    # DEVELOPER MODE: Version Management & Releases
    # ============================================

    async def bump_version(self, bump_type: str = "patch", custom_version: str = None, version_name: str = None) -> Dict:
        """
        Bump version in version.py file

        Args:
            bump_type: 'major', 'minor', or 'patch'
            custom_version: Custom version string (e.g., "2.5.0")
            version_name: Optional new version name

        Returns:
            Dict with old and new version info
        """
        try:
            version_file = "/opt/xui-manager/app/version.py"

            # Read current file
            with open(version_file, 'r') as f:
                content = f.read()

            old_version = CURRENT_VERSION

            # Calculate new version
            if custom_version:
                new_version = custom_version.lstrip('v')
            else:
                current = Version(CURRENT_VERSION)
                if bump_type == "major":
                    new_version = f"{current.major + 1}.0.0"
                elif bump_type == "minor":
                    new_version = f"{current.major}.{current.minor + 1}.0"
                else:  # patch
                    new_version = f"{current.major}.{current.minor}.{current.patch + 1}"

            # Update version in file
            import re
            content = re.sub(
                r'CURRENT_VERSION\s*=\s*"[^"]+"',
                f'CURRENT_VERSION = "{new_version}"',
                content
            )

            # Update version name if provided
            if version_name:
                content = re.sub(
                    r'VERSION_NAME\s*=\s*"[^"]+"',
                    f'VERSION_NAME = "{version_name}"',
                    content
                )

            # Write back
            with open(version_file, 'w') as f:
                f.write(content)

            logger.info(f"Version bumped from {old_version} to {new_version}")

            return {
                "success": True,
                "old_version": old_version,
                "new_version": new_version,
                "version_name": version_name,
                "file": version_file
            }

        except Exception as e:
            logger.error(f"Error bumping version: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def git_commit_and_push(self, commit_message: str, github_token: str = None) -> Dict:
        """
        Commit all changes and push to GitHub

        Args:
            commit_message: Commit message
            github_token: GitHub personal access token (uses settings.GITHUB_TOKEN if not provided)

        Returns:
            Dict with result
        """
        try:
            repo_dir = "/opt/xui-manager"
            token = github_token or settings.GITHUB_TOKEN

            if not token:
                return {"success": False, "error": "GitHub token not configured. Set GITHUB_TOKEN in .env"}

            # Configure git user if not set
            subprocess.run(
                ["git", "config", "user.email", "xui-manager@server.local"],
                cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "XUI Manager"],
                cwd=repo_dir, capture_output=True
            )

            # Stage all changes
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_dir, capture_output=True, text=True
            )
            if result.returncode != 0:
                return {"success": False, "error": f"git add failed: {result.stderr}"}

            # Check if there are changes to commit
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_dir, capture_output=True, text=True
            )
            if not status.stdout.strip():
                return {"success": False, "error": "No changes to commit"}

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=repo_dir, capture_output=True, text=True
            )
            if result.returncode != 0:
                return {"success": False, "error": f"git commit failed: {result.stderr}"}

            # Get remote URL and inject token
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_dir, capture_output=True, text=True
            )
            original_url = remote_result.stdout.strip()

            # Build authenticated URL
            if "github.com" in original_url:
                if original_url.startswith("https://"):
                    # https://github.com/user/repo.git -> https://TOKEN@github.com/user/repo.git
                    auth_url = original_url.replace("https://", f"https://{token}@")
                else:
                    # git@github.com:user/repo.git -> https://TOKEN@github.com/user/repo.git
                    auth_url = original_url.replace("git@github.com:", "https://github.com/")
                    auth_url = auth_url.replace("https://", f"https://{token}@")
            else:
                auth_url = original_url

            # Push with token
            result = subprocess.run(
                ["git", "push", auth_url, "main"],
                cwd=repo_dir, capture_output=True, text=True,
                env={**os.environ, "GIT_ASKPASS": "/bin/true"}
            )

            if result.returncode != 0:
                # Try master branch
                result = subprocess.run(
                    ["git", "push", auth_url, "master"],
                    cwd=repo_dir, capture_output=True, text=True,
                    env={**os.environ, "GIT_ASKPASS": "/bin/true"}
                )

            if result.returncode != 0:
                return {"success": False, "error": f"git push failed: {result.stderr}"}

            logger.info(f"Successfully pushed to GitHub: {commit_message}")

            return {
                "success": True,
                "message": "Changes pushed to GitHub",
                "commit_message": commit_message
            }

        except Exception as e:
            logger.error(f"Error pushing to GitHub: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def create_github_release(
        self,
        version: str,
        release_name: str = None,
        release_notes: str = None,
        github_token: str = None,
        prerelease: bool = False,
        draft: bool = False
    ) -> Dict:
        """
        Create a new release on GitHub

        Args:
            version: Version tag (e.g., "2.5.0")
            release_name: Release title
            release_notes: Release description/changelog
            github_token: GitHub PAT (uses settings.GITHUB_TOKEN if not provided)
            prerelease: Mark as pre-release
            draft: Create as draft

        Returns:
            Dict with release info
        """
        try:
            token = github_token or settings.GITHUB_TOKEN

            if not token:
                return {"success": False, "error": "GitHub token not configured. Set GITHUB_TOKEN in .env"}

            # Ensure version starts with 'v'
            tag_name = f"v{version.lstrip('v')}"

            # Create git tag locally first
            repo_dir = "/opt/xui-manager"
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
                cwd=repo_dir, capture_output=True
            )

            # Push tag
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_dir, capture_output=True, text=True
            )
            original_url = remote_result.stdout.strip()

            if "github.com" in original_url:
                if original_url.startswith("https://"):
                    auth_url = original_url.replace("https://", f"https://{token}@")
                else:
                    auth_url = original_url.replace("git@github.com:", "https://github.com/")
                    auth_url = auth_url.replace("https://", f"https://{token}@")
            else:
                auth_url = original_url

            # Push tag
            subprocess.run(
                ["git", "push", auth_url, tag_name],
                cwd=repo_dir, capture_output=True, text=True,
                env={**os.environ, "GIT_ASKPASS": "/bin/true"}
            )

            # Create release via GitHub API
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

            payload = {
                "tag_name": tag_name,
                "name": release_name or f"Release {tag_name}",
                "body": release_notes or f"## XUI Manager {tag_name}\n\nNew release version.",
                "draft": draft,
                "prerelease": prerelease
            }

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "XUI-Manager"
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 201:
                        data = await response.json()
                        logger.info(f"Created GitHub release: {tag_name}")
                        return {
                            "success": True,
                            "tag_name": tag_name,
                            "release_name": data.get("name"),
                            "html_url": data.get("html_url"),
                            "id": data.get("id"),
                            "created_at": data.get("created_at")
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"GitHub API error {response.status}: {error_text}"
                        }

        except Exception as e:
            logger.error(f"Error creating GitHub release: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def full_release_cycle(
        self,
        bump_type: str = "patch",
        custom_version: str = None,
        version_name: str = None,
        release_notes: str = None,
        github_token: str = None
    ) -> Dict:
        """
        Complete release cycle: bump version -> commit -> push -> create release

        Args:
            bump_type: 'major', 'minor', or 'patch'
            custom_version: Custom version string
            version_name: Optional new version name
            release_notes: Release description
            github_token: GitHub PAT

        Returns:
            Dict with all steps results
        """
        results = {
            "success": False,
            "steps": {}
        }

        try:
            # Step 1: Bump version
            bump_result = await self.bump_version(
                bump_type=bump_type,
                custom_version=custom_version,
                version_name=version_name
            )
            results["steps"]["bump_version"] = bump_result

            if not bump_result["success"]:
                results["error"] = f"Version bump failed: {bump_result['error']}"
                return results

            new_version = bump_result["new_version"]

            # Step 2: Commit and push
            commit_message = f"Release v{new_version}"
            if version_name:
                commit_message += f" - {version_name}"

            push_result = self.git_commit_and_push(
                commit_message=commit_message,
                github_token=github_token
            )
            results["steps"]["git_push"] = push_result

            if not push_result["success"]:
                results["error"] = f"Git push failed: {push_result['error']}"
                return results

            # Step 3: Create GitHub release
            release_result = await self.create_github_release(
                version=new_version,
                release_name=f"v{new_version}" + (f" - {version_name}" if version_name else ""),
                release_notes=release_notes,
                github_token=github_token
            )
            results["steps"]["github_release"] = release_result

            if not release_result["success"]:
                results["error"] = f"Release creation failed: {release_result['error']}"
                return results

            results["success"] = True
            results["new_version"] = new_version
            results["release_url"] = release_result.get("html_url")

            logger.info(f"Full release cycle completed: v{new_version}")
            return results

        except Exception as e:
            logger.error(f"Error in release cycle: {e}", exc_info=True)
            results["error"] = str(e)
            return results

    def get_github_token_status(self) -> Dict:
        """Check if GitHub token is configured and valid"""
        token = settings.GITHUB_TOKEN

        if not token:
            return {
                "configured": False,
                "message": "GITHUB_TOKEN not set in .env file"
            }

        return {
            "configured": True,
            "token_preview": f"{token[:10]}...{token[-4:]}" if len(token) > 14 else "***",
            "message": "GitHub token is configured"
        }


# Global instance
update_manager = UpdateManager()
