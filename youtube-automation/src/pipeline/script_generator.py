"""
대본 생성 모듈
--------------
enrich_issue() 로 만들어진 이슈 컨텍스트(제목/요약/출처)를 바탕으로
Claude API를 호출해 쇼츠(~50초) 나레이션 대본을 생성한다.

채널마다 다른 논조(stance_prompt, config/channels/*.yaml)를 적용할 수 있지만,
아래 핵심 원칙(_CORE_SYSTEM_PROMPT)은 어떤 채널이든 예외 없이 강제된다:
사실 날조 금지, 인신공격·명예훼손 금지, 출처 명시. "채널 논조"는 같은 사실을
어떤 관점으로 해석/강조하느냐의 문제이지, 없는 사실을 만들어도 된다는 뜻이
아니다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic

from .config import require_env

_CORE_SYSTEM_PROMPT = """\
당신은 한국 정치 뉴스를 다루는 유튜브 쇼츠 채널의 대본 작가입니다.
아래 원칙은 채널 성향과 무관하게 절대 예외 없이 지켜야 합니다.

1. 제공된 기사 제목/요약에 없는 사실이나 수치를 지어내지 않습니다. 근거 없는
   추측이나 자극적인 허위 주장을 하지 않습니다.
2. 특정 개인을 향한 인신공격·명예훼손성 표현을 쓰지 않습니다. 정책이나
   결정에 대한 비판은 근거를 들어 해도 됩니다.
3. 의견을 말할 땐 "~라는 평가가 나온다"처럼 근거/출처를 붙입니다.
4. 영상 나레이션 대본이므로 문어체가 아닌 짧고 리듬감 있는 구어체 문장을 씁니다.
5. 반드시 아래 JSON 스키마로만 응답하세요. 다른 텍스트를 덧붙이지 마세요.

{
  "title": "유튜브 쇼츠 제목 (25자 이내, 후킹되는 문구)",
  "hook": "영상 시작 3초 안에 시선을 끄는 한 문장",
  "body": "핵심 내용 설명 (여러 문장, 자연스러운 구어체)",
  "cta": "마무리 멘트 (구독/의견 유도, 1문장)",
  "caption_lines": ["자막용으로 나눈 짧은 문장 리스트(각 8~18자 내외)"],
  "sources": ["실제로 참고한 기사 출처명 목록"],
  "disclaimer": "영상 하단에 표기할 출처/고지 문구 1문장"
}
"""

_DEFAULT_BALANCE_PROMPT = """
채널별 논조가 따로 지정되지 않았습니다. 특정 정당이나 정치인을 일방적으로
비난/옹호하지 말고, 쟁점과 팩트 중심으로 균형 있게 서술하세요.
"""


def _build_system_prompt(stance_prompt: str | None) -> str:
    return _CORE_SYSTEM_PROMPT + "\n" + (stance_prompt or _DEFAULT_BALANCE_PROMPT)


@dataclass
class ShortsScript:
    title: str
    hook: str
    body: str
    cta: str
    caption_lines: list[str]
    sources: list[str]
    disclaimer: str

    @property
    def full_narration(self) -> str:
        return " ".join([self.hook, self.body, self.cta]).strip()

    @classmethod
    def from_json(cls, data: dict) -> "ShortsScript":
        return cls(
            title=data["title"],
            hook=data["hook"],
            body=data["body"],
            cta=data["cta"],
            caption_lines=data.get("caption_lines", []),
            sources=data.get("sources", []),
            disclaimer=data.get(
                "disclaimer", "본 영상은 공개된 보도를 바탕으로 재구성한 해설입니다."
            ),
        )


def _build_user_prompt(issue: dict, target_seconds: int, max_words: int) -> str:
    lines = [
        f"이슈 키워드: {issue['keyword']} (최근 24시간 내 언급 {issue['mention_count']}회)",
        f"목표 영상 길이: 약 {target_seconds}초 (한국어 나레이션 기준 최대 {max_words}단어 내외)",
        "",
        "참고 기사 목록:",
    ]
    for art in issue["articles"]:
        excerpt = art.get("excerpt") or art.get("summary") or ""
        lines.append(f"- [{art['source']}] {art['title']} :: {excerpt}")

    if issue.get("related_bills"):
        lines.append("\n관련 국회 의안 정보:")
        for bill in issue["related_bills"]:
            lines.append(f"- {bill.get('bill_name')} ({bill.get('propose_dt')})")

    return "\n".join(lines)


def generate_script(
    issue: dict,
    model: str = "claude-sonnet-5",
    target_seconds: int = 50,
    max_words: int = 160,
    stance_prompt: str | None = None,
) -> ShortsScript:
    client = Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    user_prompt = _build_user_prompt(issue, target_seconds, max_words)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_build_system_prompt(stance_prompt),
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    data = _extract_json(raw_text)
    return ShortsScript.from_json(data)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"모델 응답에서 JSON을 찾을 수 없습니다: {text[:200]}")
    return json.loads(text[start : end + 1])


if __name__ == "__main__":
    from .config import load_config
    from .issue_selector import select_issues
    from .source_fetcher import enrich_issue

    cfg = load_config()
    issues = select_issues(cfg)
    if issues:
        enriched = enrich_issue(issues[0])
        sg_cfg = cfg["script_generation"]
        script = generate_script(
            enriched,
            model=sg_cfg["model"],
            target_seconds=sg_cfg["target_seconds"],
            max_words=sg_cfg["max_words"],
            stance_prompt=sg_cfg.get("stance_prompt"),
        )
        print(script)
