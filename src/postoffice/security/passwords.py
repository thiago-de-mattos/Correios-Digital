from __future__ import annotations

import hashlib
import hmac
import secrets

ITERACOES = 600_000

TAMANHO_SALT = 16

_ALGORITMO = "sha256"


def gerar_salt() -> bytes:
    return secrets.token_bytes(TAMANHO_SALT)


def calcular_hash(senha: str, salt: bytes) -> bytes:
    if not senha:
        raise ValueError("senha não pode ser vazia")
    return hashlib.pbkdf2_hmac(
        _ALGORITMO, senha.encode("utf-8"), salt, ITERACOES
    )


def conferir(senha: str, salt: bytes, hash_guardado: bytes) -> bool:
    if not senha:
        return False
    calculado = hashlib.pbkdf2_hmac(
        _ALGORITMO, senha.encode("utf-8"), salt, ITERACOES
    )
    return hmac.compare_digest(calculado, hash_guardado)