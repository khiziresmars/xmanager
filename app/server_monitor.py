#!/usr/bin/env python3
"""
Server Health Monitor for XUI-Manager
Monitors server health with false-positive protection
"""

import asyncio
import json
import logging
import os
import time
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerHealthState:
    """Overall server health state"""
    overall_status: HealthStatus
    checks: Dict[str, HealthCheckResult]
    consecutive_failures: int
    last_healthy: float
    last_check: float
    uptime_seconds: float
    alerts_sent: List[str] = field(default_factory=list)


class ServerHealthMonitor:
    """
    Server health monitor with false-positive protection

    Features:
    - Multiple check types (API, Xray, Database, System)
    - Consecutive failure threshold before alerting
    - History tracking for trend analysis
    - Anti-spam alert mechanism
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        check_interval: int = 60,
        state_file: str = "/opt/xui-manager/monitor_state.json"
    ):
        self.failure_threshold = failure_threshold
        self.check_interval = check_interval
        self.state_file = state_file

        # State
        self.check_history: List[Dict[str, HealthCheckResult]] = []
        self.consecutive_failures: int = 0
        self.last_healthy: float = time.time()
        self.last_alert_time: Dict[str, float] = {}
        self._running: bool = False

        # Load state
        self._load_state()

    def _load_state(self):
        """Load monitor state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.consecutive_failures = data.get("consecutive_failures", 0)
                    self.last_healthy = data.get("last_healthy", time.time())
                    self.last_alert_time = data.get("last_alert_time", {})
        except Exception as e:
            logger.error(f"Error loading monitor state: {e}")

    def _save_state(self):
        """Save monitor state to file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump({
                    "consecutive_failures": self.consecutive_failures,
                    "last_healthy": self.last_healthy,
                    "last_alert_time": self.last_alert_time,
                    "last_check": time.time(),
                }, f)
        except Exception as e:
            logger.error(f"Error saving monitor state: {e}")

    async def check_xui_api(self) -> HealthCheckResult:
        """Check 3x-ui panel API availability"""
        start_time = time.time()

        try:
            import aiohttp
            from app.config import settings

            url = f"{settings.XUI_PANEL_URL}/login"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    allow_redirects=True
                ) as response:
                    latency = (time.time() - start_time) * 1000

                    if response.status in [200, 302, 404]:
                        return HealthCheckResult(
                            name="xui_api",
                            status=HealthStatus.HEALTHY,
                            message="3x-ui panel is responding",
                            latency_ms=latency,
                            details={"status_code": response.status}
                        )
                    else:
                        return HealthCheckResult(
                            name="xui_api",
                            status=HealthStatus.UNHEALTHY,
                            message=f"3x-ui panel returned {response.status}",
                            latency_ms=latency,
                            details={"status_code": response.status}
                        )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                name="xui_api",
                status=HealthStatus.UNHEALTHY,
                message="3x-ui panel timeout",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name="xui_api",
                status=HealthStatus.UNHEALTHY,
                message=f"3x-ui panel error: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def check_xray_process(self) -> HealthCheckResult:
        """Check if Xray process is running"""
        start_time = time.time()

        try:
            # Check for xray process
            xray_running = False
            xray_pid = None
            xray_memory = 0

            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'xray' in proc.info['name'].lower():
                        xray_running = True
                        xray_pid = proc.info['pid']
                        xray_memory = proc.info['memory_info'].rss if proc.info['memory_info'] else 0
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            latency = (time.time() - start_time) * 1000

            if xray_running:
                return HealthCheckResult(
                    name="xray_process",
                    status=HealthStatus.HEALTHY,
                    message="Xray is running",
                    latency_ms=latency,
                    details={
                        "pid": xray_pid,
                        "memory_mb": xray_memory / (1024 * 1024) if xray_memory else 0
                    }
                )
            else:
                return HealthCheckResult(
                    name="xray_process",
                    status=HealthStatus.UNHEALTHY,
                    message="Xray process not found",
                    latency_ms=latency,
                )

        except Exception as e:
            return HealthCheckResult(
                name="xray_process",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking Xray: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def check_database(self) -> HealthCheckResult:
        """Check database accessibility"""
        start_time = time.time()

        try:
            from app.config import settings
            import sqlite3

            db_path = settings.XUI_DB_PATH

            if not os.path.exists(db_path):
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database file not found: {db_path}",
                    latency_ms=(time.time() - start_time) * 1000,
                )

            # Try to connect and query
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM client_traffics")
            count = cursor.fetchone()[0]
            conn.close()

            latency = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database is accessible",
                latency_ms=latency,
                details={
                    "user_count": count,
                    "db_size_mb": os.path.getsize(db_path) / (1024 * 1024)
                }
            )

        except sqlite3.OperationalError as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking database: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def check_system_resources(self) -> HealthCheckResult:
        """Check system resources (CPU, Memory, Disk)"""
        start_time = time.time()

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory
            memory = psutil.virtual_memory()
            mem_percent = memory.percent

            # Disk
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            latency = (time.time() - start_time) * 1000

            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            warnings = []

            if cpu_percent > 90:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"CPU critical: {cpu_percent}%")
            elif cpu_percent > 75:
                status = HealthStatus.DEGRADED
                warnings.append(f"CPU high: {cpu_percent}%")

            if mem_percent > 90:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Memory critical: {mem_percent}%")
            elif mem_percent > 80:
                if status != HealthStatus.UNHEALTHY:
                    status = HealthStatus.DEGRADED
                warnings.append(f"Memory high: {mem_percent}%")

            if disk_percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Disk critical: {disk_percent}%")
            elif disk_percent > 85:
                if status != HealthStatus.UNHEALTHY:
                    status = HealthStatus.DEGRADED
                warnings.append(f"Disk high: {disk_percent}%")

            message = "; ".join(warnings) if warnings else "System resources OK"

            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                latency_ms=latency,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": mem_percent,
                    "memory_used_gb": memory.used / (1024 ** 3),
                    "memory_total_gb": memory.total / (1024 ** 3),
                    "disk_percent": disk_percent,
                    "disk_used_gb": disk.used / (1024 ** 3),
                    "disk_total_gb": disk.total / (1024 ** 3),
                }
            )

        except Exception as e:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking resources: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def check_xray_service(self) -> HealthCheckResult:
        """Check Xray systemd service status"""
        start_time = time.time()

        try:
            # Check x-ui service (which manages xray)
            result = subprocess.run(
                ["systemctl", "is-active", "x-ui"],
                capture_output=True,
                text=True,
                timeout=5
            )

            latency = (time.time() - start_time) * 1000
            service_status = result.stdout.strip()

            if service_status == "active":
                return HealthCheckResult(
                    name="xray_service",
                    status=HealthStatus.HEALTHY,
                    message="x-ui service is active",
                    latency_ms=latency,
                    details={"service_status": service_status}
                )
            else:
                return HealthCheckResult(
                    name="xray_service",
                    status=HealthStatus.UNHEALTHY,
                    message=f"x-ui service is {service_status}",
                    latency_ms=latency,
                    details={"service_status": service_status}
                )

        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                name="xray_service",
                status=HealthStatus.UNKNOWN,
                message="Timeout checking service",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name="xray_service",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking service: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def check_network_connectivity(self) -> HealthCheckResult:
        """Check basic network connectivity"""
        start_time = time.time()

        try:
            import aiohttp

            # Try to reach a reliable endpoint
            test_urls = [
                "https://www.google.com",
                "https://www.cloudflare.com",
                "https://www.microsoft.com",
            ]

            async with aiohttp.ClientSession() as session:
                for url in test_urls:
                    try:
                        async with session.head(
                            url,
                            timeout=aiohttp.ClientTimeout(total=5),
                            allow_redirects=True
                        ) as response:
                            if response.status < 400:
                                return HealthCheckResult(
                                    name="network",
                                    status=HealthStatus.HEALTHY,
                                    message="Network connectivity OK",
                                    latency_ms=(time.time() - start_time) * 1000,
                                    details={"tested_url": url}
                                )
                    except:
                        continue

            return HealthCheckResult(
                name="network",
                status=HealthStatus.UNHEALTHY,
                message="Cannot reach external services",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return HealthCheckResult(
                name="network",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking network: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def run_all_checks(self) -> ServerHealthState:
        """Run all health checks and return overall state"""
        checks: Dict[str, HealthCheckResult] = {}

        # Run checks in parallel
        check_tasks = [
            self.check_xui_api(),
            self.check_xray_process(),
            self.check_xray_service(),
            self.check_database(),
            self.check_system_resources(),
            self.check_network_connectivity(),
        ]

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        check_names = [
            "xui_api", "xray_process", "xray_service",
            "database", "system_resources", "network"
        ]

        for name, result in zip(check_names, results):
            if isinstance(result, Exception):
                checks[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(result)}"
                )
            else:
                checks[name] = result

        # Determine overall status
        statuses = [c.status for c in checks.values()]

        if HealthStatus.UNHEALTHY in statuses:
            # Count critical checks
            critical_checks = ["xui_api", "xray_process", "database"]
            critical_unhealthy = sum(
                1 for name in critical_checks
                if checks.get(name, HealthCheckResult(name="", status=HealthStatus.UNKNOWN)).status == HealthStatus.UNHEALTHY
            )

            if critical_unhealthy >= 2:
                overall_status = HealthStatus.UNHEALTHY
                self.consecutive_failures += 1
            else:
                overall_status = HealthStatus.DEGRADED
                # Only increment failures for truly critical issues
                if critical_unhealthy >= 1:
                    self.consecutive_failures += 1
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
            # Reset consecutive failures on degraded (not critical)
            self.consecutive_failures = max(0, self.consecutive_failures - 1)
        else:
            overall_status = HealthStatus.HEALTHY
            self.consecutive_failures = 0
            self.last_healthy = time.time()

        # Update history
        self.check_history.append(checks)
        if len(self.check_history) > 60:  # Keep last 60 checks (1 hour at 1min interval)
            self.check_history.pop(0)

        # Calculate uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time

        # Save state
        self._save_state()

        return ServerHealthState(
            overall_status=overall_status,
            checks=checks,
            consecutive_failures=self.consecutive_failures,
            last_healthy=self.last_healthy,
            last_check=time.time(),
            uptime_seconds=uptime_seconds,
        )

    def should_alert(self, alert_type: str) -> bool:
        """
        Determine if an alert should be sent

        Protection against false positives:
        - Requires consecutive_failures >= threshold
        - Respects cooldown periods
        """
        # Check consecutive failures
        if self.consecutive_failures < self.failure_threshold:
            return False

        # Check cooldown (5 minutes between same alerts)
        cooldown = 300  # 5 minutes
        last_alert = self.last_alert_time.get(alert_type, 0)

        if time.time() - last_alert < cooldown:
            return False

        return True

    def mark_alert_sent(self, alert_type: str):
        """Mark that an alert was sent"""
        self.last_alert_time[alert_type] = time.time()
        self._save_state()

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of current health status"""
        return {
            "consecutive_failures": self.consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "last_healthy": datetime.fromtimestamp(self.last_healthy).isoformat() if self.last_healthy else None,
            "history_length": len(self.check_history),
            "would_alert": self.consecutive_failures >= self.failure_threshold,
        }

    def get_health_trend(self) -> Dict[str, Any]:
        """Analyze health trend from history"""
        if len(self.check_history) < 2:
            return {"trend": "unknown", "samples": len(self.check_history)}

        # Count statuses in recent history
        recent = self.check_history[-10:]  # Last 10 checks
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0

        for checks in recent:
            statuses = [c.status for c in checks.values()]
            if HealthStatus.UNHEALTHY in statuses:
                unhealthy_count += 1
            elif HealthStatus.DEGRADED in statuses:
                degraded_count += 1
            else:
                healthy_count += 1

        # Determine trend
        if unhealthy_count > len(recent) / 2:
            trend = "declining"
        elif healthy_count > len(recent) * 0.8:
            trend = "stable"
        elif healthy_count > degraded_count + unhealthy_count:
            trend = "improving"
        else:
            trend = "unstable"

        return {
            "trend": trend,
            "samples": len(recent),
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
        }


# Global instance
_monitor: Optional[ServerHealthMonitor] = None


def get_monitor() -> ServerHealthMonitor:
    """Get global monitor instance"""
    global _monitor
    if _monitor is None:
        try:
            from app.config import settings
            _monitor = ServerHealthMonitor(
                failure_threshold=settings.MONITOR_FAILURE_THRESHOLD,
                check_interval=settings.MONITOR_INTERVAL,
                state_file=settings.MONITOR_STATE_FILE,
            )
        except Exception:
            _monitor = ServerHealthMonitor()
    return _monitor
