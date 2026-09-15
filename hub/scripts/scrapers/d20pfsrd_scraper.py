# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# d20pfsrd.com Scraper - Community 1e Data
# Source: https://www.d20pfsrd.com | License: OGL/Community Use

import asyncio
import sqlite3
import sys
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fleet import Checkpoint, DomainLimiter
from fleet import fetch as fleet_fetch
from fleet import FetchError


@dataclass
class ScrapedEntry:
    system: str
    category: str
    name: str
    source_book: str
    raw_content: str
    source_url: str


class D20PFSRDScraper:
    """Scrapes d20pfsrd.com for Pathfinder 1e community data."""

    def __init__(self, db_path: Path, rate_limit: float = 2.0):
        self.db_path = db_path
        self.rate_limit = rate_limit
        self.conn: Optional[sqlite3.Connection] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "by_category": {}
        }
        self._limiter = DomainLimiter()
        self._ckpt: Checkpoint | None = None

        self.category_urls = {
            "spell": "https://www.d20pfsrd.com/magic/spell-lists-and-domains/spell-lists",
            "feat": "https://www.d20pfsrd.com/feats",
            "item": "https://www.d20pfsrd.com/magic-items",
            "equipment": "https://www.d20pfsrd.com/equipment",
            "weapon": "https://www.d20pfsrd.com/equipment/weapons",
            "armor": "https://www.d20pfsrd.com/equipment/armor",
            "monster": "https://www.d20pfsrd.com/bestiary",
            "race": "https://www.d20pfsrd.com/races",
            "class": "https://www.d20pfsrd.com/classes",
            "prestige_class": "https://www.d20pfsrd.com/classes/prestige-classes",
            "archetype": "https://www.d20pfsrd.com/classes/archetypes",
            "condition": "https://www.d20pfsrd.com/conditions",
            "skill": "https://www.d20pfsrd.com/skills",
            "trait": "https://www.d20pfsrd.com/traits",
            "deity": "https://www.d20pfsrd.com/deities",
        }

    async def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "PathfinderGod/1.0 (Educational/Research)"}
        )

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    async def _fetch(self, url: str) -> Optional[str]:
        """Fetch via the fleet (rotating UA, probed rate limits, backoff)."""
        try:
            return await fleet_fetch(self.session, url, limiter=self._limiter)
        except FetchError as e:
            print(f"fleet fetch failed: {e}")
            return None

    def _clean_html(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()
        for tag in soup.find_all("div", class_="ads"):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text.strip()

    def _parse_list_page(self, html: str, base_url: str, category: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries = []

        # d20pfsrd uses various structures - try multiple approaches
        # Look for links in main content area
        main = soup.find("main") or soup.find("div", id="main-content") or soup.find("div", id="content") or soup.body

        links = main.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            if not href:
                continue

            # Filter for relevant paths
            if not any(x in href for x in ["/feats/", "/spells/", "/magic-items/", "/equipment/", "/bestiary/", "/races/", "/classes/", "/conditions/", "/skills/", "/traits/", "/deities/"]):
                continue

            name = link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            full_url = urljoin("https://www.d20pfsrd.com/", href)

            entries.append({
                "name": name,
                "url": full_url,
            })

        # Deduplicate
        seen = set()
        unique = []
        for e in entries:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)

        return unique[:100]  # Limit for testing

    async def _fetch_detail_page(self, url: str) -> Optional[str]:
        html = await self._fetch(url)
        if not html:
            return None
        try:
            soup = BeautifulSoup(html, "html.parser")

            main = soup.find("main") or soup.find("div", id="main-content") or soup.find("div", id="content") or soup.body
            for tag in main(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
                tag.decompose()

            text = main.get_text(separator="\n", strip=True)
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()
        except Exception as e:
            print(f"Error parsing {url}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _build_content(self, entry_data: Dict[str, str], detail_text: str, category: str) -> str:
        parts = []
        name = entry_data.get("name", "")
        if name:
            parts.append(f"# {name}")
        if detail_text:
            clean_text = re.sub(r'<[^>]+>', '', detail_text)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            if clean_text.strip():
                parts.append(clean_text.strip())
        return "\n\n".join(parts)

    async def scrape_category(
        self, category: str, max_pages: Optional[int] = None, offset: int = 0
    ) -> int:
        url = self.category_urls.get(category)
        if not url:
            return 0

        print(f"Scraping {category} from {url} (offset={offset}, limit={max_pages})")
        html = await self._fetch(url)
        if not html:
            return 0

        # Parse the main page for links
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup.find("div", id="main-content") or soup.find("div", id="content") or soup.body

        links = main.find_all("a", href=True)
        entries = []
        for link in links:
            href = link.get("href", "")
            name = link.get_text(strip=True)
            if name and len(name) > 2:
                full_url = urljoin("https://www.d20pfsrd.com/", href)
                entries.append({"name": name, "url": full_url})

        # Deduplicate
        seen = set()
        unique = []
        for e in entries:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)

        print(f"Found {len(unique)} entries for {category}")
        queue = unique[offset:(offset + max_pages) if max_pages else None]

        imported = 0
        for entry in queue:
            if self._ckpt is not None and self._ckpt.has(entry["url"]):
                self.stats["skipped"] += 1
                continue
            self.stats["total"] += 1

            try:
                detail_text = await self._fetch_detail_page(entry["url"])
                content = self._build_content(entry, detail_text or "", category)

                if not content or len(content) < 20:
                    self.stats["skipped"] += 1
                    continue

                scraped = ScrapedEntry(
                    system="1e",
                    category=category,
                    name=entry["name"],
                    source_book="d20pfsrd.com",
                    raw_content=self._build_content(entry, detail_text or "", category),
                    source_url=entry["url"]
                )

                if self._insert_entry(scraped):
                    self.stats["imported"] += 1
                    self.stats["by_category"][category] = self.stats["by_category"].get(category, 0) + 1
                    imported += 1
                else:
                    self.stats["skipped"] += 1
                if self._ckpt is not None:
                    self._ckpt.mark(entry["url"])

            except Exception as e:
                print(f"Error processing {entry['name']}: {e}")
                self.stats["errors"] += 1

        return imported

    def _insert_entry(self, entry) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM rules WHERE system = ? AND name = ? AND source_book = ?",
            (entry.system, entry.name, "d20pfsrd.com")
        )
        if cursor.fetchone():
            self.stats["skipped"] += 1
            return False

        self.conn.execute(
            """INSERT INTO rules (system, category, name, source_book, raw_content)
               VALUES (?, ?, ?, ?, ?)""",
            (entry.system, entry.category, entry.name, "d20pfsrd.com", entry.raw_content)
        )
        self.conn.commit()
        return True

    async def scrape_all(
        self,
        max_per_category: Optional[int] = None,
        offset: int = 0,
        categories: Optional[list] = None,
        resume: bool = False,
    ):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "PathfinderGod/1.0"},
        )
        if resume:
            ckpt_path = Path(__file__).resolve().parent.parent / "checkpoints" / "d20pfsrd.json"
            self._ckpt = Checkpoint(ckpt_path)
            print(f"Resuming from checkpoint ({len(self._ckpt.done)} done)")

        total_imported = 0
        for category in categories or list(self.category_urls.keys()):
            self.stats["total"] = 0
            self.stats["imported"] = 0
            self.stats["skipped"] = 0
            self.stats["errors"] = 0
            self.stats["by_category"] = {}

            try:
                await self.scrape_category(category, max_pages=max_per_category, offset=offset)
                print(f"\n=== {category} Complete ===")
                print(f"Total: {self.stats['total']}, Imported: {self.stats['imported']}, Skipped: {self.stats['skipped']}, Errors: {self.stats['errors']}")
                total_imported += self.stats["imported"]
            except Exception as e:
                print(f"Error scraping {category}: {e}")
                self.stats["errors"] += 1

        if self._ckpt is not None:
            self._ckpt.save(force=True)
        print(f"\n=== d20pfsrd Scraping Complete ===")
        print(f"Total Imported: {total_imported}")
        await self.session.close()
        self.conn.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape d20pfsrd.com (fleet chunk)")
    parser.add_argument("--db-path", required=True, help="Path to output SQLite database")
    parser.add_argument("--max-per-category", type=int, help="Max entries per category (chunk size)")
    parser.add_argument("--offset", type=int, default=0, help="Start offset within each category")
    parser.add_argument("--categories", nargs="*", help="Subset of categories (default: all)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint file")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    scraper = D20PFSRDScraper(db_path)
    await scraper.scrape_all(
        max_per_category=args.max_per_category,
        offset=args.offset,
        categories=args.categories,
        resume=args.resume,
    )


if __name__ == "__main__":
    asyncio.run(main())