from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from postoffice.domain.user import CredenciaisInvalidasError, Usuario
from postoffice.security.vault import Cofre
from postoffice.services.keyring import Chaveiro
from postoffice.structures import ArvoreAVL


class LoginJaExisteError(ValueError):
    pass


class UsuarioNaoEncontradoError(KeyError):
    pass


class SessaoEncerradaError(Exception):
    pass


@dataclass(slots=True)
class Sessao:
    usuario: Usuario
    cofre: Cofre = field(repr=False)
    _chave_privada: Any = field(repr=False, default=None)

    @property
    def login(self) -> str:
        return self.usuario.login

    @property
    def ativa(self) -> bool:
        return self._chave_privada is not None

    @property
    def chave_privada(self) -> Any:
        if self._chave_privada is None:
            raise SessaoEncerradaError("sessão encerrada: faça login novamente")
        return self._chave_privada

    def impressao_digital(self) -> str:
        return self.usuario.impressao_digital()

    def sair(self) -> None:
        self.cofre.fechar()
        self._chave_privada = None

    def __enter__(self) -> Sessao:
        return self

    def __exit__(self, *_) -> None:
        self.sair()


class Autenticacao:
    def __init__(self, chaveiro: Chaveiro | None = None) -> None:
        self.chaveiro = chaveiro if chaveiro is not None else Chaveiro()
        self._usuarios = ArvoreAVL()

    def __len__(self) -> int:
        return len(self._usuarios)

    def existe(self, login: str) -> bool:
        return (login or "").strip().lower() in self._usuarios

    def logins(self) -> list[str]:
        return [login for login, _ in self._usuarios.em_ordem()]

    def buscar(self, login: str) -> Usuario:
        usuario = self._usuarios.buscar((login or "").strip().lower())
        if usuario is None:
            raise UsuarioNaoEncontradoError(login)
        return usuario

    def cadastrar(self, login: str, nome: str, email: str, senha: str) -> Usuario:
        usuario = Usuario.cadastrar(login, nome, email, senha)
        if usuario.login in self._usuarios:
            raise LoginJaExisteError(f"o login {usuario.login} já está em uso")
        self._usuarios.inserir(usuario.login, usuario)
        self.chaveiro.adicionar(usuario.login, usuario.chave_publica)
        return usuario

    def entrar(self, login: str, senha: str) -> Sessao:
        usuario = self._usuarios.buscar((login or "").strip().lower())
        if usuario is None:
            raise CredenciaisInvalidasError("login ou senha incorretos")
        return Sessao(
            usuario=usuario,
            cofre=usuario.entrar(senha),
            _chave_privada=usuario.abrir_chave_privada(senha),
        )