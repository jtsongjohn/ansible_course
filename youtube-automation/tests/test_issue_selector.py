"""issue_selector 의 순수 로직(네트워크/API 키 불필요)에 대한 테스트."""
from datetime import datetime, timezone

from src.pipeline.issue_selector import (
    Article,
    extract_keywords,
    group_issues,
)


def _article(title: str, summary: str = "", link: str = "", source: str = "테스트") -> Article:
    return Article(
        title=title,
        summary=summary,
        link=link or title,
        source=source,
        published=datetime.now(timezone.utc),
    )


def test_extract_keywords_counts_each_article_once():
    articles = [
        _article("국회 예산안 처리 지연", "국회 파행 계속"),
        _article("예산안 두고 여야 충돌", "국회 예산안 갈등"),
        _article("예산안 예산안 예산안", "같은 기사 반복 단어"),
    ]
    keywords = dict(extract_keywords(articles, stopwords=set(), top_n=10))

    # "예산안"은 3개 기사 모두에 등장하지만, 세번째 기사는 같은 단어 반복이므로
    # 기사당 1회만 카운트되어 총 3이어야 한다(4가 아님).
    assert keywords["예산안"] == 3


def test_extract_keywords_respects_stopwords():
    articles = [_article("국회 기자 브리핑", "기자 질의응답")]
    keywords = dict(extract_keywords(articles, stopwords={"기자"}, top_n=10))
    assert "기자" not in keywords


def test_extract_keywords_boosts_watch_keywords_ranking():
    articles = [
        _article("특검법 통과", "특검법 관련 내용"),          # mention=1
        _article("예산안 협상", "예산안 협상 계속"),            # mention=1
        _article("예산안 재논의", "여야 예산안 재논의"),        # mention=1
        _article("예산안 최종 타결", "예산안 최종 타결 발표"),  # mention=1
    ]
    # 가중치 없이는 "예산안"(3회)이 "특검법"(1회)보다 우선이어야 한다.
    plain = [kw for kw, _ in extract_keywords(articles, set(), top_n=5)]
    assert plain.index("예산안") < plain.index("특검법")

    # watch_keywords 로 "특검법"에 큰 가중치를 주면 순위가 역전되어야 한다.
    boosted = [
        kw
        for kw, _ in extract_keywords(
            articles, set(), top_n=5, watch_keywords=["특검법"], watch_keyword_boost=10
        )
    ]
    assert boosted.index("특검법") < boosted.index("예산안")


def test_group_issues_filters_min_mentions_and_dedupes_links():
    articles = [
        _article("탄핵소추안 발의", "탄핵 관련 기사1", link="a1"),
        _article("탄핵 정국 계속", "탄핵 관련 기사2", link="a2"),
        _article("단독 보도 이슈", "언급 1회뿐", link="a3"),
    ]
    keywords = [("탄핵", 2), ("단독", 1)]

    issues = group_issues(articles, keywords, top_n_issues=5, min_mentions=2)

    assert len(issues) == 1
    assert issues[0].keyword == "탄핵"
    assert {a.link for a in issues[0].articles} == {"a1", "a2"}


def test_group_issues_respects_top_n_issues():
    articles = [
        _article("키워드A 기사1", link="a1"),
        _article("키워드A 기사2", link="a2"),
        _article("키워드B 기사1", link="b1"),
        _article("키워드B 기사2", link="b2"),
    ]
    keywords = [("키워드A", 2), ("키워드B", 2)]

    issues = group_issues(articles, keywords, top_n_issues=1, min_mentions=1)
    assert len(issues) == 1
