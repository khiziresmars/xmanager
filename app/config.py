#!/usr/bin/env python3
"""
Configuration module for XUI-Manager
Extended with Telegram, regions, monitoring settings
"""

import os
import random
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # ============================================
    # BASIC SETTINGS
    # ============================================
    APP_NAME: str = "X-UI Manager"
    APP_VERSION: str = "2.1.0"
    DEBUG: bool = False

    # ============================================
    # NETWORK SETTINGS
    # ============================================
    HOST: str = "0.0.0.0"
    PORT: int = 8888

    # ============================================
    # DATABASE
    # ============================================
    XUI_DB_PATH: str = "/etc/x-ui/x-ui.db"
    DB_PATH: str = "/etc/x-ui/x-ui.db"
    XUI_CONFIG_PATH: str = "/usr/local/x-ui/bin/config.json"

    # ============================================
    # 3X-UI PANEL API
    # ============================================
    XUI_PANEL_URL: str = "http://localhost:2053"
    XUI_PANEL_USERNAME: str = "admin"
    XUI_PANEL_PASSWORD: str = "admin"

    # ============================================
    # AUTHENTICATION
    # ============================================
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    API_KEY: str = ""

    # Session settings
    SESSION_EXPIRE_HOURS: int = 24
    SESSION_FILE: str = "/opt/xui-manager/sessions.json"

    # ============================================
    # TELEGRAM BOT
    # ============================================
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_IDS: str = ""  # Comma-separated list of admin IDs
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_ALERT_COOLDOWN: int = 30  # Minutes between same alerts

    # ============================================
    # MONITORING
    # ============================================
    MONITOR_ENABLED: bool = True
    MONITOR_INTERVAL: int = 60  # Seconds
    MONITOR_FAILURE_THRESHOLD: int = 3  # Consecutive failures before alert
    MONITOR_CHECK_XUI_API: bool = True
    MONITOR_CHECK_XRAY: bool = True
    MONITOR_CHECK_DATABASE: bool = True

    # ============================================
    # REGIONS
    # ============================================
    DEFAULT_REGION: str = "GLOBAL"
    SERVER_COUNTRY: str = ""  # Auto-detected if empty
    TARGET_REGION: str = ""  # Target users region

    # ============================================
    # SITE CHECKER
    # ============================================
    SITE_CHECK_ENABLED: bool = True
    SITE_CHECK_INTERVAL: int = 3600  # Seconds (1 hour)
    SITE_CHECK_TIMEOUT: int = 10  # Seconds per site

    # ============================================
    # PATHS
    # ============================================
    BACKUP_DIR: str = "/opt/xui-manager/backups"
    TEMPLATES_FILE: str = "/opt/xui-manager/templates.json"
    LOG_FILE: str = "/opt/xui-manager/logs/app.log"
    SERVER_ID_FILE: str = "/opt/xui-manager/server_id.txt"
    MONITOR_STATE_FILE: str = "/opt/xui-manager/monitor_state.json"
    ALERT_HISTORY_FILE: str = "/opt/xui-manager/alert_history.json"

    # ============================================
    # LIMITS
    # ============================================
    MAX_BULK_CREATE: int = 100
    MAX_BULK_DELETE: int = 500
    MAX_QUEUE_SIZE: int = 5000

    # ============================================
    # RATE LIMITING
    # ============================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100  # Requests per window
    RATE_LIMIT_WINDOW: int = 60  # Window in seconds

    # ============================================
    # UPDATE SERVER
    # ============================================
    UPDATE_SERVER_PORT: int = 8889
    UPDATE_SERVER_USERNAME: str = "admin"
    UPDATE_SERVER_PASSWORD: str = "admin"

    # ============================================
    # GITHUB (for updates from private repos)
    # ============================================
    # Set your GitHub Personal Access Token in .env file
    # Format: GITHUB_TOKEN=github_pat_xxxxxxxxxxxx
    GITHUB_TOKEN: str = ""

    class Config:
        env_file = "/opt/xui-manager/.env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

    def get_telegram_admin_ids(self) -> List[int]:
        """Parse telegram admin IDs from comma-separated string"""
        if not self.TELEGRAM_ADMIN_IDS:
            return []
        try:
            return [int(x.strip()) for x in self.TELEGRAM_ADMIN_IDS.split(",") if x.strip()]
        except ValueError:
            return []


# Create settings instance
settings = Settings()


def get_or_create_server_id() -> str:
    """Get or create unique server ID"""
    server_id_file = settings.SERVER_ID_FILE

    if os.path.exists(server_id_file):
        try:
            with open(server_id_file, 'r') as f:
                server_id = f.read().strip()
                if server_id and len(server_id) == 10 and server_id.isdigit():
                    return server_id
        except Exception as e:
            print(f"Error reading server ID: {e}")

    # Generate new 10-digit ID
    server_id = ''.join([str(random.randint(0, 9)) for _ in range(10)])

    try:
        os.makedirs(os.path.dirname(server_id_file), exist_ok=True)
        with open(server_id_file, 'w') as f:
            f.write(server_id)
        print(f"Generated new server ID: {server_id}")
    except Exception as e:
        print(f"Error saving server ID: {e}")

    return server_id


# Generate or load Server ID at startup
SERVER_ID = get_or_create_server_id()
