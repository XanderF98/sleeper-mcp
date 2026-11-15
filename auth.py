"""Verify Microsoft Entra ID access tokens for the MCP server.

When a client calls the server it sends an access token in the Authorization
header. The token is a signed JSON Web Token (JWT) issued by Entra ID. This
module checks four things before the server answers:

  1. Signature  - the token was signed by Entra ID, using its published keys.
  2. Issuer     - it came from this organization's tenant, not another one.
  3. Audience   - it was issued for this server, not for some other API.
  4. Expiry     - it has not expired.

The required scope (league.read) is checked by the MCP library afterwards,
using the scopes this module reports.
"""

import asyncio

import jwt
from mcp.server.auth.provider import AccessToken


class EntraTokenVerifier:
    """Checks that a bearer token is a valid Entra ID token for this server."""

    def __init__(self, tenant_id: str, api_client_id: str):
        # Entra publishes the public keys it signs tokens with at this address.
        self._keys = jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            cache_keys=True,
        )
        # Entra issues two token formats; which one depends on the app registration.
        self._issuers = [
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",  # v2 tokens
            f"https://sts.windows.net/{tenant_id}/",                # v1 tokens
        ]
        self._audiences = [api_client_id, f"api://{api_client_id}"]

    def _decode(self, token: str) -> dict:
        signing_key = self._keys.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._audiences,
            issuer=self._issuers,
            options={"require": ["exp", "iss", "aud"]},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return the token's details if it is valid, or None to reject the call."""
        try:
            # Fetching keys is a blocking network call, so run it off the event loop.
            claims = await asyncio.to_thread(self._decode, token)
        except jwt.PyJWTError:
            return None
        return AccessToken(
            token=token,
            client_id=claims.get("azp") or claims.get("appid") or "",
            scopes=claims.get("scp", "").split(),
            expires_at=claims["exp"],
            subject=claims.get("sub"),
        )
