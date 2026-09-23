
import os
import json
import time
import base64
import hashlib
import secrets
import webbrowser
import threading
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

DATA_ROOT = Path(__file__).resolve().parent.parent / os.environ["DATA_FOLDER_NAME"]

PLATFORM_NAME = 'Etsy'

KEY_STRING = os.environ["ETSY_KEY_STRING"] # app keystring == OAuth client_id
SHOP_NAME  = os.environ["ETSY_SHOP_NAME"]
SHARED_SECRET = os.environ["ETSY_SHARED_SECRET"]
SHOP_ID = os.environ["ETSY_SHOP_ID"]

REDIRECT_URI = os.environ["ETSY_REDIRECT_URI"]
REDIRECT_HOST, REDIRECT_PORT = "localhost", 3003 

# Scopes: shops_r to read shop info, transactions_r to read receipts/orders.
# Add more (listings_r, etc.) as needed - space separated.
SCOPES = "shops_r transactions_r"

ETSY_API_BASE = "https://api.etsy.com/v3/application"
ETSY_OAUTH_AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
ETSY_OAUTH_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

TOKEN_STORE_PATH = DATA_ROOT / 'etsy_access_token.json'

######################################################################################
### HELPERS ##########################################################################
### Access tokens expire after ~3600s. Re-run this cell (instead of the whole ########
### OAuth dance) any time you come back to the notebook after the token has expired. #
######################################################################################

def load_tokens():
    return json.loads(TOKEN_STORE_PATH.read_text())

def refresh_access_token():
    tok = load_tokens()
    resp = requests.post(
        ETSY_OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": KEY_STRING,
            "refresh_token": tok["refresh_token"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["obtained_at"] = time.time()
    TOKEN_STORE_PATH.write_text(json.dumps(new_tokens, indent=2))
    return new_tokens["access_token"]

def get_headers():
    tok = load_tokens()
    if time.time() - tok["obtained_at"] > tok.get("expires_in", 3600) - 60:
        access_token = refresh_access_token()
    else:
        access_token = tok["access_token"]
    return {
        "x-api-key": f'{KEY_STRING}:{SHARED_SECRET}',       # keystring only - never append the shared secret
        "Authorization": f"Bearer {access_token}",
    }

def setup():
    if _have_valid_or_refreshable_token():
        print("Reusing stored Etsy access token - no sign-in needed.")
    else:
        _run_authentication()

def _have_valid_or_refreshable_token() -> bool:
    if not TOKEN_STORE_PATH.exists():
        return False
    try:
        tok = load_tokens()
        if time.time() - tok["obtained_at"] > tok.get("expires_in", 3600) - 60:
            refresh_access_token()   # raises if refresh_token itself is dead
        return True
    except Exception as e:
        print(f"Stored token unusable ({e}); falling back to full auth flow.")
        return False

def _run_authentication():
    #### 1. Generate PKCE verifier/challenge + CSRF state
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    code_verifier = _b64url(secrets.token_bytes(32))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(16))

    
    # ### 2. Build the authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": KEY_STRING,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"{ETSY_OAUTH_AUTHORIZE_URL}?{urlencode(auth_params)}"
    print(authorize_url)

    # ### 3. Local redirect listener
    # 
    # This spins up a tiny local HTTP server on `localhost:3003` to catch Etsy's
    # redirect after you approve access, so you don't have to copy/paste the code
    # by hand. It stores the `code` and `state` it receives, then shuts itself down.
    # 
    from http.server import BaseHTTPRequestHandler, HTTPServer

    _callback_result = {}

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != urlparse(REDIRECT_URI).path:
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(parsed.query)
            _callback_result["code"] = qs.get("code", [None])[0]
            _callback_result["state"] = qs.get("state", [None])[0]
            _callback_result["error"] = qs.get("error", [None])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h3>Etsy authorization received. "
                            b"You can close this tab and return to Jupyter.</h3></body></html>")

        def log_message(self, format, *args):
            pass  # silence default request logging

    def _serve_once():
        httpd = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler)
        httpd.handle_request()  # blocks until exactly one request is served
        httpd.server_close()

    server_thread = threading.Thread(target=_serve_once, daemon=True)
    server_thread.start()
    print(f"Listening on {REDIRECT_URI} ...")

    # ### 4. Open the browser and authorize
    webbrowser.open(authorize_url)
    print("If a browser tab didn't open, visit this URL manually:")
    print(authorize_url)

    # Block until the callback thread has captured the redirect (or time out)
    server_thread.join(timeout=600)

    if not _callback_result:
        raise TimeoutError("No callback received within 5 minutes.")
    if _callback_result.get("error"):
        raise RuntimeError(f"Etsy returned an error: {_callback_result['error']}")
    if _callback_result.get("state") != state:
        raise RuntimeError("State mismatch - possible CSRF, aborting.")

    auth_code = _callback_result["code"]
    print("Got authorization code.")

    # ### 5. Exchange the authorization code for an access token

    token_response = requests.post(
        ETSY_OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": KEY_STRING,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    token_response.raise_for_status()
    tokens = token_response.json()

    tokens["obtained_at"] = time.time()
    TOKEN_STORE_PATH.write_text(json.dumps(tokens, indent=2))

    print("Access token acquired, expires_in:", tokens.get("expires_in"), "seconds")



if __name__ == '__main__':
    setup()
