from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any, NamedTuple

from postoffice.domain.message import ChaveMensagem, Mensagem, agora, gerar_chave
from postoffice.security.vault import ConteudoIlegivelError
from postoffice.services.conversation import Conversa
from postoffice.services.keyring import Chaveiro

MARCADOR_ILEGIVEL = "[mensagem ilegível]"


class RemetenteNaoParticipaError(ValueError):
    pass


class MensagemExibida(NamedTuple):
    chave: ChaveMensagem
    remetente: str
    texto: str
    legivel: bool


class Mensageria:
    def __init__(self, chaveiro: Chaveiro) -> None:
        self.chaveiro = chaveiro
        self._conversas: dict[str, Conversa] = {}

    def conversa_entre(self, um: str, outro: str) -> Conversa:
        nova = Conversa.criar(um, outro)
        return self._conversas.setdefault(nova.identificador, nova)

    def conversas_de(self, login: str) -> list[Conversa]:
        return sorted(
            (c for c in self._conversas.values() if c.inclui(login)),
            key=lambda c: c.identificador,
        )

    def registrar(self, conversa: Conversa) -> None:
        self._conversas[conversa.identificador] = conversa

    def enviar(self, conversa: Conversa, remetente: str, texto: str) -> Mensagem:
        if not conversa.inclui(remetente):
            raise RemetenteNaoParticipaError(
                f"{remetente} não participa da conversa {conversa.identificador}"
            )

        destinatario = conversa.outro_participante(remetente)
        publicas = {
            quem: self.chaveiro.obter(quem) for quem in (remetente, destinatario)
        }
        chave = gerar_chave(agora(), lambda c: c in conversa.arvore)
        mensagem = Mensagem.criar(remetente, destinatario, texto, publicas, chave)
        conversa.arvore.inserir(chave, mensagem)
        return mensagem

    def receber(self, conversa: Conversa, mensagem: Mensagem) -> None:
        if not conversa.inclui(mensagem.remetente):
            raise RemetenteNaoParticipaError(
                f"{mensagem.remetente} não participa da conversa {conversa.identificador}"
            )
        conversa.arvore.inserir(mensagem.chave, mensagem)

    def historico(
        self,
        conversa: Conversa,
        login: str,
        chave_privada: Any,
    ) -> list[MensagemExibida]:
        return [
            self._exibir(m, login, chave_privada) for _, m in conversa.arvore.em_ordem()
        ]

    def buscar_por_dia(
        self,
        conversa: Conversa,
        login: str,
        chave_privada: Any,
        dia: date,
    ) -> list[MensagemExibida]:
        inicio = ChaveMensagem(datetime.combine(dia, time.min, tzinfo=UTC))
        fim = ChaveMensagem(datetime.combine(dia, time.max, tzinfo=UTC), sequencia=2**31)
        return [
            self._exibir(m, login, chave_privada)
            for _, m in conversa.arvore.intervalo(inicio, fim)
        ]

    def excluir(self, conversa: Conversa, chave: ChaveMensagem) -> None:
        conversa.arvore.remover(chave)

    @staticmethod
    def _exibir(mensagem: Mensagem, login: str, chave_privada: Any) -> MensagemExibida:
        try:
            texto, legivel = mensagem.ler(login, chave_privada), True
        except ConteudoIlegivelError:
            texto, legivel = MARCADOR_ILEGIVEL, False
        return MensagemExibida(mensagem.chave, mensagem.remetente, texto, legivel)