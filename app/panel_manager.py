"""
Panel Manager for 3x-ui
Handles panel credentials, database backup/restore, reinstallation with forks selection
Inspired by: https://github.com/GFW4Fun/x-ui-pro, https://github.com/MHSanaei/3x-ui
"""

import os
import json
import sqlite3
import subprocess
import shutil
import logging
import asyncio
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PanelFork(Enum):
    """Available 3x-ui forks"""
    MHSANAEI = "mhsanaei"  # Most popular, recommended
    ALIREZA = "alireza"    # Alireza0 fork
    FRANZKAFKA = "franzkafka"  # FranzKafkaYu fork


@dataclass
class PanelCredentials:
    """Panel login credentials"""
    username: str
    password_hash: str
    panel_url: str
    port: int
    base_path: str
    secret_token: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "panel_url": self.panel_url,
            "port": self.port,
            "base_path": self.base_path,
            "has_secret": bool(self.secret_token)
        }


@dataclass
class PanelStatus:
    """Panel status information"""
    installed: bool
    running: bool
    version: Optional[str]
    xray_version: Optional[str]
    uptime: Optional[str]
    database_size_mb: float
    users_count: int
    inbounds_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "installed": self.installed,
            "running": self.running,
            "version": self.version,
            "xray_version": self.xray_version,
            "uptime": self.uptime,
            "database_size_mb": self.database_size_mb,
            "users_count": self.users_count,
            "inbounds_count": self.inbounds_count
        }


# Fork installation URLs
FORK_URLS = {
    PanelFork.MHSANAEI: "https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh",
    PanelFork.ALIREZA: "https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh",
    PanelFork.FRANZKAFKA: "https://raw.githubusercontent.com/FranzKafkaYu/x-ui/master/install.sh",
}

FORK_DESCRIPTIONS = {
    PanelFork.MHSANAEI: {
        "name": "MHSanaei/3x-ui",
        "description": "Most popular fork with active development, recommended",
        "features": ["Multi-protocol", "Telegram bot", "Traffic limits", "Subscription", "Reality support"]
    },
    PanelFork.ALIREZA: {
        "name": "alireza0/x-ui",
        "description": "Original x-ui with improvements",
        "features": ["Multi-protocol", "Basic features", "Lightweight"]
    },
    PanelFork.FRANZKAFKA: {
        "name": "FranzKafkaYu/x-ui",
        "description": "Enhanced x-ui with additional features",
        "features": ["Multi-protocol", "Enhanced UI", "Traffic stats"]
    }
}


class PanelManager:
    """Manages 3x-ui panel operations"""

    def __init__(self, db_path: str = "/etc/x-ui/x-ui.db"):
        self.db_path = db_path
        self.backup_dir = "/opt/xui-manager/backups/panel"
        os.makedirs(self.backup_dir, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        return sqlite3.connect(self.db_path)

    def get_credentials(self) -> Optional[PanelCredentials]:
        """Get current panel credentials"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get user credentials
            cursor.execute("SELECT username, password FROM users WHERE id = 1")
            user_row = cursor.fetchone()

            if not user_row:
                conn.close()
                return None

            username, password_hash = user_row

            # Get panel settings
            settings = {}
            cursor.execute("SELECT key, value FROM settings")
            for key, value in cursor.fetchall():
                settings[key] = value

            conn.close()

            port = int(settings.get('webPort', 2053))
            base_path = settings.get('webBasePath', '/')
            secret = settings.get('secretEnable', '')

            # Build panel URL
            panel_url = f"http://localhost:{port}{base_path}"

            return PanelCredentials(
                username=username,
                password_hash=password_hash,
                panel_url=panel_url,
                port=port,
                base_path=base_path,
                secret_token=secret
            )

        except Exception as e:
            logger.error(f"Error getting credentials: {e}")
            return None

    def reset_credentials(self, new_username: str = "admin", new_password: str = "admin") -> Dict[str, Any]:
        """
        Reset panel credentials to specified values
        Based on: https://hostkey.com/documentation/marketplace/security/3x_ui/
        """
        try:
            # Generate bcrypt hash for password
            try:
                import bcrypt
                password_hash = bcrypt.hashpw(
                    new_password.encode(),
                    bcrypt.gensalt(rounds=10)
                ).decode()
            except ImportError:
                # Fallback: use plain password (panel will rehash on first login)
                password_hash = new_password
                logger.warning("bcrypt not available, using plain password")

            conn = self._get_connection()
            cursor = conn.cursor()

            # Update credentials
            cursor.execute("""
                UPDATE users
                SET username = ?, password = ?, login_secret = ''
                WHERE id = 1
            """, (new_username, password_hash))

            conn.commit()
            conn.close()

            # Restart panel to apply
            subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

            return {
                "success": True,
                "message": f"Credentials reset. Username: {new_username}, Password: {new_password}",
                "username": new_username,
                "password": new_password
            }

        except Exception as e:
            logger.error(f"Error resetting credentials: {e}")
            return {"success": False, "error": str(e)}

    def get_panel_status(self) -> PanelStatus:
        """Get comprehensive panel status"""
        installed = os.path.exists("/usr/local/x-ui/x-ui")
        running = False
        version = None
        xray_version = None
        uptime = None
        db_size = 0
        users_count = 0
        inbounds_count = 0

        # Check if running
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'x-ui'],
                capture_output=True, text=True
            )
            running = result.stdout.strip() == "active"
        except:
            pass

        # Get version
        if installed:
            try:
                result = subprocess.run(
                    ['/usr/local/x-ui/x-ui', 'version'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
            except:
                pass

        # Get Xray version
        try:
            result = subprocess.run(
                ['/usr/local/x-ui/bin/xray-linux-amd64', '-version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                import re
                match = re.search(r'Xray (\d+\.\d+\.\d+)', result.stdout)
                if match:
                    xray_version = match.group(1)
        except:
            pass

        # Get uptime
        if running:
            try:
                result = subprocess.run(
                    ['systemctl', 'show', 'x-ui', '--property=ActiveEnterTimestamp'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    uptime = result.stdout.split('=')[1].strip()
            except:
                pass

        # Get database stats
        if os.path.exists(self.db_path):
            try:
                db_size = os.path.getsize(self.db_path) / (1024 * 1024)

                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM client_traffics")
                users_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM inbounds")
                inbounds_count = cursor.fetchone()[0]

                conn.close()
            except:
                pass

        return PanelStatus(
            installed=installed,
            running=running,
            version=version,
            xray_version=xray_version,
            uptime=uptime,
            database_size_mb=round(db_size, 2),
            users_count=users_count,
            inbounds_count=inbounds_count
        )

    def backup_database(self, include_timestamp: bool = True) -> Dict[str, Any]:
        """Create database backup"""
        try:
            if not os.path.exists(self.db_path):
                return {"success": False, "error": "Database not found"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if include_timestamp else "latest"
            backup_name = f"x-ui_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_name)

            # Copy database
            shutil.copy2(self.db_path, backup_path)

            # Also create a latest symlink
            latest_path = os.path.join(self.backup_dir, "x-ui_backup_latest.db")
            if os.path.exists(latest_path):
                os.remove(latest_path)
            shutil.copy2(self.db_path, latest_path)

            backup_size = os.path.getsize(backup_path) / (1024 * 1024)

            logger.info(f"Database backup created: {backup_path}")

            return {
                "success": True,
                "backup_path": backup_path,
                "backup_name": backup_name,
                "size_mb": round(backup_size, 2),
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {"success": False, "error": str(e)}

    def restore_database(self, backup_path: str) -> Dict[str, Any]:
        """Restore database from backup"""
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "error": f"Backup not found: {backup_path}"}

            # Stop panel
            subprocess.run(['systemctl', 'stop', 'x-ui'], capture_output=True)

            # Create backup of current database
            if os.path.exists(self.db_path):
                current_backup = f"{self.db_path}.before_restore"
                shutil.copy2(self.db_path, current_backup)

            # Restore
            shutil.copy2(backup_path, self.db_path)

            # Start panel
            subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)

            logger.info(f"Database restored from: {backup_path}")

            return {
                "success": True,
                "message": "Database restored successfully",
                "restored_from": backup_path
            }

        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            # Try to start panel anyway
            subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = []

        try:
            for filename in os.listdir(self.backup_dir):
                if filename.endswith('.db') and 'backup' in filename:
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    backups.append({
                        "filename": filename,
                        "path": filepath,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })

            # Sort by creation time, newest first
            backups.sort(key=lambda x: x['created'], reverse=True)

        except Exception as e:
            logger.error(f"Error listing backups: {e}")

        return backups

    def get_available_forks(self) -> List[Dict[str, Any]]:
        """Get list of available panel forks"""
        forks = []
        for fork in PanelFork:
            info = FORK_DESCRIPTIONS.get(fork, {})
            forks.append({
                "id": fork.value,
                "name": info.get("name", fork.value),
                "description": info.get("description", ""),
                "features": info.get("features", []),
                "install_url": FORK_URLS.get(fork, "")
            })
        return forks

    async def reinstall_panel(
        self,
        fork: str = "mhsanaei",
        preserve_database: bool = True,
        preserve_config: bool = True
    ) -> Dict[str, Any]:
        """
        Reinstall 3x-ui panel with optional fork selection
        Preserves database and configuration if requested
        """
        try:
            # Validate fork
            try:
                selected_fork = PanelFork(fork.lower())
            except ValueError:
                return {"success": False, "error": f"Invalid fork: {fork}"}

            install_url = FORK_URLS.get(selected_fork)

            # Backup if requested
            backup_result = None
            config_backup = None

            if preserve_database and os.path.exists(self.db_path):
                backup_result = self.backup_database()
                if not backup_result.get("success"):
                    return {"success": False, "error": "Failed to backup database"}

            if preserve_config:
                config_path = "/usr/local/x-ui/bin/config.json"
                if os.path.exists(config_path):
                    config_backup = os.path.join(self.backup_dir, "config_before_reinstall.json")
                    shutil.copy2(config_path, config_backup)

            # Stop current panel
            subprocess.run(['systemctl', 'stop', 'x-ui'], capture_output=True)

            # Run installation script
            logger.info(f"Installing {selected_fork.value} fork from {install_url}")

            result = subprocess.run(
                f"bash <(curl -Ls {install_url})",
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Restore database if backed up
            if preserve_database and backup_result and backup_result.get("success"):
                # Wait a bit for installation to complete
                await asyncio.sleep(3)

                # Stop panel to restore database
                subprocess.run(['systemctl', 'stop', 'x-ui'], capture_output=True)

                # Restore database
                shutil.copy2(backup_result["backup_path"], self.db_path)

                logger.info("Database restored after reinstallation")

            # Start panel
            subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)

            return {
                "success": True,
                "message": f"Panel reinstalled with {FORK_DESCRIPTIONS[selected_fork]['name']}",
                "fork": fork,
                "database_preserved": preserve_database,
                "config_preserved": preserve_config,
                "backup_path": backup_result.get("backup_path") if backup_result else None
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timeout (5 minutes)"}
        except Exception as e:
            logger.error(f"Error reinstalling panel: {e}")
            # Try to start panel
            subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)
            return {"success": False, "error": str(e)}

    def get_panel_settings(self) -> Dict[str, Any]:
        """Get all panel settings from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM settings")
            settings = {}
            for key, value in cursor.fetchall():
                settings[key] = value

            conn.close()

            # Parse important settings
            return {
                "success": True,
                "settings": {
                    "port": int(settings.get("webPort", 2053)),
                    "base_path": settings.get("webBasePath", "/"),
                    "cert_file": settings.get("webCertFile", ""),
                    "key_file": settings.get("webKeyFile", ""),
                    "tls_enabled": bool(settings.get("webCertFile")),
                    "secret_enabled": settings.get("secretEnable", "") == "true",
                    "traffic_unit": settings.get("trafficUnit", "GB"),
                    "default_expiry": settings.get("defaultExpiry", "0"),
                    "subscription_port": settings.get("subPort", ""),
                    "subscription_path": settings.get("subPath", "/sub/"),
                    "telegram_enabled": settings.get("tgBotEnable", "") == "true",
                    "telegram_token": settings.get("tgBotToken", "")[:10] + "..." if settings.get("tgBotToken") else ""
                },
                "raw": settings
            }

        except Exception as e:
            logger.error(f"Error getting panel settings: {e}")
            return {"success": False, "error": str(e)}

    def update_panel_port(self, new_port: int) -> Dict[str, Any]:
        """Update panel web port"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE settings SET value = ? WHERE key = 'webPort'",
                (str(new_port),)
            )

            conn.commit()
            conn.close()

            # Restart panel
            subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

            return {
                "success": True,
                "message": f"Panel port updated to {new_port}",
                "new_port": new_port
            }

        except Exception as e:
            logger.error(f"Error updating port: {e}")
            return {"success": False, "error": str(e)}

    def update_panel_path(self, new_path: str) -> Dict[str, Any]:
        """Update panel base path (for security through obscurity)"""
        try:
            # Ensure path starts and ends with /
            if not new_path.startswith('/'):
                new_path = '/' + new_path
            if not new_path.endswith('/'):
                new_path = new_path + '/'

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE settings SET value = ? WHERE key = 'webBasePath'",
                (new_path,)
            )

            conn.commit()
            conn.close()

            # Restart panel
            subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

            return {
                "success": True,
                "message": f"Panel path updated to {new_path}",
                "new_path": new_path
            }

        except Exception as e:
            logger.error(f"Error updating path: {e}")
            return {"success": False, "error": str(e)}

    def generate_random_credentials(self) -> Dict[str, str]:
        """Generate random secure credentials"""
        username = f"admin_{secrets.token_hex(4)}"
        password = secrets.token_urlsafe(16)
        return {"username": username, "password": password}


# Global instance
_panel_manager = None


def get_panel_manager() -> PanelManager:
    """Get or create panel manager instance"""
    global _panel_manager
    if _panel_manager is None:
        from app.config import settings
        _panel_manager = PanelManager(settings.XUI_DB_PATH)
    return _panel_manager
