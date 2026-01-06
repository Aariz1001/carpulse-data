#!/usr/bin/env python3
"""
DTC Code Web Scraper

Scrapes DTC (Diagnostic Trouble Code) codes from manufacturer-specific websites.
Extracts codes matching patterns like P0xxx, P1xxx, B1xxx, C1xxx, U0xxx, etc.

Usage:
    python scrape_dtc.py --url "https://example.com/fault-codes" --manufacturer honda
    python scrape_dtc.py --url "https://example.com/codes" --manufacturer toyota --output custom_output.csv
    python scrape_dtc.py --list-sources                    # Show known sources
    python scrape_dtc.py --manufacturer honda              # Use known source for manufacturer

The output CSV can then be processed by fill_dtc_gaps.py to enrich the data.

Environment Variables:
    None required (no AI needed for scraping)
"""

import os
import sys
import re
import csv
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import time

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: BeautifulSoup not installed. Run: pip install beautifulsoup4")
    sys.exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
SCRAPED_DIR = OUTPUT_DIR / "scraped"

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
SCRAPED_DIR.mkdir(exist_ok=True)

# Known DTC sources for various manufacturers
KNOWN_SOURCES = {
    "honda": [
        "https://hondacodes.wordpress.com/honda-fault-codes/",
    ],
    "toyota": [
        # Add Toyota sources as discovered
    ],
    "ford": [
        # Add Ford sources as discovered
    ],
    "bmw": [
        # Add BMW sources as discovered
    ],
    "mercedes-benz": [
        # Add Mercedes sources as discovered
    ],
    "volkswagen": [
        # Add VW sources as discovered
    ],
    "audi": [
        # Add Audi sources as discovered
    ],
    "nissan": [
        # Add Nissan sources as discovered
    ],
}

# DTC Code Pattern
# Matches: P0xxx, P1xxx, P2xxx, P3xxx, B0xxx-B3xxx, C0xxx-C3xxx, U0xxx-U3xxx
# Where x can be 0-9 or A-F (hex)
DTC_PATTERN = re.compile(
    r'\b([PBCU][0-3][0-9A-Fa-f]{3})\b'
)

# Extended pattern for codes that might have additional characters (e.g., P0420A)
DTC_EXTENDED_PATTERN = re.compile(
    r'\b([PBCU][0-3][0-9A-Fa-f]{3}[A-Za-z]?)\b'
)

# Legacy Honda numeric codes (1-99)
LEGACY_NUMERIC_PATTERN = re.compile(
    r'^(\d{1,2})\s+([A-Z][A-Za-z0-9\s\-\(\)]+)'
)


@dataclass
class DTCCode:
    """Represents a scraped DTC code."""
    code: str
    description: str
    source_url: str
    manufacturer: str
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "description": self.description,
            "source_url": self.source_url,
            "manufacturer": self.manufacturer,
            "scraped_at": self.scraped_at
        }


class DTCScraper:
    """Scrapes DTC codes from web pages."""
    
    def __init__(self, manufacturer: str, user_agent: str = None):
        self.manufacturer = manufacturer.lower()
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.scraped_codes: Set[str] = set()
        self.results: List[DTCCode] = []
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a web page with error handling."""
        try:
            print(f"  Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            return None
    
    def extract_text_content(self, html: str) -> str:
        """Extract readable text content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Get text content
        text = soup.get_text(separator='\n')
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)
    
    def parse_dtc_codes_from_text(self, text: str, source_url: str) -> List[DTCCode]:
        """
        Parse DTC codes and descriptions from text content.
        
        Handles various formats:
        1. "P0010 Description here" - code followed by description
        2. "P0010 - Description here" - code with dash separator
        3. "P0010: Description here" - code with colon separator
        """
        codes = []
        lines = text.split('\n')
        
        # Pattern to match DTC code at start of line/segment followed by description
        # This handles cases like "P0010 Variable Valve Timing Control..."
        code_desc_pattern = re.compile(
            r'([PBCU][0-3][0-9A-Fa-f]{3}[A-Za-z]?)\s*[-–:.]?\s*(.+?)(?=[PBCU][0-3][0-9A-Fa-f]{3}|$)',
            re.DOTALL
        )
        
        # Join all text for continuous parsing (handles codes that span "lines" in the HTML)
        full_text = ' '.join(lines)
        
        # Find all matches
        matches = code_desc_pattern.findall(full_text)
        
        for code, description in matches:
            code = code.upper()
            description = self._clean_description(description)
            
            if code not in self.scraped_codes and description and len(description) > 5:
                self.scraped_codes.add(code)
                codes.append(DTCCode(
                    code=code,
                    description=description,
                    source_url=source_url,
                    manufacturer=self.manufacturer
                ))
        
        return codes
    
    def parse_dtc_from_structured_html(self, html: str, source_url: str) -> List[DTCCode]:
        """
        Parse DTC codes from structured HTML (tables, lists, etc.)
        """
        codes = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try parsing tables
        for table in soup.find_all('table'):
            codes.extend(self._parse_table(table, source_url))
        
        # Try parsing definition lists
        for dl in soup.find_all('dl'):
            codes.extend(self._parse_definition_list(dl, source_url))
        
        # Try parsing unordered/ordered lists
        for ul in soup.find_all(['ul', 'ol']):
            codes.extend(self._parse_list(ul, source_url))
        
        return codes
    
    def _parse_table(self, table, source_url: str) -> List[DTCCode]:
        """Parse DTC codes from an HTML table."""
        codes = []
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                
                # Check if first cell contains a DTC code
                for i, text in enumerate(cell_texts):
                    match = DTC_EXTENDED_PATTERN.match(text)
                    if match:
                        code = match.group(1).upper()
                        # Description is likely in the next cell
                        if i + 1 < len(cell_texts):
                            description = self._clean_description(cell_texts[i + 1])
                            if code not in self.scraped_codes and description:
                                self.scraped_codes.add(code)
                                codes.append(DTCCode(
                                    code=code,
                                    description=description,
                                    source_url=source_url,
                                    manufacturer=self.manufacturer
                                ))
                        break
        
        return codes
    
    def _parse_definition_list(self, dl, source_url: str) -> List[DTCCode]:
        """Parse DTC codes from definition list (dt/dd)."""
        codes = []
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        
        for dt, dd in zip(dts, dds):
            dt_text = dt.get_text(strip=True)
            match = DTC_EXTENDED_PATTERN.match(dt_text)
            if match:
                code = match.group(1).upper()
                description = self._clean_description(dd.get_text(strip=True))
                if code not in self.scraped_codes and description:
                    self.scraped_codes.add(code)
                    codes.append(DTCCode(
                        code=code,
                        description=description,
                        source_url=source_url,
                        manufacturer=self.manufacturer
                    ))
        
        return codes
    
    def _parse_list(self, ul, source_url: str) -> List[DTCCode]:
        """Parse DTC codes from ul/ol lists."""
        codes = []
        
        for li in ul.find_all('li'):
            text = li.get_text(strip=True)
            match = DTC_EXTENDED_PATTERN.match(text)
            if match:
                code = match.group(1).upper()
                # Description follows the code
                description = text[match.end():].strip()
                description = self._clean_description(description)
                if code not in self.scraped_codes and description:
                    self.scraped_codes.add(code)
                    codes.append(DTCCode(
                        code=code,
                        description=description,
                        source_url=source_url,
                        manufacturer=self.manufacturer
                    ))
        
        return codes
    
    def _clean_description(self, description: str) -> str:
        """Clean up a description string."""
        # Remove leading separators
        description = re.sub(r'^[-–:.]\s*', '', description)
        
        # Remove extra whitespace
        description = ' '.join(description.split())
        
        # Remove trailing incomplete sentences/fragments
        description = description.strip()
        
        # Limit length (some descriptions run into the next code)
        if len(description) > 300:
            # Try to cut at a sentence boundary
            sentences = re.split(r'(?<=[.!?])\s+', description[:350])
            if len(sentences) > 1:
                description = ' '.join(sentences[:-1])
            else:
                description = description[:300] + '...'
        
        return description
    
    def scrape_url(self, url: str) -> List[DTCCode]:
        """Scrape DTC codes from a single URL."""
        html = self.fetch_page(url)
        if not html:
            return []
        
        codes = []
        
        # Try structured parsing first (tables, lists)
        structured_codes = self.parse_dtc_from_structured_html(html, url)
        codes.extend(structured_codes)
        
        # Then try text-based parsing for any codes not in structured elements
        text_content = self.extract_text_content(html)
        text_codes = self.parse_dtc_codes_from_text(text_content, url)
        codes.extend(text_codes)
        
        return codes
    
    def scrape_urls(self, urls: List[str], follow_links: bool = False) -> List[DTCCode]:
        """Scrape DTC codes from multiple URLs."""
        all_codes = []
        visited = set()
        
        for url in urls:
            if url in visited:
                continue
            visited.add(url)
            
            codes = self.scrape_url(url)
            all_codes.extend(codes)
            print(f"  Found {len(codes)} codes from {url}")
            
            # Optional: follow links on the page to find more codes
            if follow_links:
                html = self.fetch_page(url)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        # Only follow links that might contain codes
                        if any(term in href.lower() for term in ['code', 'dtc', 'fault', 'error', 'diagnostic']):
                            full_url = urljoin(url, href)
                            if full_url not in visited and urlparse(full_url).netloc == urlparse(url).netloc:
                                visited.add(full_url)
                                time.sleep(1)  # Be polite
                                sub_codes = self.scrape_url(full_url)
                                all_codes.extend(sub_codes)
                                print(f"  Found {len(sub_codes)} codes from {full_url}")
        
        self.results = all_codes
        return all_codes
    
    def save_to_csv(self, output_path: Path = None) -> Path:
        """Save scraped codes to CSV file."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = SCRAPED_DIR / f"scraped_{self.manufacturer}_dtc_{timestamp}.csv"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['code', 'description', 'source_url', 'manufacturer', 'scraped_at'])
            writer.writeheader()
            for code in self.results:
                writer.writerow(code.to_dict())
        
        print(f"\nSaved {len(self.results)} codes to: {output_path}")
        return output_path
    
    def get_statistics(self) -> Dict:
        """Get statistics about scraped codes."""
        stats = {
            "total_codes": len(self.results),
            "by_category": {},
            "manufacturer": self.manufacturer
        }
        
        for code in self.results:
            prefix = code.code[:2]
            stats["by_category"][prefix] = stats["by_category"].get(prefix, 0) + 1
        
        return stats


def prepare_for_gap_filler(scraped_csv: Path, output_csv: Path = None) -> Path:
    """
    Transform scraped CSV into format expected by fill_dtc_gaps.py
    
    The fill_dtc_gaps.py expects columns:
    code,make_id,description,detailed_description,system,severity,common_causes,symptoms,applicable_models,applicable_years,powertrain_type
    """
    import pandas as pd
    
    if output_csv is None:
        output_csv = scraped_csv.parent / f"{scraped_csv.stem}_prepared.csv"
    
    # Read scraped data
    df = pd.read_csv(scraped_csv)
    
    # Transform to gap filler format
    prepared = pd.DataFrame({
        'code': df['code'],
        'make_id': df['manufacturer'],
        'description': df['description'],
        'detailed_description': '',  # To be filled by AI
        'system': '',  # To be filled by AI
        'severity': '',  # To be filled by AI
        'common_causes': '[]',
        'symptoms': '[]',
        'applicable_models': 'All',
        'applicable_years': 'All',
        'powertrain_type': 'All'
    })
    
    prepared.to_csv(output_csv, index=False)
    print(f"Prepared {len(prepared)} codes for gap filler: {output_csv}")
    return output_csv


def main():
    parser = argparse.ArgumentParser(
        description="Scrape DTC codes from manufacturer websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_dtc.py --url "https://hondacodes.wordpress.com/honda-fault-codes/" --manufacturer honda
  python scrape_dtc.py --manufacturer honda                    # Use known sources
  python scrape_dtc.py --manufacturer honda --follow-links     # Follow links on pages
  python scrape_dtc.py --list-sources                          # Show known sources

Output:
  Saves to: output/scraped/scraped_<manufacturer>_dtc_<timestamp>.csv
  
Workflow:
  1. scrape_dtc.py extracts raw codes from websites
  2. fill_dtc_gaps.py enriches with AI (detailed descriptions, systems, etc.)
  3. merge_to_json.py combines into app's data files
        """
    )
    
    parser.add_argument('--url', '-u', type=str, help='URL to scrape')
    parser.add_argument('--urls', '-U', type=str, nargs='+', help='Multiple URLs to scrape')
    parser.add_argument('--manufacturer', '-m', type=str, help='Manufacturer name (e.g., honda, toyota)')
    parser.add_argument('--output', '-o', type=str, help='Output CSV file path')
    parser.add_argument('--follow-links', '-f', action='store_true', help='Follow links on scraped pages')
    parser.add_argument('--list-sources', '-l', action='store_true', help='List known DTC sources')
    parser.add_argument('--prepare', '-p', action='store_true', help='Also prepare CSV for fill_dtc_gaps.py')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # List known sources
    if args.list_sources:
        print("\nKnown DTC Sources:")
        print("=" * 50)
        for make, urls in KNOWN_SOURCES.items():
            if urls:
                print(f"\n{make.title()}:")
                for url in urls:
                    print(f"  - {url}")
        print("\nContribute more sources by adding URLs to KNOWN_SOURCES in scrape_dtc.py")
        return
    
    # Validate arguments
    if not args.manufacturer:
        parser.error("--manufacturer is required")
    
    urls = []
    
    # Get URLs from arguments or known sources
    if args.url:
        urls.append(args.url)
    if args.urls:
        urls.extend(args.urls)
    
    if not urls:
        # Try known sources
        known = KNOWN_SOURCES.get(args.manufacturer.lower(), [])
        if known:
            urls = known
            print(f"Using {len(urls)} known source(s) for {args.manufacturer}")
        else:
            parser.error(f"No URL provided and no known sources for {args.manufacturer}")
    
    print(f"\n{'='*60}")
    print(f"DTC Code Scraper")
    print(f"{'='*60}")
    print(f"Manufacturer: {args.manufacturer}")
    print(f"URLs to scrape: {len(urls)}")
    print(f"Follow links: {args.follow_links}")
    print(f"{'='*60}\n")
    
    # Create scraper and run
    scraper = DTCScraper(manufacturer=args.manufacturer)
    codes = scraper.scrape_urls(urls, follow_links=args.follow_links)
    
    # Print statistics
    stats = scraper.get_statistics()
    print(f"\n{'='*60}")
    print(f"Scraping Complete!")
    print(f"{'='*60}")
    print(f"Total codes found: {stats['total_codes']}")
    print(f"\nBy category:")
    for cat, count in sorted(stats['by_category'].items()):
        print(f"  {cat}xxx: {count} codes")
    
    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = None
    
    saved_path = scraper.save_to_csv(output_path)
    
    # Optionally prepare for gap filler
    if args.prepare:
        prepare_for_gap_filler(saved_path)
    
    print(f"\nNext steps:")
    print(f"  1. Review the scraped CSV: {saved_path}")
    print(f"  2. Run fill_dtc_gaps.py to enrich with AI:")
    print(f"     python fill_dtc_gaps.py --input {saved_path}")
    print(f"  3. Run merge_to_json.py to update app data")


if __name__ == "__main__":
    main()
