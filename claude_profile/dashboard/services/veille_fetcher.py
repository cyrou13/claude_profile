"""Fetch updates from GitHub, dev.to, Hacker News, and community sources."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from claude_profile.models import (
    CommunityRepo,
    FeedEntry,
    ReleaseInfo,
    VeilleConfig,
    VeilleReport,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".config" / "claude-profile"
CACHE_FILE = CACHE_DIR / "veille-cache.json"


class VeilleFetcher:
    """Fetches updates from configured sources."""

    def __init__(self, config: VeilleConfig, github_token: str | None = None) -> None:
        self.config = config
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN", "")

    async def fetch_all(self) -> VeilleReport:
        """Fetch all sources and return aggregated report."""
        releases: list[ReleaseInfo] = []
        feed_entries: list[FeedEntry] = []
        community_repos: list[CommunityRepo] = []

        github_headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if self.github_token:
            github_headers["Authorization"] = f"Bearer {self.github_token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # GitHub releases
            for repo in self.config.github_repos:
                try:
                    repo_releases = await self._fetch_releases(client, repo, github_headers)
                    releases.extend(repo_releases)
                except (httpx.HTTPError, KeyError) as e:
                    logger.warning("Failed to fetch releases for %s: %s", repo, e)

            # GitHub community repos
            try:
                repos = await self._search_community(client, github_headers)
                community_repos.extend(repos)
            except (httpx.HTTPError, KeyError) as e:
                logger.warning("Failed to search community repos: %s", e)

            # Dev.to articles
            try:
                articles = await self._fetch_devto(client)
                feed_entries.extend(articles)
            except (httpx.HTTPError, KeyError) as e:
                logger.warning("Failed to fetch dev.to articles: %s", e)

            # Hacker News stories
            try:
                stories = await self._fetch_hackernews(client)
                feed_entries.extend(stories)
            except (httpx.HTTPError, KeyError) as e:
                logger.warning("Failed to fetch HN stories: %s", e)

        # Sort feed entries by popularity (likes/points stored in summary prefix)
        feed_entries.sort(
            key=lambda e: e.published or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        report = VeilleReport(
            fetched_at=datetime.now(tz=timezone.utc),
            releases=sorted(releases, key=lambda r: r.published_at, reverse=True),
            feed_entries=feed_entries,
            community_repos=sorted(community_repos, key=lambda r: r.stars, reverse=True),
        )

        self._save_cache(report)
        return report

    async def _fetch_releases(
        self, client: httpx.AsyncClient, repo: str, headers: dict[str, str]
    ) -> list[ReleaseInfo]:
        """Fetch latest releases for a GitHub repo."""
        url = f"https://api.github.com/repos/{repo}/releases"
        resp = await client.get(url, params={"per_page": 5}, headers=headers)
        resp.raise_for_status()

        releases: list[ReleaseInfo] = []
        for r in resp.json():
            releases.append(
                ReleaseInfo(
                    repo=repo,
                    tag=r.get("tag_name", ""),
                    name=r.get("name", ""),
                    published_at=datetime.fromisoformat(
                        r["published_at"].replace("Z", "+00:00")
                    ),
                    body=r.get("body", "")[:500],
                    url=r.get("html_url", ""),
                )
            )
        return releases

    async def _fetch_devto(self, client: httpx.AsyncClient) -> list[FeedEntry]:
        """Fetch popular Claude Code articles from dev.to."""
        entries: list[FeedEntry] = []

        # Search multiple relevant tags
        for tag in ("claudecode", "claude", "anthropic"):
            url = "https://dev.to/api/articles"
            params = {"tag": tag, "per_page": 15, "top": 365}
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                continue

            for a in resp.json():
                title = a.get("title", "")
                # Filter for Claude Code relevance
                title_lower = title.lower()
                desc_lower = (a.get("description", "") or "").lower()
                if not any(
                    kw in title_lower or kw in desc_lower
                    for kw in ("claude code", "claude-code", "claudecode", "claude skill", "claude.md", "mcp server")
                ):
                    continue

                likes = a.get("positive_reactions_count", 0)
                if likes < 5:
                    continue

                published = None
                if a.get("published_at"):
                    try:
                        published = datetime.fromisoformat(
                            a["published_at"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

                entries.append(
                    FeedEntry(
                        title=f"[dev.to {likes} likes] {title}",
                        link=a.get("url", ""),
                        published=published,
                        summary=(a.get("description", "") or "")[:200],
                    )
                )

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[FeedEntry] = []
        for e in entries:
            if e.link not in seen:
                seen.add(e.link)
                unique.append(e)

        return sorted(unique, key=lambda e: e.title, reverse=True)[:15]

    async def _fetch_hackernews(self, client: httpx.AsyncClient) -> list[FeedEntry]:
        """Fetch popular Claude Code stories from Hacker News (Algolia API)."""
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": "claude code",
            "tags": "story",
            "hitsPerPage": 20,
        }
        resp = await client.get(url, params=params)
        resp.raise_for_status()

        entries: list[FeedEntry] = []
        for h in resp.json().get("hits", []):
            points = h.get("points", 0) or 0
            if points < 20:
                continue

            title = h.get("title", "")
            link = h.get("url", "") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"

            published = None
            if h.get("created_at"):
                try:
                    published = datetime.fromisoformat(
                        h["created_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            entries.append(
                FeedEntry(
                    title=f"[HN {points} pts] {title}",
                    link=link,
                    published=published,
                    summary=f"{h.get('num_comments', 0)} comments",
                )
            )

        return sorted(entries, key=lambda e: e.title, reverse=True)[:15]

    async def _search_community(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> list[CommunityRepo]:
        """Search GitHub for popular Claude Code repos (>= 10 stars)."""
        url = "https://api.github.com/search/repositories"
        params = {
            "q": "claude-code stars:>=10",
            "sort": "stars",
            "order": "desc",
            "per_page": 20,
        }
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()

        repos: list[CommunityRepo] = []
        for r in resp.json().get("items", []):
            repos.append(
                CommunityRepo(
                    name=r.get("name", ""),
                    full_name=r.get("full_name", ""),
                    description=r.get("description", "") or "",
                    stars=r.get("stargazers_count", 0),
                    url=r.get("html_url", ""),
                    updated_at=datetime.fromisoformat(
                        r["updated_at"].replace("Z", "+00:00")
                    )
                    if r.get("updated_at")
                    else None,
                )
            )
        return repos

    def _save_cache(self, report: VeilleReport) -> None:
        """Cache veille results locally."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(report.model_dump_json(indent=2))

    @staticmethod
    def load_cache() -> VeilleReport | None:
        """Load cached veille results."""
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text())
            return VeilleReport.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return None
