"""
Nginx Manager for XUI-Manager
Handles nginx configuration, validation, inbound routing requirements
"""

import os
import re
import json
import subprocess
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InboundType(Enum):
    """Inbound transport types that may need nginx config"""
    WEBSOCKET = "ws"
    GRPC = "grpc"
    HTTP_UPGRADE = "httpupgrade"
    SPLIT_HTTP = "splithttp"
    TCP = "tcp"
    QUIC = "quic"


@dataclass
class NginxLocation:
    """Nginx location block"""
    path: str
    upstream: str
    websocket: bool = False
    grpc: bool = False
    proxy_headers: Dict[str, str] = None

    def to_config(self) -> str:
        """Generate nginx location config"""
        config = f"    location {self.path} {{\n"

        if self.grpc:
            config += f"        grpc_pass grpc://{self.upstream};\n"
            config += "        grpc_set_header Host $host;\n"
            config += "        grpc_set_header X-Real-IP $remote_addr;\n"
        else:
            config += f"        proxy_pass http://{self.upstream};\n"
            config += "        proxy_http_version 1.1;\n"
            config += "        proxy_set_header Host $host;\n"
            config += "        proxy_set_header X-Real-IP $remote_addr;\n"
            config += "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"

            if self.websocket:
                config += "        proxy_set_header Upgrade $http_upgrade;\n"
                config += "        proxy_set_header Connection 'upgrade';\n"
                config += "        proxy_cache_bypass $http_upgrade;\n"
                config += "        proxy_read_timeout 86400s;\n"
                config += "        proxy_send_timeout 86400s;\n"

        if self.proxy_headers:
            for key, value in self.proxy_headers.items():
                config += f"        proxy_set_header {key} {value};\n"

        config += "    }\n"
        return config


@dataclass
class NginxConfigStatus:
    """Status of nginx configuration"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    has_xui_manager: bool
    has_xui_panel: bool
    domains: List[str]
    ssl_enabled: bool
    inbound_locations: Dict[str, bool]  # path -> configured


class NginxManager:
    """Manages nginx configuration for 3x-ui and XUI-Manager"""

    SITES_AVAILABLE = "/etc/nginx/sites-available"
    SITES_ENABLED = "/etc/nginx/sites-enabled"
    NGINX_CONF = "/etc/nginx/nginx.conf"

    def __init__(self):
        self.config_files = self._find_config_files()

    def _find_config_files(self) -> List[str]:
        """Find all nginx configuration files"""
        files = []

        # Check sites-enabled
        if os.path.exists(self.SITES_ENABLED):
            for f in os.listdir(self.SITES_ENABLED):
                path = os.path.join(self.SITES_ENABLED, f)
                if os.path.isfile(path) or os.path.islink(path):
                    # Resolve symlink
                    real_path = os.path.realpath(path)
                    if real_path not in files:
                        files.append(real_path)

        # Check sites-available for unlinked configs
        if os.path.exists(self.SITES_AVAILABLE):
            for f in os.listdir(self.SITES_AVAILABLE):
                path = os.path.join(self.SITES_AVAILABLE, f)
                if os.path.isfile(path) and path not in files:
                    files.append(path)

        return files

    def test_config(self) -> Tuple[bool, str]:
        """Test nginx configuration"""
        try:
            result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True,
                text=True
            )
            success = result.returncode == 0
            output = result.stderr if result.stderr else result.stdout
            return success, output
        except Exception as e:
            return False, str(e)

    def reload_nginx(self) -> Tuple[bool, str]:
        """Reload nginx configuration"""
        try:
            # First test config
            valid, error = self.test_config()
            if not valid:
                return False, f"Config invalid: {error}"

            result = subprocess.run(
                ['systemctl', 'reload', 'nginx'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return True, "Nginx reloaded successfully"
            else:
                return False, result.stderr or "Reload failed"

        except Exception as e:
            return False, str(e)

    def get_config_content(self, config_file: str = None) -> Dict[str, Any]:
        """Get content of nginx configuration file(s)"""
        result = {
            "success": True,
            "configs": {}
        }

        try:
            if config_file:
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        result["configs"][config_file] = f.read()
                else:
                    return {"success": False, "error": f"File not found: {config_file}"}
            else:
                # Get all configs
                for path in self.config_files:
                    try:
                        with open(path, 'r') as f:
                            result["configs"][path] = f.read()
                    except Exception as e:
                        result["configs"][path] = f"Error reading: {e}"

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_config(self) -> NginxConfigStatus:
        """Analyze nginx configuration for XUI requirements"""
        errors = []
        warnings = []
        has_xui_manager = False
        has_xui_panel = False
        domains = []
        ssl_enabled = False
        inbound_locations = {}

        for config_path in self.config_files:
            try:
                with open(config_path, 'r') as f:
                    content = f.read()

                # Check for XUI-Manager location
                if '/manager/' in content or 'proxy_pass http://127.0.0.1:8888' in content:
                    has_xui_manager = True

                # Check for 3x-ui panel
                if 'proxy_pass http://127.0.0.1:2053' in content or '/panel/' in content:
                    has_xui_panel = True

                # Extract domains
                domain_matches = re.findall(r'server_name\s+([^;]+);', content)
                for match in domain_matches:
                    for domain in match.split():
                        domain = domain.strip()
                        if domain and domain not in ['_', 'localhost'] and not domain.startswith('$'):
                            domains.append(domain)

                # Check SSL
                if 'ssl_certificate' in content or 'listen 443 ssl' in content:
                    ssl_enabled = True

                # Find location blocks for potential inbounds
                location_matches = re.findall(r'location\s+(/[^\s{]+)\s*\{', content)
                for loc in location_matches:
                    inbound_locations[loc] = True

            except Exception as e:
                errors.append(f"Error reading {config_path}: {e}")

        # Test configuration validity
        valid, test_output = self.test_config()
        if not valid:
            errors.append(f"Nginx config test failed: {test_output}")

        # Add warnings
        if not has_xui_manager:
            warnings.append("XUI-Manager location not configured in nginx")

        if not ssl_enabled:
            warnings.append("SSL not configured - recommend enabling HTTPS")

        return NginxConfigStatus(
            valid=valid,
            errors=errors,
            warnings=warnings,
            has_xui_manager=has_xui_manager,
            has_xui_panel=has_xui_panel,
            domains=list(set(domains)),
            ssl_enabled=ssl_enabled,
            inbound_locations=inbound_locations
        )

    def get_inbound_nginx_requirements(self, inbounds: List[Dict]) -> List[Dict[str, Any]]:
        """
        Analyze inbounds and determine which need nginx configuration
        Returns list of required nginx configurations
        """
        requirements = []

        for inbound in inbounds:
            try:
                stream_settings = inbound.get('stream_settings', '{}')
                if isinstance(stream_settings, str):
                    stream_settings = json.loads(stream_settings)

                network = stream_settings.get('network', 'tcp')
                security = stream_settings.get('security', '')
                port = inbound.get('port', 0)
                remark = inbound.get('remark', f'Inbound {inbound.get("id")}')

                requirement = {
                    "inbound_id": inbound.get('id'),
                    "remark": remark,
                    "port": port,
                    "network": network,
                    "needs_nginx": False,
                    "reason": "",
                    "suggested_config": None
                }

                # WebSocket needs nginx for path-based routing
                if network == 'ws':
                    ws_settings = stream_settings.get('wsSettings', {})
                    path = ws_settings.get('path', '/ws')

                    requirement["needs_nginx"] = True
                    requirement["reason"] = "WebSocket transport requires nginx reverse proxy for path routing"
                    requirement["suggested_config"] = {
                        "type": "websocket",
                        "path": path,
                        "upstream": f"127.0.0.1:{port}",
                        "location": NginxLocation(
                            path=path,
                            upstream=f"127.0.0.1:{port}",
                            websocket=True
                        ).to_config()
                    }

                # gRPC needs special nginx config
                elif network == 'grpc':
                    grpc_settings = stream_settings.get('grpcSettings', {})
                    service_name = grpc_settings.get('serviceName', 'grpc')

                    requirement["needs_nginx"] = True
                    requirement["reason"] = "gRPC transport requires nginx with grpc_pass"
                    requirement["suggested_config"] = {
                        "type": "grpc",
                        "service_name": service_name,
                        "upstream": f"127.0.0.1:{port}",
                        "location": f"""    location /{service_name} {{
        grpc_pass grpc://127.0.0.1:{port};
        grpc_set_header Host $host;
        grpc_set_header X-Real-IP $remote_addr;
    }}
"""
                    }

                # HTTP Upgrade (similar to WebSocket)
                elif network == 'httpupgrade':
                    http_settings = stream_settings.get('httpupgradeSettings', {})
                    path = http_settings.get('path', '/httpupgrade')

                    requirement["needs_nginx"] = True
                    requirement["reason"] = "HTTP Upgrade transport requires nginx reverse proxy"
                    requirement["suggested_config"] = {
                        "type": "httpupgrade",
                        "path": path,
                        "upstream": f"127.0.0.1:{port}",
                        "location": NginxLocation(
                            path=path,
                            upstream=f"127.0.0.1:{port}",
                            websocket=True  # Similar handling
                        ).to_config()
                    }

                # Split HTTP
                elif network == 'splithttp':
                    split_settings = stream_settings.get('splithttpSettings', {})
                    path = split_settings.get('path', '/splithttp')

                    requirement["needs_nginx"] = True
                    requirement["reason"] = "Split HTTP transport requires nginx reverse proxy"
                    requirement["suggested_config"] = {
                        "type": "splithttp",
                        "path": path,
                        "upstream": f"127.0.0.1:{port}"
                    }

                # Reality/TLS on port 443 may conflict with nginx
                elif security == 'reality' and port == 443:
                    requirement["needs_nginx"] = False
                    requirement["reason"] = "Reality on port 443 - ensure nginx doesn't listen on 443 or use different port"
                    requirement["warning"] = True

                requirements.append(requirement)

            except Exception as e:
                logger.error(f"Error analyzing inbound: {e}")

        return requirements

    def generate_inbound_config(self, inbounds_requirements: List[Dict]) -> str:
        """Generate nginx configuration for inbounds that need it"""
        config_parts = []

        for req in inbounds_requirements:
            if req.get("needs_nginx") and req.get("suggested_config"):
                suggested = req["suggested_config"]
                if "location" in suggested:
                    config_parts.append(f"    # {req['remark']} ({req['network']})")
                    config_parts.append(suggested["location"])

        if not config_parts:
            return "# No inbounds require nginx configuration"

        return "\n".join(config_parts)

    def add_location_to_config(
        self,
        config_file: str,
        location_config: str,
        server_block_index: int = 0
    ) -> Dict[str, Any]:
        """Add a location block to nginx config"""
        try:
            with open(config_file, 'r') as f:
                content = f.read()

            # Find server blocks
            server_blocks = list(re.finditer(r'server\s*\{', content))

            if not server_blocks:
                return {"success": False, "error": "No server blocks found"}

            if server_block_index >= len(server_blocks):
                return {"success": False, "error": f"Server block {server_block_index} not found"}

            # Find the closing brace of the target server block
            target_start = server_blocks[server_block_index].end()

            # Find matching closing brace
            brace_count = 1
            pos = target_start
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1

            # Insert before the closing brace
            insert_pos = pos - 1

            # Find the last newline before the closing brace
            while insert_pos > 0 and content[insert_pos - 1] in ' \t':
                insert_pos -= 1

            # Insert the location config
            new_content = content[:insert_pos] + "\n" + location_config + "\n" + content[insert_pos:]

            # Backup original
            backup_path = f"{config_file}.backup"
            with open(backup_path, 'w') as f:
                f.write(content)

            # Write new config
            with open(config_file, 'w') as f:
                f.write(new_content)

            # Test configuration
            valid, error = self.test_config()
            if not valid:
                # Restore backup
                with open(backup_path, 'r') as f:
                    original = f.read()
                with open(config_file, 'w') as f:
                    f.write(original)
                return {"success": False, "error": f"Config invalid after changes: {error}"}

            return {
                "success": True,
                "message": "Location added successfully",
                "backup": backup_path
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive nginx status"""
        analysis = self.analyze_config()

        # Check if nginx is running
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'nginx'],
                capture_output=True,
                text=True
            )
            running = result.stdout.strip() == 'active'
        except:
            running = False

        return {
            "running": running,
            "config_valid": analysis.valid,
            "errors": analysis.errors,
            "warnings": analysis.warnings,
            "has_xui_manager": analysis.has_xui_manager,
            "has_xui_panel": analysis.has_xui_panel,
            "ssl_enabled": analysis.ssl_enabled,
            "domains": analysis.domains,
            "config_files": self.config_files,
            "locations_configured": list(analysis.inbound_locations.keys())
        }


# Global instance
_nginx_manager = None


def get_nginx_manager() -> NginxManager:
    """Get or create nginx manager instance"""
    global _nginx_manager
    if _nginx_manager is None:
        _nginx_manager = NginxManager()
    return _nginx_manager
