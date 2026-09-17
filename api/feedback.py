import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

import requests

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
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

        email = str(data.get("email") or "").strip()
        content = str(data.get("content") or "").strip()
        if not EMAIL_RE.match(email) or not content:
            return self._send(400, {"error": "이메일과 의견을 확인해주세요."})
        if len(content) > 500:
            return self._send(400, {"error": "의견은 500자까지 입력할 수 있습니다."})

        webhook = os.environ.get("FEEDBACK_WEBHOOK_URL")
        if not webhook:
            # 웹훅 미설정이면 로그만 남기고 성공 처리 (개발 단계)
            print("feedback(no webhook):", email, content[:120])
            return self._send(200, {"ok": True})

        try:
            requests.post(
                webhook,
                json={
                    "email": email,
                    "content": content,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "source": "sell-in-one",
                },
                timeout=8,
            ).raise_for_status()
        except requests.RequestException:
            return self._send(502, {"error": "전송에 실패했습니다."})

        return self._send(200, {"ok": True})
