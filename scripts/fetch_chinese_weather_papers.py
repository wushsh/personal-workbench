#!/usr/bin/env python3
"""Fetch recent Chinese meteorology journal papers for the workbench.

This script intentionally uses only the Python standard library so it can run
in GitHub Actions without dependency installation. It scrapes public journal
pages, extracts article links, and writes a small JSON file consumed by
personal-workbench.html.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTS = [
    ROOT / "personal-workbench-site" / "data" / "chinese-weather-papers.json",
    ROOT / "data" / "chinese-weather-papers.json",
]


SOURCES = [
    {
        "name": "应用气象学报",
        "topic": "中文期刊",
        "url": "https://qikan.camscma.cn/ch/index.aspx",
        "base": "https://qikan.camscma.cn/ch/",
    },
    {
        "name": "气象",
        "topic": "中文期刊",
        "url": "http://qxqk.nmc.cn/qx/ch/index.aspx",
        "base": "http://qxqk.nmc.cn/qx/ch/",
    },
    {
        "name": "气象学报",
        "topic": "中文期刊",
        "url": "http://qxxb.ijournals.cn/qxxb_cn/ch/index.aspx",
        "base": "http://qxxb.ijournals.cn/qxxb_cn/ch/",
    },
    {
        "name": "大气科学",
        "topic": "中文期刊",
        "url": "https://www.iapjournals.ac.cn/dqkx/",
        "base": "https://www.iapjournals.ac.cn/dqkx/",
    },
    {
        "name": "气候与环境研究",
        "topic": "中文期刊",
        "url": "https://www.iapjournals.ac.cn/qhhj/",
        "base": "https://www.iapjournals.ac.cn/qhhj/",
    },
    {
        "name": "高原气象",
        "topic": "中文期刊",
        "url": "http://www.gyqx.ac.cn/",
        "base": "http://www.gyqx.ac.cn/",
    },
    {
        "name": "热带气象学报",
        "topic": "中文期刊",
        "url": "https://rdqxxb.itmm.org.cn/",
        "base": "https://rdqxxb.itmm.org.cn/",
    },
    {
        "name": "暴雨灾害",
        "topic": "中文期刊",
        "url": "http://byzh.org.cn/",
        "base": "http://byzh.org.cn/",
    },
    {
        "name": "气象科技",
        "topic": "中文期刊",
        "url": "http://www.qxkj.net.cn/",
        "base": "http://www.qxkj.net.cn/",
    },
    {
        "name": "中国农业气象",
        "topic": "中文期刊",
        "url": "https://zgnyqx.ieda.org.cn/",
        "base": "https://zgnyqx.ieda.org.cn/",
    },
]


ARTICLE_HINTS = (
    "reader/view_abstract",
    "article/doi",
    "article/id",
    "article/abstract",
    "cn/article",
)

BAD_TITLE_PARTS = (
    "首页",
    "下载",
    "投稿",
    "征稿",
    "编委会",
    "期刊介绍",
    "联系我们",
    "过刊浏览",
    "在线办公",
    "更多",
    "English",
)


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {k.lower(): v for k, v in attrs if v}
        self._href = attrs_dict.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            title = clean_text("".join(self._text))
            self.anchors.append((self._href, title))
            self._href = None
            self._text = []


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -_|\t\r\n")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/126 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        content_type = resp.headers.get("content-type", "")
    encoding = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if match:
        encoding = match.group(1)
    for enc in (encoding, "utf-8", "gb18030"):
        try:
            return raw.decode(enc, errors="replace")
        except LookupError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_article_url(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in ARTICLE_HINTS)


def title_ok(title: str) -> bool:
    if len(title) < 8:
        return False
    if any(part.lower() in title.lower() for part in BAD_TITLE_PARTS):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", title))


def scrape_source(source: dict[str, str]) -> list[dict[str, str]]:
    text = fetch_text(source["url"])
    parser = AnchorParser()
    parser.feed(text)
    papers: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for href, title in parser.anchors:
        if not href:
            continue
        full_url = urllib.parse.urljoin(source["base"], href)
        if not is_article_url(full_url) or not title_ok(title):
            continue
        normalized_url = full_url.split("#", 1)[0]
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        papers.append(
            {
                "topic": source["topic"],
                "title": title[:120],
                "journal": source["name"],
                "year": "最新目录",
                "note": f"由 GitHub Actions 从《{source['name']}》官网最新页面采集。",
                "url": normalized_url,
            }
        )
        if len(papers) >= 5:
            break

    return papers


def main() -> int:
    all_papers: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    statuses: list[dict[str, str | int | bool]] = []
    seen_titles: set[str] = set()

    for source in SOURCES:
        try:
            papers = scrape_source(source)
            statuses.append(
                {
                    "source": source["name"],
                    "ok": bool(papers),
                    "count": len(papers),
                    "url": source["url"],
                    "message": "成功" if papers else "未采集到论文",
                }
            )
            for paper in papers:
                key = clean_text(paper["title"]).lower()
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                all_papers.append(paper)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            message = str(exc)[:180]
            errors.append({"source": source["name"], "error": message})
            statuses.append(
                {
                    "source": source["name"],
                    "ok": False,
                    "count": 0,
                    "url": source["url"],
                    "message": message,
                }
            )
        time.sleep(0.4)

    payload = {
        "updatedAt": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "GitHub Actions: public Chinese meteorology journal pages",
        "count": len(all_papers),
        "papers": all_papers[:40],
        "statuses": statuses,
        "errors": errors,
    }

    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out} with {len(all_papers[:40])} papers")
    if errors:
        print(json.dumps(errors, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0 if all_papers else 1


if __name__ == "__main__":
    raise SystemExit(main())
