#!/usr/bin/env python3
"""
Region Manager for XUI-Manager
Handles regional configurations, routing rules, and optimal settings for different regions
"""

import json
import logging
import aiohttp
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class RegionCode(str, Enum):
    """Supported region codes"""
    RU = "RU"      # Russia
    CN = "CN"      # China
    IR = "IR"      # Iran
    UAE = "UAE"    # UAE
    TR = "TR"      # Turkey
    GLOBAL = "GLOBAL"  # Global/Universal


@dataclass
class ServerLocation:
    """Server physical location info"""
    country_code: str
    country_name: str
    city: str = ""
    isp: str = ""
    ip: str = ""
    timezone: str = ""


@dataclass
class RegionConfig:
    """Region-specific configuration"""
    code: str
    name: str
    name_ru: str
    description: str

    # Recommended Reality domains for this region
    reality_domains: List[str] = field(default_factory=list)

    # Routing rules
    routing_block: List[str] = field(default_factory=list)
    routing_direct: List[str] = field(default_factory=list)
    routing_proxy: List[str] = field(default_factory=list)

    # Recommended protocols (in order of preference)
    recommended_protocols: List[str] = field(default_factory=list)

    # Sites that are typically blocked in this region
    blocked_sites: List[str] = field(default_factory=list)

    # Fingerprint recommendations
    recommended_fingerprints: List[str] = field(default_factory=list)


# ============================================
# REGION CONFIGURATIONS
# ============================================

REGIONS: Dict[str, RegionConfig] = {
    "RU": RegionConfig(
        code="RU",
        name="Russia",
        name_ru="Россия",
        description="Configuration for users in Russia (bypassing RKN blocks)",
        reality_domains=[
            "www.microsoft.com",
            "www.google.com",
            "dl.google.com",
            "www.googletagmanager.com",
            "www.cloudflare.com",
            "cdn.cloudflare.com",
            "www.amazon.com",
            "aws.amazon.com",
            "www.apple.com",
            "www.nvidia.com",
            "developer.nvidia.com",
        ],
        routing_block=[
            "geosite:category-ads",
            "geosite:category-ads-all",
        ],
        routing_direct=[
            "geosite:ru",
            "geoip:ru",
            "geoip:private",
            "geosite:yandex",
            "geosite:mailru",
            "geosite:vk",
        ],
        routing_proxy=[
            "geosite:google",
            "geosite:youtube",
            "geosite:twitter",
            "geosite:facebook",
            "geosite:instagram",
            "geosite:telegram",
            "geosite:discord",
            "geosite:linkedin",
            "geosite:netflix",
            "geosite:spotify",
            "geosite:openai",
        ],
        recommended_protocols=[
            "vless+reality",
            "vless+ws+tls",
            "trojan+tcp+tls",
            "vmess+ws+tls",
        ],
        blocked_sites=[
            "instagram.com",
            "twitter.com",
            "facebook.com",
            "linkedin.com",
            "discord.com",
            "medium.com",
            "bbc.com",
            "spotify.com",
        ],
        recommended_fingerprints=["chrome", "firefox", "safari"],
    ),

    "CN": RegionConfig(
        code="CN",
        name="China",
        name_ru="Китай",
        description="Configuration for users in China (bypassing GFW)",
        reality_domains=[
            "www.apple.com",
            "itunes.apple.com",
            "www.microsoft.com",
            "www.logitech.com",
            "www.samsung.com",
            "www.amd.com",
            "www.cisco.com",
        ],
        routing_block=[
            "geosite:category-ads",
        ],
        routing_direct=[
            "geosite:cn",
            "geoip:cn",
            "geoip:private",
            "geosite:apple-cn",
            "geosite:google-cn",
            "geosite:microsoft@cn",
        ],
        routing_proxy=[
            "geosite:google",
            "geosite:youtube",
            "geosite:twitter",
            "geosite:facebook",
            "geosite:telegram",
            "geosite:geolocation-!cn",
        ],
        recommended_protocols=[
            "vless+reality",
            "vless+ws+tls",
            "trojan+ws+tls",
        ],
        blocked_sites=[
            "google.com",
            "youtube.com",
            "facebook.com",
            "twitter.com",
            "instagram.com",
            "whatsapp.com",
            "telegram.org",
        ],
        recommended_fingerprints=["chrome", "safari", "ios"],
    ),

    "IR": RegionConfig(
        code="IR",
        name="Iran",
        name_ru="Иран",
        description="Configuration for users in Iran",
        reality_domains=[
            "www.speedtest.net",
            "www.samsung.com",
            "www.nvidia.com",
            "www.asus.com",
            "www.amd.com",
            "www.intel.com",
            "www.hp.com",
        ],
        routing_block=[
            "geosite:category-ads",
            "geosite:malware",
        ],
        routing_direct=[
            "geosite:ir",
            "geoip:ir",
            "geoip:private",
        ],
        routing_proxy=[
            "geosite:google",
            "geosite:youtube",
            "geosite:twitter",
            "geosite:facebook",
            "geosite:telegram",
            "geosite:instagram",
        ],
        recommended_protocols=[
            "vless+reality",
            "vless+grpc+reality",
            "trojan+ws+tls",
        ],
        blocked_sites=[
            "youtube.com",
            "twitter.com",
            "facebook.com",
            "telegram.org",
        ],
        recommended_fingerprints=["chrome", "firefox"],
    ),

    "UAE": RegionConfig(
        code="UAE",
        name="UAE",
        name_ru="ОАЭ",
        description="Configuration for users in UAE",
        reality_domains=[
            "www.microsoft.com",
            "www.google.com",
            "www.apple.com",
            "www.amazon.com",
        ],
        routing_block=[
            "geosite:category-ads",
        ],
        routing_direct=[
            "geoip:ae",
            "geoip:private",
        ],
        routing_proxy=[
            "geosite:whatsapp",
            "geosite:telegram",
            "geosite:discord",
        ],
        recommended_protocols=[
            "vless+reality",
            "vless+ws+tls",
        ],
        blocked_sites=[
            "discord.com",
            "some voip services",
        ],
        recommended_fingerprints=["chrome", "safari"],
    ),

    "TR": RegionConfig(
        code="TR",
        name="Turkey",
        name_ru="Турция",
        description="Configuration for users in Turkey",
        reality_domains=[
            "www.microsoft.com",
            "www.google.com",
            "www.cloudflare.com",
        ],
        routing_block=[
            "geosite:category-ads",
        ],
        routing_direct=[
            "geosite:tr",
            "geoip:tr",
            "geoip:private",
        ],
        routing_proxy=[
            "geosite:twitter",
            "geosite:wikipedia",
        ],
        recommended_protocols=[
            "vless+reality",
            "vmess+ws+tls",
        ],
        blocked_sites=[
            "twitter.com (sometimes)",
            "wikipedia.org (sometimes)",
        ],
        recommended_fingerprints=["chrome", "firefox"],
    ),

    "GLOBAL": RegionConfig(
        code="GLOBAL",
        name="Global",
        name_ru="Глобальный",
        description="Universal configuration for any region",
        reality_domains=[
            "www.microsoft.com",
            "www.google.com",
            "www.cloudflare.com",
            "www.apple.com",
            "www.amazon.com",
        ],
        routing_block=[
            "geosite:category-ads",
            "geosite:category-ads-all",
        ],
        routing_direct=[
            "geoip:private",
        ],
        routing_proxy=[],
        recommended_protocols=[
            "vless+reality",
            "vless+ws+tls",
            "vmess+ws+tls",
            "trojan+tcp+tls",
        ],
        blocked_sites=[],
        recommended_fingerprints=["chrome", "firefox", "safari"],
    ),
}


class RegionManager:
    """Manager for regional configurations"""

    def __init__(self):
        self._server_location: Optional[ServerLocation] = None
        self._location_cache_time: float = 0

    async def detect_server_location(self, force: bool = False) -> ServerLocation:
        """Detect server location using IP geolocation API"""
        import time

        # Cache for 1 hour
        if not force and self._server_location and (time.time() - self._location_cache_time) < 3600:
            return self._server_location

        try:
            async with aiohttp.ClientSession() as session:
                # Try ip-api.com first (free, no API key)
                async with session.get(
                    "http://ip-api.com/json/?fields=status,country,countryCode,city,isp,query,timezone",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            self._server_location = ServerLocation(
                                country_code=data.get("countryCode", ""),
                                country_name=data.get("country", ""),
                                city=data.get("city", ""),
                                isp=data.get("isp", ""),
                                ip=data.get("query", ""),
                                timezone=data.get("timezone", ""),
                            )
                            self._location_cache_time = time.time()
                            logger.info(f"Detected server location: {self._server_location.country_name} ({self._server_location.city})")
                            return self._server_location
        except Exception as e:
            logger.error(f"Error detecting server location: {e}")

        # Return unknown location
        self._server_location = ServerLocation(
            country_code="XX",
            country_name="Unknown",
        )
        return self._server_location

    def get_region(self, region_code: str) -> Optional[RegionConfig]:
        """Get region configuration by code"""
        return REGIONS.get(region_code.upper())

    def list_regions(self) -> List[Dict[str, Any]]:
        """List all available regions"""
        return [
            {
                "code": region.code,
                "name": region.name,
                "name_ru": region.name_ru,
                "description": region.description,
                "recommended_protocols": region.recommended_protocols,
            }
            for region in REGIONS.values()
        ]

    def get_reality_domains(self, region_code: str) -> List[str]:
        """Get recommended Reality domains for region"""
        region = self.get_region(region_code)
        if region:
            return region.reality_domains
        return REGIONS["GLOBAL"].reality_domains

    def get_routing_rules(self, region_code: str) -> Dict[str, List[str]]:
        """Get routing rules for region"""
        region = self.get_region(region_code)
        if not region:
            region = REGIONS["GLOBAL"]

        return {
            "block": region.routing_block,
            "direct": region.routing_direct,
            "proxy": region.routing_proxy,
        }

    def generate_routing_config(self, region_code: str) -> Dict[str, Any]:
        """Generate full Xray routing configuration for region"""
        rules = self.get_routing_rules(region_code)

        routing_rules = []

        # Block rules
        if rules["block"]:
            # Separate domain and IP rules
            domain_rules = [r for r in rules["block"] if r.startswith("geosite:")]
            ip_rules = [r for r in rules["block"] if r.startswith("geoip:")]

            if domain_rules:
                routing_rules.append({
                    "type": "field",
                    "domain": domain_rules,
                    "outboundTag": "block"
                })
            if ip_rules:
                routing_rules.append({
                    "type": "field",
                    "ip": ip_rules,
                    "outboundTag": "block"
                })

        # Direct rules
        if rules["direct"]:
            domain_rules = [r for r in rules["direct"] if r.startswith("geosite:")]
            ip_rules = [r for r in rules["direct"] if r.startswith("geoip:")]

            if domain_rules:
                routing_rules.append({
                    "type": "field",
                    "domain": domain_rules,
                    "outboundTag": "direct"
                })
            if ip_rules:
                routing_rules.append({
                    "type": "field",
                    "ip": ip_rules,
                    "outboundTag": "direct"
                })

        # Proxy rules (if specified)
        if rules["proxy"]:
            domain_rules = [r for r in rules["proxy"] if r.startswith("geosite:")]
            ip_rules = [r for r in rules["proxy"] if r.startswith("geoip:")]

            if domain_rules:
                routing_rules.append({
                    "type": "field",
                    "domain": domain_rules,
                    "outboundTag": "proxy"
                })
            if ip_rules:
                routing_rules.append({
                    "type": "field",
                    "ip": ip_rules,
                    "outboundTag": "proxy"
                })

        return {
            "domainStrategy": "AsIs",
            "domainMatcher": "hybrid",
            "rules": routing_rules
        }

    def get_optimal_config(
        self,
        server_country: str,
        target_region: str
    ) -> Dict[str, Any]:
        """
        Get optimal inbound configuration for server-region combination

        Args:
            server_country: Country where server is located (e.g., "NL", "DE", "US")
            target_region: Target user region (e.g., "RU", "CN", "IR")

        Returns:
            Optimal configuration recommendations
        """
        region = self.get_region(target_region)
        if not region:
            region = REGIONS["GLOBAL"]

        # Determine best protocol based on server location and target region
        recommended_protocol = region.recommended_protocols[0] if region.recommended_protocols else "vless+reality"

        # Get best Reality domain
        reality_domain = region.reality_domains[0] if region.reality_domains else "www.microsoft.com"

        # Get fingerprint
        fingerprint = region.recommended_fingerprints[0] if region.recommended_fingerprints else "chrome"

        return {
            "server_country": server_country,
            "target_region": target_region,
            "recommended_protocol": recommended_protocol,
            "all_recommended_protocols": region.recommended_protocols,
            "reality_domain": reality_domain,
            "all_reality_domains": region.reality_domains,
            "fingerprint": fingerprint,
            "routing_rules": self.get_routing_rules(target_region),
            "blocked_sites": region.blocked_sites,
            "notes": self._get_optimization_notes(server_country, target_region),
        }

    def _get_optimization_notes(self, server_country: str, target_region: str) -> List[str]:
        """Get optimization notes for specific combination"""
        notes = []

        # Server location recommendations
        if target_region == "RU":
            if server_country in ["NL", "DE", "FI", "LV", "LT", "EE"]:
                notes.append("Good server location for Russia - low latency")
            elif server_country in ["US", "SG", "JP"]:
                notes.append("Higher latency expected, consider European servers")

        elif target_region == "CN":
            if server_country in ["HK", "SG", "JP", "TW", "KR"]:
                notes.append("Good server location for China - low latency")
            elif server_country in ["US", "EU"]:
                notes.append("Higher latency expected, consider Asian servers")

        elif target_region == "IR":
            if server_country in ["DE", "NL", "TR"]:
                notes.append("Good server location for Iran")

        # Protocol recommendations
        if target_region in ["RU", "CN", "IR"]:
            notes.append("Reality protocol strongly recommended for this region")
            notes.append("Avoid VMess without TLS - easily detectable")

        return notes

    def get_blocked_sites(self, region_code: str) -> List[str]:
        """Get list of typically blocked sites in region"""
        region = self.get_region(region_code)
        if region:
            return region.blocked_sites
        return []


# Global instance
region_manager = RegionManager()
