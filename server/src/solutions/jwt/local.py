import json
from collections.abc import Mapping, Sequence
from typing import Any

from draive import getenv_str
from joserfc.jwk import KeySet
from joserfc.jwt import ClaimsOption
from joserfc.jwt import Token as JWTToken
from starlette.requests import Request

from solutions.jwt.state import JWTVerification
from solutions.jwt.types import JWTUnauthorized
from solutions.jwt.validator import validated_token

__all__ = ("LocalJWTVerification",)


def LocalJWTVerification() -> JWTVerification:
    try:
        key_set: KeySet = KeySet.import_key_set(
            json.loads(
                getenv_str(
                    "AUTH_TOKEN_SETS",
                    required=True,
                )
            )
        )

    except Exception as exc:
        raise ValueError("Invalid auth configuration format") from exc

    async def verifier(
        request: Request,
        claims: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        authorization_header: str | None = request.headers.get(
            "Authorization",
            default=None,
        )
        if authorization_header is None:
            raise JWTUnauthorized("Missing authorization token")

        authorization_parts: Sequence[str] = authorization_header.split()
        if len(authorization_parts) != 2 or authorization_parts[0] != "Bearer":  # noqa: PLR2004
            raise JWTUnauthorized("Invalid authorization token")

        jwt_token: JWTToken = validated_token(
            token=authorization_parts[-1],
            key=key_set,
            claims={
                "exp": ClaimsOption(
                    essential=True,
                    allow_blank=False,
                ),
                "iss": ClaimsOption(
                    essential=True,
                    allow_blank=False,
                ),
                "aud": ClaimsOption(
                    essential=True,
                    allow_blank=False,
                ),
                **(
                    {
                        key: ClaimsOption(
                            essential=True,
                            allow_blank=False,
                            value=value,
                        )
                        for key, value in claims.items()
                    }
                    if claims
                    else {}
                ),
            },
        )
        return jwt_token.claims

    return JWTVerification(jwt_verifying=verifier)
