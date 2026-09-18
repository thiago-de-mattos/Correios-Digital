from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from datetime import datetime
from typing import Any

from postoffice.domain.message import ChaveMensagem, Mensagem
from postoffice.domain.user import Usuario
from postoffice.services.conversation import Conversa
from postoffice.structures import ArvoreAVL

VERSAO_FORMATO = 1


class FormatoInvalidoError(ValueError):
    pass


def _texto(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def _bytes(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"), validate=True)


def arvore_para_lista(arvore: ArvoreAVL, converter: Callable[[Any], dict]) -> list[dict]:
    return [converter(valor) for _, valor in arvore.pre_ordem()]


def lista_para_arvore(
    itens: list[dict],
    converter: Callable[[dict], Any],
    chave_de: Callable[[Any], Any],
) -> ArvoreAVL:
    arvore = ArvoreAVL()
    for item in itens:
        valor = converter(item)
        arvore.inserir(chave_de(valor), valor)
    return arvore


def mensagem_para_dicionario(mensagem: Mensagem) -> dict:
    return {
        "instante": mensagem.chave.instante.isoformat(),
        "sequencia": mensagem.chave.sequencia,
        "remetente": mensagem.remetente,
        "destinatario": mensagem.destinatario,
        "conteudo": _texto(mensagem.conteudo_cifrado),
        "envelopes": {
            login: _texto(envelope)
            for login, envelope in mensagem.chaves_cifradas.items()
        },
    }


def dicionario_para_mensagem(dados: dict) -> Mensagem:
    try:
        chave = ChaveMensagem(
            datetime.fromisoformat(dados["instante"]), int(dados["sequencia"])
        )
        return Mensagem(
            chave=chave,
            remetente=dados["remetente"],
            destinatario=dados["destinatario"],
            conteudo_cifrado=_bytes(dados["conteudo"]),
            chaves_cifradas={
                login: _bytes(envelope)
                for login, envelope in dados["envelopes"].items()
            },
        )
    except (KeyError, TypeError, ValueError, AttributeError, binascii.Error) as erro:
        raise FormatoInvalidoError("mensagem em formato inválido") from erro


def usuario_para_dicionario(usuario: Usuario) -> dict:
    return {
        "login": usuario.login,
        "nome": usuario.nome,
        "email": usuario.email,
        "hash_senha": _texto(usuario.hash_senha),
        "salt_autenticacao": _texto(usuario.salt_autenticacao),
        "salt_cofre": _texto(usuario.salt_cofre),
        "chave_publica": _texto(usuario.chave_publica),
        "chave_privada_cifrada": _texto(usuario.chave_privada_cifrada),
    }


def dicionario_para_usuario(dados: dict) -> Usuario:
    try:
        return Usuario(
            login=dados["login"],
            nome=dados["nome"],
            email=dados["email"],
            hash_senha=_bytes(dados["hash_senha"]),
            salt_autenticacao=_bytes(dados["salt_autenticacao"]),
            salt_cofre=_bytes(dados["salt_cofre"]),
            chave_publica=_bytes(dados["chave_publica"]),
            chave_privada_cifrada=_bytes(dados["chave_privada_cifrada"]),
        )
    except (KeyError, TypeError, ValueError, AttributeError, binascii.Error) as erro:
        raise FormatoInvalidoError("usuário em formato inválido") from erro


def conversa_para_dicionario(conversa: Conversa) -> dict:
    return {
        "versao": VERSAO_FORMATO,
        "participantes": sorted(conversa.participantes),
        "mensagens": arvore_para_lista(conversa.arvore, mensagem_para_dicionario),
    }


def dicionario_para_conversa(dados: dict) -> Conversa:
    try:
        participantes = dados["participantes"]
        if len(participantes) != 2:
            raise FormatoInvalidoError("uma conversa precisa de dois participantes")

        conversa = Conversa(participantes=frozenset(participantes))
        for item in dados["mensagens"]:
            mensagem = dicionario_para_mensagem(item)
            conversa.arvore.inserir(mensagem.chave, mensagem)
        return conversa
    except FormatoInvalidoError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as erro:
        raise FormatoInvalidoError("conversa em formato inválido") from erro