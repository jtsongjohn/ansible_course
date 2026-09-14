"""
소스 보강 모듈
--------------
issue_selector 가 뽑은 이슈(키워드+관련 기사 제목/요약)에 대해,
- 기사 페이지의 메타 설명(og:description) 정도만 짧게 덧붙이고
- (선택) 국회 열린국회정보 Open API로 관련 의안 정보를 덧붙인다.

절대 기사 본문 전체를 긁어 저장/재배포하지 않는다. LLM 대본 생성에
필요한 최소한의 맥락(제목/짧은 설명)만 모아 script_generator 에 넘긴다.
"""
from __future__ import annotations

import os
from dataclasses import asdict

import requests
from bs4 import BeautifulSoup

from .issue_selector import Issue

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PoliticsShortsBot/0.1)"}
_TIMEOUT = 6


def enrich_article_excerpt(link: str) -> str | None:
    """기사 페이지의 og:description(짧은 요약)만 가져온다. 실패 시 None."""
    try:
        resp = requests.get(link, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("meta", property="og:description") or soup.find(
            "meta", attrs={"name": "description"}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()[:300]
    except Exception as exc:
        print(f"[source_fetcher] 기사 요약 보강 실패 ({link}): {exc}")
    return None


def fetch_related_bills(keyword: str, limit: int = 3) -> list[dict]:
    """국회 열린국회정보 Open API에서 키워드 관련 의안 검색(선택 기능).

    ASSEMBLY_OPEN_API_KEY 가 없으면 빈 리스트를 반환한다.
    참고: https://open.assembly.go.kr (공공데이터, 자유 이용 가능한 공공저작물)
    """
    api_key = os.environ.get("ASSEMBLY_OPEN_API_KEY")
    if not api_key:
        return []

    url = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": limit,
        "BILL_NAME": keyword,
    }
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("nzmimeepazxkubdpn", [{}, {}])[1].get("row", [])
        return [
            {
                "bill_name": row.get("BILL_NAME"),
                "propose_dt": row.get("PROPOSE_DT"),
                "committee": row.get("COMMITTEE"),
                "link": row.get("DETAIL_LINK"),
            }
            for row in rows
        ]
    except Exception as exc:
        print(f"[source_fetcher] 국회 의안 정보 조회 실패: {exc}")
        return []


def enrich_issue(issue: Issue) -> dict:
    """이슈 dict에 og:description 및 관련 의안 정보를 덧붙여 반환."""
    data = issue.to_dict()
    for art in data["articles"]:
        excerpt = enrich_article_excerpt(art["link"])
        if excerpt:
            art["excerpt"] = excerpt
    data["related_bills"] = fetch_related_bills(issue.keyword)
    return data


if __name__ == "__main__":
    from .config import load_config
    from .issue_selector import select_issues

    cfg = load_config()
    for _issue in select_issues(cfg):
        enriched = enrich_issue(_issue)
        print(enriched)
