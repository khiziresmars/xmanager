"""
Xray Configuration Generator
Generates Reality keys, UUIDs, short IDs, and other Xray-related values
Compatible with 3x-ui panel format
"""

import os
import uuid
import base64
import secrets
import subprocess
import socket
import string
import random
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RealityKeys:
    """Reality X25519 key pair"""
    private_key: str
    public_key: str


@dataclass
class InboundConfig:
    """Generated inbound configuration"""
    protocol: str
    port: int
    tag: str
    settings: Dict[str, Any]
    stream_settings: Dict[str, Any]
    sniffing: Dict[str, Any]
    nginx_config: Optional[str] = None


class XrayGenerator:
    """Generates various Xray configuration values"""

    # Good SNI targets for Reality
    REALITY_SNI_TARGETS = [
        "dl.google.com",
        "www.microsoft.com",
        "www.apple.com",
        "www.samsung.com",
        "addons.mozilla.org",
        "www.logitech.com",
        "www.asus.com",
        "www.amd.com",
        "www.nvidia.com",
        "steamcommunity.com",
        "www.cloudflare.com",
        "www.ebay.com",
        "www.spotify.com",
        "www.discord.com",
        "gateway.icloud.com",
    ]

    # Recommended fingerprints
    FINGERPRINTS = [
        "chrome",
        "firefox",
        "safari",
        "ios",
        "android",
        "edge",
        "randomized",
        "random",
    ]

    # Default cipher for ShadowSocks
    SS_CIPHERS = [
        "2022-blake3-aes-128-gcm",
        "2022-blake3-aes-256-gcm",
        "2022-blake3-chacha20-poly1305",
        "chacha20-ietf-poly1305",
        "aes-256-gcm",
        "aes-128-gcm",
    ]

    def __init__(self):
        self.xray_path = self._find_xray_binary()

    def _find_xray_binary(self) -> Optional[str]:
        """Find xray binary path"""
        paths = [
            "/usr/local/x-ui/bin/xray-linux-amd64",
            "/usr/local/bin/xray",
            "/usr/bin/xray",
            "/opt/xray/xray",
        ]
        for path in paths:
            if os.path.exists(path):
                return path

        # Try to find via which
        try:
            result = subprocess.run(['which', 'xray'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        return None

    def generate_uuid(self) -> str:
        """Generate UUIDv4"""
        return str(uuid.uuid4())

    def generate_short_id(self, length: int = 8) -> str:
        """Generate short ID for Reality (hex string, 1-16 chars)"""
        if length < 1:
            length = 1
        if length > 16:
            length = 16
        # Must be even number of hex chars
        if length % 2 != 0:
            length += 1
        return secrets.token_hex(length // 2)

    def generate_short_ids(self, count: int = 3) -> List[str]:
        """Generate multiple short IDs with varying lengths"""
        ids = []
        lengths = [2, 4, 8, 8, 16]
        for i in range(count):
            length = lengths[i % len(lengths)]
            ids.append(self.generate_short_id(length))
        return ids

    def generate_x25519_keys(self) -> RealityKeys:
        """Generate X25519 key pair for Reality using xray binary"""
        if self.xray_path:
            try:
                result = subprocess.run(
                    [self.xray_path, 'x25519'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    output = result.stdout
                    private_key = ""
                    public_key = ""
                    for line in output.split('\n'):
                        if 'Private key:' in line:
                            private_key = line.split(':')[1].strip()
                        elif 'Public key:' in line:
                            public_key = line.split(':')[1].strip()

                    if private_key and public_key:
                        return RealityKeys(private_key=private_key, public_key=public_key)
            except Exception as e:
                logger.warning(f"Failed to generate x25519 via xray binary: {e}")

        # Fallback: use Python cryptography library
        return self._generate_x25519_python()

    def _generate_x25519_python(self) -> RealityKeys:
        """Generate X25519 keys using Python cryptography library"""
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives import serialization

            private_key = X25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Get raw bytes and encode to base64
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            # Convert to URL-safe base64 without padding (xray format)
            private_b64 = base64.urlsafe_b64encode(private_bytes).decode().rstrip('=')
            public_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')

            return RealityKeys(private_key=private_b64, public_key=public_b64)
        except ImportError:
            logger.error("cryptography library not installed, generating placeholder keys")
            # Return placeholder (NOT SECURE - just for development)
            return RealityKeys(
                private_key="PLACEHOLDER_INSTALL_CRYPTOGRAPHY_LIBRARY",
                public_key="PLACEHOLDER_INSTALL_CRYPTOGRAPHY_LIBRARY"
            )

    def generate_password(self, length: int = 16, include_special: bool = True) -> str:
        """Generate secure random password"""
        chars = string.ascii_letters + string.digits
        if include_special:
            chars += "!@#$%&*"
        return ''.join(secrets.choice(chars) for _ in range(length))

    def generate_username(self, length: int = 8) -> str:
        """Generate random username (alphanumeric)"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    def generate_path(self, prefix: str = "", length: int = 8) -> str:
        """Generate random URL path"""
        chars = string.ascii_lowercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(length))
        if prefix:
            return f"/{prefix}/{random_part}"
        return f"/{random_part}"

    def generate_ss_password(self, cipher: str = "2022-blake3-aes-128-gcm") -> str:
        """Generate ShadowSocks password based on cipher"""
        if "2022" in cipher:
            if "128" in cipher:
                # 16 bytes for 128-bit
                return base64.b64encode(secrets.token_bytes(16)).decode()
            else:
                # 32 bytes for 256-bit
                return base64.b64encode(secrets.token_bytes(32)).decode()
        else:
            # Legacy ciphers - any password works
            return self.generate_password(16, include_special=False)

    def find_available_port(self, start: int = 30000, end: int = 60000) -> int:
        """Find an available port in range"""
        for _ in range(100):  # Try up to 100 times
            port = random.randint(start, end)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('127.0.0.1', port))
                sock.close()
                return port
            except OSError:
                continue

        # Fallback to random port
        return random.randint(start, end)

    def get_random_sni(self) -> str:
        """Get random SNI target for Reality"""
        return random.choice(self.REALITY_SNI_TARGETS)

    def get_random_fingerprint(self) -> str:
        """Get random browser fingerprint"""
        return random.choice(self.FINGERPRINTS)

    def generate_credentials(self) -> Dict[str, str]:
        """Generate complete set of credentials for 3x-ui panel"""
        return {
            "username": self.generate_username(),
            "password": self.generate_password(12, include_special=False),
            "port": self.find_available_port(),
            "web_base_path": self.generate_path("panel", 6),
        }

    # ==================== INBOUND GENERATORS ====================

    def generate_vless_reality_config(
        self,
        port: int = None,
        tag: str = "vless-reality",
        dest: str = None,
        sni: str = None
    ) -> Dict[str, Any]:
        """Generate VLESS+Reality inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if sni is None:
            sni = self.get_random_sni()

        if dest is None:
            dest = f"{sni}:443"

        keys = self.generate_x25519_keys()
        client_uuid = self.generate_uuid()
        short_ids = self.generate_short_ids(3)

        return {
            "protocol": "vless",
            "port": port,
            "tag": tag,
            "remark": f"VLESS-Reality-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "flow": "xtls-rprx-vision",
                    "email": "default@example.com"
                }],
                "decryption": "none"
            },
            "stream_settings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": False,
                    "dest": dest,
                    "xver": 0,
                    "serverNames": [sni],
                    "privateKey": keys.private_key,
                    "shortIds": short_ids,
                    "fingerprint": "chrome",
                    "spiderX": "/"
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "client_config": {
                "publicKey": keys.public_key,
                "shortId": short_ids[0],
                "uuid": client_uuid,
                "sni": sni
            }
        }

    def generate_vless_ws_config(
        self,
        port: int = None,
        tag: str = "vless-ws",
        path: str = None,
        host: str = ""
    ) -> Dict[str, Any]:
        """Generate VLESS+WebSocket inbound configuration (for CDN/Nginx)"""
        if port is None:
            port = self.find_available_port()

        if path is None:
            path = self.generate_path("ws")

        client_uuid = self.generate_uuid()

        config = {
            "protocol": "vless",
            "port": port,
            "tag": tag,
            "remark": f"VLESS-WS-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "email": "default@example.com"
                }],
                "decryption": "none"
            },
            "stream_settings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": path,
                    "headers": {"Host": host} if host else {}
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_ws_location(path, port),
            "client_config": {
                "uuid": client_uuid,
                "path": path
            }
        }

        return config

    def generate_vless_grpc_config(
        self,
        port: int = None,
        tag: str = "vless-grpc",
        service_name: str = None
    ) -> Dict[str, Any]:
        """Generate VLESS+gRPC inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if service_name is None:
            service_name = self.generate_username(8)

        client_uuid = self.generate_uuid()

        return {
            "protocol": "vless",
            "port": port,
            "tag": tag,
            "remark": f"VLESS-gRPC-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "email": "default@example.com"
                }],
                "decryption": "none"
            },
            "stream_settings": {
                "network": "grpc",
                "security": "none",
                "grpcSettings": {
                    "serviceName": service_name,
                    "multiMode": True
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_grpc_location(service_name, port),
            "client_config": {
                "uuid": client_uuid,
                "serviceName": service_name
            }
        }

    def generate_trojan_ws_config(
        self,
        port: int = None,
        tag: str = "trojan-ws",
        path: str = None
    ) -> Dict[str, Any]:
        """Generate Trojan+WebSocket inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if path is None:
            path = self.generate_path("tr")

        password = self.generate_password(16, include_special=False)

        return {
            "protocol": "trojan",
            "port": port,
            "tag": tag,
            "remark": f"Trojan-WS-{port}",
            "settings": {
                "clients": [{
                    "password": password,
                    "email": "default@example.com"
                }]
            },
            "stream_settings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": path,
                    "headers": {}
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_ws_location(path, port),
            "client_config": {
                "password": password,
                "path": path
            }
        }

    def generate_vmess_ws_config(
        self,
        port: int = None,
        tag: str = "vmess-ws",
        path: str = None
    ) -> Dict[str, Any]:
        """Generate VMess+WebSocket inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if path is None:
            path = self.generate_path("vm")

        client_uuid = self.generate_uuid()

        return {
            "protocol": "vmess",
            "port": port,
            "tag": tag,
            "remark": f"VMess-WS-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "alterId": 0,
                    "email": "default@example.com"
                }]
            },
            "stream_settings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": path,
                    "headers": {}
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_ws_location(path, port),
            "client_config": {
                "uuid": client_uuid,
                "path": path
            }
        }

    def generate_shadowsocks_config(
        self,
        port: int = None,
        tag: str = "shadowsocks",
        cipher: str = "2022-blake3-aes-128-gcm"
    ) -> Dict[str, Any]:
        """Generate ShadowSocks inbound configuration"""
        if port is None:
            port = self.find_available_port()

        password = self.generate_ss_password(cipher)

        return {
            "protocol": "shadowsocks",
            "port": port,
            "tag": tag,
            "remark": f"SS-{cipher.split('-')[-1]}-{port}",
            "settings": {
                "method": cipher,
                "password": password,
                "network": "tcp,udp"
            },
            "stream_settings": {
                "network": "tcp",
                "security": "none"
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "client_config": {
                "password": password,
                "method": cipher
            }
        }

    def generate_vless_httpupgrade_config(
        self,
        port: int = None,
        tag: str = "vless-httpupgrade",
        path: str = None
    ) -> Dict[str, Any]:
        """Generate VLESS+HTTPUpgrade inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if path is None:
            path = self.generate_path("hu")

        client_uuid = self.generate_uuid()

        return {
            "protocol": "vless",
            "port": port,
            "tag": tag,
            "remark": f"VLESS-HTTPUpgrade-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "email": "default@example.com"
                }],
                "decryption": "none"
            },
            "stream_settings": {
                "network": "httpupgrade",
                "security": "none",
                "httpupgradeSettings": {
                    "path": path,
                    "host": ""
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_httpupgrade_location(path, port),
            "client_config": {
                "uuid": client_uuid,
                "path": path
            }
        }

    def generate_vless_splithttp_config(
        self,
        port: int = None,
        tag: str = "vless-splithttp",
        path: str = None
    ) -> Dict[str, Any]:
        """Generate VLESS+SplitHTTP (XHTTP) inbound configuration"""
        if port is None:
            port = self.find_available_port()

        if path is None:
            path = self.generate_path("xh")

        client_uuid = self.generate_uuid()

        return {
            "protocol": "vless",
            "port": port,
            "tag": tag,
            "remark": f"VLESS-SplitHTTP-{port}",
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "email": "default@example.com"
                }],
                "decryption": "none"
            },
            "stream_settings": {
                "network": "splithttp",
                "security": "none",
                "splithttpSettings": {
                    "path": path,
                    "host": "",
                    "maxUploadSize": 1000000,
                    "maxConcurrentUploads": 10
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic", "fakedns"]
            },
            "nginx_config": self._generate_nginx_splithttp_location(path, port),
            "client_config": {
                "uuid": client_uuid,
                "path": path
            }
        }

    # ==================== NGINX CONFIG GENERATORS ====================

    def _generate_nginx_ws_location(self, path: str, port: int) -> str:
        """Generate nginx location block for WebSocket"""
        return f"""    location {path} {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }}"""

    def _generate_nginx_grpc_location(self, service_name: str, port: int) -> str:
        """Generate nginx location block for gRPC"""
        return f"""    location /{service_name} {{
        grpc_pass grpc://127.0.0.1:{port};
        grpc_set_header Host $host;
        grpc_set_header X-Real-IP $remote_addr;
        grpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        grpc_read_timeout 86400s;
        grpc_send_timeout 86400s;
    }}"""

    def _generate_nginx_httpupgrade_location(self, path: str, port: int) -> str:
        """Generate nginx location block for HTTP Upgrade"""
        return f"""    location {path} {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }}"""

    def _generate_nginx_splithttp_location(self, path: str, port: int) -> str:
        """Generate nginx location block for SplitHTTP"""
        return f"""    location {path} {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        client_max_body_size 0;
    }}"""

    def generate_full_nginx_config(
        self,
        domain: str,
        inbounds: List[Dict[str, Any]],
        ssl_cert: str = None,
        ssl_key: str = None,
        panel_port: int = 2053,
        panel_path: str = "/panel"
    ) -> str:
        """Generate complete nginx server block configuration"""

        # Collect all location blocks
        locations = []

        # Panel location
        locations.append(f"""    # 3x-ui Panel
    location {panel_path}/ {{
        proxy_pass http://127.0.0.1:{panel_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}""")

        # Inbound locations
        for inbound in inbounds:
            if inbound.get('nginx_config'):
                locations.append(f"\n    # {inbound.get('remark', 'Inbound')}")
                locations.append(inbound['nginx_config'])

        locations_str = "\n\n".join(locations)

        # SSL configuration
        if ssl_cert and ssl_key:
            ssl_config = f"""
    ssl_certificate {ssl_cert};
    ssl_certificate_key {ssl_key};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;
"""
            listen_directive = "listen 443 ssl http2;"
            listen_directive_v6 = "listen [::]:443 ssl http2;"
        else:
            ssl_config = ""
            listen_directive = "listen 80;"
            listen_directive_v6 = "listen [::]:80;"

        config = f"""server {{
    {listen_directive}
    {listen_directive_v6}
    server_name {domain};
{ssl_config}
    # Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_vary on;
    gzip_min_length 1000;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Root location - fake site or default
    location / {{
        root /var/www/html;
        index index.html index.htm;
        try_files $uri $uri/ =404;
    }}

{locations_str}
}}
"""
        return config


# Global instance
_xray_generator = None


def get_xray_generator() -> XrayGenerator:
    """Get or create XrayGenerator instance"""
    global _xray_generator
    if _xray_generator is None:
        _xray_generator = XrayGenerator()
    return _xray_generator
