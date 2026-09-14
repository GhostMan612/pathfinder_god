# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Archives of Nethys 1e Scraper (aonprd.com)
# Source: https://www.aonprd.com | License: Paizo Community Use Policy

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


@dataclass
class ScrapedEntry:
    system: str
    category: str
    name: str
    source_book: str
    raw_content: str
    source_url: str


class Aon1eScraper:
    """Scrapes Archives of Nethys 1e (aonprd.com) for PF1e rules data."""

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
        self._last_request_time = 0

        self.category_urls = {
            "spell": "https://www.aonprd.com/SpellDisplay.aspx",
            "feat": "https://www.aonprd.com/Feats.aspx",
            "item": "https://www.aonprd.com/MagicItems.aspx",
            "equipment": "https://www.aonprd.com/Equipment.aspx",
            "weapon": "https://www.aonprd.com/Weapons.aspx",
            "armor": "https://www.aonprd.com/Armor.aspx",
            "monster": "https://www.aonprd.com/Monsters.aspx",
            "race": "https://www.aonprd.com/Races.aspx",
            "class": "https://www.aonprd.com/Classes.aspx",
            "prestige_class": "https://www.aonprd.com/PrestigeClasses.aspx",
            "archetype": "https://www.aonprd.com/Archetypes.aspx",
            "condition": "https://www.aonprd.com/Conditions.aspx",
            "skill": "https://www.aonprd.com/Skills.aspx",
            "deity": "https://www.aonprd.com/Deities.aspx",
            "trait": "https://www.aonprd.com/Traits.aspx",
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

    async def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def _fetch(self, url: str) -> Optional[str]:
        await self._rate_limit()
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _clean_html(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text.strip()

    def _parse_list_page(self, html: str, base_url: str, category: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries = []

        tables = soup.find_all("table", class_=re.compile(r"index|list|data"))
        if not tables:
            tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                name_cell = cells[0]
                link = name_cell.find("a", href=True)
                if not link:
                    continue

                name = link.get_text(strip=True)
                href = link["href"]
                full_url = urljoin("https://www.aonprd.com/", href)

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
        await self._rate_limit()
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    main = soup.find("main") or soup.find("div", id="main-content") or soup.body
                    for tag in main(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
                        tag.decompose()

                    text = main.get_text(separator="\n", strip=True)
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    return text.strip()
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
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

        if entry_data.get("level"):
            parts.append(f"**Level:** {entry_data['level']}")

        if entry_data.get("traits"):
            parts.append(f"**Traits:** {entry_data['traits']}")

        if entry_data.get("source"):
            parts.append(f"**Source:** {entry_data['source']}")

        if detail_text:
            clean_text = self._clean_text(detail_text)
            if clean_text:
                parts.append(clean_text)

        return "\n\n".join(parts)

    async def scrape_category(self, category: str, max_pages: Optional[int] = None) -> int:
        url = self.category_urls.get(category)
        if not url:
            print(f"Unknown category: {category}")
            return 0

        print(f"Scraping {category} from {url}")
        html = await self._fetch(url)
        if not html:
            return 0

        entries = self._parse_list_page(html, url, category)
        print(f"Found {len(entries)} entries for {category}")

        imported = 0
        for i, entry in enumerate(entries):
            if max_pages and i >= max_pages:
                break

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
                    system="1e",
                    category=category,
                    name=entry["name"],
                    source_book="Archives of Nethys 1e",
                    raw_content=self._build_content(entry, detail_text or "", category),
                    source_url=entry["url"]
                )

                if self._insert_entry(scraped):
                    self.stats["imported"] += 1
                    self.stats["by_category"][category] = self.stats["by_category"].get(category, 0) + 1
                    imported += 1
                else:
                    self.stats["skipped"] += 1

            except Exception as e:
                print(f"Error processing {entry['name']}: {e}")
                self.stats["errors"] += 1

        return imported

    def _insert_entry(self, entry) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM rules WHERE system = ? AND name = ? AND source_book = ?",
            (entry.system, entry.name, "Archives of Nethys 1e")
        )
        if cursor.fetchone():
            self.stats["skipped"] += 1
            return False

        self.conn.execute(
            """INSERT INTO rules (system, category, name, source_book, raw_content)
               VALUES (?, ?, ?, ?, ?)""",
            (entry.system, entry.category, entry.name, "Archives of Nethys 1e", entry.raw_content)
        )
        self.conn.commit()
        return True

    async def scrape_all(self, max_per_category: Optional[int] = None):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "PathfinderGod/1.0 (Educational/Research)"}
        )

        total_imported = 0
        for category in self.category_urls.keys():
            self.stats["total"] = 0
            self.stats["imported"] = 0
            self.stats["skipped"] = 0
            self.stats["errors"] = 0
            self.stats["by_category"] = {}

            try:
                await self.scrape_category(category, max_pages=max_per_category)
                print(f"\n=== {category} Complete ===")
                print(f"Total: {self.stats['total']}, Imported: {self.stats['imported']}, Skipped: {self.stats['skipped']}, Errors: {self.stats['errors']}")
                total_imported += self.stats["imported"]
            except Exception as e:
                print(f"Error scraping {category}: {e}")
                self.stats["errors"] += 1

        print(f"\n=== AoN 1e Scraping Complete ===")
        print(f"Total Imported: {total_imported}")
        await self.session.close()
        self.conn.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Archives of Nethys 1e")
    parser.add_argument("--db-path", required=True, help="Path to output SQLite database")
    parser.add_argument("--max-per-category", type=int, help="Max entries per category (for testing)")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    scraper = Aon1eScraper(db_path)
    await scraper.scrape_all(max_per_category=args.max_per_category)


if __name__ == "__main__":
    asyncio.run(main())