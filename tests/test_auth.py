"""Check which tokens the protected server accepts and refuses.

The tests sign their own tokens with a throwaway key and point the verifier at
that key, so nothing here talks to Entra ID. Run with:  pytest
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

import jwt
import pytest
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa

TENANT = "11111111-1111-1111-1111-111111111111"
API_ID = "22222222-2222-2222-2222-222222222222"
PORT = 8765

os.environ.update(
    ENTRA_TENANT_ID=TENANT,
    ENTRA_API_CLIENT_ID=API_ID,
    PUBLIC_URL="https://example.test",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.simplefilter("ignore")

import server  # noqa: E402

GOOD_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

INITIALIZE = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "test", "version": "1"}},
}).encode()


class _SigningKey:
    key = GOOD_KEY.public_key()


@pytest.fixture(scope="module", autouse=True)
def running_server():
    """Start the server in a background thread, trusting GOOD_KEY instead of Entra's keys."""
    verifier = server.auth_config()["token_verifier"]
    verifier._keys.get_signing_key_from_jwt = lambda token: _SigningKey
    # MCPServer was built at import time with its own verifier; swap in the patched one.
    server.mcp._token_verifier = verifier
    app = server.mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")
    instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=instance.run, daemon=True).start()
    time.sleep(1.5)
    yield
    instance.should_exit = True


def make_token(key=GOOD_KEY, **overrides) -> str:
    claims = {
        "iss": f"https://sts.windows.net/{TENANT}/",
        "aud": f"api://{API_ID}",
        "exp": int(time.time()) + 600,
        "scp": "league.read",
        "appid": "test-client",
        "sub": "user-1",
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")


def call(token: str | None) -> int:
    """POST an MCP initialize request and return the HTTP status code."""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/mcp", data=INITIALIZE, headers=headers)
    try:
        return urllib.request.urlopen(request, timeout=10).status
    except urllib.error.HTTPError as error:
        return error.code


def test_no_token_is_refused():
    assert call(None) == 401


def test_valid_v1_token_is_accepted():
    assert call(make_token()) == 200


def test_valid_v2_token_is_accepted():
    token = make_token(iss=f"https://login.microsoftonline.com/{TENANT}/v2.0", aud=API_ID, appid=None, azp="test-client")
    assert call(token) == 200


def test_token_for_another_api_is_refused():
    assert call(make_token(aud="api://someone-else")) == 401


def test_token_from_another_tenant_is_refused():
    assert call(make_token(iss="https://sts.windows.net/00000000-0000-0000-0000-000000000000/")) == 401


def test_expired_token_is_refused():
    assert call(make_token(exp=int(time.time()) - 60)) == 401


def test_token_signed_with_another_key_is_refused():
    assert call(make_token(key=OTHER_KEY)) == 401


def test_token_without_the_scope_is_forbidden():
    assert call(make_token(scp="something.else")) == 403


def test_garbage_token_is_refused():
    assert call("not-a-token") == 401
