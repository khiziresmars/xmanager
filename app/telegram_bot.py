#!/usr/bin/env python3
"""
Telegram Bot & Notifications for XUI-Manager
Handles alerts, notifications, and bot commands
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import aiogram, but make it optional
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.filters import Command
    from aiogram.enums import ParseMode
    AIOGRAM_AVAILABLE = True
except ImportError:
    AIOGRAM_AVAILABLE = False
    logger.warning("aiogram not installed. Telegram features will use HTTP API directly.")


class AlertType(str, Enum):
    """Types of alerts"""
    SERVER_OFFLINE = "server_offline"
    SERVER_ONLINE = "server_online"
    USER_EXPIRED = "user_expired"
    USER_EXPIRING_SOON = "user_expiring_soon"
    TRAFFIC_LOW = "traffic_low"
    TRAFFIC_EXHAUSTED = "traffic_exhausted"
    HIGH_CPU_LOAD = "high_cpu_load"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    SSL_EXPIRING = "ssl_expiring"
    SSL_EXPIRED = "ssl_expired"
    UPDATE_AVAILABLE = "update_available"
    BACKUP_CREATED = "backup_created"
    BACKUP_FAILED = "backup_failed"
    LOGIN_ATTEMPT = "login_attempt"
    XRAY_ERROR = "xray_error"
    CUSTOM = "custom"


@dataclass
class AlertConfig:
    """Alert configuration"""
    alert_type: AlertType
    emoji: str
    title: str
    title_ru: str
    cooldown_minutes: int = 30  # Min time between same alerts
    enabled: bool = True


# Alert configurations
ALERT_CONFIGS: Dict[str, AlertConfig] = {
    AlertType.SERVER_OFFLINE: AlertConfig(
        alert_type=AlertType.SERVER_OFFLINE,
        emoji="🔴",
        title="Server Offline",
        title_ru="Сервер недоступен",
        cooldown_minutes=5,
    ),
    AlertType.SERVER_ONLINE: AlertConfig(
        alert_type=AlertType.SERVER_ONLINE,
        emoji="🟢",
        title="Server Online",
        title_ru="Сервер снова онлайн",
        cooldown_minutes=0,  # No cooldown for recovery
    ),
    AlertType.USER_EXPIRED: AlertConfig(
        alert_type=AlertType.USER_EXPIRED,
        emoji="⏰",
        title="User Expired",
        title_ru="Пользователь истёк",
        cooldown_minutes=60,
    ),
    AlertType.USER_EXPIRING_SOON: AlertConfig(
        alert_type=AlertType.USER_EXPIRING_SOON,
        emoji="⚠️",
        title="User Expiring Soon",
        title_ru="Пользователь скоро истечёт",
        cooldown_minutes=360,  # 6 hours
    ),
    AlertType.TRAFFIC_LOW: AlertConfig(
        alert_type=AlertType.TRAFFIC_LOW,
        emoji="📉",
        title="Low Traffic",
        title_ru="Мало трафика",
        cooldown_minutes=120,
    ),
    AlertType.TRAFFIC_EXHAUSTED: AlertConfig(
        alert_type=AlertType.TRAFFIC_EXHAUSTED,
        emoji="🚫",
        title="Traffic Exhausted",
        title_ru="Трафик исчерпан",
        cooldown_minutes=60,
    ),
    AlertType.HIGH_CPU_LOAD: AlertConfig(
        alert_type=AlertType.HIGH_CPU_LOAD,
        emoji="🔥",
        title="High CPU Load",
        title_ru="Высокая нагрузка CPU",
        cooldown_minutes=15,
    ),
    AlertType.HIGH_MEMORY_USAGE: AlertConfig(
        alert_type=AlertType.HIGH_MEMORY_USAGE,
        emoji="💾",
        title="High Memory Usage",
        title_ru="Высокое использование памяти",
        cooldown_minutes=15,
    ),
    AlertType.SSL_EXPIRING: AlertConfig(
        alert_type=AlertType.SSL_EXPIRING,
        emoji="🔐",
        title="SSL Certificate Expiring",
        title_ru="SSL сертификат истекает",
        cooldown_minutes=1440,  # 24 hours
    ),
    AlertType.SSL_EXPIRED: AlertConfig(
        alert_type=AlertType.SSL_EXPIRED,
        emoji="❌",
        title="SSL Certificate Expired",
        title_ru="SSL сертификат истёк",
        cooldown_minutes=360,
    ),
    AlertType.UPDATE_AVAILABLE: AlertConfig(
        alert_type=AlertType.UPDATE_AVAILABLE,
        emoji="📦",
        title="Update Available",
        title_ru="Доступно обновление",
        cooldown_minutes=1440,  # 24 hours
    ),
    AlertType.BACKUP_CREATED: AlertConfig(
        alert_type=AlertType.BACKUP_CREATED,
        emoji="💾",
        title="Backup Created",
        title_ru="Бэкап создан",
        cooldown_minutes=0,
    ),
    AlertType.BACKUP_FAILED: AlertConfig(
        alert_type=AlertType.BACKUP_FAILED,
        emoji="❌",
        title="Backup Failed",
        title_ru="Ошибка бэкапа",
        cooldown_minutes=60,
    ),
    AlertType.LOGIN_ATTEMPT: AlertConfig(
        alert_type=AlertType.LOGIN_ATTEMPT,
        emoji="🔑",
        title="Login Attempt",
        title_ru="Попытка входа",
        cooldown_minutes=1,
    ),
    AlertType.XRAY_ERROR: AlertConfig(
        alert_type=AlertType.XRAY_ERROR,
        emoji="⚡",
        title="Xray Error",
        title_ru="Ошибка Xray",
        cooldown_minutes=30,
    ),
    AlertType.CUSTOM: AlertConfig(
        alert_type=AlertType.CUSTOM,
        emoji="📢",
        title="Notification",
        title_ru="Уведомление",
        cooldown_minutes=0,
    ),
}


class TelegramNotifier:
    """Telegram notification system with anti-spam protection"""

    def __init__(
        self,
        bot_token: str = "",
        admin_ids: List[int] = None,
        cooldown_minutes: int = 30,
        history_file: str = "/opt/xui-manager/alert_history.json"
    ):
        self.bot_token = bot_token
        self.admin_ids = admin_ids or []
        self.default_cooldown = cooldown_minutes
        self.history_file = history_file
        self.alert_history: Dict[str, float] = {}
        self._bot: Optional[Any] = None

        # Load alert history
        self._load_history()

    def _load_history(self):
        """Load alert history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.alert_history = json.load(f)
        except Exception as e:
            logger.error(f"Error loading alert history: {e}")
            self.alert_history = {}

    def _save_history(self):
        """Save alert history to file"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.alert_history, f)
        except Exception as e:
            logger.error(f"Error saving alert history: {e}")

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.admin_ids)

    def _should_send_alert(self, alert_type: str, alert_key: str = "") -> bool:
        """Check if alert should be sent (anti-spam)"""
        # Get alert config
        config = ALERT_CONFIGS.get(alert_type)
        if not config or not config.enabled:
            return False

        # Create unique key for this alert
        unique_key = f"{alert_type}:{alert_key}" if alert_key else alert_type

        # Check cooldown
        last_sent = self.alert_history.get(unique_key, 0)
        cooldown_seconds = config.cooldown_minutes * 60

        if time.time() - last_sent < cooldown_seconds:
            logger.debug(f"Alert {unique_key} suppressed (cooldown)")
            return False

        return True

    def _mark_alert_sent(self, alert_type: str, alert_key: str = ""):
        """Mark alert as sent"""
        unique_key = f"{alert_type}:{alert_key}" if alert_key else alert_type
        self.alert_history[unique_key] = time.time()
        self._save_history()

    async def send_message(self, text: str, chat_id: int = None, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram chat"""
        if not self.is_configured():
            logger.debug("Telegram not configured, skipping message")
            return False

        try:
            import aiohttp

            targets = [chat_id] if chat_id else self.admin_ids

            for target_id in targets:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": target_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status != 200:
                            result = await response.text()
                            logger.error(f"Telegram API error: {result}")
                            return False

            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def send_alert(
        self,
        alert_type: AlertType,
        message: str,
        alert_key: str = "",
        extra_data: Dict[str, Any] = None,
        force: bool = False
    ) -> bool:
        """
        Send alert with anti-spam protection

        Args:
            alert_type: Type of alert
            message: Alert message
            alert_key: Unique key for deduplication (e.g., user email)
            extra_data: Additional data to include
            force: Skip cooldown check

        Returns:
            True if alert was sent
        """
        if not self.is_configured():
            return False

        # Check cooldown
        if not force and not self._should_send_alert(alert_type.value, alert_key):
            return False

        # Get alert config
        config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS[AlertType.CUSTOM])

        # Format message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"{config.emoji} <b>{config.title_ru}</b>\n\n"
        formatted_message += f"{message}\n\n"

        if extra_data:
            for key, value in extra_data.items():
                formatted_message += f"• <b>{key}:</b> {value}\n"

        formatted_message += f"\n<i>{timestamp}</i>"

        # Send message
        success = await self.send_message(formatted_message)

        if success:
            self._mark_alert_sent(alert_type.value, alert_key)

        return success

    async def send_server_status(self, status: Dict[str, Any]) -> bool:
        """Send server status summary"""
        if not self.is_configured():
            return False

        # Format status message
        cpu = status.get("cpu", 0)
        memory = status.get("memory", {})
        mem_percent = memory.get("percent", 0) if isinstance(memory, dict) else 0

        xray_status = "🟢 Running" if status.get("xray_running") else "🔴 Stopped"

        message = f"""📊 <b>Статус сервера</b>

🖥 <b>CPU:</b> {cpu:.1f}%
💾 <b>Память:</b> {mem_percent:.1f}%
⚡ <b>Xray:</b> {xray_status}
👥 <b>Онлайн:</b> {status.get("online_users", 0)}
📅 <b>Uptime:</b> {status.get("uptime", "N/A")}

<i>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</i>"""

        return await self.send_message(message)

    async def send_daily_report(self, stats: Dict[str, Any]) -> bool:
        """Send daily statistics report"""
        if not self.is_configured():
            return False

        message = f"""📈 <b>Ежедневный отчёт</b>

👥 <b>Всего пользователей:</b> {stats.get("total_users", 0)}
✅ <b>Активных:</b> {stats.get("active_users", 0)}
❌ <b>Отключенных:</b> {stats.get("disabled_users", 0)}
⏰ <b>Истекающих (7 дней):</b> {stats.get("expiring_soon", 0)}

📊 <b>Трафик за сегодня:</b>
↑ Upload: {self._format_bytes(stats.get("today_upload", 0))}
↓ Download: {self._format_bytes(stats.get("today_download", 0))}

📊 <b>Трафик всего:</b>
↑ Upload: {self._format_bytes(stats.get("total_upload", 0))}
↓ Download: {self._format_bytes(stats.get("total_download", 0))}

<i>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</i>"""

        return await self.send_message(message)

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes to human readable string"""
        if bytes_value == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0

        while bytes_value >= 1024 and unit_index < len(units) - 1:
            bytes_value /= 1024
            unit_index += 1

        return f"{bytes_value:.2f} {units[unit_index]}"

    def clear_alert_history(self, alert_type: str = None):
        """Clear alert history"""
        if alert_type:
            # Clear specific alert type
            keys_to_remove = [k for k in self.alert_history.keys() if k.startswith(alert_type)]
            for key in keys_to_remove:
                del self.alert_history[key]
        else:
            # Clear all
            self.alert_history.clear()

        self._save_history()

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        stats = {}
        for key, timestamp in self.alert_history.items():
            alert_type = key.split(":")[0]
            if alert_type not in stats:
                stats[alert_type] = {"count": 0, "last_sent": 0}
            stats[alert_type]["count"] += 1
            stats[alert_type]["last_sent"] = max(stats[alert_type]["last_sent"], timestamp)

        return stats


class TelegramBotHandler:
    """Telegram bot command handler (optional)"""

    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self._dp: Optional[Any] = None
        self._bot: Optional[Any] = None

    async def setup_bot(self):
        """Setup bot with command handlers"""
        if not AIOGRAM_AVAILABLE:
            logger.warning("aiogram not available, bot commands disabled")
            return

        if not self.notifier.is_configured():
            logger.warning("Telegram not configured")
            return

        self._bot = Bot(token=self.notifier.bot_token)
        self._dp = Dispatcher()

        # Register handlers
        @self._dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            if message.from_user.id not in self.notifier.admin_ids:
                return

            await message.answer(
                "👋 <b>XUI-Manager Bot</b>\n\n"
                "Доступные команды:\n"
                "/status - Статус сервера\n"
                "/users - Статистика пользователей\n"
                "/online - Онлайн пользователи\n"
                "/help - Помощь",
                parse_mode=ParseMode.HTML
            )

        @self._dp.message(Command("status"))
        async def cmd_status(message: types.Message):
            if message.from_user.id not in self.notifier.admin_ids:
                return

            await message.answer("🔄 Получение статуса...")
            # Status would be fetched from server_monitor

        @self._dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            if message.from_user.id not in self.notifier.admin_ids:
                return

            await message.answer(
                "📖 <b>Справка</b>\n\n"
                "/status - Показать статус сервера\n"
                "/users - Статистика пользователей\n"
                "/online - Список онлайн пользователей\n"
                "/expiring - Пользователи с истекающим сроком\n"
                "/traffic - Статистика трафика\n",
                parse_mode=ParseMode.HTML
            )

    async def start_polling(self):
        """Start bot polling (blocking)"""
        if not self._dp or not self._bot:
            await self.setup_bot()

        if self._dp and self._bot:
            await self._dp.start_polling(self._bot)


# Convenience function to create notifier from config
def create_notifier_from_config() -> TelegramNotifier:
    """Create TelegramNotifier from application config"""
    try:
        from app.config import settings

        admin_ids = settings.get_telegram_admin_ids()

        return TelegramNotifier(
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            admin_ids=admin_ids,
            cooldown_minutes=settings.TELEGRAM_ALERT_COOLDOWN,
            history_file=settings.ALERT_HISTORY_FILE,
        )
    except Exception as e:
        logger.error(f"Error creating notifier from config: {e}")
        return TelegramNotifier()


# Global instance (lazy initialization)
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Get global notifier instance"""
    global _notifier
    if _notifier is None:
        _notifier = create_notifier_from_config()
    return _notifier
