from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from postoffice.security import keys as _chaves
from postoffice.security import passwords as senhas
from postoffice.security import vault as _cofre
from postoffice.security.vault import Cofre

TAMANHO_MINIMO_SENHA = 8


class CredenciaisInvalidasError(Exception):
    pass


class DadosDeCadastroInvalidosError(ValueError):
    pass


@dataclass(slots=True)
class Usuario:
    login: str
    nome: str
    email: str
    hash_senha: bytes = field(repr=False)
    salt_autenticacao: bytes = field(repr=False)
    salt_cofre: bytes = field(repr=False)
    chave_publica: bytes = field(repr=False)
    chave_privada_cifrada: bytes = field(repr=False)

    @classmethod
    def cadastrar(cls, login: str, nome: str, email: str, senha: str) -> Usuario:
        login = (login or "").strip().lower()
        nome = (nome or "").strip()
        email = (email or "").strip().lower()

        if not login:
            raise DadosDeCadastroInvalidosError("login é obrigatório")
        if not nome:
            raise DadosDeCadastroInvalidosError("nome é obrigatório")
        if "@" not in email or "." not in email.split("@")[-1]:
            raise DadosDeCadastroInvalidosError("e-mail inválido")
        if len(senha or "") < TAMANHO_MINIMO_SENHA:
            raise DadosDeCadastroInvalidosError(
                f"a senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres"
            )

        privada, publica = _chaves.gerar_par()
        salt_autenticacao = senhas.gerar_salt()

        return cls(
            login=login,
            nome=nome,
            email=email,
            hash_senha=senhas.calcular_hash(senha, salt_autenticacao),
            salt_autenticacao=salt_autenticacao,
            salt_cofre=_cofre.gerar_salt(),
            chave_publica=_chaves.exportar_publica(publica),
            chave_privada_cifrada=_chaves.exportar_privada(privada, senha),
        )

    def senha_confere(self, senha: str) -> bool:
        return senhas.conferir(senha, self.salt_autenticacao, self.hash_senha)

    def entrar(self, senha: str) -> Cofre:
        if not self.senha_confere(senha):
            raise CredenciaisInvalidasError("login ou senha incorretos")
        return Cofre.abrir(senha, self.salt_cofre)

    def abrir_chave_privada(self, senha: str) -> Any:
        if not self.senha_confere(senha):
            raise CredenciaisInvalidasError("login ou senha incorretos")
        return _chaves.importar_privada(self.chave_privada_cifrada, senha)

    def impressao_digital(self) -> str:
        return _chaves.impressao_digital(self.chave_publica)