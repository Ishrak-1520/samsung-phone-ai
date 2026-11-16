import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY_SECONDS = 5
# Caches HTML locally to avoid hitting GSMArena rate limits
CACHE_DIR = Path(__file__).parent / "html_cache"
CACHE_DIR.mkdir(exist_ok=True)

PHONES = {
    "Samsung Galaxy S21": "https://www.gsmarena.com/samsung_galaxy_s21_5g-10626.php",
    "Samsung Galaxy S22": "https://www.gsmarena.com/samsung_galaxy_s22_5g-11253.php",
    "Samsung Galaxy S22 Ultra": "https://www.gsmarena.com/samsung_galaxy_s22_ultra_5g-11251.php",
    "Samsung Galaxy S23": "https://www.gsmarena.com/samsung_galaxy_s23-12082.php",
    "Samsung Galaxy S23+": "https://www.gsmarena.com/samsung_galaxy_s23+-12083.php",
    "Samsung Galaxy S23 Ultra": "https://www.gsmarena.com/samsung_galaxy_s23_ultra-12024.php",
    "Samsung Galaxy S24": "https://www.gsmarena.com/samsung_galaxy_s24-12773.php",
    "Samsung Galaxy S24 Ultra": "https://www.gsmarena.com/samsung_galaxy_s24_ultra-12771.php",
    "Samsung Galaxy A54": "https://www.gsmarena.com/samsung_galaxy_a54-12070.php",
    "Samsung Galaxy A34": "https://www.gsmarena.com/samsung_galaxy_a34-12074.php",
    "Samsung Galaxy Z Flip5": "https://www.gsmarena.com/samsung_galaxy_z_flip5-12252.php",
    "Samsung Galaxy Z Fold5": "https://www.gsmarena.com/samsung_galaxy_z_fold5-12418.php",
}


def name_to_filename(phone_name: str) -> str:
    cleaned = phone_name.replace("+", " Plus")
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_").lower()
    return f"{safe}.html"


def normalize_category(category_name: str) -> str:
    cat = category_name.strip()
    special_cases = {
        "selfie camera": "Selfie Camera",
        "main camera": "Main Camera",
        "our tests": "Our Tests",
    }
    return special_cases.get(cat.lower(), cat.title())


def clean_cell_text(cell) -> str:
    if not cell:
        return ""
    cell_copy = BeautifulSoup(str(cell), "html.parser")
    for tag in cell_copy.find_all(["br", "p", "li"]):
        tag.replace_with("\n")

    raw_text = cell_copy.get_text()
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.split("\n")]
    lines = [line for line in lines if line]
    return " | ".join(lines)


def get_html(phone_name: str, url: str) -> str:
    cache_file = CACHE_DIR / name_to_filename(phone_name)

    if cache_file.exists():
        print(f"Reading '{phone_name}' from {cache_file.name}")
        return cache_file.read_text(encoding="utf-8")

    print(f"Waiting {REQUEST_DELAY_SECONDS}s before requesting '{phone_name}'...")
    time.sleep(REQUEST_DELAY_SECONDS)

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"Could not reach {url}: {e}")
        print(f"Please save '{cache_file.name}' into scraper/html_cache/ manually.")
        raise SystemExit(1)

    if response.status_code == 429:
        print("GSMArena returned HTTP 429 (rate limited)")
        print(f"Save page manually to scraper/html_cache/{cache_file.name}")
        raise SystemExit(1)

    response.raise_for_status()
    response.encoding = "utf-8"
    html_text = response.text

    soup = BeautifulSoup(html_text, "html.parser")
    page_title = soup.title.string.strip() if soup.title else ""
    core_parts = [p.lower() for p in phone_name.split() if p.lower() not in ["samsung", "galaxy"]]
    if not any(part in page_title.lower() for part in core_parts):
        print(f"Title mismatch for '{phone_name}': '{page_title}'")
    else:
        print(f"Verified title: '{page_title}'")

    cache_file.write_text(html_text, encoding="utf-8")
    print(f"Saved HTML to {cache_file.name}")
    return html_text


def parse_specs(html: str, phone_name: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    specs = {}

    specs_div = soup.find("div", id="specs-list")
    if not specs_div:
        print(f"No specs-list found for '{phone_name}'")
        return specs

    for table in specs_div.find_all("table"):
        th = table.find("th")
        if not th:
            continue

        raw_category = th.get_text(strip=True)
        category = normalize_category(raw_category)
        if category not in specs:
            specs[category] = {}

        last_key = None
        for tr in table.find_all("tr"):
            ttl = tr.find("td", class_="ttl")
            nfo = tr.find("td", class_="nfo")
            if not nfo:
                continue

            val = clean_cell_text(nfo)
            if not val:
                continue

            raw_key = clean_cell_text(ttl) if ttl else ""
            raw_key = raw_key.replace("\xa0", "").strip()

            if not raw_key:
                if last_key and last_key in specs[category]:
                    specs[category][last_key] += f" | {val}"
                else:
                    specs[category]["Details"] = val
                    last_key = "Details"
            else:
                specs[category][raw_key] = val
                last_key = raw_key

    price_cell = soup.find("td", {"data-spec": "price"})
    if price_cell:
        price_val = clean_cell_text(price_cell)
        if price_val:
            specs.setdefault("Price", {})["Official Price"] = price_val

    if "Price" not in specs:
        pricing_div = soup.find("div", class_="pricing")
        if pricing_div:
            price_val = clean_cell_text(pricing_div)
            if price_val:
                specs.setdefault("Price", {})["Official Price"] = price_val

    return specs


def scrape_all():
    all_phone_data = {}
    for name, url in PHONES.items():
        print(f"Processing: {name}")
        html = get_html(name, url)
        specs = parse_specs(html, name)
        all_phone_data[name] = {
            "url": url,
            "specs": specs,
        }
        total_keys = sum(len(v) for v in specs.values())
        print(f"Parsed {total_keys} entries across {len(specs)} categories for '{name}'")
    return all_phone_data


if __name__ == "__main__":
    scrape_all()
