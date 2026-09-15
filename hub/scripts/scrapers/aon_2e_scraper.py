# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Archives of Nethys 2e Scraper (aonprd.com)
# Source: https://2e.aonprd.com | License: Paizo Community Use Policy

import asyncio
import sqlite3
import sys
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from dataclasses import dataclass

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


class Aon2eScraper:
    """Scrapes Archives of Nethys 2e (2e.aonprd.com) for PF2e rules data."""

    def __init__(self, db_path: Path, rate_limit: float = 1.0):
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

        # Category URLs from sources.yaml
        self.category_urls = {
            "spell": "https://2e.aonprd.com/Spells.aspx",
            "feat": "https://2e.aonprd.com/Feats.aspx",
            "item": "https://2e.aonprd.com/Items.aspx",
            "equipment": "https://2e.aonprd.com/Equipment.aspx",
            "weapon": "https://2e.aonprd.com/Weapons.aspx",
            "armor": "https://2e.aonprd.com/Armor.aspx",
            "monster": "https://2e.aonprd.com/Monsters.aspx",
            "ancestry": "https://2e.aonprd.com/Ancestries.aspx",
            "class": "https://2e.aonprd.com/Classes.aspx",
            "background": "https://2e.aonprd.com/Backgrounds.aspx",
            "condition": "https://2e.aonprd.com/Conditions.aspx",
            "action": "https://2e.aonprd.com/Actions.aspx",
            "skill": "https://2e.aonprd.com/Skills.aspx",
            "deity": "https://2e.aonprd.com/Deities.aspx",
            "ritual": "https://2e.aonprd.com/Rituals.aspx",
            "archetype": "https://2e.aonprd.com/Archetypes.aspx",
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
        """Clean HTML to extract readable text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts, styles, nav, footer, ads
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()

        # Get text with structure preserved
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text.strip()

    def _parse_list_page(self, html: str, base_url: str, category: str) -> List[Dict[str, str]]:
        """Parse a list page (e.g., Spells.aspx) to extract entry links."""
        soup = BeautifulSoup(html, "html.parser")
        entries = []

        # AoN 2e uses tables with class "index" or similar for listings
        # Try multiple selectors
        tables = soup.find_all("table", class_=re.compile(r"index|list|data"))
        if not tables:
            tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                # First cell usually has the name/link
                name_cell = cells[0]
                link = name_cell.find("a", href=True)
                if not link:
                    continue

                name = link.get_text(strip=True)
                href = link["href"]
                full_url = urljoin("https://2e.aonprd.com/", href)

                # Other cells might have level, traits, source
                level = ""
                traits = ""
                source = ""
                if len(cells) > 1:
                    level = cells[1].get_text(strip=True)
                if len(cells) > 2:
                    traits = cells[2].get_text(strip=True)
                if len(cells) > 3:
                    source = cells[3].get_text(strip=True)

                entries.append({
                    "name": name,
                    "url": full_url,
                    "level": level,
                    "traits": traits,
                    "source": source
                })

        return entries

    async def _fetch_detail_page(self, url: str) -> Optional[str]:
        """Fetch and clean a detail page."""
        html = await self._fetch(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Main content area
        main = soup.find("main") or soup.find("div", id="main-content") or soup.find("div", class_="main")
        if not main:
            main = soup.body

        # Remove navigation, ads, etc.
        for tag in main(["nav", "header", "footer", "aside", "script", "style", "form", "iframe"]):
            tag.decompose()

        # Get clean text
        text = main.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _build_content(self, entry_data: Dict[str, str], detail_text: str, category: str) -> str:
        parts = []

        name = entry_data.get("name", "")
        if name:
            parts.append(f"# {name}")

        if entry_data.get("level"):
            parts.append(f"**Level:** {entry_data['level']}")

        if entry_data.get("traits"):
            parts.append(f"**Traits:** {entry_data['traits']}")

        if entry_data.get("source"):
            parts.append(f"**Source:** {entry_data['source']}")

        if detail_text:
            # Clean up the detail text
            clean_text = self._clean_text(detail_text)
            if clean_text:
                parts.append(clean_text)

        return "\n\n".join(parts)

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    async def scrape_category(
        self, category: str, max_pages: Optional[int] = None, offset: int = 0
    ) -> int:
        """Scrape a single category (chunk: entries[offset:offset+max_pages])."""
        url = self.category_urls.get(category)
        if not url:
            print(f"Unknown category: {category}")
            return 0

        print(f"Scraping {category} from {url} (offset={offset}, limit={max_pages})")
        html = await self._fetch(url)
        if not html:
            return 0

        entries = self._parse_list_page(html, url, category)
        print(f"Found {len(entries)} entries for {category}")
        queue = entries[offset:(offset + max_pages) if max_pages else None]

        imported = 0
        for entry in queue:
            if self._ckpt is not None and self._ckpt.has(entry["url"]):
                self.stats["skipped"] += 1
                continue
            self.stats["total"] += 1

            try:
                detail_text = await self._fetch_detail_page(entry["url"])
                content = self._build_content({
                    "name": entry["name"],
                    "level": entry.get("level", ""),
                    "traits": entry.get("traits", ""),
                    "source": entry.get("source", "")
                }, detail_text or "", category)

                if not content or len(content) < 20:
                    self.stats["skipped"] += 1
                    continue

                scraped = ScrapedEntry(
                    system="2e",
                    category=category,
                    name=entry["name"],
                    source_book="Archives of Nethys 2e",
                    raw_content=content,
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

    def _insert_entry(self, entry: ScrapedEntry) -> bool:
        """Insert entry with deduplication."""
        cursor = self.conn.execute(
            "SELECT 1 FROM rules WHERE system = ? AND name = ? AND source_book = ?",
            (entry.system, entry.name, "Archives of Nethys 2e")
        )
        if cursor.fetchone():
            self.stats["skipped"] += 1
            return False

        self.conn.execute(
            """INSERT INTO rules (system, category, name, source_book, raw_content)
               VALUES (?, ?, ?, ?, ?)""",
            (entry.system, entry.category, entry.name, "Archives of Nethys 2e", entry.raw_content)
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
            ckpt_path = Path(__file__).resolve().parent.parent / "checkpoints" / "aon_2e.json"
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
        print(f"\n=== AoN 2e Scraping Complete ===")
        print(f"Total Imported: {total_imported}")
        await self.session.close()
        self.conn.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Archives of Nethys 2e (fleet chunk)")
    parser.add_argument("--db-path", required=True, help="Path to output SQLite database")
    parser.add_argument("--max-per-category", type=int, help="Max entries per category (chunk size)")
    parser.add_argument("--offset", type=int, default=0, help="Start offset within each category")
    parser.add_argument("--categories", nargs="*", help="Subset of categories (default: all)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint file")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    scraper = Aon2eScraper(db_path)
    await scraper.scrape_all(
        max_per_category=args.max_per_category,
        offset=args.offset,
        categories=args.categories,
        resume=args.resume,
    )


if __name__ == "__main__":
    asyncio.run(main())