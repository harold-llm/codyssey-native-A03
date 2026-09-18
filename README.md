# 팔아줘, 한 줄 (Sell-in-One)

물건 정보 6가지만 고르면 AI가 중고거래 판매글(제목 3안 · 상세 설명 · 금액 코멘트 · 태그)을 만들어 주는 웹서비스입니다.

## 기술 스택

| 레이어 | 사용 기술 |
| --- | --- |
| 프론트엔드 | HTML / CSS / JavaScript (프레임워크 없음) |
| 백엔드 | Vercel Python Serverless Functions |
| AI | OpenAI `gpt-4o-mini` (JSON 모드) |
| 배포 | Vercel |
| (보너스) 문의 자동화 | n8n Webhook → Google Sheets |

## 폴더 구조

```txt
sell-in-one/
├── index.html          # 페이지 (Hero / 작성 팁 / 생성기 / 문의)
├── css/style.css       # 스타일 (다크 모드 · 반응형 포함)
├── js/main.js          # 폼 검증 · API 호출 · 복사 · 토스트 · 테마
├── api/
│   ├── generate.py     # 판매글 생성 API (OpenAI 호출)
│   └── feedback.py     # 문의 접수 API (Webhook 전달, 미설치 시 로그)
├── images/             # 제출 스크린샷 등 이미지
├── requirements.txt    # requests==2.32.3
├── vercel.json         # 함수 maxDuration 60초 (AI 호출 ~20초 대응)
└── .gitignore          # .env 등 민감 파일 제외
```

## 로컬 실행

```bash
# 1) 환경 변수 (파일은 git에 올라가지 않습니다)
cat > .env <<'EOF'
OPENAI_API_KEY=sk-본인키
OPENAI_BASE_URL=https://copa.codyssey.kr/v1
OPENAI_MODEL=gpt-5-mini
FEEDBACK_WEBHOOK_URL=
EOF

# 2) 실행 (Node 18+ 필요)
vercel dev
# → http://localhost:3000
```

단독 테스트

```bash
curl -s -X POST http://localhost:3000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"category":"digital","itemName":"무선 이어폰 3세대","usedPeriod":"1년","condition":"양호","price":"45000","trade":["직거래"],"tone":"차분하게"}'
```

## 배포 방법 (Vercel)

1. Vercel → **Add New Project** → 이 저장소 Import (Framework Preset: **Other**)
2. **Settings → Environment Variables** 등록 (Production + Preview)
3. **Deploy**
4. 환경 변수를 수정했다면 **Redeploy** (변수는 재배포 시에만 주입됩니다)

## 배포 URL

- Production: `https://codyssey-native-a03.vercel.app`

## 환경 변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `OPENAI_API_KEY` | O | OpenAI API 키 (코드/문서에 실제값을 노출하지 않습니다) |
| `OPENAI_BASE_URL` | X | OpenAI 호환 API의 base URL. 미설정 시 OpenAI 공식 API(`https://api.openai.com/v1`) 사용. 기관 제공 키라면 `https://copa.codyssey.kr/v1` |
| `OPENAI_MODEL` | X | 모델명. 미설정 시 `gpt-4o-mini`. 기관 게이트웨이는 `gpt-5-mini` 사용 |
| `FEEDBACK_WEBHOOK_URL` | X (보너스) | n8n Webhook URL. 미설정 시 문의는 서버 로그에만 기록됩니다 |

## 실패 처리

- 필수값 누락 / 하자 필드 미입력 / 금액 0 이하 → 요청 전송 전 안내
- 응답 15초 초과 → 프론트에서 요청 중단 후 안내
- API 4xx/5xx, 429, 비정상 응답 → 구분된 안내 메시지
