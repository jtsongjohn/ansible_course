"""fact_checker.py 의 파싱/프롬프트 조립 로직 테스트 (실제 API 호출 없이,
verify_script 내부에서 쓰는 Anthropic 클라이언트를 모킹한다)."""
from unittest.mock import MagicMock, patch

from src.pipeline.fact_checker import FactCheckResult, _build_user_prompt, verify_script
from src.pipeline.script_generator import ShortsScript


def _sample_script() -> ShortsScript:
    return ShortsScript(
        title="테스트 제목",
        hook="테스트 훅입니다",
        body="테스트 본문입니다",
        cta="구독해주세요",
        caption_lines=["테스트", "자막"],
        sources=["연합뉴스"],
        disclaimer="테스트 고지",
    )


def _sample_issue() -> dict:
    return {
        "keyword": "테스트 이슈",
        "mention_count": 2,
        "articles": [
            {"title": "기사 제목1", "summary": "요약1", "source": "연합뉴스", "link": "a1"},
        ],
    }


def test_fact_check_result_from_json_defaults():
    result = FactCheckResult.from_json({})
    assert result.passed is False
    assert result.flagged_claims == []
    assert result.notes == ""


def test_fact_check_result_round_trip_to_dict():
    result = FactCheckResult(passed=True, flagged_claims=["a"], notes="ok")
    assert result.to_dict() == {"passed": True, "flagged_claims": ["a"], "notes": "ok"}


def test_build_user_prompt_includes_script_and_sources():
    prompt = _build_user_prompt(_sample_script(), _sample_issue())
    assert "테스트 제목" in prompt
    assert "테스트 훅입니다" in prompt
    assert "테스트 본문입니다" in prompt
    assert "[연합뉴스] 기사 제목1" in prompt


@patch("src.pipeline.fact_checker.Anthropic")
@patch("src.pipeline.fact_checker.require_env", return_value="fake-key")
def test_verify_script_parses_mocked_response(mock_require_env, mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = '{"passed": false, "flagged_claims": ["근거 없는 수치"], "notes": "확인 필요"}'
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    result = verify_script(_sample_script(), _sample_issue(), model="claude-sonnet-5")

    assert result.passed is False
    assert result.flagged_claims == ["근거 없는 수치"]
    assert result.notes == "확인 필요"
    mock_client.messages.create.assert_called_once()
