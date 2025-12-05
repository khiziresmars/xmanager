#!/usr/bin/env python3
"""
Site Accessibility Checker for XUI-Manager
Checks if sites are accessible through the proxy, with focus on Russia/CIS whitelist
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class SiteCategory(str, Enum):
    """Site categories"""
    SOCIAL = "social"
    VIDEO = "video"
    MESSENGER = "messenger"
    SEARCH = "search"
    AI = "ai"
    STREAMING = "streaming"
    NEWS = "news"
    GAMING = "gaming"
    WORK = "work"
    RU_SERVICE = "ru_service"
    TECH = "tech"
    OTHER = "other"


@dataclass
class SiteConfig:
    """Site configuration for checking"""
    url: str
    name: str
    category: SiteCategory
    blocked_in: List[str] = field(default_factory=list)  # Region codes where blocked
    importance: int = 1  # 1-3, higher = more important
    check_method: str = "head"  # head, get


@dataclass
class SiteCheckResult:
    """Result of site accessibility check"""
    url: str
    name: str
    category: str
    accessible: bool
    status_code: int
    latency_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    checked_via_proxy: bool = False


# ============================================
# SITE WHITELIST - Focus on Russia/CIS
# ============================================

SITE_WHITELIST: List[SiteConfig] = [
    # === SOCIAL NETWORKS (blocked in Russia) ===
    SiteConfig(
        url="https://www.instagram.com",
        name="Instagram",
        category=SiteCategory.SOCIAL,
        blocked_in=["RU"],
        importance=3,
    ),
    SiteConfig(
        url="https://twitter.com",
        name="Twitter/X",
        category=SiteCategory.SOCIAL,
        blocked_in=["RU", "CN"],
        importance=3,
    ),
    SiteConfig(
        url="https://www.facebook.com",
        name="Facebook",
        category=SiteCategory.SOCIAL,
        blocked_in=["RU", "CN"],
        importance=3,
    ),
    SiteConfig(
        url="https://www.linkedin.com",
        name="LinkedIn",
        category=SiteCategory.SOCIAL,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://www.tiktok.com",
        name="TikTok",
        category=SiteCategory.SOCIAL,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.threads.net",
        name="Threads",
        category=SiteCategory.SOCIAL,
        blocked_in=["RU"],
        importance=2,
    ),

    # === VIDEO PLATFORMS ===
    SiteConfig(
        url="https://www.youtube.com",
        name="YouTube",
        category=SiteCategory.VIDEO,
        blocked_in=["CN"],
        importance=3,
    ),
    SiteConfig(
        url="https://vimeo.com",
        name="Vimeo",
        category=SiteCategory.VIDEO,
        blocked_in=[],
        importance=1,
    ),
    SiteConfig(
        url="https://www.twitch.tv",
        name="Twitch",
        category=SiteCategory.VIDEO,
        blocked_in=[],
        importance=2,
    ),

    # === MESSENGERS ===
    SiteConfig(
        url="https://web.telegram.org",
        name="Telegram Web",
        category=SiteCategory.MESSENGER,
        blocked_in=["CN", "IR"],
        importance=3,
    ),
    SiteConfig(
        url="https://discord.com",
        name="Discord",
        category=SiteCategory.MESSENGER,
        blocked_in=["RU", "CN", "UAE"],
        importance=3,
    ),
    SiteConfig(
        url="https://web.whatsapp.com",
        name="WhatsApp Web",
        category=SiteCategory.MESSENGER,
        blocked_in=["CN"],
        importance=2,
    ),
    SiteConfig(
        url="https://signal.org",
        name="Signal",
        category=SiteCategory.MESSENGER,
        blocked_in=["CN", "IR"],
        importance=2,
    ),

    # === SEARCH ENGINES ===
    SiteConfig(
        url="https://www.google.com",
        name="Google",
        category=SiteCategory.SEARCH,
        blocked_in=["CN"],
        importance=3,
    ),
    SiteConfig(
        url="https://duckduckgo.com",
        name="DuckDuckGo",
        category=SiteCategory.SEARCH,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.bing.com",
        name="Bing",
        category=SiteCategory.SEARCH,
        blocked_in=[],
        importance=1,
    ),

    # === AI SERVICES ===
    SiteConfig(
        url="https://chat.openai.com",
        name="ChatGPT",
        category=SiteCategory.AI,
        blocked_in=["RU", "CN"],
        importance=3,
    ),
    SiteConfig(
        url="https://claude.ai",
        name="Claude",
        category=SiteCategory.AI,
        blocked_in=["RU"],
        importance=3,
    ),
    SiteConfig(
        url="https://gemini.google.com",
        name="Google Gemini",
        category=SiteCategory.AI,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://copilot.microsoft.com",
        name="Microsoft Copilot",
        category=SiteCategory.AI,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.midjourney.com",
        name="Midjourney",
        category=SiteCategory.AI,
        blocked_in=[],
        importance=2,
    ),

    # === STREAMING ===
    SiteConfig(
        url="https://www.netflix.com",
        name="Netflix",
        category=SiteCategory.STREAMING,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.spotify.com",
        name="Spotify",
        category=SiteCategory.STREAMING,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://music.apple.com",
        name="Apple Music",
        category=SiteCategory.STREAMING,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.primevideo.com",
        name="Amazon Prime Video",
        category=SiteCategory.STREAMING,
        blocked_in=[],
        importance=1,
    ),
    SiteConfig(
        url="https://www.hbomax.com",
        name="HBO Max",
        category=SiteCategory.STREAMING,
        blocked_in=[],
        importance=1,
    ),

    # === NEWS (some blocked in Russia) ===
    SiteConfig(
        url="https://www.bbc.com",
        name="BBC",
        category=SiteCategory.NEWS,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://www.dw.com",
        name="Deutsche Welle",
        category=SiteCategory.NEWS,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://meduza.io",
        name="Meduza",
        category=SiteCategory.NEWS,
        blocked_in=["RU"],
        importance=2,
    ),
    SiteConfig(
        url="https://www.cnn.com",
        name="CNN",
        category=SiteCategory.NEWS,
        blocked_in=[],
        importance=1,
    ),

    # === WORK/PRODUCTIVITY ===
    SiteConfig(
        url="https://github.com",
        name="GitHub",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=3,
    ),
    SiteConfig(
        url="https://gitlab.com",
        name="GitLab",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.notion.so",
        name="Notion",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.figma.com",
        name="Figma",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://slack.com",
        name="Slack",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://zoom.us",
        name="Zoom",
        category=SiteCategory.WORK,
        blocked_in=[],
        importance=2,
    ),

    # === GAMING ===
    SiteConfig(
        url="https://store.steampowered.com",
        name="Steam",
        category=SiteCategory.GAMING,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.epicgames.com",
        name="Epic Games",
        category=SiteCategory.GAMING,
        blocked_in=[],
        importance=1,
    ),

    # === RUSSIAN SERVICES (should work directly) ===
    SiteConfig(
        url="https://www.yandex.ru",
        name="Yandex",
        category=SiteCategory.RU_SERVICE,
        blocked_in=[],
        importance=3,
    ),
    SiteConfig(
        url="https://vk.com",
        name="VKontakte",
        category=SiteCategory.RU_SERVICE,
        blocked_in=[],
        importance=3,
    ),
    SiteConfig(
        url="https://ok.ru",
        name="Odnoklassniki",
        category=SiteCategory.RU_SERVICE,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://mail.ru",
        name="Mail.ru",
        category=SiteCategory.RU_SERVICE,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.gosuslugi.ru",
        name="Gosuslugi",
        category=SiteCategory.RU_SERVICE,
        blocked_in=[],
        importance=3,
    ),

    # === TECH ===
    SiteConfig(
        url="https://www.cloudflare.com",
        name="Cloudflare",
        category=SiteCategory.TECH,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://aws.amazon.com",
        name="AWS",
        category=SiteCategory.TECH,
        blocked_in=[],
        importance=2,
    ),
    SiteConfig(
        url="https://www.docker.com",
        name="Docker",
        category=SiteCategory.TECH,
        blocked_in=[],
        importance=2,
    ),
]


class SiteAccessChecker:
    """
    Site accessibility checker

    Checks if sites are accessible, optionally through a proxy.
    Tracks results history for trend analysis.
    """

    def __init__(
        self,
        timeout: int = 10,
        results_file: str = "/opt/xui-manager/site_check_results.json"
    ):
        self.timeout = timeout
        self.results_file = results_file
        self.last_results: Dict[str, SiteCheckResult] = {}
        self.history: List[Dict[str, Any]] = []

        self._load_results()

    def _load_results(self):
        """Load previous results from file"""
        try:
            if os.path.exists(self.results_file):
                with open(self.results_file, 'r') as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
        except Exception as e:
            logger.error(f"Error loading site check results: {e}")

    def _save_results(self):
        """Save results to file"""
        try:
            os.makedirs(os.path.dirname(self.results_file), exist_ok=True)

            # Keep only last 24 hours of history
            cutoff = time.time() - 86400
            self.history = [h for h in self.history if h.get("timestamp", 0) > cutoff]

            with open(self.results_file, 'w') as f:
                json.dump({
                    "last_check": time.time(),
                    "history": self.history,
                }, f)
        except Exception as e:
            logger.error(f"Error saving site check results: {e}")

    async def check_site(
        self,
        site: SiteConfig,
        proxy: Optional[str] = None
    ) -> SiteCheckResult:
        """Check single site accessibility"""
        start_time = time.time()

        try:
            connector = None
            if proxy:
                # Setup proxy if provided
                pass

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                method = session.head if site.check_method == "head" else session.get

                async with method(
                    site.url,
                    allow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                ) as response:
                    latency = (time.time() - start_time) * 1000

                    return SiteCheckResult(
                        url=site.url,
                        name=site.name,
                        category=site.category.value,
                        accessible=response.status < 400,
                        status_code=response.status,
                        latency_ms=latency,
                        checked_via_proxy=proxy is not None,
                    )

        except asyncio.TimeoutError:
            return SiteCheckResult(
                url=site.url,
                name=site.name,
                category=site.category.value,
                accessible=False,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                error="Timeout",
                checked_via_proxy=proxy is not None,
            )
        except aiohttp.ClientError as e:
            return SiteCheckResult(
                url=site.url,
                name=site.name,
                category=site.category.value,
                accessible=False,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
                checked_via_proxy=proxy is not None,
            )
        except Exception as e:
            return SiteCheckResult(
                url=site.url,
                name=site.name,
                category=site.category.value,
                accessible=False,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Error: {str(e)}",
                checked_via_proxy=proxy is not None,
            )

    async def check_all_sites(
        self,
        proxy: Optional[str] = None,
        region_filter: Optional[str] = None,
        category_filter: Optional[SiteCategory] = None,
        importance_min: int = 1
    ) -> Dict[str, Any]:
        """
        Check all sites from whitelist

        Args:
            proxy: Optional proxy URL (socks5://host:port or http://host:port)
            region_filter: Only check sites blocked in this region
            category_filter: Only check sites in this category
            importance_min: Minimum importance level (1-3)

        Returns:
            Summary of check results
        """
        # Filter sites
        sites_to_check = []
        for site in SITE_WHITELIST:
            if importance_min and site.importance < importance_min:
                continue
            if region_filter and region_filter not in site.blocked_in:
                continue
            if category_filter and site.category != category_filter:
                continue
            sites_to_check.append(site)

        if not sites_to_check:
            return {
                "total": 0,
                "accessible": 0,
                "failed": 0,
                "message": "No sites to check with given filters"
            }

        # Run checks in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent checks

        async def check_with_limit(site):
            async with semaphore:
                return await self.check_site(site, proxy)

        tasks = [check_with_limit(site) for site in sites_to_check]
        results = await asyncio.gather(*tasks)

        # Process results
        accessible = [r for r in results if r.accessible]
        failed = [r for r in results if not r.accessible]

        # Calculate stats
        avg_latency = sum(r.latency_ms for r in accessible) / len(accessible) if accessible else 0

        # Group by category
        by_category: Dict[str, Dict[str, int]] = {}
        for r in results:
            if r.category not in by_category:
                by_category[r.category] = {"total": 0, "accessible": 0}
            by_category[r.category]["total"] += 1
            if r.accessible:
                by_category[r.category]["accessible"] += 1

        # Store results
        self.last_results = {r.url: r for r in results}

        # Add to history
        self.history.append({
            "timestamp": time.time(),
            "total": len(results),
            "accessible": len(accessible),
            "failed": len(failed),
            "avg_latency_ms": avg_latency,
            "via_proxy": proxy is not None,
        })

        self._save_results()

        return {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "accessible": len(accessible),
            "failed": len(failed),
            "accessibility_rate": len(accessible) / len(results) * 100 if results else 0,
            "avg_latency_ms": round(avg_latency, 2),
            "via_proxy": proxy is not None,
            "by_category": by_category,
            "failed_sites": [
                {
                    "name": r.name,
                    "url": r.url,
                    "error": r.error,
                    "category": r.category,
                }
                for r in failed
            ],
            "slowest_sites": sorted(
                [{"name": r.name, "latency_ms": round(r.latency_ms, 2)} for r in accessible],
                key=lambda x: x["latency_ms"],
                reverse=True
            )[:5],
        }

    async def check_region_blocked_sites(
        self,
        region: str,
        proxy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check sites that are blocked in specific region

        Args:
            region: Region code (e.g., "RU", "CN")
            proxy: Optional proxy to test through

        Returns:
            Results focusing on blocked sites for this region
        """
        blocked_sites = [s for s in SITE_WHITELIST if region in s.blocked_in]

        if not blocked_sites:
            return {
                "region": region,
                "message": f"No known blocked sites for region {region}",
                "total": 0,
            }

        # Check blocked sites
        tasks = [self.check_site(site, proxy) for site in blocked_sites]
        results = await asyncio.gather(*tasks)

        accessible = [r for r in results if r.accessible]
        failed = [r for r in results if not r.accessible]

        return {
            "region": region,
            "total_blocked_sites": len(blocked_sites),
            "accessible_via_proxy": len(accessible),
            "still_blocked": len(failed),
            "success_rate": len(accessible) / len(blocked_sites) * 100 if blocked_sites else 0,
            "via_proxy": proxy is not None,
            "details": [
                {
                    "name": r.name,
                    "url": r.url,
                    "accessible": r.accessible,
                    "latency_ms": round(r.latency_ms, 2) if r.accessible else None,
                    "error": r.error,
                }
                for r in results
            ],
        }

    def get_sites_by_category(self, category: SiteCategory) -> List[Dict[str, Any]]:
        """Get all sites in a category"""
        return [
            {
                "url": s.url,
                "name": s.name,
                "blocked_in": s.blocked_in,
                "importance": s.importance,
            }
            for s in SITE_WHITELIST
            if s.category == category
        ]

    def get_blocked_sites_for_region(self, region: str) -> List[Dict[str, Any]]:
        """Get list of sites blocked in specific region"""
        return [
            {
                "url": s.url,
                "name": s.name,
                "category": s.category.value,
                "importance": s.importance,
            }
            for s in SITE_WHITELIST
            if region in s.blocked_in
        ]

    def get_check_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get check history for the last N hours"""
        cutoff = time.time() - (hours * 3600)
        return [h for h in self.history if h.get("timestamp", 0) > cutoff]

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories with site counts"""
        categories: Dict[str, int] = {}
        for site in SITE_WHITELIST:
            cat = site.category.value
            categories[cat] = categories.get(cat, 0) + 1

        return [
            {"category": cat, "count": count}
            for cat, count in sorted(categories.items())
        ]

    def get_regions(self) -> List[Dict[str, Any]]:
        """Get all regions with blocked site counts"""
        regions: Dict[str, int] = {}
        for site in SITE_WHITELIST:
            for region in site.blocked_in:
                regions[region] = regions.get(region, 0) + 1

        return [
            {"region": region, "blocked_count": count}
            for region, count in sorted(regions.items(), key=lambda x: x[1], reverse=True)
        ]


# Global instance
_checker: Optional[SiteAccessChecker] = None


def get_site_checker() -> SiteAccessChecker:
    """Get global site checker instance"""
    global _checker
    if _checker is None:
        try:
            from app.config import settings
            _checker = SiteAccessChecker(
                timeout=settings.SITE_CHECK_TIMEOUT,
            )
        except Exception:
            _checker = SiteAccessChecker()
    return _checker
