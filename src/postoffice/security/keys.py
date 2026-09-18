from __future__ import annotations

import hashlib
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

TAMANHO_CHAVE = 2048
EXPOENTE = 65537


class ChaveIlegivelError(Exception):
    pass


class ChavePrivadaBloqueadaError(Exception):
    pass


class ChavePublicaInvalidaError(ValueError):
    pass


def _enchimento() -> padding.OAEP:
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def gerar_par() -> tuple[Any, Any]:
    privada = rsa.generate_private_key(public_exponent=EXPOENTE, key_size=TAMANHO_CHAVE)
    return privada, privada.public_key()


def exportar_publica(publica: Any) -> bytes:
    return publica.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def importar_publica(pem: bytes) -> Any:
    try:
        return serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as erro:
        raise ChavePublicaInvalidaError("chave pública inválida ou corrompida") from erro


def exportar_privada(privada: Any, senha: str) -> bytes:
    if not senha:
        raise ValueError("senha não pode ser vazia")
    return privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode("utf-8")),
    )


def importar_privada(pem: bytes, senha: str) -> Any:
    if not senha:
        raise ChavePrivadaBloqueadaError("senha não pode ser vazia")
    try:
        return serialization.load_pem_private_key(pem, password=senha.encode("utf-8"))
    except (ValueError, TypeError) as erro:
        raise ChavePrivadaBloqueadaError(
            "não foi possível abrir a chave privada: senha incorreta ou arquivo corrompido"
        ) from erro


def cifrar_chave(publica: Any, chave: bytes) -> bytes:
    return publica.encrypt(chave, _enchimento())


def decifrar_chave(privada: Any, dados: bytes) -> bytes:
    try:
        return privada.decrypt(dados, _enchimento())
    except Exception as erro:
        raise ChaveIlegivelError(
            "esta mensagem não foi endereçada a esta chave privada"
        ) from erro


def impressao_digital(pem: bytes) -> str:
    resumo = hashlib.sha256(pem).hexdigest().upper()
    return " ".join(resumo[i : i + 4] for i in range(0, 32, 4))