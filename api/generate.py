# runtime: vercel-python3.12
import json
import os
import re
from http.server import BaseHTTPRequestHandler

import requests

# base URL은 환경변수로 받음 (OpenAI 호환 프로바이더 지원)
# 기본값은 OpenAI 공식 API, 기관 제공 키라면 OPENAI_BASE_URL=https://copa.codyssey.kr/v1 로 설정
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_URL = f"{BASE_URL}/chat/completions"
# 기관 게이트웨이는 gpt-4o-mini가 없어서 환경변수로 모델 지정 (기본값만 공식 OpenAI용)
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
UPSTREAM_TIMEOUT = 28  # 게이트웨이 지연 변동이 커서 넉넉하게 (실패 시 1회 재시도)
# gpt-5 계열은 추론(reasoning)에 토큰 예산을 쓰므로 max_tokens를 넉넉히
MAX_TOKENS = 4000
MAX_ATTEMPTS = 2

CATEGORY_LABELS = {
    "fashion": "의류·패션잡화",
    "digital": "디지털·가전",
    "furniture": "가구·인테리어",
    "living": "생활·주방",
    "beauty": "뷰티·건강",
    "hobby": "취미·스포츠",
    "culture": "도서·티켓",
    "etc": "기타",
}

SYSTEM_PROMPT = """역할: 한국 중고거래 판매글을 쓰는 카피라이터.
지키는 원칙:
- 사용자가 주지 않은 제조사·모델명·사양·구매가는 절대 만들어내지 마십시오.
- "판매사연" 같은 사실은 지어내지 마십시오. 상태·관리에 대한 진솔한 표현으로 신뢰를 주세요.
- 하자 정보가 있으면 상세 설명에 반드시 포함하십시오.
- 사실과 다른 과장 표현과 이모지 나열은 금지합니다.

쓰는 법:
- 상세 설명은 물건 상태뿐 아니라 다음도 담아 매수인에게 호감을 주세요:
  * 이 물건을 쓰는 사람에게 어떤 상황·용도에 좋은지 (카테고리·물품명으로 추론 가능한 범위만)
  * 상태를 안심시켜 주는 진심 어린 한두 문장
- 상세 설명은 6~8줄, 각 줄은 짧게.
- 제목은 매수인의 눈이 멈추게 하되, 내용은 사실에 기반해야 합니다.

다른 설명·마크다운 없이 JSON만 반환하십시오.
JSON 구조:
{"titles": [3개 문자열], "description": "본문", "price_comment": "한 줄", "hashtags": [3~5개]}
"""


def parse_result(content: str) -> dict:
    # 마크다운 펜스·여분 텍스트가 섞여도 JSON 객체만 추출
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("no json object")
    return json.loads(match.group(0))


def build_user_prompt(d: dict) -> str:
    category = CATEGORY_LABELS.get(d.get("category", ""), "기타")
    trade = ", ".join(d.get("trade") or []) or "미지정"
    defect = d.get("defect") or "없음"
    return (
        f"카테고리: {category}\n"
        f"물품명: {d.get('itemName')}\n"
        f"사용 기간: {d.get('usedPeriod')}\n"
        f"상태: {d.get('condition')}\n"
        f"하자: {defect}\n"
        f"희망 금액: {d.get('price')}원\n"
        f"거래 방식: {trade}\n"
        f"톤: {d.get('tone') or '차분하게'}"
    )


def validate(d: dict):
    required = ["category", "itemName", "usedPeriod", "condition", "price"]
    for key in required:
        if not str(d.get(key) or "").strip():
            return "필수 입력값이 누락되었습니다."
    if d.get("condition") == "하자 있음" and not str(d.get("defect") or "").strip():
        return "하자 설명이 필요합니다."
    if len(str(d.get("itemName"))) > 40 or len(str(d.get("defect") or "")) > 200:
        return "입력 길이가 제한을 초과했습니다."
    try:
        if float(d.get("price")) <= 0:
            return "희망 금액이 유효하지 않습니다."
    except (TypeError, ValueError):
        return "희망 금액은 숫자여야 합니다."
    return None


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "요청 형식이 잘못되었습니다."})

        error = validate(data)
        if error:
            return self._send(400, {"error": error})

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self._send(500, {"error": "서버 설정 오류입니다."})

        res = None
        for _ in range(MAX_ATTEMPTS):
            try:
                res = requests.post(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "max_tokens": MAX_TOKENS,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": build_user_prompt(data)},
                        ],
                    },
                    timeout=UPSTREAM_TIMEOUT,
                )
                break  # 연결 성공 → 재시도 중단
            except requests.Timeout:
                continue  # 지연만 재시도 (마지막 회차 후 504)
            except requests.RequestException:
                return self._send(502, {"error": "AI 서버 연결에 실패했습니다."})
        if res is None:
            return self._send(504, {"error": "AI 응답이 지연되었습니다."})

        if res.status_code == 429:
            return self._send(429, {"error": "요청이 많아 잠시 후 다시 시도해주세요."})
        if res.status_code >= 400:
            print("upstream error", res.status_code, res.text[:300])
            return self._send(502, {"error": "AI 호출에 실패했습니다."})

        try:
            content = res.json()["choices"][0]["message"]["content"]
            parsed = parse_result(content)
            result = {
                "titles": [str(t) for t in parsed.get("titles", [])][:3],
                "description": str(parsed.get("description", "")),
                "price_comment": str(parsed.get("price_comment", "")),
                "hashtags": [str(h) for h in parsed.get("hashtags", [])][:5],
            }
            if not result["titles"] or not result["description"]:
                raise ValueError("empty result")
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            return self._send(502, {"error": "AI 응답을 해석하지 못했습니다."})

        return self._send(200, result)

    def do_GET(self):
        return self._send(405, {"error": "POST만 지원합니다."})
