import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser

CRAIGSLIST_URL = "https://sfbay.craigslist.org/search/sfc/bia?purveyor=owner&sort=date"
KEYWORD = "aventon"
LOOKBACK_HOURS = 2

def fetch_listings():
    r = requests.get(CRAIGSLIST_URL, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    posts = []
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=LOOKBACK_HOURS)

    for post in soup.select(".result-row"):
        title_el = post.select_one(".result-title")
        time_el = post.select_one("time")

        if not title_el or not time_el:
            continue

        title = title_el.text.strip()
        url = title_el["href"]
        post_time = parser.parse(time_el["datetime"])

        if post_time < cutoff:
            continue

        posts.append({
            "title": title,
            "url": url,
            "post_time": post_time
        })

    return posts

def build_report(listings):
    matches = [p for p in listings if KEYWORD.lower() in p["title"].lower()]

    report = []
    report.append(f"Checked at: {datetime.utcnow().isoformat()}")
    report.append(f"Listings in last {LOOKBACK_HOURS}h: {len(listings)}")
    report.append(f"Aventon matches: {len(matches)}\n")

    if matches:
        report.append("🚲 **Aventon Listings Found:**\n")
        for m in matches:
            report.append(f"- *{m['title']}* ({m['post_time']})\n{m['url']}\n")
    else:
        report.append("No Aventon listings found.")

    return "\n".join(report)

def send_slack_message(webhook_url, text):
    requests.post(webhook_url, json={"text": text})

def main():
    webhook = os.environ["SLACK_WEBHOOK"]
    listings = fetch_listings()
    report = build_report(listings)
    send_slack_message(webhook, report)

if __name__ == "__main__":
    import os
    main()
