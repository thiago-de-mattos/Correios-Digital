from __future__ import annotations

import json
from pathlib import Path

from postoffice.persistence.serializer import (
    VERSAO_FORMATO,
    FormatoInvalidoError,
    conversa_para_dicionario,
    dicionario_para_conversa,
    dicionario_para_usuario,
    usuario_para_dicionario,
)
from postoffice.security.vault import Cofre, ConteudoIlegivelError
from postoffice.services.conversation import Conversa
from postoffice.services.keyring import Chaveiro
from postoffice.structures import ArvoreAVL

ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_CHAVEIRO = "chaveiro.json"
PASTA_CONVERSAS = "conversas"
EXTENSAO_CONVERSA = ".cofre"


class ArquivoCorrompidoError(Exception):
    pass


class ConversaNaoEncontradaError(FileNotFoundError):
    pass


def _ler_json(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as erro:
        raise ArquivoCorrompidoError(f"não foi possível ler {caminho.name}") from erro


def _gravar_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(caminho)


class Repositorio:
    def __init__(self, pasta: str | Path) -> None:
        self.pasta = Path(pasta)

    @property
    def arquivo_usuarios(self) -> Path:
        return self.pasta / ARQUIVO_USUARIOS

    @property
    def arquivo_chaveiro(self) -> Path:
        return self.pasta / ARQUIVO_CHAVEIRO

    def pasta_de_conversas(self, login: str) -> Path:
        return self.pasta / login.strip().lower() / PASTA_CONVERSAS

    def salvar_usuarios(self, usuarios: ArvoreAVL) -> None:
        _gravar_json(
            self.arquivo_usuarios,
            {
                "versao": VERSAO_FORMATO,
                "usuarios": [
                    usuario_para_dicionario(u) for _, u in usuarios.pre_ordem()
                ],
            },
        )

    def carregar_usuarios(self) -> ArvoreAVL:
        arvore = ArvoreAVL()
        if not self.arquivo_usuarios.exists():
            return arvore

        dados = _ler_json(self.arquivo_usuarios)
        try:
            lista = dados["usuarios"]
        except (KeyError, TypeError) as erro:
            raise ArquivoCorrompidoError("arquivo de usuários sem a chave esperada") from erro

        for item in lista:
            usuario = dicionario_para_usuario(item)
            arvore.inserir(usuario.login, usuario)
        return arvore

    def salvar_chaveiro(self, chaveiro: Chaveiro) -> None:
        _gravar_json(
            self.arquivo_chaveiro,
            {
                "versao": VERSAO_FORMATO,
                "contatos": {
                    contato.login: {
                        "chave_publica": contato.chave_publica.decode("ascii"),
                        "endereco": contato.endereco,
                    }
                    for contato in chaveiro.todos()
                },
            },
        )

    def carregar_chaveiro(self) -> Chaveiro:
        chaveiro = Chaveiro()
        if not self.arquivo_chaveiro.exists():
            return chaveiro

        dados = _ler_json(self.arquivo_chaveiro)
        try:
            contatos = dados["contatos"]
        except (KeyError, TypeError) as erro:
            raise ArquivoCorrompidoError("arquivo de chaveiro sem a chave esperada") from erro

        for login, dados_do_contato in contatos.items():
            try:
                chaveiro.adicionar(
                    login,
                    dados_do_contato["chave_publica"].encode("ascii"),
                    dados_do_contato.get("endereco"),
                )
            except (KeyError, TypeError, AttributeError) as erro:
                raise ArquivoCorrompidoError(
                    f"contato {login} em formato inválido"
                ) from erro
        return chaveiro

    def caminho_da_conversa(self, login: str, identificador: str) -> Path:
        return self.pasta_de_conversas(login) / f"{identificador}{EXTENSAO_CONVERSA}"

    def conversas_salvas(self, login: str) -> list[str]:
        pasta = self.pasta_de_conversas(login)
        if not pasta.is_dir():
            return []
        return sorted(p.stem for p in pasta.glob(f"*{EXTENSAO_CONVERSA}"))

    def salvar_conversa(self, login: str, conversa: Conversa, cofre: Cofre) -> None:
        conteudo = json.dumps(conversa_para_dicionario(conversa), ensure_ascii=False)
        caminho = self.caminho_da_conversa(login, conversa.identificador)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(EXTENSAO_CONVERSA + ".tmp")
        temporario.write_bytes(cofre.cifrar(conteudo))
        temporario.replace(caminho)

    def carregar_conversa(self, login: str, identificador: str, cofre: Cofre) -> Conversa:
        caminho = self.caminho_da_conversa(login, identificador)
        if not caminho.exists():
            raise ConversaNaoEncontradaError(f"conversa {identificador} não encontrada")

        try:
            texto = cofre.decifrar(caminho.read_bytes())
        except ConteudoIlegivelError as erro:
            raise ArquivoCorrompidoError(
                f"não foi possível abrir {caminho.name}: senha incorreta ou arquivo adulterado"
            ) from erro
        except OSError as erro:
            raise ArquivoCorrompidoError(f"não foi possível ler {caminho.name}") from erro

        try:
            return dicionario_para_conversa(json.loads(texto))
        except json.JSONDecodeError as erro:
            raise ArquivoCorrompidoError(f"{caminho.name} não contém JSON válido") from erro
        except FormatoInvalidoError as erro:
            raise ArquivoCorrompidoError(str(erro)) from erro

    def carregar_conversas(self, login: str, cofre: Cofre) -> list[Conversa]:
        return [
            self.carregar_conversa(login, identificador, cofre)
            for identificador in self.conversas_salvas(login)
        ]