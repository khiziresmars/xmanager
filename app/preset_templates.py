#!/usr/bin/env python3
"""
Preset Inbound Templates for 3x-ui
Ready-to-use configurations for popular protocols
"""

import json
import random
import string

# ==================== TEMPLATE DEFINITIONS ====================

PRESET_TEMPLATES = {
    "vless_reality": {
        "name": "VLESS + Reality",
        "description": "Рекомендуемый протокол с маскировкой под HTTPS",
        "protocol": "vless",
        "port": 443,
        "settings": {
            "clients": [],
            "decryption": "none",
            "fallbacks": []
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "show": False,
                "xver": 0,
                "dest": "www.google.com:443",
                "serverNames": ["www.google.com", "google.com"],
                "privateKey": "{{PRIVATE_KEY}}",
                "shortIds": ["{{SHORT_ID}}"],
                "spiderX": ""
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        }
    },

    "vless_ws_tls": {
        "name": "VLESS + WebSocket + TLS",
        "description": "Для работы через CDN (Cloudflare)",
        "protocol": "vless",
        "port": 443,
        "settings": {
            "clients": [],
            "decryption": "none",
            "fallbacks": []
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "wsSettings": {
                "path": "/vless",
                "headers": {}
            },
            "tlsSettings": {
                "serverName": "{{DOMAIN}}",
                "certificates": [
                    {
                        "certificateFile": "/etc/letsencrypt/live/{{DOMAIN}}/fullchain.pem",
                        "keyFile": "/etc/letsencrypt/live/{{DOMAIN}}/privkey.pem"
                    }
                ]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    },

    "vmess_ws_tls": {
        "name": "VMess + WebSocket + TLS",
        "description": "Классический протокол для CDN",
        "protocol": "vmess",
        "port": 443,
        "settings": {
            "clients": []
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "wsSettings": {
                "path": "/vmess",
                "headers": {}
            },
            "tlsSettings": {
                "serverName": "{{DOMAIN}}",
                "certificates": [
                    {
                        "certificateFile": "/etc/letsencrypt/live/{{DOMAIN}}/fullchain.pem",
                        "keyFile": "/etc/letsencrypt/live/{{DOMAIN}}/privkey.pem"
                    }
                ]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    },

    "trojan_tcp_tls": {
        "name": "Trojan + TCP + TLS",
        "description": "Простой и надежный протокол",
        "protocol": "trojan",
        "port": 443,
        "settings": {
            "clients": [],
            "fallbacks": []
        },
        "streamSettings": {
            "network": "tcp",
            "security": "tls",
            "tlsSettings": {
                "serverName": "{{DOMAIN}}",
                "certificates": [
                    {
                        "certificateFile": "/etc/letsencrypt/live/{{DOMAIN}}/fullchain.pem",
                        "keyFile": "/etc/letsencrypt/live/{{DOMAIN}}/privkey.pem"
                    }
                ]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    },

    "shadowsocks": {
        "name": "Shadowsocks",
        "description": "Легаси протокол, высокая совместимость",
        "protocol": "shadowsocks",
        "port": 8388,
        "settings": {
            "method": "chacha20-ietf-poly1305",
            "password": "{{PASSWORD}}",
            "network": "tcp,udp"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "none"
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    },

    "vless_grpc_reality": {
        "name": "VLESS + gRPC + Reality",
        "description": "Высокая производительность с Reality",
        "protocol": "vless",
        "port": 443,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "grpc",
            "security": "reality",
            "grpcSettings": {
                "serviceName": "grpc"
            },
            "realitySettings": {
                "show": False,
                "xver": 0,
                "dest": "www.google.com:443",
                "serverNames": ["www.google.com"],
                "privateKey": "{{PRIVATE_KEY}}",
                "shortIds": ["{{SHORT_ID}}"]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"]
        }
    },

    "vless_tcp_xtls": {
        "name": "VLESS + TCP + XTLS",
        "description": "Максимальная производительность",
        "protocol": "vless",
        "port": 443,
        "settings": {
            "clients": [],
            "decryption": "none",
            "fallbacks": [
                {
                    "dest": 80
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "xtls",
            "xtlsSettings": {
                "serverName": "{{DOMAIN}}",
                "certificates": [
                    {
                        "certificateFile": "/etc/letsencrypt/live/{{DOMAIN}}/fullchain.pem",
                        "keyFile": "/etc/letsencrypt/live/{{DOMAIN}}/privkey.pem"
                    }
                ]
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    }
}


def generate_short_id(length: int = 8) -> str:
    """Generate random short ID for Reality"""
    return ''.join(random.choices('0123456789abcdef', k=length))


def generate_password(length: int = 16) -> str:
    """Generate random password"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def get_template(template_id: str) -> dict:
    """Get template by ID"""
    return PRESET_TEMPLATES.get(template_id)


def list_templates() -> list:
    """List all available templates"""
    templates = []
    for template_id, template in PRESET_TEMPLATES.items():
        templates.append({
            "id": template_id,
            "name": template.get("name"),
            "description": template.get("description"),
            "protocol": template.get("protocol"),
            "port": template.get("port")
        })
    return templates


def apply_template(template_id: str, params: dict) -> dict:
    """
    Apply template with custom parameters

    Args:
        template_id: Template identifier
        params: Dictionary with parameters to replace:
            - domain: Domain name for TLS
            - port: Custom port
            - remark: Inbound name
            - private_key: Reality private key
            - public_key: Reality public key
            - short_id: Reality short ID

    Returns:
        Complete inbound configuration ready for import
    """
    template = get_template(template_id)
    if not template:
        return None

    # Deep copy template
    config = json.loads(json.dumps(template))

    # Remove metadata
    config.pop("name", None)
    config.pop("description", None)

    # Apply custom port
    if "port" in params:
        config["port"] = params["port"]

    # Apply remark
    config["remark"] = params.get("remark", template.get("name", "Imported"))

    # Convert settings to JSON strings (3x-ui format)
    settings_str = json.dumps(config.get("settings", {}))
    stream_str = json.dumps(config.get("streamSettings", {}))
    sniffing_str = json.dumps(config.get("sniffing", {}))

    # Replace placeholders
    domain = params.get("domain", "example.com")
    private_key = params.get("private_key", "")
    short_id = params.get("short_id", generate_short_id())
    password = params.get("password", generate_password())

    settings_str = settings_str.replace("{{DOMAIN}}", domain)
    settings_str = settings_str.replace("{{PASSWORD}}", password)

    stream_str = stream_str.replace("{{DOMAIN}}", domain)
    stream_str = stream_str.replace("{{PRIVATE_KEY}}", private_key)
    stream_str = stream_str.replace("{{SHORT_ID}}", short_id)

    config["settings"] = settings_str
    config["streamSettings"] = stream_str
    config["sniffing"] = sniffing_str

    # Add default values
    config["enable"] = True
    config["expiryTime"] = 0
    config["listen"] = ""
    config["total"] = 0
    config["up"] = 0
    config["down"] = 0

    return config


def get_template_params(template_id: str) -> list:
    """Get required parameters for template"""
    template = get_template(template_id)
    if not template:
        return []

    params = []
    template_str = json.dumps(template)

    if "{{DOMAIN}}" in template_str:
        params.append({
            "name": "domain",
            "label": "Домен",
            "required": True,
            "type": "string"
        })

    if "{{PRIVATE_KEY}}" in template_str:
        params.append({
            "name": "private_key",
            "label": "Private Key (Reality)",
            "required": True,
            "type": "string"
        })
        params.append({
            "name": "short_id",
            "label": "Short ID",
            "required": False,
            "type": "string",
            "default": "auto"
        })

    if "{{PASSWORD}}" in template_str:
        params.append({
            "name": "password",
            "label": "Пароль",
            "required": False,
            "type": "string",
            "default": "auto"
        })

    # Common params
    params.extend([
        {
            "name": "port",
            "label": "Порт",
            "required": False,
            "type": "number",
            "default": template.get("port", 443)
        },
        {
            "name": "remark",
            "label": "Название",
            "required": False,
            "type": "string",
            "default": template.get("name", "")
        }
    ])

    return params
