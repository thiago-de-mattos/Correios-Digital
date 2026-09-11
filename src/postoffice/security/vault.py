from __future__ import annotations

import base64
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERACOES = 600_000

TAMANHO_SALT = 16


class ConteudoIlegivelError(Exception):
    pass


class CofreFechadoError(Exception):
    pass


def gerar_salt() -> bytes:
    return secrets.token_bytes(TAMANHO_SALT)


def _derivar_chave(senha: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERACOES,
    )
    return base64.urlsafe_b64encode(kdf.derive(senha.encode("utf-8")))


class Cofre:
    __slots__ = ("_fernet",)

    def __init__(self, chave: bytes) -> None:
        self._fernet: Fernet | None = Fernet(chave)

    @classmethod
    def abrir(cls, senha: str, salt: bytes) -> Cofre:
        if not senha:
            raise ValueError("senha não pode ser vazia")
        return cls(_derivar_chave(senha, salt))

    @property
    def aberto(self) -> bool:
        return self._fernet is not None

    def cifrar(self, texto: str) -> bytes:
        if self._fernet is None:
            raise CofreFechadoError("cofre fechado: faça login novamente")
        return self._fernet.encrypt(texto.encode("utf-8"))

    def decifrar(self, dados: bytes) -> str:
        if self._fernet is None:
            raise CofreFechadoError("cofre fechado: faça login novamente")
        try:
            return self._fernet.decrypt(dados).decode("utf-8")
        except InvalidToken as erro:
            raise ConteudoIlegivelError(
                "conteúdo ilegível: chave incorreta ou dados adulterados"
            ) from erro

    def fechar(self) -> None:
        self._fernet = None

    def __enter__(self) -> Cofre:
        return self

    def __exit__(self, *_) -> None:
        self.fechar()

    def __repr__(self) -> str:
        estado = "aberto" if self.aberto else "fechado"
        return f"<Cofre {estado}>"