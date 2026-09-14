# 유튜브 정치 콘텐츠 자동화 파이프라인

뉴스/국회 관련 정치 이슈를 자동으로 찾아 **쇼츠(Shorts) 영상 초안**을 만들어주는
파이프라인입니다. 업로드는 의도적으로 자동화하지 않았습니다 — 정치 콘텐츠는
사실관계·편향성·저작권 리스크가 크기 때문에, 사람이 마지막에 반드시 검수하고
직접 업로드하는 것을 전제로 설계했습니다.

```
이슈 선정 → 소스 보강 → 대본 생성(Claude) → 나레이션(TTS) → 자막 → 영상 합성
   (자동)      (자동)         (자동)            (자동)        (자동)     (자동)   →  [사람이 검수] → 수동 업로드
```

---

## 0. 먼저 읽어주세요 — 저작권/법적 리스크

처음 질문에서 "**뉴스/국회영상 원본 클립을 그대로 재업로드**"하고 싶다고
하셨는데, 이 방식은 **강하게 비권장**합니다. 이유:

- **뉴스 영상/기사**: 방송사·언론사가 저작권을 가지며, 원본을 그대로 잘라
  올리는 것은 대부분 공정이용(fair use) 범위를 벗어나 **저작권 침해**입니다.
  유튜브 Content ID에 걸려 수익 미귀속·영상 차단은 물론, 반복되면
  **채널 자체가 해지(저작권 삼진 아웃)**될 수 있습니다. 국내법상으로도
  저작권법 위반(민·형사 책임) 소지가 있습니다.
- **국회 본회의/상임위 영상**: 국회사무처가 제공하는 영상은 상당 부분
  "공공저작물"로 자유이용이 허용되는 경우가 많지만(출처표시 조건 등),
  **국회방송(NATV) 자체 제작 리포트·인터뷰 편집본**은 별도 저작권이
  있을 수 있어 확인이 필요합니다. 국회 의안정보시스템/회의록 "텍스트"는
  대부분 자유이용 가능합니다.
- **채널 생존 관점**: 정치 채널은 신고가 몰리기 쉬운 카테고리입니다.
  저작권 스트라이크 3회면 채널이 삭제되므로, 초기 성장 단계에서
  리스크를 최소화하는 것이 장기적으로 유리합니다.

**그래서 이 파이프라인은 기본값을 다음과 같이 설계했습니다.**

- `config/config.yaml`의 `content_mode.reupload_raw_clips: false` (기본값)
- 원본 영상/이미지를 가져오지 않고, **자체 배경(그라디언트) + AI 나레이션
  음성 + 자막**으로 영상을 새로 "제작"합니다. (마치 뉴스 요약/해설
  채널처럼 — 이 형식은 팩트 기반 해설·비평이라는 점에서 저작권상
  훨씬 안전합니다.)
- 기사 본문 전체를 긁어오지 않고, RSS 제목/요약(og:description) 정도의
  **짧은 발췌**만 대본 작성 참고용으로 사용합니다.
- 국회 의안정보(Open API)는 공공데이터이므로 비교적 자유롭게 활용합니다.

`reupload_raw_clips: true`로 바꿔도 `video_assembler.py`는 원본 클립을
삽입하는 기능 자체가 구현되어 있지 않습니다. 정말 원본 클립을 쓰고
싶다면, 방송사/국회사무처에 **별도 이용허락을 받는 것**을 권장하며,
그 경우에도 반드시 변호사 등 전문가 검토를 받으세요. (이 도구는 법률
자문이 아닙니다.)

---

## 1. 유튜브 채널 개설 절차

1. **구글 계정 준비**: 채널 전용으로 새 구글 계정을 만드는 것을 권장합니다
   (개인 계정과 분리 → 브랜드/수익 관리 용이).
2. **유튜브 채널 생성**: YouTube 접속 → 우측 상단 프로필 → "채널 만들기" →
   "브랜드 계정으로 만들기" 선택(공동 운영자 추가 가능, 개인정보 분리).
3. **채널 설정**:
   - 카테고리: "뉴스/정치" 또는 "뉴스 및 정치"
   - 채널 아트/프로필 이미지 업로드
   - 채널 설명에 "본 채널은 공개된 보도를 바탕으로 한 요약·해설
     콘텐츠입니다" 같은 고지 문구 추가 권장
4. **정치 콘텐츠 관련 유튜브 정책 숙지** (필수):
   - [스팸, 기만 행위 및 사기 정책](https://support.google.com/youtube/answer/2801973)
   - [잘못된 정보(선거 관련 등) 정책](https://support.google.com/youtube/answer/10835034)
   - "재사용된 콘텐츠(Reused content)" 정책 — 타인 영상을 별다른 부가가치
     없이 재업로드하면 수익 창출 제한/채널 경고 대상이 될 수 있습니다.
   - 선거철에는 "공인" 관련 콘텐츠에 추가 라벨/규정이 붙을 수 있으니
     선거 국면에는 별도로 최신 정책을 재확인하세요.
5. **YPP(파트너 프로그램) 요건 확인**: 구독자 500명 + 최근 90일 내
   업로드 3개 이상(2024년 개편 기준 Shorts 조건 포함) 또는 구독자
   1,000명 + 시청시간 4,000시간(또는 쇼츠 조회수 1,000만) 등 — 정확한
   최신 기준은 유튜브 고객센터에서 재확인하세요(정책이 자주 바뀝니다).
6. **Shorts 업로드 규격**: 세로 9:16, 최대 3분(채널 정책에 따라 변동),
   `#Shorts` 해시태그 포함 권장. 이 파이프라인은 기본 1080x1920 해상도로
   출력합니다.

---

## 2. 파이프라인 구조

```
youtube-automation/
├── config/
│   ├── config.yaml         # 소스, 이슈 선정 기준, 톤, 영상 스타일 설정
│   └── stopwords_ko.txt    # 키워드 추출용 불용어
├── src/pipeline/
│   ├── issue_selector.py   # RSS에서 최근 정치 뉴스 수집 → 키워드 빈도 기반 이슈 후보 선정
│   ├── source_fetcher.py   # 이슈별 기사 요약 보강 + (선택) 국회 의안정보 Open API 연동
│   ├── script_generator.py # Claude API로 쇼츠 대본(JSON) 생성 — 출처 인용 강제
│   ├── narration.py        # edge-tts로 음성 합성 + 단어별 타임스탬프 추출
│   ├── captions.py         # 타임스탬프 기반 자막 큐/SRT 생성
│   ├── video_assembler.py  # 그라디언트 배경 + 자막 + 음성 합성 → mp4
│   └── main.py             # 전체 파이프라인 오케스트레이션 (진입점)
├── scripts/run_pipeline.sh # 실행 스크립트 (cron/systemd 겸용)
├── ansible/                # 서버 배포용 플레이북/role
└── output/                 # 결과물 (script.json, captions.srt, short.mp4)
```

### 왜 이 구성인가

- **이슈 선정을 자동화하되, 사람의 정치 감각은 대본 생성 프롬프트/설정
  튜닝으로 반영**합니다. 예를 들어 특정 상임위·특정 키워드에 가중치를
  주고 싶다면 `config.yaml`의 `rss_feeds`나 `issue_selection`을
  조정하세요. 사용자님이 이미 이슈를 항상 트래킹하신다니, 향후
  "관심 키워드 화이트리스트" 기능을 추가하면 직접 쓰시는 감각을
  자동 선정에 결합할 수 있습니다(3번 확장 아이디어 참고).
- **소스와 최종 렌더링을 분리**: `content_mode` 설정 하나로 나중에
  전략을 바꿀 수 있게 설계했습니다.
- **업로드는 의도적으로 제외**: 정치 콘텐츠는 사실 오류·편향 논란이
  나오면 채널 신뢰도에 타격이 크므로, 사람이 마지막 관문 역할을
  하도록 했습니다.

---

## 3. 로컬에서 실행하기

```bash
cd youtube-automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 ANTHROPIC_API_KEY 입력 (https://console.anthropic.com/)

# 시스템 패키지 필요: ffmpeg, imagemagick, 한글 폰트(nanum 등)
#   Ubuntu/Debian: sudo apt install ffmpeg imagemagick fonts-nanum
#   macOS:         brew install ffmpeg imagemagick && brew install --cask font-nanum-gothic

python -m src.pipeline.main
```

결과물은 `output/YYYYMMDD/<이슈-슬러그>/` 아래에 생성됩니다:
- `script.json` — 생성된 대본 전문 + 참고한 기사 출처
- `narration.mp3` — TTS 음성
- `captions.srt` — 자막 파일
- `short.mp4` — 최종 쇼츠 영상

> ImageMagick이 "not authorized" 오류를 낸다면 `/etc/ImageMagick-6/policy.xml`
> 에서 `pattern="@*"` 정책을 `read|write`로 완화해야 합니다. Ansible로
> 배포하면 이 설정이 자동 적용됩니다.

---

## 4. 서버에 자동 배포하기 (Ansible)

이 저장소가 원래 Ansible 강의 자료이니, 배운 내용을 그대로 활용해 매일
정해진 시각에 자동 실행되도록 배포할 수 있습니다.

```bash
cd youtube-automation/ansible
cp inventory.ini.example inventory.ini      # 서버 SSH 정보 입력
cp secrets.yml.example secrets.yml
# secrets.yml 에 anthropic_api_key 입력

ansible-galaxy collection install -r requirements.yml
ansible-vault encrypt secrets.yml           # (권장) 비밀값 암호화

ansible-playbook -i inventory.ini deploy.yml --ask-vault-pass
```

배포되는 것:
- Python venv + 의존성 설치
- ffmpeg / ImageMagick / 한글 폰트 설치, ImageMagick 정책 자동 완화
- `/etc/systemd/system/youtube-pipeline.service` (1회 실행 유닛)
- `/etc/systemd/system/youtube-pipeline.timer` (매일 `tts_hour:tts_minute`에 자동 실행,
  `deploy.yml`의 vars에서 조정)
- 전용 시스템 사용자(`ytauto`)로 격리 실행

서버에 접속해 수동으로 한 번 실행/확인하려면:
```bash
sudo systemctl start youtube-pipeline.service
sudo journalctl -u youtube-pipeline.service -f
ls /opt/youtube-automation/output/
```
생성된 `output/` 결과물을 로컬로 내려받아(`scp`/`rsync`) 검수 후 직접
유튜브 스튜디오에 업로드하세요.

---

## 5. 다음 단계로 확장하고 싶다면

- **관심 키워드 가중치**: `issue_selector.py`에 화이트리스트 키워드
  가중치를 추가해, 사용자님이 평소 트래킹하는 이슈가 우선 선정되도록
  튜닝할 수 있습니다.
- **팩트체크 2차 검증**: 대본 생성 후 별도 LLM 호출로 "이 문장이
  기사 출처로 뒷받침되는가"를 재검증하는 단계를 추가하면 편향/오류
  리스크를 더 낮출 수 있습니다.
- **업로드 자동화**: YouTube Data API v3 (`videos.insert`)로 업로드까지
  자동화할 수 있지만, 정치 콘텐츠 특성상 **"검수 후 승인" 단계는 남겨둘
  것을 권장**합니다(예: 생성된 영상을 슬랙/이메일로 알림 → 승인 버튼
  누르면 업로드).
- **B-roll 라이선스 확보**: 그라디언트 배경 대신 직접 촬영하거나
  라이선스가 명확한 스톡 영상을 쓰면 시청 지속률을 높일 수 있습니다.
- **다국어/썸네일 자동 생성**도 파이프라인에 단계 추가가 용이한 구조입니다.

---

## 6. 업로드 전 체크리스트 (사람이 직접 확인)

- [ ] 대본의 사실관계가 실제 기사 내용과 일치하는가
- [ ] 특정 정당/정치인에 대한 일방적 편향 표현이 없는가
- [ ] 출처(`script.json`의 `sources`)가 영상 설명란에 명시되었는가
- [ ] 저작권 문제될 이미지/영상/음악이 섞이지 않았는가
- [ ] 제목/썸네일이 낚시성·허위 정보가 아닌가
