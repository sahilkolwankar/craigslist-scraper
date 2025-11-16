import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser
import os
import re

CRAIGSLIST_URL = "https://sfbay.craigslist.org/search/sfc/bia?purveyor=owner&sort=date"
KEYWORD = "bike"
LOOKBACK = timedelta(hours=2)


# --- TIME PARSER ------------------------------------------------------------

def parse_relative_time(text: str) -> datetime:
    """
    Craigslist uses phrases like:
    - "21 mins ago"
    - "1h ago"
    - "2h ago"
    - "5h ago"

    Convert those into actual datetimes.
    """
    text = text.strip().lower()

    now = datetime.utcnow()

    # Minutes
    m = re.match(r"(\d+)\s*mins?\s*ago", text)
    if m:
        mins = int(m.group(1))
        return now - timedelta(minutes=mins)

    # Hours: "1h ago", "2h ago"
    m = re.match(r"(\d+)\s*h\s*ago", text)
    if m:
        hrs = int(m.group(1))
        return now - timedelta(hours=hrs)

    # Fallback — assume now
    return now


# --- SCRAPER ----------------------------------------------------------------

def fetch_listings():
    r = requests.get(CRAIGSLIST_URL, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    listings = []

    # Each listing container looks like:
    # <div class="cl-search-result cl-search-view-mode-gallery" data-pid="...">
    for post in soup.select(".cl-search-result"):
        # Title is inside:
        # <a ... class="posting-title"><span class="label">TITLE</span></a>
        title_el = post.select_one(".posting-title .label")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)

        # URL is same link as above
        url_el = post.select_one(".posting-title")
        url = url_el["href"] if url_el and url_el.has_attr("href") else None

        # Time is inside:
        # <div class="meta">56 mins ago<span ...>Neighborhood</span></div>
        meta_el = post.select_one(".meta")
        if not meta_el:
            continue

        # First piece of text before the separator is the relative time
        # ex: "56 mins ago"
        relative_str = meta_el.get_text(" ", strip=True).split(" ")[0:3]
        # Reconstruct phrases like "56 mins ago" or "2h ago"
        relative_str = " ".join(relative_str)

        posted_at = parse_relative_time(relative_str)

        listings.append({
            "title": title,
            "url": url,
            "posted_at": posted_at,
        })

    return listings


# --- REPORT BUILDER ---------------------------------------------------------

def build_report(listings):
    cutoff = datetime.utcnow() - LOOKBACK

    recent = [l for l in listings if l["posted_at"] >= cutoff]
    matches = [l for l in recent if KEYWORD.lower() in l["title"].lower()]

    lines = []
    lines.append(f"Checked at: {datetime.utcnow().isoformat()} UTC")
    lines.append(f"Listings checked in last 2h: {len(recent)}")
    lines.append(f"bike matches: {len(matches)}\n")

    if matches:
        for m in matches:
            lines.append(f"- {m['title']}")
            lines.append(f"  {m['url']}")
            lines.append(f"  Posted: {m['posted_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    else:
        lines.append("No bike listings found.")

    return "\n".join(lines)


# --- SLACK ------------------------------------------------------------------

def send_slack(text):
    webhook = os.environ["SLACK_WEBHOOK"]
    requests.post(webhook, json={"text": text})


# --- MAIN -------------------------------------------------------------------

def main():
    listings = fetch_listings()
    report = build_report(listings)
    send_slack(report)


if __name__ == "__main__":
    main()
