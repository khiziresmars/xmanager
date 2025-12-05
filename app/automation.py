"""
Automation Module for XUI-Manager
Handles scheduled tasks: backups, restarts, SSL renewal, monitoring
"""

import os
import json
import asyncio
import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AutomationSettings:
    """Settings for automation tasks"""
    # Backup settings
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    backup_retention_days: int = 7
    backup_path: str = "/var/backups/xui-manager"

    # Service restart settings
    auto_restart_enabled: bool = False
    restart_interval_hours: int = 24
    restart_time: str = "04:00"  # Time to restart (HH:MM)

    # SSL certificate settings
    ssl_check_enabled: bool = True
    ssl_check_interval_hours: int = 12
    ssl_auto_renew: bool = True
    ssl_renew_days_before: int = 30

    # WARP settings
    warp_health_check_enabled: bool = False
    warp_check_interval_minutes: int = 5
    warp_auto_restart: bool = True

    # Nginx settings
    nginx_reload_on_change: bool = True

    # Bot protection
    bot_blocking_enabled: bool = False
    blocked_user_agents: List[str] = None

    # Geo-blocking
    geo_blocking_enabled: bool = False
    blocked_countries: List[str] = None
    allowed_countries: List[str] = None

    def __post_init__(self):
        if self.blocked_user_agents is None:
            self.blocked_user_agents = ["clash", "hiddify", "v2box", "v2rayng", "nekobox"]
        if self.blocked_countries is None:
            self.blocked_countries = []
        if self.allowed_countries is None:
            self.allowed_countries = []


class AutomationManager:
    """Manages automated tasks and scheduling"""

    SETTINGS_FILE = "/opt/xui-manager/automation_settings.json"
    BACKUP_PATHS = [
        "/etc/x-ui/x-ui.db",
        "/usr/local/x-ui/bin/config.json",
        "/opt/xui-manager/.env"
    ]

    def __init__(self):
        self.settings = self._load_settings()
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._last_backup: Optional[datetime] = None
        self._last_ssl_check: Optional[datetime] = None
        self._last_warp_check: Optional[datetime] = None

    def _load_settings(self) -> AutomationSettings:
        """Load settings from file"""
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    return AutomationSettings(**data)
        except Exception as e:
            logger.error(f"Error loading automation settings: {e}")
        return AutomationSettings()

    def save_settings(self) -> bool:
        """Save settings to file"""
        try:
            os.makedirs(os.path.dirname(self.SETTINGS_FILE), exist_ok=True)
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(asdict(self.settings), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving automation settings: {e}")
            return False

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        """Update settings with new values"""
        try:
            for key, value in updates.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)
            return self.save_settings()
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False

    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dict"""
        return asdict(self.settings)

    # ==================== BACKUP FUNCTIONS ====================

    def create_backup(self) -> Dict[str, Any]:
        """Create backup of important files"""
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "backup_path": None,
            "message": ""
        }

        try:
            # Create backup directory
            backup_dir = Path(self.settings.backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped backup folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = backup_dir / timestamp
            backup_folder.mkdir(exist_ok=True)

            # Copy files
            for src_path in self.BACKUP_PATHS:
                if os.path.exists(src_path):
                    dst_path = backup_folder / os.path.basename(src_path)
                    shutil.copy2(src_path, dst_path)
                    result["files"].append({
                        "source": src_path,
                        "destination": str(dst_path),
                        "size": os.path.getsize(dst_path)
                    })

            result["backup_path"] = str(backup_folder)
            result["success"] = True
            result["message"] = f"Backup created: {len(result['files'])} files"

            self._last_backup = datetime.now()

            # Cleanup old backups
            self._cleanup_old_backups()

            logger.info(f"Backup created: {backup_folder}")

        except Exception as e:
            result["message"] = str(e)
            logger.error(f"Backup failed: {e}")

        return result

    def _cleanup_old_backups(self):
        """Remove backups older than retention period"""
        try:
            backup_dir = Path(self.settings.backup_path)
            if not backup_dir.exists():
                return

            cutoff = datetime.now() - timedelta(days=self.settings.backup_retention_days)

            for folder in backup_dir.iterdir():
                if folder.is_dir():
                    try:
                        # Parse folder name as timestamp
                        folder_time = datetime.strptime(folder.name, "%Y%m%d_%H%M%S")
                        if folder_time < cutoff:
                            shutil.rmtree(folder)
                            logger.info(f"Removed old backup: {folder}")
                    except ValueError:
                        pass  # Skip folders with non-timestamp names

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backups = []
        try:
            backup_dir = Path(self.settings.backup_path)
            if backup_dir.exists():
                for folder in sorted(backup_dir.iterdir(), reverse=True):
                    if folder.is_dir():
                        try:
                            folder_time = datetime.strptime(folder.name, "%Y%m%d_%H%M%S")
                            files = list(folder.glob("*"))
                            size = sum(f.stat().st_size for f in files if f.is_file())
                            backups.append({
                                "name": folder.name,
                                "path": str(folder),
                                "timestamp": folder_time.isoformat(),
                                "files_count": len(files),
                                "size_bytes": size,
                                "size_human": self._format_size(size)
                            })
                        except ValueError:
                            pass
        except Exception as e:
            logger.error(f"Error listing backups: {e}")

        return backups

    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore from a backup"""
        result = {"success": False, "message": "", "restored_files": []}

        try:
            backup_folder = Path(self.settings.backup_path) / backup_name
            if not backup_folder.exists():
                result["message"] = "Backup not found"
                return result

            # Stop services before restore
            subprocess.run(["systemctl", "stop", "x-ui"], capture_output=True)

            # Restore files
            for backup_file in backup_folder.glob("*"):
                if backup_file.name == "x-ui.db":
                    dst = "/etc/x-ui/x-ui.db"
                elif backup_file.name == "config.json":
                    dst = "/usr/local/x-ui/bin/config.json"
                elif backup_file.name == ".env":
                    dst = "/opt/xui-manager/.env"
                else:
                    continue

                # Create backup of current file
                if os.path.exists(dst):
                    shutil.copy2(dst, dst + ".pre-restore")

                shutil.copy2(backup_file, dst)
                result["restored_files"].append(dst)

            # Restart services
            subprocess.run(["systemctl", "start", "x-ui"], capture_output=True)
            subprocess.run(["systemctl", "restart", "xui-manager"], capture_output=True)

            result["success"] = True
            result["message"] = f"Restored {len(result['restored_files'])} files from {backup_name}"

        except Exception as e:
            result["message"] = str(e)
            # Try to restart services even on error
            subprocess.run(["systemctl", "start", "x-ui"], capture_output=True)

        return result

    def delete_backup(self, backup_name: str) -> bool:
        """Delete a specific backup"""
        try:
            backup_folder = Path(self.settings.backup_path) / backup_name
            if backup_folder.exists() and backup_folder.is_dir():
                shutil.rmtree(backup_folder)
                logger.info(f"Deleted backup: {backup_name}")
                return True
        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
        return False

    # ==================== SERVICE FUNCTIONS ====================

    def restart_service(self, service: str) -> Dict[str, Any]:
        """Restart a system service"""
        result = {"success": False, "service": service, "message": ""}

        allowed_services = ["x-ui", "xui-manager", "nginx", "warp-svc"]
        if service not in allowed_services:
            result["message"] = f"Service not allowed: {service}"
            return result

        try:
            proc = subprocess.run(
                ["systemctl", "restart", service],
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode == 0:
                result["success"] = True
                result["message"] = f"{service} restarted successfully"
            else:
                result["message"] = proc.stderr or "Unknown error"

        except subprocess.TimeoutExpired:
            result["message"] = "Restart timed out"
        except Exception as e:
            result["message"] = str(e)

        return result

    def get_service_status(self, service: str) -> Dict[str, Any]:
        """Get status of a service"""
        result = {
            "service": service,
            "active": False,
            "status": "unknown",
            "uptime": None
        }

        try:
            proc = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True,
                text=True
            )
            result["status"] = proc.stdout.strip()
            result["active"] = proc.returncode == 0

            if result["active"]:
                # Get uptime
                proc = subprocess.run(
                    ["systemctl", "show", service, "--property=ActiveEnterTimestamp"],
                    capture_output=True,
                    text=True
                )
                if proc.returncode == 0:
                    timestamp = proc.stdout.strip().split("=")[1]
                    if timestamp:
                        result["uptime"] = timestamp

        except Exception as e:
            logger.error(f"Error getting service status: {e}")

        return result

    # ==================== SSL FUNCTIONS ====================

    def check_ssl_certificates(self) -> List[Dict[str, Any]]:
        """Check SSL certificate expiry dates"""
        certs = []

        # Check Let's Encrypt certificates
        le_path = Path("/etc/letsencrypt/live")
        if le_path.exists():
            for domain_dir in le_path.iterdir():
                if domain_dir.is_dir():
                    cert_file = domain_dir / "fullchain.pem"
                    if cert_file.exists():
                        try:
                            proc = subprocess.run(
                                ["openssl", "x509", "-enddate", "-noout", "-in", str(cert_file)],
                                capture_output=True,
                                text=True
                            )
                            if proc.returncode == 0:
                                expiry_str = proc.stdout.strip().replace("notAfter=", "")
                                expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                                days_left = (expiry - datetime.now()).days

                                certs.append({
                                    "domain": domain_dir.name,
                                    "cert_path": str(cert_file),
                                    "expiry": expiry.isoformat(),
                                    "days_left": days_left,
                                    "needs_renewal": days_left <= self.settings.ssl_renew_days_before,
                                    "status": "ok" if days_left > 30 else ("warning" if days_left > 7 else "critical")
                                })
                        except Exception as e:
                            logger.error(f"Error checking cert for {domain_dir.name}: {e}")

        self._last_ssl_check = datetime.now()
        return certs

    def renew_ssl_certificates(self) -> Dict[str, Any]:
        """Renew SSL certificates using certbot"""
        result = {"success": False, "message": "", "renewed": []}

        try:
            proc = subprocess.run(
                ["certbot", "renew", "--quiet"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if proc.returncode == 0:
                result["success"] = True
                result["message"] = "Certificate renewal completed"

                # Reload nginx to apply new certs
                subprocess.run(["systemctl", "reload", "nginx"], capture_output=True)
            else:
                result["message"] = proc.stderr or "Renewal failed"

        except subprocess.TimeoutExpired:
            result["message"] = "Renewal timed out"
        except FileNotFoundError:
            result["message"] = "Certbot not installed"
        except Exception as e:
            result["message"] = str(e)

        return result

    # ==================== WARP FUNCTIONS ====================

    def check_warp_status(self) -> Dict[str, Any]:
        """Check WARP connection status"""
        result = {
            "installed": False,
            "running": False,
            "connected": False,
            "ip": None,
            "country": None
        }

        try:
            # Check if warp-cli exists
            if shutil.which("warp-cli"):
                result["installed"] = True

                # Check status
                proc = subprocess.run(
                    ["warp-cli", "status"],
                    capture_output=True,
                    text=True
                )

                if "Connected" in proc.stdout:
                    result["running"] = True
                    result["connected"] = True
                elif "Disconnected" in proc.stdout:
                    result["running"] = True
                    result["connected"] = False

                # Get IP through WARP proxy
                if result["connected"]:
                    try:
                        proc = subprocess.run(
                            ["curl", "-s", "--socks5-hostname", "127.0.0.1:40000",
                             "https://ipinfo.io/json", "--max-time", "5"],
                            capture_output=True,
                            text=True
                        )
                        if proc.returncode == 0:
                            ip_info = json.loads(proc.stdout)
                            result["ip"] = ip_info.get("ip")
                            result["country"] = ip_info.get("country")
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error checking WARP status: {e}")

        self._last_warp_check = datetime.now()
        return result

    def restart_warp(self) -> bool:
        """Restart WARP service"""
        try:
            subprocess.run(["warp-cli", "disconnect"], capture_output=True)
            subprocess.run(["warp-cli", "connect"], capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Error restarting WARP: {e}")
            return False

    # ==================== SCHEDULED TASKS ====================

    async def start_scheduler(self):
        """Start all scheduled tasks"""
        if self._running:
            return

        self._running = True
        logger.info("Starting automation scheduler")

        # Start backup task
        if self.settings.backup_enabled:
            self._tasks["backup"] = asyncio.create_task(self._backup_loop())

        # Start SSL check task
        if self.settings.ssl_check_enabled:
            self._tasks["ssl_check"] = asyncio.create_task(self._ssl_check_loop())

        # Start WARP health check
        if self.settings.warp_health_check_enabled:
            self._tasks["warp_check"] = asyncio.create_task(self._warp_check_loop())

    async def stop_scheduler(self):
        """Stop all scheduled tasks"""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Automation scheduler stopped")

    async def _backup_loop(self):
        """Periodic backup task"""
        while self._running:
            try:
                await asyncio.sleep(self.settings.backup_interval_hours * 3600)
                if self.settings.backup_enabled:
                    self.create_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup loop error: {e}")

    async def _ssl_check_loop(self):
        """Periodic SSL check task"""
        while self._running:
            try:
                await asyncio.sleep(self.settings.ssl_check_interval_hours * 3600)
                if self.settings.ssl_check_enabled:
                    certs = self.check_ssl_certificates()
                    # Auto-renew if needed
                    if self.settings.ssl_auto_renew:
                        for cert in certs:
                            if cert.get("needs_renewal"):
                                self.renew_ssl_certificates()
                                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSL check loop error: {e}")

    async def _warp_check_loop(self):
        """Periodic WARP health check"""
        while self._running:
            try:
                await asyncio.sleep(self.settings.warp_check_interval_minutes * 60)
                if self.settings.warp_health_check_enabled:
                    status = self.check_warp_status()
                    if status["installed"] and not status["connected"]:
                        if self.settings.warp_auto_restart:
                            logger.warning("WARP disconnected, restarting...")
                            self.restart_warp()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WARP check loop error: {e}")

    # ==================== UTILITY ====================

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def get_status(self) -> Dict[str, Any]:
        """Get overall automation status"""
        return {
            "running": self._running,
            "active_tasks": list(self._tasks.keys()),
            "last_backup": self._last_backup.isoformat() if self._last_backup else None,
            "last_ssl_check": self._last_ssl_check.isoformat() if self._last_ssl_check else None,
            "last_warp_check": self._last_warp_check.isoformat() if self._last_warp_check else None,
            "settings": self.get_settings()
        }


# Global instance
automation_manager = AutomationManager()


def get_automation_manager() -> AutomationManager:
    """Get global automation manager instance"""
    return automation_manager
