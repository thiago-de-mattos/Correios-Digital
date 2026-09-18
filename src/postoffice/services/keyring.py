from __future__ import annotations

from typing import Any

from postoffice.security import keys as _chaves
from postoffice.structures import ArvoreAVL


class ContatoDesconhecidoError(KeyError):
    pass


def _normalizar(login: str) -> str:
    return (login or "").strip().lower()


class Chaveiro:
    def __init__(self) -> None:
        self._contatos = ArvoreAVL()

    def __len__(self) -> int:
        return len(self._contatos)

    def __contains__(self, login: str) -> bool:
        return _normalizar(login) in self._contatos

    def adicionar(self, login: str, chave_publica: bytes) -> None:
        login = _normalizar(login)
        if not login:
            raise ValueError("login é obrigatório")

        _chaves.importar_publica(chave_publica)

        if login in self._contatos:
            self._contatos.remover(login)
        self._contatos.inserir(login, chave_publica)

    def pem(self, login: str) -> bytes:
        guardada = self._contatos.buscar(_normalizar(login))
        if guardada is None:
            raise ContatoDesconhecidoError(
                f"chave pública de {_normalizar(login)} não está no chaveiro"
            )
        return guardada

    def obter(self, login: str) -> Any:
        return _chaves.importar_publica(self.pem(login))

    def impressao_digital(self, login: str) -> str:
        return _chaves.impressao_digital(self.pem(login))

    def contatos(self) -> list[str]:
        return [login for login, _ in self._contatos.em_ordem()]