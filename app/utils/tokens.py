from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import uuid

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError



# configuration container
# when creating a token, the secret is used to generate the signature
# when decoding a token, the same secret is used to verify that signature
#if the secret changes, old tokens will stop working
@dataclass
class JWTConfig:
    secret_key: str
    algorithm: str = "HS256"
    access_token_expiry_minutes: int = 15
    refresh_token_expiry_days: int = 1


class JWTUtility:

    def __init__(self, config: JWTConfig) -> None:
        self.config = config

    # internal helper method for token creation
    def _create_token(
        self,
        # This is the main identity stored in the token
        # usually this is user_id, username,email,uuid as string
        subject: str, 
        token_type: str,# access or refresh
        expires_delta: timedelta,
        additional_claims: Dict[str, Any] | None = None,# allows adding extra data to token payload ({"role":"admin"})
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": subject,
            "type": token_type,
            "iat": now, # issued at
            "exp": now + expires_delta,
            "jti": str(uuid.uuid4()),  # unique token id, used for revocation
        }

        # add extra data to the payload if needed
        if additional_claims:
            payload.update(additional_claims)

        # creates the jwt string
        return jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

    # public method to create JWT access tokens
    def create_access_token(
        self,
        subject: str,
        additional_claims: Dict[str, Any] | None = None,
    ) -> str:
        return self._create_token(
            subject=subject,
            token_type="access",
            expires_delta=timedelta(minutes=self.config.access_token_expiry_minutes),
            additional_claims=additional_claims,
        )
    

    # public method to create JWT refresh tokens
    def create_refresh_token(
        self,
        subject: str,
        additional_claims: Dict[str, Any] | None = None,
    ) -> str:
        return self._create_token(
            subject=subject,
            token_type="refresh",
            expires_delta=timedelta(days=self.config.refresh_token_expiry_days),
            additional_claims=additional_claims,
        )
    

    # private method for decoding tokens
    def _decode_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )
        except ExpiredSignatureError as exc:
            raise ValueError("Token has expired") from exc
        except InvalidTokenError as exc:
            raise ValueError("Invalid token") from exc
        

    # public decode and signature verification method
    def decode_access_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Invalid token type: expected access token")
        return payload
    

    # public decode and signature verification method
    def decode_refresh_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type: expected refresh token")
        return payload