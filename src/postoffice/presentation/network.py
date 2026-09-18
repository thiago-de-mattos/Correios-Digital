from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

TEMPO_LIMITE = 6.0

_ESQUEMA = re.compile(r"^https?://", re.IGNORECASE)
_ENDERECO = re.compile(r"^[A-Za-z0-9._~%-]+(:\d{1,5})?(/[A-Za-z0-9._~%/-]*)?$")


class FalhaDeRedeError(Exception):
    pass


class EnderecoInvalidoError(FalhaDeRedeError):
    pass


class RespostaInvalidaError(Exception):
    pass


def _normalizar_endereco(endereco: str) -> str:
    endereco = (endereco or "").strip().rstrip("/")

    if not endereco:
        raise EnderecoInvalidoError(
            "Informe o endereço da outra máquina, por exemplo 192.168.0.15:5000"
        )

    sem_esquema = _ESQUEMA.sub("", endereco)
    if not _ENDERECO.match(sem_esquema):
        raise EnderecoInvalidoError(
            "Isso não parece um endereço de máquina. Use algo como 192.168.0.15:5000. "
            "A impressão digital serve para conferir depois, não para colar aqui."
        )

    if _ESQUEMA.match(endereco):
        return endereco
    return f"http://{endereco}"


def _abrir_padrao(requisicao: urllib.request.Request, tempo_limite: float) -> bytes:
    with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
        return resposta.read()


@dataclass(slots=True)
class ClienteRede:
    tempo_limite: float = TEMPO_LIMITE
    abrir: Callable[[urllib.request.Request, float], bytes] = _abrir_padrao

    def _pedir(self, endereco: str, caminho: str, corpo: dict | None = None) -> dict:
        url = f"{_normalizar_endereco(endereco)}{caminho}"
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None

        try:
            requisicao = urllib.request.Request(
                url,
                data=dados,
                headers={"Content-Type": "application/json"},
                method="POST" if dados else "GET",
            )
            bruto = self.abrir(requisicao, self.tempo_limite)
        except urllib.error.HTTPError as erro:
            raise FalhaDeRedeError(
                f"A outra máquina respondeu com erro {erro.code}."
            ) from erro
        except (http.client.InvalidURL, ValueError) as erro:
            raise EnderecoInvalidoError(
                f"'{endereco}' não é um endereço válido. Use algo como 192.168.0.15:5000."
            ) from erro
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            raise FalhaDeRedeError(
                f"Não consegui falar com {endereco}. A máquina está ligada, "
                "rodando o servidor e na mesma rede?"
            ) from erro

        try:
            return json.loads(bruto)
        except (json.JSONDecodeError, UnicodeDecodeError) as erro:
            raise RespostaInvalidaError(
                f"{endereco} respondeu, mas não parece um Correios Digital."
            ) from erro

    def identidade(self, endereco: str) -> dict:
        resposta = self._pedir(endereco, "/api/identidade")
        if not {"login", "chave_publica"} <= set(resposta):
            raise RespostaInvalidaError(
                f"{endereco} respondeu, mas não parece um Correios Digital."
            )
        return resposta

    def entregar(self, endereco: str, mensagem: dict) -> dict:
        return self._pedir(endereco, "/api/mensagens", {"mensagem": mensagem})