from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from postoffice.security import keys as _chaves
from postoffice.structures import ArvoreAVL


class ContatoDesconhecidoError(KeyError):
    pass


def _normalizar(login: str) -> str:
    return (login or "").strip().lower()


@dataclass(frozen=True, slots=True)
class Contato:
    login: str
    chave_publica: bytes
    endereco: str | None = None

    @property
    def impressao_digital(self) -> str:
        return _chaves.impressao_digital(self.chave_publica)

    @property
    def alcancavel(self) -> bool:
        return bool(self.endereco)

    def __repr__(self) -> str:
        destino = self.endereco or "sem endereço"
        return f"Contato({self.login}, {destino})"


class Chaveiro:
    def __init__(self) -> None:
        self._contatos = ArvoreAVL()

    def __len__(self) -> int:
        return len(self._contatos)

    def __contains__(self, login: str) -> bool:
        return _normalizar(login) in self._contatos

    def adicionar(
        self,
        login: str,
        chave_publica: bytes,
        endereco: str | None = None,
    ) -> Contato:
        login = _normalizar(login)
        if not login:
            raise ValueError("login é obrigatório")

        _chaves.importar_publica(chave_publica)
        contato = Contato(login, chave_publica, (endereco or "").strip() or None)

        if login in self._contatos:
            self._contatos.remover(login)
        self._contatos.inserir(login, contato)
        return contato

    def contato(self, login: str) -> Contato:
        guardado = self._contatos.buscar(_normalizar(login))
        if guardado is None:
            raise ContatoDesconhecidoError(
                f"{_normalizar(login)} não está no chaveiro"
            )
        return guardado

    def pem(self, login: str) -> bytes:
        return self.contato(login).chave_publica

    def obter(self, login: str) -> Any:
        return _chaves.importar_publica(self.pem(login))

    def impressao_digital(self, login: str) -> str:
        return self.contato(login).impressao_digital

    def endereco(self, login: str) -> str | None:
        return self.contato(login).endereco

    def contatos(self) -> list[str]:
        return [login for login, _ in self._contatos.em_ordem()]

    def todos(self) -> list[Contato]:
        return [contato for _, contato in self._contatos.em_ordem()]