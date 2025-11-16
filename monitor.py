import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser
import os
import re

CRAIGSLIST_URL = "https://sfbay.craigslist.org/search/sfc/bia?purveyor=owner&sort=date"
KEYWORD = "aventon"  # change to whatever you want
LOOKBACK = timedelta(hours=2)


# ------------------------------
# Time parsing
# ------------------------------

def parse_relative_time(text: str) -> datetime:
    """
    Handles:
        '21 mins ago'
        '56 mins ago'
        '1h ago'
        '2h ago'
        '11/14'
        '11/14 potrero'
        '11/14 Outer Richmond, SF'
        '11/15 oakland'
    """

    text = text.strip().lower()
    now = datetime.utcnow()

    # --- Case 1: X mins ago ---
    m = re.match(r"(\d+)\s*mins?\s*ago", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    # --- Case 2: Xh ago ---
    m = re.match(r"(\d+)\s*h\s*ago", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    # --- Case 3: MM/DD or MM/DD <location> ---
    m = re.match(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = now.year
        try:
            return datetime(year, month, day)
        except ValueError:
            return now

    # Fallback
    return now


# ------------------------------
# Scraper
# ------------------------------

def fetch_listings():
    r = requests.get(CRAIGSLIST_URL, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    listings = []

    # Universal selector for each posting block
    posts = soup.select(".cl-search-result")
    for post in posts:

        # ---- Title ----
        # Safest selector based on your HTML: <span class="label">TITLE</span>
        title_el = post.select_one("span.label")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        # ---- URL ----
        # Use the parent anchor of the label
        link_el = title_el.find_parent("a")
        url = link_el["href"] if link_el and link_el.has_attr("href") else None

        # ---- Time ----
        meta_el = post.select_one(".meta")
        if not meta_el:
            continue

        # Example meta: "21 mins ago", "11/14", "56 mins ago glen park"
        relative_str = meta_el.get_text(" ", strip=True).split(" ")[0]
        posted_at = parse_relative_time(relative_str)

        # ---- Price ----
        price_el = post.select_one(".priceinfo")
        price = price_el.get_text(strip=True) if price_el else None

        # ---- Location (optional) ----
        # After the first separator, location text lives in the same .meta
        location = None
        parts = meta_el.get_text(" ", strip=True).split(" ")
        if len(parts) > 1:
            location = " ".join(parts[1:])

        listings.append({
            "title": title,
            "url": url,
            "posted_at": posted_at,
            "price": price,
            "location": location,
        })

    return listings


# ------------------------------
# Report
# ------------------------------

def build_report(listings):
    now = datetime.utcnow()
    cutoff = now - LOOKBACK

    total = len(listings)
    recent = [l for l in listings if l["posted_at"] >= cutoff]
    matches = [l for l in recent if KEYWORD.lower() in l["title"].lower()]

    lines = []
    lines.append(f"Checked at: {now.isoformat()} UTC")
    lines.append(f"Total listings scraped: {total}")
    lines.append(f"Listings in last 2h: {len(recent)}")
    lines.append(f"Matches for '{KEYWORD}': {len(matches)}\n")

    if not matches:
        lines.append("No matches found.")
        return "\n".join(lines)

    for m in matches:
        lines.append(f"• {m['title']}")
        if m["price"]:
            lines.append(f"  Price: {m['price']}")
        if m["location"]:
            lines.append(f"  Location: {m['location']}")
        lines.append(f"  Posted: {m['posted_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"  {m['url']}\n")

    return "\n".join(lines)


# ------------------------------
# Slack notification
# ------------------------------

def send_slack(text: str):
    webhook = os.environ["SLACK_WEBHOOK"]
    requests.post(webhook, json={"text": text})


# ------------------------------
# Main
# ------------------------------

def main():
    try:
        listings = fetch_listings()
        report = build_report(listings)
        send_slack(report)
    except Exception as e:
        send_slack(f"❌ Scraper crashed:\n{str(e)}")
        raise


if __name__ == "__main__":
    main()
