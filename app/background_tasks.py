"""
Background Tasks for XUI Manager - Extended Version
Handles periodic tasks: monitoring, alerts, site checking, cleanup
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages all background tasks with improved monitoring"""

    def __init__(self):
        self.tasks = {}
        self.running = False
        self.db = None
        self._monitor = None
        self._notifier = None
        self._site_checker = None

    def _init_components(self):
        """Initialize components lazily"""
        try:
            from app.database import XUIDatabase
            self.db = XUIDatabase()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

        try:
            from app.server_monitor import get_monitor
            self._monitor = get_monitor()
        except Exception as e:
            logger.warning(f"Server monitor not available: {e}")

        try:
            from app.telegram_bot import get_notifier
            self._notifier = get_notifier()
        except Exception as e:
            logger.warning(f"Telegram notifier not available: {e}")

        try:
            from app.site_checker import get_site_checker
            self._site_checker = get_site_checker()
        except Exception as e:
            logger.warning(f"Site checker not available: {e}")

    async def start(self):
        """Start all background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return

        self.running = True
        self._init_components()
        logger.info("Starting background tasks...")

        # Core tasks
        self.tasks['update_checker'] = asyncio.create_task(
            self._update_checker_task()
        )
        self.tasks['expired_cleanup'] = asyncio.create_task(
            self._expired_cleanup_task()
        )
        self.tasks['low_traffic_alerts'] = asyncio.create_task(
            self._low_traffic_alerts_task()
        )

        # New monitoring tasks
        if self._monitor:
            self.tasks['health_monitor'] = asyncio.create_task(
                self._health_monitor_task()
            )

        if self._site_checker:
            self.tasks['site_checker'] = asyncio.create_task(
                self._site_checker_task()
            )

        # Daily report task
        if self._notifier and self._notifier.is_configured():
            self.tasks['daily_report'] = asyncio.create_task(
                self._daily_report_task()
            )

        logger.info(f"Started {len(self.tasks)} background tasks")

    async def stop(self):
        """Stop all background tasks"""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping background tasks...")

        for name, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Task '{name}' stopped")

        self.tasks.clear()
        logger.info("All background tasks stopped")

    async def _update_checker_task(self):
        """Check for updates every 24 hours"""
        logger.info("Update checker task started (interval: 24h)")

        while self.running:
            try:
                from app.update_manager import update_manager

                logger.info("Checking for updates...")
                update_info = await update_manager.check_for_updates(force=False)

                if update_info.get("update_available"):
                    logger.info(
                        f"Update available: {update_info['current_version']} -> {update_info['latest_version']}"
                    )

                    # Send Telegram notification
                    if self._notifier and self._notifier.is_configured():
                        from app.telegram_bot import AlertType
                        await self._notifier.send_alert(
                            AlertType.UPDATE_AVAILABLE,
                            f"Доступна новая версия: {update_info['latest_version']}\n"
                            f"Текущая: {update_info['current_version']}",
                        )
                else:
                    logger.info(f"No updates available (current: {update_info.get('current_version')})")

                await asyncio.sleep(24 * 60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update checker task: {e}", exc_info=True)
                await asyncio.sleep(60 * 60)

    async def _expired_cleanup_task(self):
        """Clean up expired users every hour"""
        logger.info("Expired users cleanup task started (interval: 1h)")

        while self.running:
            try:
                if not self.db:
                    await asyncio.sleep(60 * 60)
                    continue

                current_time = int(time.time() * 1000)
                expired_users = self.db.get_users(
                    limit=1000,
                    offset=0,
                    search=None,
                    inbound_id=None,
                    enable=None
                )

                expired_count = 0
                disabled_count = 0

                for user in expired_users.get('users', []):
                    expiry_time = user.get('expiry_time', 0)

                    if expiry_time > 0 and expiry_time < current_time:
                        if user.get('enable', False):
                            try:
                                self.db.toggle_user_status(user['id'], False)
                                disabled_count += 1
                                logger.info(f"Disabled expired user: {user.get('email', user['id'])}")

                                # Send notification for important users
                                if self._notifier and disabled_count <= 10:
                                    from app.telegram_bot import AlertType
                                    await self._notifier.send_alert(
                                        AlertType.USER_EXPIRED,
                                        f"Пользователь истёк: {user.get('email')}",
                                        alert_key=user.get('email'),
                                    )
                            except Exception as e:
                                logger.error(f"Error disabling user {user['id']}: {e}")

                        expired_count += 1

                if expired_count > 0:
                    logger.info(f"Processed {expired_count} expired users, disabled {disabled_count}")

                await asyncio.sleep(60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in expired cleanup task: {e}", exc_info=True)
                await asyncio.sleep(10 * 60)

    async def _low_traffic_alerts_task(self):
        """Monitor users with low traffic and send alerts"""
        logger.info("Low traffic alerts task started (interval: 6h)")

        while self.running:
            try:
                if not self.db:
                    await asyncio.sleep(6 * 60 * 60)
                    continue

                low_traffic_threshold = 1024 * 1024 * 1024  # 1GB
                low_traffic_users = self.db.get_low_traffic_users(
                    threshold=low_traffic_threshold,
                    sort_by="remaining",
                    order="asc"
                )

                if low_traffic_users:
                    logger.info(f"Found {len(low_traffic_users)} users with low traffic (<1GB remaining)")

                    for i, user in enumerate(low_traffic_users[:10], 1):
                        remaining = user.get('remaining', 0)
                        remaining_gb = remaining / (1024 ** 3)
                        logger.info(f"  {i}. {user.get('email')}: {remaining_gb:.2f}GB remaining")

                    # Send summary notification
                    if self._notifier and self._notifier.is_configured() and len(low_traffic_users) > 0:
                        from app.telegram_bot import AlertType
                        await self._notifier.send_alert(
                            AlertType.TRAFFIC_LOW,
                            f"Обнаружено {len(low_traffic_users)} пользователей с низким трафиком (<1GB)",
                            force=False,
                        )

                await asyncio.sleep(6 * 60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in low traffic alerts task: {e}", exc_info=True)
                await asyncio.sleep(60 * 60)

    async def _health_monitor_task(self):
        """Monitor server health with false-positive protection"""
        logger.info("Health monitor task started (interval: 60s)")

        last_status = None

        while self.running:
            try:
                if not self._monitor:
                    await asyncio.sleep(60)
                    continue

                # Run health checks
                health_state = await self._monitor.run_all_checks()

                # Log status changes
                current_status = health_state.overall_status.value
                if last_status != current_status:
                    logger.info(f"Server health status changed: {last_status} -> {current_status}")
                    last_status = current_status

                # Check if we should send alerts
                if self._monitor.should_alert("server_offline"):
                    if self._notifier and self._notifier.is_configured():
                        from app.telegram_bot import AlertType

                        # Determine what's wrong
                        failed_checks = [
                            name for name, check in health_state.checks.items()
                            if check.status.value == "unhealthy"
                        ]

                        await self._notifier.send_alert(
                            AlertType.SERVER_OFFLINE,
                            f"Сервер недоступен!\n"
                            f"Проблемные компоненты: {', '.join(failed_checks)}\n"
                            f"Последовательных сбоев: {health_state.consecutive_failures}",
                            force=True,
                        )
                        self._monitor.mark_alert_sent("server_offline")

                # Check for recovery
                elif current_status == "healthy" and health_state.consecutive_failures == 0:
                    # Server recovered - send notification if we had issues
                    pass

                # Check system resources
                system_check = health_state.checks.get("system_resources")
                if system_check:
                    details = system_check.details
                    cpu = details.get("cpu_percent", 0)
                    mem = details.get("memory_percent", 0)

                    if cpu > 90 and self._notifier:
                        from app.telegram_bot import AlertType
                        await self._notifier.send_alert(
                            AlertType.HIGH_CPU_LOAD,
                            f"Высокая нагрузка CPU: {cpu:.1f}%",
                            alert_key="cpu_high",
                        )

                    if mem > 90 and self._notifier:
                        from app.telegram_bot import AlertType
                        await self._notifier.send_alert(
                            AlertType.HIGH_MEMORY_USAGE,
                            f"Высокое использование памяти: {mem:.1f}%",
                            alert_key="mem_high",
                        )

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor task: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _site_checker_task(self):
        """Check site accessibility periodically"""
        logger.info("Site checker task started (interval: 1h)")

        while self.running:
            try:
                if not self._site_checker:
                    await asyncio.sleep(60 * 60)
                    continue

                # Check sites blocked in Russia
                logger.info("Running site accessibility check for RU region...")
                results = await self._site_checker.check_region_blocked_sites("RU")

                accessible = results.get("accessible_via_proxy", 0)
                total = results.get("total_blocked_sites", 0)
                success_rate = results.get("success_rate", 0)

                logger.info(
                    f"Site check completed: {accessible}/{total} accessible "
                    f"({success_rate:.1f}% success rate)"
                )

                # Alert if many sites are inaccessible
                if total > 0 and success_rate < 50:
                    if self._notifier and self._notifier.is_configured():
                        from app.telegram_bot import AlertType
                        await self._notifier.send_alert(
                            AlertType.CUSTOM,
                            f"Низкая доступность сайтов!\n"
                            f"Доступно: {accessible}/{total} ({success_rate:.1f}%)",
                            alert_key="site_check_failed",
                        )

                await asyncio.sleep(60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in site checker task: {e}", exc_info=True)
                await asyncio.sleep(60 * 60)

    async def _daily_report_task(self):
        """Send daily statistics report"""
        logger.info("Daily report task started")

        while self.running:
            try:
                # Calculate time until next 9:00 AM
                now = datetime.now()
                next_report = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if now.hour >= 9:
                    next_report = next_report.replace(day=now.day + 1)

                wait_seconds = (next_report - now).total_seconds()
                logger.info(f"Next daily report in {wait_seconds / 3600:.1f} hours")

                await asyncio.sleep(wait_seconds)

                # Generate and send report
                if self.db and self._notifier and self._notifier.is_configured():
                    stats = self.db.get_stats()

                    # Get expiring users
                    expiring_threshold = int((time.time() + 7 * 24 * 60 * 60) * 1000)
                    all_users = self.db.get_users(limit=10000, offset=0)
                    expiring_soon = sum(
                        1 for u in all_users.get('users', [])
                        if 0 < u.get('expiry_time', 0) < expiring_threshold
                    )

                    report_stats = {
                        "total_users": stats.get("total_users", 0),
                        "active_users": stats.get("active_users", 0),
                        "disabled_users": stats.get("disabled_users", 0),
                        "expiring_soon": expiring_soon,
                        "total_upload": stats.get("total_upload", 0),
                        "total_download": stats.get("total_download", 0),
                        "today_upload": 0,
                        "today_download": 0,
                    }

                    await self._notifier.send_daily_report(report_stats)
                    logger.info("Daily report sent")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily report task: {e}", exc_info=True)
                await asyncio.sleep(60 * 60)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all background tasks"""
        return {
            "running": self.running,
            "tasks": {
                name: {
                    "running": not task.done(),
                    "cancelled": task.cancelled(),
                    "done": task.done()
                }
                for name, task in self.tasks.items()
            },
            "monitor_available": self._monitor is not None,
            "notifier_configured": self._notifier.is_configured() if self._notifier else False,
            "site_checker_available": self._site_checker is not None,
        }


# Global instance
background_tasks = BackgroundTaskManager()
