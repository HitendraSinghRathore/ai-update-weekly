#!/usr/bin/env python3
"""
generate_report.py

Fetches the latest entries from a set of AI & Generative-AI RSS feeds
(only posts matching AI/gen-AI keywords), then writes a Jekyll-compatible
Markdown file under _reports/YYYY-MM-DD.md (up to 10 items per feed).
"""

import sys
import time
import datetime
import pathlib

import feedparser
import requests
from requests.exceptions import HTTPError, RequestException

# ------------------------------------------------------------------------------
#  CONFIGURATION
# ------------------------------------------------------------------------------

RSS_FEEDS = {
    "ArXiv cs.AI":                   "https://rss.arxiv.org/rss/cs.AI",
    "ArXiv cs.LG":                   "https://rss.arxiv.org/rss/cs.LG",
    "ArXiv cs.CV":                   "https://rss.arxiv.org/rss/cs.CV",

    "Hacker News: AI":               "https://hnrss.org/newest?q=AI",
    "Hacker News: Generative AI":    "https://hnrss.org/newest?q=Generative+AI",

    "Import AI (Substack)":          "https://importai.substack.com/feed.xml",
    "OpenAI Blog":                   "https://openai.com/blog/rss.xml",
    "DeepMind Blog":                 "https://deepmind.com/blog/feed/basic",
    # Use Google’s main blog RSS & let our filter pick AI posts
    "Google Blog":                   "https://blog.google/rss",
    # Switch Microsoft AI → Microsoft Research Blog
    "Microsoft Research Blog":       "https://www.microsoft.com/en-us/research/feed/",

    "Machine Learning Mastery":      "https://machinelearningmastery.com/blog/feed/",
    "TechCrunch AI":                 "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "VentureBeat AI":                "https://feeds.venturebeat.com/VentureBeat",
    "MIT Technology Review – AI":    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "Synced – AI Technology Review": "https://syncedreview.com/feed/",
    "Last Week in AI":               "https://lastweekin.ai/feed",
    "MarkTechPost":                  "https://www.marktechpost.com/feed",
    "The Gradient":                  "https://thegradient.pub/rss/",
}

# Only keep entries whose title/summary mention one of these:
KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "deep learning", "neural network", "generative",
    "llm", "gpt", "transformer", "diffusion"
]

TIMEOUT     = 20   # seconds per request
MAX_RETRIES = 3    # retry non-404 failures
RETRY_DELAY = 5    # seconds between retries


def matches_keyword(entry):
    text = " ".join([
        entry.get("title", ""),
        entry.get("summary", "")
    ]).lower()
    return any(k in text for k in KEYWORDS)


def fetch_entries(limit=10):
    all_entries = {}
    for name, url in RSS_FEEDS.items():
        matched = []

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(url, timeout=TIMEOUT)

                # skip immediately on forbidden or missing
                if r.status_code in (403, 404):
                    print(f"[!] {r.status_code} for '{name}' ({url})—skipping.", file=sys.stderr)
                    break

                r.raise_for_status()

                # Decode into a Unicode string, replacing bad bytes if needed
                try:
                    text = r.content.decode(r.encoding or 'utf-8')
                except (LookupError, UnicodeDecodeError):
                    text = r.content.decode('utf-8', errors='replace')

                # Parse the feed
                feed = feedparser.parse(text)

                # If it's malformed, log the exception but continue
                if feed.bozo:
                    ex = getattr(feed, "bozo_exception", "Unknown error")
                    print(f"[!] Malformed feed for '{name}': {ex}—attempting to salvage entries.", file=sys.stderr)  # :contentReference[oaicite:0]{index=0}

                # Sort newest first and filter by your keywords
                for e in sorted(
                    feed.entries,
                    key=lambda e: e.get("published_parsed", datetime.datetime.min),
                    reverse=True
                ):
                    if matches_keyword(e):
                        pub = e.get("published") or e.get("updated") or ""
                        matched.append({
                            "title":     e.get("title", "No title"),
                            "link":      e.get("link", "#"),
                            "published": pub
                        })
                        if len(matched) >= limit:
                            break

                # Done with this feed (whether malformed or not)
                break

            except (HTTPError, RequestException) as err:
                print(f"[!] Error fetching '{name}' (attempt {attempt}/{MAX_RETRIES}): {err}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"[!] Giving up on '{name}' after {MAX_RETRIES} attempts.", file=sys.stderr)

        all_entries[name] = matched

    return all_entries



def build_md(entries):
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
        icon = (
            f"https://www.google.com/s2/favicons?"
            f"domain_url={RSS_FEEDS[src]}"
        )
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
