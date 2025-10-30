"""
Background Tasks for XUI Manager
Handles periodic tasks like update checks, expired user cleanup, etc.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import time

from app.database import XUIDatabase
from app.update_manager import update_manager

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages all background tasks"""

    def __init__(self):
        self.tasks = {}
        self.running = False
        self.db = XUIDatabase()

    async def start(self):
        """Start all background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return

        self.running = True
        logger.info("Starting background tasks...")

        # Start update checker (every 24 hours)
        self.tasks['update_checker'] = asyncio.create_task(self._update_checker_task())

        # Start expired users cleanup (every 1 hour)
        self.tasks['expired_cleanup'] = asyncio.create_task(self._expired_cleanup_task())

        # Start low traffic alerts (every 6 hours)
        self.tasks['low_traffic_alerts'] = asyncio.create_task(self._low_traffic_alerts_task())

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
                # Check for updates
                logger.info("Checking for updates...")
                update_info = await update_manager.check_for_updates(force=False)

                if update_info.get("update_available"):
                    logger.info(
                        f"Update available: {update_info['current_version']} -> {update_info['latest_version']}"
                    )
                else:
                    logger.info(f"No updates available (current: {update_info.get('current_version')})")

                # Wait 24 hours
                await asyncio.sleep(24 * 60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update checker task: {e}", exc_info=True)
                # Wait 1 hour before retry
                await asyncio.sleep(60 * 60)

    async def _expired_cleanup_task(self):
        """Clean up expired users every hour"""
        logger.info("Expired users cleanup task started (interval: 1h)")

        while self.running:
            try:
                # Get current timestamp
                current_time = int(time.time() * 1000)

                # Find expired users (expiry_time > 0 and expiry_time < now)
                expired_users = self.db.get_users(
                    limit=1000,
                    offset=0,
                    search=None,
                    inbound_id=None,
                    enable=None  # Get all users
                )

                expired_count = 0
                disabled_count = 0

                for user in expired_users.get('users', []):
                    expiry_time = user.get('expiry_time', 0)

                    # Check if expired
                    if expiry_time > 0 and expiry_time < current_time:
                        # Check if user is still enabled
                        if user.get('enable', False):
                            # Disable expired user
                            try:
                                self.db.toggle_user_status(user['id'], False)
                                disabled_count += 1
                                logger.info(f"Disabled expired user: {user.get('email', user['id'])}")
                            except Exception as e:
                                logger.error(f"Error disabling user {user['id']}: {e}")

                        expired_count += 1

                if expired_count > 0:
                    logger.info(f"Processed {expired_count} expired users, disabled {disabled_count}")
                else:
                    logger.debug("No expired users found")

                # Wait 1 hour
                await asyncio.sleep(60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in expired cleanup task: {e}", exc_info=True)
                # Wait 10 minutes before retry
                await asyncio.sleep(10 * 60)

    async def _low_traffic_alerts_task(self):
        """Monitor users with low traffic and log alerts"""
        logger.info("Low traffic alerts task started (interval: 6h)")

        while self.running:
            try:
                # Get users with less than 1GB remaining
                low_traffic_threshold = 1024 * 1024 * 1024  # 1GB in bytes
                low_traffic_users = self.db.get_low_traffic_users(
                    threshold=low_traffic_threshold,
                    sort_by="remaining",
                    order="asc"
                )

                if low_traffic_users:
                    logger.info(f"Found {len(low_traffic_users)} users with low traffic (<1GB remaining)")

                    # Log top 10 users
                    for i, user in enumerate(low_traffic_users[:10], 1):
                        remaining = user.get('remaining', 0)
                        remaining_gb = remaining / (1024 ** 3)
                        logger.info(
                            f"  {i}. {user.get('email')}: {remaining_gb:.2f}GB remaining"
                        )

                # Wait 6 hours
                await asyncio.sleep(6 * 60 * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in low traffic alerts task: {e}", exc_info=True)
                # Wait 1 hour before retry
                await asyncio.sleep(60 * 60)

    def get_status(self) -> dict:
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
            }
        }


# Global instance
background_tasks = BackgroundTaskManager()
