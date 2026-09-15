"""
팩트체크 2차 검증 모듈
----------------------
script_generator가 만든 대본이 제공된 기사(참고 컨텍스트)로 실제로
뒷받침되는지 별도 Claude 호출로 재검증한다.

이건 사람의 최종 검수를 대체하지 않는다 — 명백히 근거 없는 문장이나
인신공격성 표현을 자동으로 걸러내, 사람이 검수할 때 어디를 더 유심히
봐야 하는지 표시해주는 보조 장치다. (README "업로드 전 체크리스트" 참고)
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic

from .config import require_env
from .script_generator import ShortsScript

_FACT_CHECK_SYSTEM_PROMPT = """\
당신은 냉정한 팩트체커입니다. 아래 "참고 기사"만을 근거로, 주어진 "대본"의
각 사실 주장이 실제로 뒷받침되는지 검증하세요.

- 참고 기사에 없는 사실·수치·인용이 대본에 있다면 flagged_claims에 적으세요.
- 특정 개인에 대한 인신공격·명예훼손 소지가 있는 표현도 flagged_claims에
  적으세요.
- 사소한 논조·강조 차이(어떤 관점을 강조하는지)는 문제 삼지 마세요 —
  이는 편집상의 관점 차이이지 사실 왜곡이 아닙니다.

반드시 아래 JSON으로만 응답하세요. 다른 텍스트를 덧붙이지 마세요.

{
  "passed": true 또는 false,
  "flagged_claims": ["문제될 수 있는 문장과 그 이유"],
  "notes": "종합 코멘트 1~2문장"
}
"""


@dataclass
class FactCheckResult:
    passed: bool
    flagged_claims: list[str]
    notes: str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "flagged_claims": self.flagged_claims,
            "notes": self.notes,
        }

    @classmethod
    def from_json(cls, data: dict) -> "FactCheckResult":
        return cls(
            passed=bool(data.get("passed", False)),
            flagged_claims=data.get("flagged_claims", []),
            notes=data.get("notes", ""),
        )


def _build_user_prompt(script: ShortsScript, issue: dict) -> str:
    lines = ["참고 기사:"]
    for art in issue["articles"]:
        excerpt = art.get("excerpt") or art.get("summary") or ""
        lines.append(f"- [{art['source']}] {art['title']} :: {excerpt}")

    lines += [
        "",
        "대본:",
        f"제목: {script.title}",
        f"훅: {script.hook}",
        f"본문: {script.body}",
        f"마무리: {script.cta}",
    ]
    return "\n".join(lines)


def verify_script(
    script: ShortsScript, issue: dict, model: str = "claude-sonnet-5"
) -> FactCheckResult:
    client = Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=_FACT_CHECK_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(script, issue)}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    data = _extract_json(raw_text)
    return FactCheckResult.from_json(data)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"모델 응답에서 JSON을 찾을 수 없습니다: {text[:200]}")
    return json.loads(text[start : end + 1])
