from __future__ import annotations

from dataclasses import dataclass, field

from postoffice.structures import ArvoreAVL


class ParticipanteInvalidoError(ValueError):
    pass


def _normalizar(login: str) -> str:
    return (login or "").strip().lower()


@dataclass(slots=True)
class Conversa:
    participantes: frozenset[str]
    arvore: ArvoreAVL = field(default_factory=ArvoreAVL, repr=False)

    @classmethod
    def criar(cls, um: str, outro: str) -> Conversa:
        um, outro = _normalizar(um), _normalizar(outro)

        if not um or not outro:
            raise ParticipanteInvalidoError("os dois participantes são obrigatórios")
        if um == outro:
            raise ParticipanteInvalidoError(
                "uma conversa precisa de dois participantes diferentes"
            )

        return cls(participantes=frozenset({um, outro}))

    @property
    def identificador(self) -> str:
        return "-".join(sorted(self.participantes))

    def inclui(self, login: str) -> bool:
        return _normalizar(login) in self.participantes

    def outro_participante(self, login: str) -> str:
        login = _normalizar(login)
        if login not in self.participantes:
            raise ParticipanteInvalidoError(f"{login} não participa desta conversa")
        return next(p for p in self.participantes if p != login)

    def __len__(self) -> int:
        return len(self.arvore)

    def __repr__(self) -> str:
        return f"Conversa({self.identificador}, {len(self.arvore)} mensagens)"