from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple

from postoffice.security.keys import ChaveIlegivelError, cifrar_chave, decifrar_chave
from postoffice.security.vault import Cofre, ConteudoIlegivelError


class MensagemVaziaError(ValueError):
    pass


class DestinatarioSemChaveError(ValueError):
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


def _normalizar(login: str) -> str:
    return (login or "").strip().lower()


@dataclass(frozen=True, slots=True)
class Mensagem:
    chave: ChaveMensagem
    remetente: str
    destinatario: str
    conteudo_cifrado: bytes
    chaves_cifradas: dict[str, bytes]

    @classmethod
    def criar(
        cls,
        remetente: str,
        destinatario: str,
        texto: str,
        chaves_publicas: Mapping[str, Any],
        chave: ChaveMensagem,
    ) -> Mensagem:
        remetente, destinatario = _normalizar(remetente), _normalizar(destinatario)

        if not texto or not texto.strip():
            raise MensagemVaziaError("a mensagem não pode ser vazia")
        if not remetente or not destinatario:
            raise ValueError("remetente e destinatário são obrigatórios")

        publicas = {_normalizar(login): pub for login, pub in chaves_publicas.items()}
        for quem in (remetente, destinatario):
            if quem not in publicas:
                raise DestinatarioSemChaveError(f"chave pública de {quem} não encontrada")

        chave_da_mensagem = Cofre.gerar_chave()
        cofre = Cofre(chave_da_mensagem)
        conteudo = cofre.cifrar(texto.strip())
        cofre.fechar()

        return cls(
            chave=chave,
            remetente=remetente,
            destinatario=destinatario,
            conteudo_cifrado=conteudo,
            chaves_cifradas={
                quem: cifrar_chave(publicas[quem], chave_da_mensagem)
                for quem in (remetente, destinatario)
            },
        )

    def ler(self, login: str, chave_privada: Any) -> str:
        envelope = self.chaves_cifradas.get(_normalizar(login))
        if envelope is None:
            raise ConteudoIlegivelError(
                f"esta mensagem não foi endereçada a {_normalizar(login)}"
            )

        try:
            chave_da_mensagem = decifrar_chave(chave_privada, envelope)
        except ChaveIlegivelError as erro:
            raise ConteudoIlegivelError("conteúdo ilegível: chave privada incorreta") from erro

        cofre = Cofre(chave_da_mensagem)
        try:
            return cofre.decifrar(self.conteudo_cifrado)
        finally:
            cofre.fechar()

    def destinada_a(self, login: str) -> bool:
        return _normalizar(login) in self.chaves_cifradas

    def __repr__(self) -> str:
        return (
            f"Mensagem({self.chave}, {self.remetente} -> {self.destinatario}, "
            f"{len(self.conteudo_cifrado)} bytes cifrados, "
            f"{len(self.chaves_cifradas)} envelopes)"
        )