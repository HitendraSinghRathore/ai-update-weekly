#!/usr/bin/env python3
"""
generate_report.py

Fetches the latest entries from a set of RSS/Atom feeds and
generates a Markdown report with Jekyll front matter.

Usage:
    python3 generate_report.py
"""

import datetime
import pathlib
import sys
import time

import feedparser
import requests
from requests.exceptions import RequestException, HTTPError

# 1. List your feeds here (easy updates!)
FEEDS = {
    "ArXiv cs.AI":             "https://rss.arxiv.org/rss/cs.AI",
    "ArXiv cs.LG":             "https://rss.arxiv.org/rss/cs.LG",
    "ArXiv cs.CV":             "https://rss.arxiv.org/rss/cs.CV",
    "Hacker News":             "https://hnrss.org/newest",
    "Twitter (AI search)":     "https://rsshub.app/twitter/search/AI",
    "Twitter @OpenAI":         "https://rsshub.app/twitter/user/OpenAI",
    # Replace YOUR_GUILD_ID and YOUR_CHANNEL_ID with real IDs:
    "Discord #ai-discussion":  "https://rsshub.app/discord/channel/974519864045756446/998381918976479273",
    "Discord #use-cases": "https://rsshub.app/discord/channel/974519864045756446/1155775326253756456",
    "Discord #api-projects": "https://rsshub.app/discord/channel/974519864045756446/1037561385070112779"
    "Import AI":               "https://importai.substack.com/feed",
    "The Batch":               "https://www.deeplearning.ai/the-batch/rss/",
}


# Configuration for HTTP requests
timeout_seconds = 10
max_retries = 3
retry_delay = 5  # seconds between retries


def fetch_entries(limit=5):
    """
    Fetch and parse each feed with retries on failure (except 404),
    sort by date, and return a dict mapping feed name to list of entries.
    """
    all_entries = {}

    for name, url in FEEDS.items():
        entries = []
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=timeout_seconds)
                # 404 means the feed doesn't exist; stop retrying
                if response.status_code == 404:
                    print(f"[!] 404 Not Found for '{name}' ({url})", file=sys.stderr)
                    break
                response.raise_for_status()

                feed = feedparser.parse(response.content)
                if feed.bozo:
                    print(f"[!] Warning: malformed feed '{name}' ({url})", file=sys.stderr)

                # Sort entries by published date if available
                sorted_entries = sorted(
                    feed.entries,
                    key=lambda e: e.get("published_parsed", datetime.datetime.min),
                    reverse=True
                )[:limit]

                # Format entries
                for e in sorted_entries:
                    published = e.get("published") or e.get("updated") or ""
                    entries.append({
                        "title": e.get("title", "No title"),
                        "link": e.get("link", "#"),
                        "published": published
                    })

                # Successful fetch, stop retry loop
                break

            except HTTPError as he:
                # Retry on HTTP errors except 404
                print(f"[!] HTTP error on '{name}', attempt {attempt}/{max_retries}: {he}", file=sys.stderr)
            except RequestException as re:
                print(f"[!] Request error on '{name}', attempt {attempt}/{max_retries}: {re}", file=sys.stderr)
            # Delay before next attempt (unless it was the last)
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                print(f"[!] Failed to fetch '{name}' after {max_retries} attempts, skipping.", file=sys.stderr)

        all_entries[name] = entries

    return all_entries


def build_md(entries):
    """
    Build the Markdown report text (with YAML front matter).
    """
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    today = datetime.date.today().isoformat()

    lines = [
        "---",
        f"title: AI Weekly Update – {today}",
        f"date: {now}",
        "layout: report",
        "---",
        ""
    ]

    for source, items in entries.items():
        lines.append(f"## {source}\n")
        if items:
            for it in items:
                lines.append(f"- [{it['title']}]({it['link']})  ")
                if it["published"]:
                    lines.append(f"  _{it['published']}_")
        else:
            lines.append("- _No updates found. Please check the feed URL or retry._")
        lines.append("")

    return "\n".join(lines)


def write_report(md_text):
    """
    Write the Markdown to _reports/<YYYY-MM-DD>.md, creating the directory if needed.
    """
    today = datetime.date.today().isoformat()
    report_dir = pathlib.Path("_reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{today}.md"
    report_path.write_text(md_text, encoding="utf-8")
    return report_path


if __name__ == "__main__":
    try:
        entries = fetch_entries(limit=5)
        md = build_md(entries)
        path = write_report(md)
        print(f"✅ Generated report: {path}")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)