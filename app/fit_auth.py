"""Google Fit REST API の OAuth 認可を1回だけ行い、リフレッシュトークンを保存する。

  export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...   # Google Cloud で「デスクトップアプリ」の OAuth クライアントを作成
  python -m app.fit_auth

注意: Google は Fit API を 2026 年中に終了すると予告しています。終了後は Health Connect 経由（docs/phone_setup.md）を使ってください。
"""
import http.server
import json
import os
import urllib.parse
import urllib.request
import webbrowser

from . import config
from .health import FIT_SCOPES, FIT_TOKEN_FILE

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"


def main():
    cid, secret = os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"]
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": FIT_SCOPES,
        "access_type": "offline", "prompt": "consent"})
    code = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code["v"] = q.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("認可できました。このタブは閉じてください。".encode())

        def log_message(self, *a):
            pass

    print("ブラウザで次の URL を開いて許可してください:\n", url)
    webbrowser.open(url)
    http.server.HTTPServer(("127.0.0.1", PORT), H).handle_request()
    body = urllib.parse.urlencode({"code": code["v"], "client_id": cid, "client_secret": secret,
                                   "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", body) as r:
        tok = json.load(r)
    config.ensure_dirs()
    FIT_TOKEN_FILE.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    print("保存しました:", FIT_TOKEN_FILE)


if __name__ == "__main__":
    main()
