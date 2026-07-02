# SETUP — 새 컴퓨터에서 소셜 리서치 기능 세팅

X(Twitter)·Reddit·StockTwits 통합 소셜 리포트를 다른 컴퓨터에서 쓰기 위한 세팅 가이드.

> ⚠️ **git으로 오는 건 코드뿐입니다.** 실행 도구(twitter-cli·rdt-cli)와 로그인 쿠키는
> **컴퓨터마다 따로** 설치·등록해야 합니다. 쿠키는 보안상 절대 git에 커밋하지 않습니다.

## 0) 사전 요구
- Python 3.10+ , Node.js (선택: mcporter/Exa용)
- Windows는 실행 시 UTF-8 필요: `set PYTHONUTF8=1` (bash: `export PYTHONUTF8=1 PYTHONIOENCODING=utf-8`)

## 1) 저장소 클론
```bash
git clone https://github.com/jungyw89/claudecodejules89.git
cd claudecodejules89
```

## 2) 실행 도구 설치 (pipx)
```bash
python -m pip install --user pipx
python -m pipx install twitter-cli      # X/Twitter — twitter.exe
python -m pipx install rdt-cli          # Reddit — rdt.exe
python -m pipx install agent-reach      # (선택) doctor/configure 편의 도구
```
설치 위치: `~/.local/bin/{twitter,rdt}.exe` (PATH 미등록 시 절대경로로 호출)

## 3) 로그인 쿠키 등록 (컴퓨터마다 1회)

> 브라우저 자동추출은 Chrome/Edge/Brave 127+ **App-Bound 암호화(ABE)** 로 실패함.
> → **Cookie-Editor 확장으로 수동 export** 가 유일한 확실한 방법.

### Reddit
1. 브라우저에서 reddit.com 로그인 → Cookie-Editor → **Export as JSON**
2. `~/.config/rdt-cli/credential.json` 을 아래 형식으로 저장 (최소 `reddit_session` 필요):
```json
{ "cookies": { "reddit_session": "...", "token_v2": "...", "loid": "..." },
  "source": "cookie-editor", "saved_at": null }
```
3. 확인: `rdt status`  →  `authenticated: true`

### X / Twitter
1. x.com 로그인 → Cookie-Editor → Export → `auth_token`, `ct0` 값 확보
2. 환경변수로 주입 (호출마다 필요):
```bash
export TWITTER_AUTH_TOKEN="<auth_token>"
export TWITTER_CT0="<ct0>"
```
   또는 `agent-reach configure twitter-cookies "<auth_token>" "<ct0>"` 로 `~/.agent-reach/config.yaml` 에 저장.

## 4) (선택) Exa 전역검색
```bash
npx -y mcporter   # config/mcporter.json 의 exa 설정 사용
```

## 5) 사용
```bash
# 통합 소셜 리포트 (X + Reddit + StockTwits)
python scripts/social_report.py O "Realty Income" --days 2 --limit 12
```

## 참고: 각 도구 단독 사용
```bash
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
~/.local/bin/rdt.exe search "쿼리" -r stocks -s new -n 5 -c
~/.local/bin/twitter.exe -c search "쿼리" --type latest -n 5
curl -A "Mozilla/5.0" "https://api.stocktwits.com/api/2/streams/symbol/NVDA.json"
```

## 6) OpenCLI 기반 채널 (雪球 · Facebook · Instagram · 小红书)
브라우저 자동화 도구 OpenCLI가 조종하는 **단일 Chrome 프로필**에 각 사이트를 로그인해두면 읽힘.
Cookie-Editor 대신 `opencli <site> login` 을 쓰는 게 정확 (이미 로그인돼 있으면 즉시 반환).
```bash
npm install -g @jackwener/opencli        # 데몬 설치
# Chrome 웹스토어에서 'OpenCLI' 확장 설치 → 데몬이 그 프로필에 연결됨
opencli daemon restart && opencli doctor # 연결 확인 (Extension: connected 떠야 함)

opencli xueqiu login                     # 로그인창 열림 (백그라운드 실행 권장)
opencli xueqiu whoami                    # 로그인 확인
opencli xueqiu stock SH600519            # 실시간 시세
opencli xueqiu hot-stock                 # 열문 종목 랭킹
opencli rednote search "반도체"           # 小红书 검색
opencli facebook search "..." ; opencli instagram whoami
```
> OpenCLI엔 100+ 사이트 어댑터 내장 (bloomberg, sinafinance, weibo, tiktok, binance, coingecko 등).
> `opencli list` 로 전체 확인.

## 7) GitHub 전체기능
```bash
gh auth login          # 본인이 브라우저 인증 (또는 --with-token)
```

## 채널 요약
| 채널 | 방식 | 자격증명 |
|---|---|---|
| 웹·Exa·YouTube·RSS·V2EX·B站 | 기본 도구 | 불필요 |
| X / Reddit | twitter-cli / rdt-cli | Cookie-Editor |
| StockTwits | 공개 JSON API | 불필요 |
| GitHub | gh CLI | `gh auth login` |
| 小宇宙(전사) | Groq Whisper | Groq API 키 |
| 雪球·Facebook·Instagram·小红书 | OpenCLI | Chrome 프로필 로그인 |

---
⚠️ 쿠키·로그인은 계정 권한 전체입니다. 계정 정지 위험이 있으니 **부계정 사용 권장**.
