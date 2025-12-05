#!/usr/bin/env python3
"""
3x-ui Panel API Client - Extended Version
Handles all HTTP requests to the 3x-ui panel with advanced features
"""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from app.config import settings

logger = logging.getLogger(__name__)


class XUIClient:
    """Extended client for interacting with 3x-ui panel API"""

    def __init__(self):
        self.base_url = settings.XUI_PANEL_URL.rstrip('/')
        self.username = settings.XUI_PANEL_USERNAME
        self.password = settings.XUI_PANEL_PASSWORD
        self.session_cookie = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_login: float = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Login to 3x-ui panel and get session cookie"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/login"

            data = {
                "username": self.username,
                "password": self.password
            }

            async with session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        cookies = response.cookies
                        if 'session' in cookies:
                            self.session_cookie = cookies['session'].value
                        elif '3x-ui' in cookies:
                            self.session_cookie = cookies['3x-ui'].value
                        import time
                        self._last_login = time.time()
                        logger.info("Successfully logged in to 3x-ui panel")
                        return True

                logger.error(f"Login failed: {response.status}")
                return False

        except Exception as e:
            logger.error(f"Error logging in to 3x-ui: {e}")
            return False

    async def _request(
        self,
        method: str,
        endpoint: str,
        retry_on_401: bool = True,
        **kwargs
    ) -> Optional[Dict]:
        """Make authenticated request to 3x-ui panel"""
        try:
            if not self.session_cookie:
                if not await self.login():
                    return None

            session = await self._get_session()
            url = f"{self.base_url}{endpoint}"
            cookies = {'session': self.session_cookie, '3x-ui': self.session_cookie}

            async with session.request(method, url, cookies=cookies, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status in [401, 404] and retry_on_401:
                    if await self.login():
                        return await self._request(method, endpoint, retry_on_401=False, **kwargs)

                logger.error(f"Request failed: {method} {endpoint} - {response.status}")
                return None

        except Exception as e:
            logger.error(f"Error making request to 3x-ui: {e}")
            return None

    # ==================== INBOUND ENDPOINTS ====================

    async def get_inbounds(self) -> List[Dict]:
        """Get all inbounds"""
        result = await self._request("GET", "/panel/api/inbounds/list")
        if result and result.get("success"):
            return result.get("obj", [])
        return []

    async def get_inbound(self, inbound_id: int) -> Optional[Dict]:
        """Get specific inbound by ID"""
        result = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def add_inbound(self, inbound_data: Dict) -> Optional[Dict]:
        """Add new inbound"""
        result = await self._request("POST", "/panel/api/inbounds/add", json=inbound_data)
        return result

    async def update_inbound(self, inbound_id: int, inbound_data: Dict) -> Optional[Dict]:
        """Update existing inbound"""
        result = await self._request("POST", f"/panel/api/inbounds/update/{inbound_id}", json=inbound_data)
        return result

    async def delete_inbound(self, inbound_id: int) -> bool:
        """Delete inbound"""
        result = await self._request("POST", f"/panel/api/inbounds/del/{inbound_id}")
        return result and result.get("success", False)

    async def import_inbound(self, inbound_json: Dict) -> Optional[Dict]:
        """Import inbound from JSON"""
        result = await self._request("POST", "/panel/api/inbounds/import", json=inbound_json)
        return result

    # ==================== EXTENDED INBOUND METHODS ====================

    async def update_inbound_settings(
        self,
        inbound_id: int,
        settings_update: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Update specific settings of an inbound

        Args:
            inbound_id: Inbound ID
            settings_update: Dict with settings to update (merged with existing)

        Returns:
            Update result
        """
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        try:
            current_settings = json.loads(inbound.get("settings", "{}"))
            current_settings.update(settings_update)
            inbound["settings"] = json.dumps(current_settings)

            return await self.update_inbound(inbound_id, inbound)
        except json.JSONDecodeError as e:
            return {"success": False, "msg": f"Invalid settings JSON: {e}"}

    async def update_inbound_stream_settings(
        self,
        inbound_id: int,
        stream_update: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Update stream settings of an inbound

        Args:
            inbound_id: Inbound ID
            stream_update: Dict with stream settings to update

        Returns:
            Update result
        """
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        try:
            current_stream = json.loads(inbound.get("streamSettings", "{}"))
            self._deep_update(current_stream, stream_update)
            inbound["streamSettings"] = json.dumps(current_stream)

            return await self.update_inbound(inbound_id, inbound)
        except json.JSONDecodeError as e:
            return {"success": False, "msg": f"Invalid stream settings JSON: {e}"}

    async def update_inbound_sniffing(
        self,
        inbound_id: int,
        enabled: bool = True,
        dest_override: List[str] = None
    ) -> Optional[Dict]:
        """
        Update sniffing settings of an inbound

        Args:
            inbound_id: Inbound ID
            enabled: Enable/disable sniffing
            dest_override: List of dest override values ["http", "tls", "quic", "fakedns"]
        """
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        sniffing = {
            "enabled": enabled,
            "destOverride": dest_override or ["http", "tls", "quic", "fakedns"]
        }
        inbound["sniffing"] = json.dumps(sniffing)

        return await self.update_inbound(inbound_id, inbound)

    async def update_inbound_port(self, inbound_id: int, new_port: int) -> Optional[Dict]:
        """Change inbound port"""
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        inbound["port"] = new_port
        return await self.update_inbound(inbound_id, inbound)

    async def toggle_inbound(self, inbound_id: int, enable: bool) -> Optional[Dict]:
        """Enable/disable inbound"""
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        inbound["enable"] = enable
        return await self.update_inbound(inbound_id, inbound)

    async def update_reality_settings(
        self,
        inbound_id: int,
        dest: str = None,
        server_names: List[str] = None,
        private_key: str = None,
        short_ids: List[str] = None,
        fingerprint: str = None
    ) -> Optional[Dict]:
        """
        Update Reality settings for an inbound

        Args:
            inbound_id: Inbound ID
            dest: Destination domain:port (e.g., "www.microsoft.com:443")
            server_names: List of allowed server names
            private_key: Reality private key
            short_ids: List of short IDs
            fingerprint: Browser fingerprint (chrome, firefox, safari, etc.)
        """
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return {"success": False, "msg": "Inbound not found"}

        try:
            stream_settings = json.loads(inbound.get("streamSettings", "{}"))

            if stream_settings.get("security") != "reality":
                return {"success": False, "msg": "Inbound is not using Reality"}

            reality = stream_settings.get("realitySettings", {})

            if dest:
                reality["dest"] = dest
            if server_names:
                reality["serverNames"] = server_names
            if private_key:
                reality["privateKey"] = private_key
            if short_ids:
                reality["shortIds"] = short_ids
            if fingerprint:
                reality["fingerprint"] = fingerprint

            stream_settings["realitySettings"] = reality
            inbound["streamSettings"] = json.dumps(stream_settings)

            return await self.update_inbound(inbound_id, inbound)

        except json.JSONDecodeError as e:
            return {"success": False, "msg": f"Invalid JSON: {e}"}

    async def clone_inbound(
        self,
        source_id: int,
        new_port: int,
        new_remark: str = None
    ) -> Optional[Dict]:
        """
        Clone an inbound to a new port

        Args:
            source_id: Source inbound ID to clone
            new_port: Port for the new inbound
            new_remark: Optional new remark/name
        """
        source = await self.get_inbound(source_id)
        if not source:
            return {"success": False, "msg": "Source inbound not found"}

        # Create new inbound data
        new_inbound = {
            "remark": new_remark or f"{source.get('remark', 'Cloned')}_copy",
            "enable": True,
            "port": new_port,
            "protocol": source.get("protocol"),
            "settings": source.get("settings", "{}"),
            "streamSettings": source.get("streamSettings", "{}"),
            "sniffing": source.get("sniffing", "{}"),
            "expiryTime": 0,
            "listen": "",
            "total": 0,
            "up": 0,
            "down": 0,
        }

        # Clear clients from settings
        try:
            settings = json.loads(new_inbound["settings"])
            settings["clients"] = []
            new_inbound["settings"] = json.dumps(settings)
        except:
            pass

        return await self.add_inbound(new_inbound)

    def _deep_update(self, base: Dict, update: Dict):
        """Deep update nested dictionary"""
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    # ==================== CLIENT ENDPOINTS ====================

    async def get_online_clients(self) -> List[str]:
        """Get list of currently online client emails"""
        result = await self._request("POST", "/panel/api/inbounds/onlines")
        if result and result.get("success"):
            return result.get("obj", [])
        return []

    async def get_last_online(self) -> Dict[str, int]:
        """Get last online timestamps for all clients"""
        result = await self._request("POST", "/panel/api/inbounds/lastOnline")
        if result and result.get("success"):
            return result.get("obj", {})
        return {}

    async def get_client_traffics(self, email: str) -> Optional[Dict]:
        """Get traffic data for specific client"""
        result = await self._request("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def get_client_ips(self, email: str) -> List[str]:
        """Get IP addresses used by client"""
        result = await self._request("POST", f"/panel/api/inbounds/clientIps/{email}")
        if result and result.get("success"):
            ips = result.get("obj", "")
            if isinstance(ips, str):
                return [ip.strip() for ip in ips.split(",") if ip.strip()]
            return ips if isinstance(ips, list) else []
        return []

    async def clear_client_ips(self, email: str) -> bool:
        """Clear IP history for client"""
        result = await self._request("POST", f"/panel/api/inbounds/clearClientIps/{email}")
        return result and result.get("success", False)

    async def add_client(self, inbound_id: int, client_data: Dict) -> Optional[Dict]:
        """Add client to inbound"""
        data = {
            "id": inbound_id,
            "settings": client_data
        }
        result = await self._request("POST", "/panel/api/inbounds/addClient", json=data)
        return result

    async def update_client(self, client_id: str, client_data: Dict) -> Optional[Dict]:
        """Update client configuration"""
        result = await self._request("POST", f"/panel/api/inbounds/updateClient/{client_id}", json=client_data)
        return result

    async def delete_client(self, inbound_id: int, client_id: str) -> bool:
        """Delete client from inbound"""
        result = await self._request("POST", f"/panel/api/inbounds/{inbound_id}/delClient/{client_id}")
        return result and result.get("success", False)

    async def delete_client_by_email(self, inbound_id: int, email: str) -> bool:
        """Delete client by email"""
        result = await self._request("POST", f"/panel/api/inbounds/{inbound_id}/delClientByEmail/{email}")
        return result and result.get("success", False)

    async def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        """Reset traffic counter for single client"""
        result = await self._request("POST", f"/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}")
        return result and result.get("success", False)

    async def reset_all_traffics(self) -> bool:
        """Reset all traffic counters system-wide"""
        result = await self._request("POST", "/panel/api/inbounds/resetAllTraffics")
        return result and result.get("success", False)

    async def reset_inbound_client_traffics(self, inbound_id: int) -> bool:
        """Reset traffic for all clients in specific inbound"""
        result = await self._request("POST", f"/panel/api/inbounds/resetAllClientTraffics/{inbound_id}")
        return result and result.get("success", False)

    async def delete_depleted_clients(self, inbound_id: int) -> Optional[Dict]:
        """Delete clients who exceeded their traffic limits"""
        result = await self._request("POST", f"/panel/api/inbounds/delDepletedClients/{inbound_id}")
        return result

    async def update_client_traffic(self, email: str, traffic_gb: int) -> Optional[Dict]:
        """Update client traffic limit"""
        traffic_bytes = traffic_gb * 1024 * 1024 * 1024
        result = await self._request(
            "POST",
            f"/panel/api/inbounds/updateClientTraffic/{email}",
            json={"total": traffic_bytes}
        )
        return result

    # ==================== SERVER ENDPOINTS ====================

    async def get_server_status(self) -> Optional[Dict]:
        """Get server status"""
        result = await self._request("GET", "/panel/api/server/status")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def get_xray_version(self) -> Optional[List[str]]:
        """Get available Xray versions"""
        result = await self._request("GET", "/panel/api/server/getXrayVersion")
        if result and result.get("success"):
            return result.get("obj", [])
        return None

    async def get_config_json(self) -> Optional[Dict]:
        """Get Xray configuration as JSON"""
        result = await self._request("GET", "/panel/api/server/getConfigJson")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def restart_xray(self) -> bool:
        """Restart Xray service"""
        result = await self._request("POST", "/panel/api/server/restartXrayService")
        return result and result.get("success", False)

    async def stop_xray(self) -> bool:
        """Stop Xray service"""
        result = await self._request("POST", "/panel/api/server/stopXrayService")
        return result and result.get("success", False)

    async def install_xray(self, version: str) -> bool:
        """Install specific Xray version"""
        result = await self._request("POST", f"/panel/api/server/installXray/{version}")
        return result and result.get("success", False)

    async def get_new_uuid(self) -> Optional[str]:
        """Generate new UUID"""
        result = await self._request("GET", "/panel/api/server/getNewUUID")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def get_new_x25519_cert(self) -> Optional[Dict]:
        """Generate new X25519 certificate for Reality"""
        result = await self._request("GET", "/panel/api/server/getNewX25519Cert")
        if result and result.get("success"):
            return result.get("obj")
        return None

    async def get_logs(self, count: int = 100, level: str = "", syslog: str = "") -> Optional[List[str]]:
        """Get application logs"""
        data = {"level": level, "syslog": syslog}
        result = await self._request("POST", f"/panel/api/server/logs/{count}", json=data)
        if result and result.get("success"):
            return result.get("obj", [])
        return None

    async def get_xray_logs(self, count: int = 100) -> Optional[List[str]]:
        """Get Xray logs"""
        result = await self._request("POST", f"/panel/api/server/xraylogs/{count}")
        if result and result.get("success"):
            return result.get("obj", [])
        return None

    async def get_cpu_history(self, bucket: str = "1m") -> Optional[List]:
        """Get CPU usage history"""
        result = await self._request("GET", f"/panel/api/server/cpuHistory/{bucket}")
        if result and result.get("success"):
            return result.get("obj", [])
        return None

    async def update_geo_files(self) -> bool:
        """Update GeoIP and GeoSite files"""
        result = await self._request("POST", "/panel/api/server/updateGeofile")
        return result and result.get("success", False)

    async def get_database(self) -> Optional[bytes]:
        """Download database file"""
        try:
            session = await self._get_session()
            if not self.session_cookie:
                await self.login()

            cookies = {'session': self.session_cookie, '3x-ui': self.session_cookie}
            url = f"{self.base_url}/panel/api/server/getDb"

            async with session.get(url, cookies=cookies) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            logger.error(f"Error downloading database: {e}")
        return None

    async def import_database(self, db_content: bytes) -> bool:
        """Import database file"""
        try:
            session = await self._get_session()
            if not self.session_cookie:
                await self.login()

            cookies = {'session': self.session_cookie, '3x-ui': self.session_cookie}
            url = f"{self.base_url}/panel/api/server/importDB"

            data = aiohttp.FormData()
            data.add_field('file', db_content, filename='x-ui.db')

            async with session.post(url, cookies=cookies, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("success", False)
        except Exception as e:
            logger.error(f"Error importing database: {e}")
        return False

    async def backup_to_telegram(self) -> bool:
        """Backup database to Telegram (if configured in 3x-ui)"""
        result = await self._request("GET", "/panel/api/backuptotgbot")
        return result and result.get("success", False)

    # ==================== HEALTH CHECK ====================

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on 3x-ui panel"""
        result = {
            "api_accessible": False,
            "authenticated": False,
            "xray_running": False,
            "details": {}
        }

        try:
            # Check if API is accessible
            session = await self._get_session()
            async with session.get(f"{self.base_url}/login", timeout=aiohttp.ClientTimeout(total=5)) as response:
                result["api_accessible"] = response.status in [200, 302]

            # Check authentication
            if self.session_cookie or await self.login():
                result["authenticated"] = True

                # Check server status
                status = await self.get_server_status()
                if status:
                    result["xray_running"] = status.get("xray", {}).get("state") == "running"
                    result["details"] = {
                        "cpu": status.get("cpu"),
                        "mem": status.get("mem"),
                        "xray_version": status.get("xray", {}).get("version"),
                    }

        except Exception as e:
            result["error"] = str(e)

        return result


# Global instance
xui_client = XUIClient()
