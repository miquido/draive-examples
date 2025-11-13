from collections.abc import Mapping

from joserfc.errors import (
    JoseError,
)
from joserfc.jwk import KeyFlexible
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry
from joserfc.jwt import Token as JWTToken
from joserfc.jwt import decode as decode_jwt

from solutions.jwt.types import JWTForbidden, JWTUnauthorized

__all__ = ("validated_token",)


def validated_token(
    token: str,
    key: KeyFlexible,
    claims: Mapping[str, ClaimsOption] | None = None,
) -> JWTToken:
    jwt_token: JWTToken
    try:
        # rises an error if token is not valid
        jwt_token = decode_jwt(
            value=token,
            key=key,
            algorithms=["ES256", "RS256"],
        )

    except JoseError as exc:
        raise JWTUnauthorized(f"{type(exc)}") from exc

    try:
        if claims:
            jwt_claims_registry: JWTClaimsRegistry = JWTClaimsRegistry(
                now=None,
                leeway=0,
                **claims,
            )

        else:
            jwt_claims_registry: JWTClaimsRegistry = JWTClaimsRegistry()

        # rises an error if token is not valid
        jwt_claims_registry.validate(claims=jwt_token.claims)

    except JoseError as exc:
        raise JWTForbidden(f"{type(exc)}") from exc

    return jwt_token
