#!/usr/bin/env python3
"""
generate_report.py

Fetches the latest entries from a set of AI & Generative‐AI RSS feeds,
filters by AI/gen-AI keywords, and writes a Jekyll‐compatible Markdown
file under _reports/YYYY-MM-DD.md (up to 10 items per feed).
"""

import sys
import time
import datetime
import pathlib

import feedparser
import requests
from requests.exceptions import HTTPError, RequestException

# ------------------------------------------------------------------------------
#  CONFIGURATION: AI & Generative AI feeds
# ------------------------------------------------------------------------------
RSS_FEEDS = {
    "ArXiv cs.AI":                   "https://rss.arxiv.org/rss/cs.AI",
    "ArXiv cs.LG":                   "https://rss.arxiv.org/rss/cs.LG",
    "ArXiv cs.CV":                   "https://rss.arxiv.org/rss/cs.CV",

    "Hacker News: AI":               "https://hnrss.org/newest?q=AI",
    "Hacker News: Generative AI":    "https://hnrss.org/newest?q=Generative+AI",

    "Import AI (Substack)":          "https://importai.substack.com/feed",
    "OpenAI Blog":                   "https://openai.com/blog/rss.xml",
    "DeepMind Blog":                 "https://deepmind.com/blog/feed/basic",
    "Google AI":                     "https://blog.google/technology/ai/feed",

    "Microsoft AI Blog":             "https://blogs.microsoft.com/ai/feed/",
    "Machine Learning Mastery":      "https://machinelearningmastery.com/blog/feed/",
    "VentureBeat AI":                "https://venturebeat.com/category/ai/feed/",
    "TechCrunch AI":                 "https://techcrunch.com/tag/artificial-intelligence/feed/",

    "MIT Technology Review – AI":    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Synced – AI Technology Review": "https://syncedreview.com/feed/",
    "Last Week in AI":               "https://lastweekin.ai/feed",
    "MarkTechPost":                  "https://www.marktechpost.com/feed",
    "The Gradient":                  "https://thegradient.pub/rss/",
}

# Only posts whose title or summary contain one of these keywords will be kept:
KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "deep learning", "neural network", "generative",
    "llm", "gpt", "transformer", "diffusion"
]

TIMEOUT     = 20    # seconds per request
MAX_RETRIES = 3     # retry non-404 failures
RETRY_DELAY = 5     # seconds between retries


def matches_keyword(entry):
    """Check if entry title or summary contains any KEYWORDS."""
    text = " ".join([
        entry.get("title", ""),
        entry.get("summary", "")
    ]).lower()
    return any(kw in text for kw in KEYWORDS)


def fetch_entries(limit=10):
    """
    Fetch & parse each feed URL with timeout/retries.
    Filter each feed’s entries by KEYWORDS, taking newest-first
    until `limit` items are collected. Return dict: feed name → list.
    """
    all_entries = {}

    for name, url in RSS_FEEDS.items():
        matched = []
        # get all entries sorted by date
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, timeout=TIMEOUT)
                if resp.status_code == 404:
                    print(f"[!] 404 Not Found: {name}", file=sys.stderr)
                    break
                resp.raise_for_status()

                feed = feedparser.parse(resp.content)
                if feed.bozo:
                    print(f"[!] Malformed feed for '{name}'", file=sys.stderr)

                # sort by published date desc
                candidates = sorted(
                    feed.entries,
                    key=lambda e: e.get("published_parsed", datetime.datetime.min),
                    reverse=True
                )
                # keep only those matching keywords, up to limit
                for entry in candidates:
                    if matches_keyword(entry):
                        published = entry.get("published") or entry.get("updated") or ""
                        matched.append({
                            "title":     entry.get("title", "No title"),
                            "link":      entry.get("link", "#"),
                            "published": published
                        })
                        if len(matched) >= limit:
                            break
                break  # success, stop retry loop

            except (HTTPError, RequestException) as err:
                print(f"[!] Error fetching '{name}' (attempt {attempt}): {err}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"[!] Skipping '{name}' after {MAX_RETRIES} attempts", file=sys.stderr)

        all_entries[name] = matched

    return all_entries


def build_md(entries):
    """Build the Markdown with YAML front matter and inline favicons."""
    now   = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    today = datetime.date.today().isoformat()

    lines = [
        "---",
        f"title: AI Weekly Update – {today}",
        f"date:  {now}",
        "layout: report",
        "---", ""
    ]

    for src, items in entries.items():
        # favicon via Google service
        icon = f"https://www.google.com/s2/favicons?domain_url={RSS_FEEDS[src]}"
        lines.append(f"![{src}]({icon})\n")
        lines.append(f"## {src}\n")
        if items:
            for it in items:
                lines.append(f"- [{it['title']}]({it['link']})  ")
                if it["published"]:
                    lines.append(f"  _{it['published']}_")
        else:
            lines.append("- _No AI/generative-AI posts found._")
        lines.append("")

    return "\n".join(lines)


def write_report(md_text):
    """Write Markdown to _reports/YYYY-MM-DD.md (create folder if needed)."""
    date_str   = datetime.date.today().isoformat()
    report_dir = pathlib.Path("_reports")
    report_dir.mkdir(exist_ok=True)
    path = report_dir / f"{date_str}.md"
    path.write_text(md_text, encoding="utf-8")
    return path


if __name__ == "__main__":
    try:
        data = fetch_entries(limit=10)
        md   = build_md(data)
        out  = write_report(md)
        print(f"✅ Generated report: {out}")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
