"""
TOKEN PAY ID — Python SDK
Official client for TOKEN PAY ID API (OAuth 2.0 + OpenID Connect)
https://tokenpay.space/docs
"""
from .client import TokenPayIDClient, TokenPayIDError

__all__ = ["TokenPayIDClient", "TokenPayIDError"]
__version__ = "1.0.0"
