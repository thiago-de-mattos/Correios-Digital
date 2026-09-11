from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NamedTuple

from postoffice.security.vault import Cofre


class MensagemVaziaError(ValueError):
    pass


class ChaveMensagem(NamedTuple):
    instante: datetime
    sequencia: int = 0

    def proxima(self) -> ChaveMensagem:
        return ChaveMensagem(self.instante, self.sequencia + 1)

    def __str__(self) -> str:
        marca = self.instante.strftime("%d/%m/%Y %H:%M:%S")
        return marca if self.sequencia == 0 else f"{marca} (#{self.sequencia})"


def agora() -> datetime:
    return datetime.now(UTC)


def gerar_chave(
    instante: datetime,
    ja_existe: Callable[[ChaveMensagem], bool],
) -> ChaveMensagem:
    chave = ChaveMensagem(instante)
    while ja_existe(chave):
        chave = chave.proxima()
    return chave


@dataclass(frozen=True, slots=True)
class Mensagem:
    chave: ChaveMensagem
    remetente: str
    destinatario: str
    conteudo_cifrado: bytes

    @classmethod
    def criar(
        cls,
        remetente: str,
        destinatario: str,
        texto: str,
        cofre: Cofre,
        chave: ChaveMensagem,
    ) -> Mensagem:
        if not texto or not texto.strip():
            raise MensagemVaziaError("a mensagem não pode ser vazia")
        if not remetente or not destinatario:
            raise ValueError("remetente e destinatário são obrigatórios")

        return cls(
            chave=chave,
            remetente=remetente,
            destinatario=destinatario,
            conteudo_cifrado=cofre.cifrar(texto.strip()),
        )

    def ler(self, cofre: Cofre) -> str:
        return cofre.decifrar(self.conteudo_cifrado)

    def __repr__(self) -> str:
        return (
            f"Mensagem({self.chave}, {self.remetente} -> {self.destinatario}, "
            f"{len(self.conteudo_cifrado)} bytes cifrados)"
        )