#!/usr/bin/env python3
"""
Preset Inbound Templates for 3x-ui
Ready-to-use configurations for popular protocols with regional optimization
"""

import json
import random
import string
from typing import Dict, List, Optional, Any

# ============================================
# PROTOCOL TEMPLATES
# ============================================

PRESET_TEMPLATES = {
    "vless_reality": {
        "name": "VLESS + Reality",
        "description": "Recommended protocol with HTTPS masquerading",
        "description_ru": "Рекомендуемый протокол с маскировкой под HTTPS",
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
        "description": "For CDN usage (Cloudflare)",
        "description_ru": "Для работы через CDN (Cloudflare)",
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
        "description": "Classic CDN-friendly protocol",
        "description_ru": "Классический протокол для CDN",
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
        "description": "Simple and reliable protocol",
        "description_ru": "Простой и надежный протокол",
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
        "description": "Legacy protocol, high compatibility",
        "description_ru": "Легаси протокол, высокая совместимость",
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
        "description": "High performance with Reality",
        "description_ru": "Высокая производительность с Reality",
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
        "description": "Maximum performance",
        "description_ru": "Максимальная производительность",
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
    },

    "trojan_ws_tls": {
        "name": "Trojan + WebSocket + TLS",
        "description": "Trojan through CDN",
        "description_ru": "Trojan через CDN",
        "protocol": "trojan",
        "port": 443,
        "settings": {
            "clients": [],
            "fallbacks": []
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "wsSettings": {
                "path": "/trojan",
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

    # ============================================
    # CDN-FRIENDLY TEMPLATES (for Nginx reverse proxy)
    # ============================================

    "vless_ws_cdn": {
        "name": "VLESS + WS (CDN/Nginx)",
        "description": "WebSocket for Cloudflare CDN or Nginx reverse proxy",
        "description_ru": "WebSocket для CDN Cloudflare или Nginx reverse proxy",
        "protocol": "vless",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "ws",
            "security": "none",
            "wsSettings": {
                "path": "{{WS_PATH}}",
                "headers": {"Host": "{{HOST}}"}
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location {{WS_PATH}} {
        proxy_pass http://127.0.0.1:{{PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }"""
    },

    "vmess_ws_cdn": {
        "name": "VMess + WS (CDN/Nginx)",
        "description": "VMess WebSocket for CDN or Nginx reverse proxy",
        "description_ru": "VMess WebSocket для CDN или Nginx reverse proxy",
        "protocol": "vmess",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": []
        },
        "streamSettings": {
            "network": "ws",
            "security": "none",
            "wsSettings": {
                "path": "{{WS_PATH}}",
                "headers": {}
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location {{WS_PATH}} {
        proxy_pass http://127.0.0.1:{{PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }"""
    },

    "trojan_ws_cdn": {
        "name": "Trojan + WS (CDN/Nginx)",
        "description": "Trojan WebSocket for CDN or Nginx reverse proxy",
        "description_ru": "Trojan WebSocket для CDN или Nginx reverse proxy",
        "protocol": "trojan",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": []
        },
        "streamSettings": {
            "network": "ws",
            "security": "none",
            "wsSettings": {
                "path": "{{WS_PATH}}",
                "headers": {}
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location {{WS_PATH}} {
        proxy_pass http://127.0.0.1:{{PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }"""
    },

    "vless_grpc_cdn": {
        "name": "VLESS + gRPC (CDN/Nginx)",
        "description": "gRPC for Cloudflare CDN or Nginx",
        "description_ru": "gRPC для CDN Cloudflare или Nginx",
        "protocol": "vless",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "grpc",
            "security": "none",
            "grpcSettings": {
                "serviceName": "{{GRPC_SERVICE}}",
                "multiMode": True
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location /{{GRPC_SERVICE}} {
        grpc_pass grpc://127.0.0.1:{{PORT}};
        grpc_set_header Host $host;
        grpc_set_header X-Real-IP $remote_addr;
        grpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        grpc_read_timeout 86400s;
        grpc_send_timeout 86400s;
    }"""
    },

    "vless_httpupgrade_cdn": {
        "name": "VLESS + HTTPUpgrade (CDN/Nginx)",
        "description": "HTTPUpgrade for CDN or Nginx reverse proxy",
        "description_ru": "HTTPUpgrade для CDN или Nginx reverse proxy",
        "protocol": "vless",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "httpupgrade",
            "security": "none",
            "httpupgradeSettings": {
                "path": "{{WS_PATH}}",
                "host": ""
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location {{WS_PATH}} {
        proxy_pass http://127.0.0.1:{{PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }"""
    },

    "vless_splithttp_cdn": {
        "name": "VLESS + SplitHTTP/XHTTP (CDN/Nginx)",
        "description": "SplitHTTP (XHTTP) for CDN or Nginx",
        "description_ru": "SplitHTTP (XHTTP) для CDN или Nginx",
        "protocol": "vless",
        "port": "{{PORT}}",
        "requires_nginx": True,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "splithttp",
            "security": "none",
            "splithttpSettings": {
                "path": "{{WS_PATH}}",
                "host": "",
                "maxUploadSize": 1000000,
                "maxConcurrentUploads": 10
            }
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        },
        "nginx_location": """    location {{WS_PATH}} {
        proxy_pass http://127.0.0.1:{{PORT}};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        client_max_body_size 0;
    }"""
    },

    # ============================================
    # SHADOWSOCKS 2022 TEMPLATES
    # ============================================

    "ss_2022_aes128": {
        "name": "ShadowSocks 2022 (AES-128)",
        "description": "Modern ShadowSocks with AES-128-GCM",
        "description_ru": "Современный ShadowSocks с AES-128-GCM",
        "protocol": "shadowsocks",
        "port": "{{PORT}}",
        "settings": {
            "method": "2022-blake3-aes-128-gcm",
            "password": "{{SS_PASSWORD}}",
            "network": "tcp,udp"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "none"
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"]
        }
    },

    "ss_2022_aes256": {
        "name": "ShadowSocks 2022 (AES-256)",
        "description": "Modern ShadowSocks with AES-256-GCM",
        "description_ru": "Современный ShadowSocks с AES-256-GCM",
        "protocol": "shadowsocks",
        "port": "{{PORT}}",
        "settings": {
            "method": "2022-blake3-aes-256-gcm",
            "password": "{{SS_PASSWORD}}",
            "network": "tcp,udp"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "none"
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"]
        }
    },

    "ss_2022_chacha": {
        "name": "ShadowSocks 2022 (ChaCha20)",
        "description": "Modern ShadowSocks with ChaCha20-Poly1305",
        "description_ru": "Современный ShadowSocks с ChaCha20-Poly1305",
        "protocol": "shadowsocks",
        "port": "{{PORT}}",
        "settings": {
            "method": "2022-blake3-chacha20-poly1305",
            "password": "{{SS_PASSWORD}}",
            "network": "tcp,udp"
        },
        "streamSettings": {
            "network": "tcp",
            "security": "none"
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"]
        }
    },
}

# ============================================
# REGIONAL REALITY DOMAINS
# ============================================

REGIONAL_REALITY_DOMAINS = {
    "RU": {
        "name": "Russia",
        "name_ru": "Россия",
        "domains": [
            {"domain": "www.microsoft.com", "port": 443, "recommended": True},
            {"domain": "www.google.com", "port": 443, "recommended": True},
            {"domain": "dl.google.com", "port": 443, "recommended": True},
            {"domain": "www.googletagmanager.com", "port": 443, "recommended": False},
            {"domain": "www.cloudflare.com", "port": 443, "recommended": True},
            {"domain": "cdn.cloudflare.com", "port": 443, "recommended": False},
            {"domain": "www.amazon.com", "port": 443, "recommended": True},
            {"domain": "aws.amazon.com", "port": 443, "recommended": False},
            {"domain": "www.apple.com", "port": 443, "recommended": True},
            {"domain": "www.nvidia.com", "port": 443, "recommended": True},
            {"domain": "developer.nvidia.com", "port": 443, "recommended": False},
            {"domain": "www.amd.com", "port": 443, "recommended": False},
            {"domain": "www.intel.com", "port": 443, "recommended": False},
            {"domain": "www.mozilla.org", "port": 443, "recommended": False},
            {"domain": "addons.mozilla.org", "port": 443, "recommended": False},
        ],
        "fingerprints": ["chrome", "firefox", "safari", "edge"],
    },
    "CN": {
        "name": "China",
        "name_ru": "Китай",
        "domains": [
            {"domain": "www.apple.com", "port": 443, "recommended": True},
            {"domain": "itunes.apple.com", "port": 443, "recommended": True},
            {"domain": "www.microsoft.com", "port": 443, "recommended": True},
            {"domain": "www.logitech.com", "port": 443, "recommended": False},
            {"domain": "www.samsung.com", "port": 443, "recommended": True},
            {"domain": "www.amd.com", "port": 443, "recommended": False},
            {"domain": "www.cisco.com", "port": 443, "recommended": False},
            {"domain": "www.oracle.com", "port": 443, "recommended": False},
        ],
        "fingerprints": ["chrome", "safari", "ios"],
    },
    "IR": {
        "name": "Iran",
        "name_ru": "Иран",
        "domains": [
            {"domain": "www.speedtest.net", "port": 443, "recommended": True},
            {"domain": "www.samsung.com", "port": 443, "recommended": True},
            {"domain": "www.nvidia.com", "port": 443, "recommended": True},
            {"domain": "www.asus.com", "port": 443, "recommended": False},
            {"domain": "www.amd.com", "port": 443, "recommended": False},
            {"domain": "www.intel.com", "port": 443, "recommended": False},
            {"domain": "www.hp.com", "port": 443, "recommended": False},
        ],
        "fingerprints": ["chrome", "firefox"],
    },
    "GLOBAL": {
        "name": "Global",
        "name_ru": "Глобальный",
        "domains": [
            {"domain": "www.microsoft.com", "port": 443, "recommended": True},
            {"domain": "www.google.com", "port": 443, "recommended": True},
            {"domain": "www.cloudflare.com", "port": 443, "recommended": True},
            {"domain": "www.apple.com", "port": 443, "recommended": True},
            {"domain": "www.amazon.com", "port": 443, "recommended": False},
        ],
        "fingerprints": ["chrome", "firefox", "safari"],
    },
}

# ============================================
# REGIONAL ROUTING PRESETS
# ============================================

REGIONAL_ROUTING = {
    "RU": {
        "name": "Russia Bypass",
        "name_ru": "Обход блокировок РФ",
        "description": "Routes blocked sites through proxy, Russian sites directly",
        "description_ru": "Заблокированные сайты через прокси, российские напрямую",
        "rules": {
            "block": [
                "geosite:category-ads",
                "geosite:category-ads-all",
            ],
            "direct": [
                "geosite:ru",
                "geoip:ru",
                "geoip:private",
                "domain:yandex.ru",
                "domain:yandex.com",
                "domain:mail.ru",
                "domain:vk.com",
                "domain:ok.ru",
                "domain:gosuslugi.ru",
                "domain:sberbank.ru",
                "domain:tinkoff.ru",
            ],
            "proxy": [
                "geosite:google",
                "geosite:youtube",
                "geosite:twitter",
                "geosite:facebook",
                "geosite:instagram",
                "geosite:telegram",
                "geosite:discord",
                "geosite:linkedin",
                "geosite:spotify",
                "geosite:netflix",
                "geosite:openai",
                "domain:chatgpt.com",
                "domain:claude.ai",
                "domain:bbc.com",
                "domain:dw.com",
            ],
        },
    },
    "CN": {
        "name": "China GFW Bypass",
        "name_ru": "Обход GFW Китай",
        "description": "Routes international sites through proxy, Chinese sites directly",
        "description_ru": "Международные сайты через прокси, китайские напрямую",
        "rules": {
            "block": [
                "geosite:category-ads",
            ],
            "direct": [
                "geosite:cn",
                "geoip:cn",
                "geoip:private",
                "geosite:apple-cn",
                "geosite:google-cn",
            ],
            "proxy": [
                "geosite:google",
                "geosite:youtube",
                "geosite:twitter",
                "geosite:facebook",
                "geosite:telegram",
                "geosite:geolocation-!cn",
            ],
        },
    },
    "IR": {
        "name": "Iran Bypass",
        "name_ru": "Обход блокировок Иран",
        "description": "Routes blocked sites through proxy",
        "description_ru": "Заблокированные сайты через прокси",
        "rules": {
            "block": [
                "geosite:category-ads",
            ],
            "direct": [
                "geosite:ir",
                "geoip:ir",
                "geoip:private",
            ],
            "proxy": [
                "geosite:google",
                "geosite:youtube",
                "geosite:twitter",
                "geosite:facebook",
                "geosite:telegram",
                "geosite:instagram",
            ],
        },
    },
    "GLOBAL": {
        "name": "Global (Minimal)",
        "name_ru": "Глобальный (минимальный)",
        "description": "Minimal routing, all traffic through proxy except ads",
        "description_ru": "Минимальная маршрутизация, весь трафик через прокси кроме рекламы",
        "rules": {
            "block": [
                "geosite:category-ads",
                "geosite:category-ads-all",
            ],
            "direct": [
                "geoip:private",
            ],
            "proxy": [],
        },
    },
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_short_id(length: int = 8) -> str:
    """Generate random short ID for Reality"""
    return ''.join(random.choices('0123456789abcdef', k=length))


def generate_password(length: int = 16) -> str:
    """Generate random password"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def get_template(template_id: str) -> Optional[Dict]:
    """Get template by ID"""
    return PRESET_TEMPLATES.get(template_id)


def list_templates() -> List[Dict]:
    """List all available templates"""
    templates = []
    for template_id, template in PRESET_TEMPLATES.items():
        templates.append({
            "id": template_id,
            "name": template.get("name"),
            "description": template.get("description"),
            "description_ru": template.get("description_ru"),
            "protocol": template.get("protocol"),
            "port": template.get("port")
        })
    return templates


def apply_template(template_id: str, params: Dict) -> Optional[Dict]:
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
            - region: Region code for Reality domains

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
    config.pop("description_ru", None)

    # Apply custom port
    if "port" in params:
        config["port"] = params["port"]

    # Apply remark
    config["remark"] = params.get("remark", template.get("name", "Imported"))

    # Get region-specific settings
    region = params.get("region", "GLOBAL")
    region_config = REGIONAL_REALITY_DOMAINS.get(region, REGIONAL_REALITY_DOMAINS["GLOBAL"])

    # Convert settings to JSON strings (3x-ui format)
    settings_str = json.dumps(config.get("settings", {}))
    stream_str = json.dumps(config.get("streamSettings", {}))
    sniffing_str = json.dumps(config.get("sniffing", {}))

    # Replace placeholders
    domain = params.get("domain", "example.com")
    private_key = params.get("private_key", "")
    short_id = params.get("short_id", generate_short_id())
    password = params.get("password", generate_password())

    # Use regional Reality domain if not specified
    if "reality" in template_id and not params.get("reality_domain"):
        recommended_domains = [d for d in region_config["domains"] if d.get("recommended")]
        if recommended_domains:
            reality_domain = recommended_domains[0]["domain"]
            stream_str = stream_str.replace(
                '"dest": "www.google.com:443"',
                f'"dest": "{reality_domain}:443"'
            )
            stream_str = stream_str.replace(
                '"serverNames": ["www.google.com", "google.com"]',
                f'"serverNames": ["{reality_domain}"]'
            )
            stream_str = stream_str.replace(
                '"serverNames": ["www.google.com"]',
                f'"serverNames": ["{reality_domain}"]'
            )

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


def get_template_params(template_id: str) -> List[Dict]:
    """Get required parameters for template"""
    template = get_template(template_id)
    if not template:
        return []

    params = []
    template_str = json.dumps(template)

    if "{{DOMAIN}}" in template_str:
        params.append({
            "name": "domain",
            "label": "Domain",
            "label_ru": "Домен",
            "required": True,
            "type": "string"
        })

    if "{{PRIVATE_KEY}}" in template_str:
        params.append({
            "name": "private_key",
            "label": "Private Key (Reality)",
            "label_ru": "Приватный ключ (Reality)",
            "required": True,
            "type": "string"
        })
        params.append({
            "name": "short_id",
            "label": "Short ID",
            "label_ru": "Short ID",
            "required": False,
            "type": "string",
            "default": "auto"
        })
        params.append({
            "name": "region",
            "label": "Target Region",
            "label_ru": "Целевой регион",
            "required": False,
            "type": "select",
            "options": list(REGIONAL_REALITY_DOMAINS.keys()),
            "default": "GLOBAL"
        })

    if "{{PASSWORD}}" in template_str:
        params.append({
            "name": "password",
            "label": "Password",
            "label_ru": "Пароль",
            "required": False,
            "type": "string",
            "default": "auto"
        })

    # Common params
    params.extend([
        {
            "name": "port",
            "label": "Port",
            "label_ru": "Порт",
            "required": False,
            "type": "number",
            "default": template.get("port", 443)
        },
        {
            "name": "remark",
            "label": "Name",
            "label_ru": "Название",
            "required": False,
            "type": "string",
            "default": template.get("name", "")
        }
    ])

    return params


def get_regional_reality_domains(region: str) -> Dict[str, Any]:
    """Get Reality domains for specific region"""
    return REGIONAL_REALITY_DOMAINS.get(region, REGIONAL_REALITY_DOMAINS["GLOBAL"])


def get_regional_routing(region: str) -> Dict[str, Any]:
    """Get routing rules for specific region"""
    return REGIONAL_ROUTING.get(region, REGIONAL_ROUTING["GLOBAL"])


def list_regions() -> List[Dict[str, Any]]:
    """List all available regions"""
    regions = []
    for code, config in REGIONAL_REALITY_DOMAINS.items():
        regions.append({
            "code": code,
            "name": config["name"],
            "name_ru": config["name_ru"],
            "domains_count": len(config["domains"]),
            "fingerprints": config["fingerprints"],
        })
    return regions


def generate_routing_config(region: str) -> Dict[str, Any]:
    """Generate Xray routing configuration for region"""
    routing = get_regional_routing(region)
    rules = routing.get("rules", {})

    xray_rules = []

    # Block rules
    block_domains = [r for r in rules.get("block", []) if r.startswith("geosite:") or r.startswith("domain:")]
    block_ips = [r for r in rules.get("block", []) if r.startswith("geoip:")]

    if block_domains:
        xray_rules.append({
            "type": "field",
            "domain": block_domains,
            "outboundTag": "block"
        })
    if block_ips:
        xray_rules.append({
            "type": "field",
            "ip": block_ips,
            "outboundTag": "block"
        })

    # Direct rules
    direct_domains = [r for r in rules.get("direct", []) if r.startswith("geosite:") or r.startswith("domain:")]
    direct_ips = [r for r in rules.get("direct", []) if r.startswith("geoip:")]

    if direct_domains:
        xray_rules.append({
            "type": "field",
            "domain": direct_domains,
            "outboundTag": "direct"
        })
    if direct_ips:
        xray_rules.append({
            "type": "field",
            "ip": direct_ips,
            "outboundTag": "direct"
        })

    # Proxy rules
    proxy_domains = [r for r in rules.get("proxy", []) if r.startswith("geosite:") or r.startswith("domain:")]
    proxy_ips = [r for r in rules.get("proxy", []) if r.startswith("geoip:")]

    if proxy_domains:
        xray_rules.append({
            "type": "field",
            "domain": proxy_domains,
            "outboundTag": "proxy"
        })
    if proxy_ips:
        xray_rules.append({
            "type": "field",
            "ip": proxy_ips,
            "outboundTag": "proxy"
        })

    return {
        "domainStrategy": "AsIs",
        "domainMatcher": "hybrid",
        "rules": xray_rules
    }
