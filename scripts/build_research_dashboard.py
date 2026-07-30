#!/usr/bin/env python3
"""Build automated research dashboard data for the workbench."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_OUTS = [
    ROOT / "data" / "research-dashboard.json",
    ROOT / "personal-workbench-site" / "data" / "research-dashboard.json",
]
READING_OUTS = [
    ROOT / "reading-list.html",
    ROOT / "personal-workbench-site" / "reading-list.html",
]
WEEKLY_OUTS = [
    ROOT / "weekly-research-report.md",
    ROOT / "personal-workbench-site" / "weekly-research-report.md",
]


KEYWORDS = [
    "雷暴大风",
    "海上大风",
    "台风",
    "强对流",
    "双偏振雷达",
    "AI天气预报",
    "极端降水",
    "暴雨",
    "卫星",
    "数值预报",
]

GITHUB_QUERIES = [
    ("weather", "GitHub"),
    ("meteorology", "GitHub"),
    ("climate xarray", "GitHub"),
    ("radar weather", "GitHub"),
    ("satellite meteorology", "GitHub"),
    ("nowcasting", "GitHub"),
    ("wrf python", "GitHub"),
    ("typhoon", "GitHub"),
]

OPENALEX_TERMS = [
    ("severe convective storm", "强对流"),
    ("tropical cyclone", "台风"),
    ("dual polarization radar", "双偏振雷达"),
    ("extreme precipitation", "极端降水"),
    ("AI weather forecasting", "AI天气预报"),
    ("marine wind", "海上大风"),
]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "personal-weather-workbench/1.0",
            "Accept": "application/vnd.github+json, application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def github_trending() -> list[dict]:
    repos: dict[str, dict] = {}
    for query, source in GITHUB_QUERIES:
        url = (
            "https://api.github.com/search/repositories?"
            + urllib.parse.urlencode(
                {
                    "q": f"{query} pushed:>2025-01-01",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": "6",
                }
            )
        )
        try:
            payload = fetch_json(url)
        except Exception:
            continue
        for repo in payload.get("items", []):
            name = repo.get("full_name", "")
            if not name or name in repos:
                continue
            repos[name] = {
                "name": name,
                "description": clean(repo.get("description") or "暂无说明"),
                "url": repo.get("html_url"),
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language") or "未知",
                "updatedAt": repo.get("pushed_at") or repo.get("updated_at"),
                "source": source,
                "query": query,
            }
    return sorted(repos.values(), key=lambda item: item["stars"], reverse=True)[:20]


def openalex_recent() -> list[dict]:
    today = dt.date.today()
    start = today - dt.timedelta(days=30)
    works: dict[str, dict] = {}
    for term, topic in OPENALEX_TERMS:
        url = (
            "https://api.openalex.org/works?"
            + urllib.parse.urlencode(
                {
                    "search": term,
                    "filter": f"from_publication_date:{start.isoformat()},to_publication_date:{today.isoformat()}",
                    "sort": "publication_date:desc",
                    "per-page": "8",
                }
            )
        )
        try:
            payload = fetch_json(url)
        except Exception:
            continue
        for work in payload.get("results", []):
            title = clean(work.get("title") or "")
            link = work.get("doi") or (work.get("primary_location") or {}).get("landing_page_url") or work.get("id")
            if not title or not link:
                continue
            key = title.lower()
            if key in works:
                continue
            source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name") or "OpenAlex"
            works[key] = {
                "title": title,
                "topic": topic,
                "journal": source,
                "date": work.get("publication_date") or str(work.get("publication_year") or ""),
                "url": link,
            }
    return sorted(works.values(), key=lambda item: item.get("date") or "", reverse=True)[:30]


def load_chinese_papers() -> list[dict]:
    path = ROOT / "data" / "chinese-weather-papers.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload.get("papers", [])


def classify_item(text: str) -> list[str]:
    text_l = text.lower()
    hit = []
    patterns = {
        "雷暴大风": ["雷暴大风", "thunderstorm wind", "downburst"],
        "海上大风": ["海上大风", "marine wind", "sea wind", "offshore wind"],
        "台风": ["台风", "tropical cyclone", "typhoon", "hurricane"],
        "强对流": ["强对流", "severe convective", "convection", "convective storm"],
        "双偏振雷达": ["双偏振", "dual polarization", "polarimetric radar"],
        "AI天气预报": ["ai", "machine learning", "deep learning", "graphcast", "weather forecasting"],
        "极端降水": ["极端降水", "extreme precipitation", "torrential rain"],
        "暴雨": ["暴雨", "heavy rainfall", "rainstorm"],
        "卫星": ["卫星", "satellite"],
        "数值预报": ["数值预报", "numerical weather", "wrf", "ecmwf"],
    }
    for label, needles in patterns.items():
        if any(needle.lower() in text_l for needle in needles):
            hit.append(label)
    return hit


def keyword_monitor(chinese: list[dict], international: list[dict], repos: list[dict]) -> list[dict]:
    rows = []
    for paper in chinese:
        text = f"{paper.get('title', '')} {paper.get('journal', '')} {paper.get('note', '')}"
        hits = classify_item(text)
        if hits:
            rows.append(
                {
                    "keywords": hits,
                    "title": paper.get("title"),
                    "source": paper.get("journal"),
                    "type": "中文论文",
                    "url": paper.get("url"),
                }
            )
    for paper in international:
        text = f"{paper.get('title', '')} {paper.get('topic', '')} {paper.get('journal', '')}"
        hits = classify_item(text)
        if hits:
            rows.append(
                {
                    "keywords": hits,
                    "title": paper.get("title"),
                    "source": paper.get("journal"),
                    "type": "国际论文",
                    "url": paper.get("url"),
                }
            )
    for repo in repos:
        text = f"{repo.get('name', '')} {repo.get('description', '')} {repo.get('query', '')}"
        hits = classify_item(text)
        if hits:
            rows.append(
                {
                    "keywords": hits,
                    "title": repo.get("name"),
                    "source": "GitHub",
                    "type": "开源项目",
                    "url": repo.get("url"),
                }
            )
    return rows[:40]


def build_reading_list(chinese: list[dict], international: list[dict], repos: list[dict]) -> list[dict]:
    items = []
    for paper in chinese[:8]:
        items.append(
            {
                "title": paper.get("title"),
                "source": paper.get("journal"),
                "type": "中文论文",
                "url": paper.get("url"),
                "reason": "中文气象期刊最新目录",
            }
        )
    for paper in international[:6]:
        items.append(
            {
                "title": paper.get("title"),
                "source": paper.get("journal"),
                "type": "国际论文",
                "url": paper.get("url"),
                "reason": f"OpenAlex 近 30 天：{paper.get('topic')}",
            }
        )
    for repo in repos[:6]:
        items.append(
            {
                "title": repo.get("name"),
                "source": f"GitHub · {repo.get('stars')} stars",
                "type": "开源项目",
                "url": repo.get("url"),
                "reason": repo.get("description"),
            }
        )
    return items[:20]


def write_reading_html(payload: dict) -> None:
    items = payload["readingList"]
    body = "\n".join(
        f'<li><a href="{html.escape(item["url"] or "")}">{html.escape(item["title"] or "")}</a>'
        f'<span>{html.escape(item["type"])} · {html.escape(item["source"] or "")}</span>'
        f'<p>{html.escape(item["reason"] or "")}</p></li>'
        for item in items
    )
    doc = f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>科研阅读清单</title>
<style>
body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#172033;}}
main{{max-width:900px;margin:0 auto;padding:24px;}}
h1{{font-size:28px;margin:0 0 8px;}}
.meta{{color:#667085;margin-bottom:20px;}}
ol{{display:grid;gap:12px;padding-left:22px;}}
li{{background:#fff;border:1px solid #d8dee7;border-radius:8px;padding:12px 14px;}}
a{{font-weight:600;color:#1f6feb;text-decoration:none;}}
span{{display:block;color:#667085;font-size:14px;margin-top:4px;}}
p{{margin:8px 0 0;}}
</style>
<main>
<h1>科研阅读清单</h1>
<div class="meta">更新时间：{html.escape(payload["updatedAt"])}</div>
<ol>{body}</ol>
</main>
</html>
"""
    for path in READING_OUTS:
        path.write_text(doc, encoding="utf-8")


def write_weekly_report(payload: dict) -> None:
    lines = [
        "# 每周科研周报",
        "",
        f"更新时间：{payload['updatedAt']}",
        "",
        "## 值得精读",
    ]
    for item in payload["readingList"][:10]:
        lines.append(f"- [{item['title']}]({item['url']}) · {item['type']} · {item['source']}")
    lines.extend(["", "## 关键词命中"])
    for row in payload["keywordHits"][:20]:
        lines.append(f"- {', '.join(row['keywords'])}：[{row['title']}]({row['url']}) · {row['type']} · {row['source']}")
    lines.extend(["", "## GitHub 气象工具"])
    for repo in payload["githubTrending"][:10]:
        lines.append(f"- [{repo['name']}]({repo['url']}) · {repo['stars']} stars · {repo['language']} · {repo['description']}")
    doc = "\n".join(lines) + "\n"
    for path in WEEKLY_OUTS:
        path.write_text(doc, encoding="utf-8")


def main() -> int:
    updated = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    chinese = load_chinese_papers()
    repos = github_trending()
    international = openalex_recent()
    payload = {
        "updatedAt": updated,
        "keywords": KEYWORDS,
        "githubTrending": repos,
        "internationalPapers": international,
        "keywordHits": keyword_monitor(chinese, international, repos),
        "readingList": build_reading_list(chinese, international, repos),
    }
    for path in DATA_OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_reading_html(payload)
    write_weekly_report(payload)
    print(f"Dashboard: {len(repos)} repos, {len(international)} papers, {len(payload['keywordHits'])} hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
