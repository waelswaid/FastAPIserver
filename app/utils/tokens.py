from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import uuid

import jwt
from jwt import ExpiredSignatureError
from jwt import InvalidTokenError as JWTInvalidTokenError
from app.exceptions import (
    InvalidTokenError,
    ExpiredTokenError,
    WrongTokenTypeError,
)



# configuration container
# when creating a token, the private key is used to generate the signature
# when decoding a token, the public key is used to verify that signature
# if the keys change, old tokens will stop working
@dataclass
class JWTConfig:
    private_key: str
    public_key: str
    algorithm: str = "RS256"
    access_token_expiry_minutes: int = 15
    refresh_token_expiry_days: int = 1
    password_reset_token_expiry_minutes: int = 15
    email_verification_token_expiry_minutes: int = 1440


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
            self.config.private_key,
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
                self.config.public_key,
                algorithms=[self.config.algorithm],
            )
        except ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except JWTInvalidTokenError as exc:
            raise InvalidTokenError() from exc
        

    # public decode and signature verification method
    def decode_access_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "access":
            raise WrongTokenTypeError()
        return payload
    

    # public decode and signature verification method
    def decode_refresh_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "refresh":
            raise WrongTokenTypeError()
        return payload

    # public method to create a short-lived password reset token
    def create_password_reset_token(self, subject: str) -> str:
        return self._create_token(
            subject=subject,
            token_type="password_reset",
            expires_delta=timedelta(minutes=self.config.password_reset_token_expiry_minutes),
        )

    # public decode and type verification for password reset tokens
    def decode_password_reset_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "password_reset":
            raise WrongTokenTypeError()
        return payload

    # public method to create a short-lived email verification token
    def create_email_verification_token(self, subject: str) -> str:
        return self._create_token(
            subject=subject,
            token_type="email_verification",
            expires_delta=timedelta(minutes=self.config.email_verification_token_expiry_minutes),
        )

    # public decode and type verification for email verification tokens
    def decode_email_verification_token(self, token: str) -> Dict[str, Any]:
        payload = self._decode_token(token)
        if payload.get("type") != "email_verification":
            raise WrongTokenTypeError()
        return payload
