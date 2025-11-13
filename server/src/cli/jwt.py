from datetime import UTC, datetime, timedelta

from joserfc.jwk import JWKRegistry
from joserfc.jwt import encode as encode_jwt

from cli.config import AUTH_TOKEN_AUDIENCE, AUTH_TOKEN_ISSUER, AUTH_TOKEN_PRIVATE_KEY

__all__ = ("generate_jwt_token",)


def generate_jwt_token(
    expires_in_minutes: int = 60,
) -> str:
    time_now: datetime = datetime.now(UTC)
    return encode_jwt(
        header={"alg": "RS256"},
        claims={
            "iss": AUTH_TOKEN_ISSUER,
            "aud": AUTH_TOKEN_AUDIENCE,
            "sub": "cli",
            "iat": int(time_now.timestamp()),
            "exp": int((time_now + timedelta(minutes=expires_in_minutes)).timestamp()),
            "jti": f"cli-{int(time_now.timestamp())}",
        },
        key=JWKRegistry.import_key(
            AUTH_TOKEN_PRIVATE_KEY.replace("\\n", "\n"),
            key_type="RSA",
        ),
    )
