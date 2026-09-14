"""
이슈 선정 모듈
--------------
설정된 RSS 피드(뉴스/국회방송 등)에서 최근 기사 제목·요약을 수집하고,
빈도 기반으로 "오늘 다룰만한 정치 이슈" 후보를 뽑는다.

주의: 기사 본문 전체를 저장/재배포하지 않는다. 제목과 RSS가 제공하는
요약(summary) 정도만 사용하며, 이는 대본 생성을 위한 '참고 컨텍스트'로만
쓰인다(저작권 리스크를 낮추기 위함). README의 저작권 섹션 참고.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser


@dataclass
class Article:
    title: str
    summary: str
    link: str
    source: str
    published: datetime | None


@dataclass
class Issue:
    keyword: str
    mention_count: int
    articles: list[Article] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "mention_count": self.mention_count,
            "articles": [
                {
                    "title": a.title,
                    "summary": a.summary,
                    "link": a.link,
                    "source": a.source,
                }
                for a in self.articles
            ],
        }


_TOKEN_RE = re.compile(r"[가-힣]{2,}")


def _load_stopwords(path: str) -> set[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def fetch_recent_entries(feeds: list[dict], lookback_hours: int) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    articles: list[Article] = []

    for feed_cfg in feeds:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        try:
            parsed = feedparser.parse(url)
        except Exception as exc:  # 네트워크 오류 등은 개별 피드만 건너뜀
            print(f"[issue_selector] '{name}' 피드 파싱 실패: {exc}")
            continue

        for entry in parsed.entries:
            published = _entry_datetime(entry)
            if published is not None and published < cutoff:
                continue
            articles.append(
                Article(
                    title=getattr(entry, "title", "").strip(),
                    summary=getattr(entry, "summary", "").strip(),
                    link=getattr(entry, "link", ""),
                    source=name,
                    published=published,
                )
            )
    return articles


def _entry_datetime(entry) -> datetime | None:
    for field_name in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, field_name, None)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    return None


def extract_keywords(
    articles: list[Article], stopwords: set[str], top_n: int
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for art in articles:
        text = f"{art.title} {art.summary}"
        tokens = [t for t in _TOKEN_RE.findall(text) if t not in stopwords]
        counter.update(set(tokens))  # 기사당 1회만 카운트(과대표집 방지)
    return counter.most_common(top_n)


def group_issues(
    articles: list[Article],
    keywords: list[tuple[str, int]],
    top_n_issues: int,
    min_mentions: int,
) -> list[Issue]:
    issues: list[Issue] = []
    used_links: set[str] = set()

    for keyword, count in keywords:
        if count < min_mentions:
            continue
        related = [
            a
            for a in articles
            if keyword in f"{a.title} {a.summary}" and a.link not in used_links
        ]
        if not related:
            continue
        for a in related:
            used_links.add(a.link)
        issues.append(Issue(keyword=keyword, mention_count=count, articles=related[:5]))
        if len(issues) >= top_n_issues:
            break

    return issues


def select_issues(cfg: dict) -> list[Issue]:
    ic = cfg["issue_selection"]
    stopwords = _load_stopwords(_resolve(cfg, ic["stopwords_file"]))

    articles = fetch_recent_entries(cfg["rss_feeds"], ic["lookback_hours"])
    if not articles:
        print("[issue_selector] 최근 기사가 없습니다. 피드 URL/네트워크를 확인하세요.")
        return []

    keywords = extract_keywords(articles, stopwords, ic["top_n_keywords"])
    issues = group_issues(articles, keywords, ic["top_n_issues"], ic["min_mentions"])
    return issues


def _resolve(cfg: dict, relative_path: str) -> str:
    from .config import REPO_ROOT

    return str(REPO_ROOT / relative_path)


if __name__ == "__main__":
    from .config import load_config

    _cfg = load_config()
    for issue in select_issues(_cfg):
        print(f"\n=== {issue.keyword} (언급 {issue.mention_count}) ===")
        for art in issue.articles:
            print(f" - [{art.source}] {art.title}")
