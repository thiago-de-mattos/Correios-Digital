import pytest

from postoffice.security import passwords as senhas
from postoffice.security.vault import (
    Cofre,
    CofreFechadoError,
    ConteudoIlegivelError,
    gerar_salt,
)

SENHA = "senha-de-teste-123"


def test_senha_correta_confere():
    salt = senhas.gerar_salt()
    guardado = senhas.calcular_hash(SENHA, salt)
    assert senhas.conferir(SENHA, salt, guardado)


def test_senha_errada_nao_confere():
    salt = senhas.gerar_salt()
    guardado = senhas.calcular_hash(SENHA, salt)
    assert not senhas.conferir("outra-senha", salt, guardado)


def test_senha_vazia_nao_confere():
    salt = senhas.gerar_salt()
    guardado = senhas.calcular_hash(SENHA, salt)
    assert not senhas.conferir("", salt, guardado)


def test_hash_nao_contem_a_senha():
    salt = senhas.gerar_salt()
    guardado = senhas.calcular_hash(SENHA, salt)
    assert SENHA.encode() not in guardado


def test_salts_diferentes_geram_hashes_diferentes():
    a = senhas.calcular_hash(SENHA, senhas.gerar_salt())
    b = senhas.calcular_hash(SENHA, senhas.gerar_salt())
    assert a != b


def test_salt_e_aleatorio():
    assert senhas.gerar_salt() != senhas.gerar_salt()


def test_cifrar_e_decifrar_volta_ao_original():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    cifrado = cofre.cifrar("reunião sexta às 14h")
    assert cofre.decifrar(cifrado) == "reunião sexta às 14h"


def test_texto_cifrado_nao_contem_o_original():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    cifrado = cofre.cifrar("o contrato vence dia 30")
    assert b"contrato" not in cifrado
    assert b"30" not in cifrado


def test_mesma_mensagem_gera_cifras_diferentes():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    assert cofre.cifrar("ok") != cofre.cifrar("ok")


def test_senha_errada_nao_decifra():
    salt = gerar_salt()
    cifrado = Cofre.abrir(SENHA, salt).cifrar("segredo")
    intruso = Cofre.abrir("senha-errada", salt)
    with pytest.raises(ConteudoIlegivelError):
        intruso.decifrar(cifrado)


def test_dados_adulterados_sao_detectados():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    cifrado = bytearray(cofre.cifrar("saldo: 1000"))
    cifrado[-5] ^= 0xFF
    with pytest.raises(ConteudoIlegivelError):
        cofre.decifrar(bytes(cifrado))


def test_salts_diferentes_geram_cofres_incompativeis():
    cifrado = Cofre.abrir(SENHA, gerar_salt()).cifrar("mensagem")
    outro = Cofre.abrir(SENHA, gerar_salt())
    with pytest.raises(ConteudoIlegivelError):
        outro.decifrar(cifrado)


def test_cofre_fechado_recusa_operacoes():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    cifrado = cofre.cifrar("antes do logout")
    cofre.fechar()

    assert not cofre.aberto
    with pytest.raises(CofreFechadoError):
        cofre.cifrar("depois do logout")
    with pytest.raises(CofreFechadoError):
        cofre.decifrar(cifrado)


def test_cofre_como_context_manager_fecha_sozinho():
    with Cofre.abrir(SENHA, gerar_salt()) as cofre:
        assert cofre.aberto
    assert not cofre.aberto


def test_repr_nao_vaza_a_chave():
    cofre = Cofre.abrir(SENHA, gerar_salt())
    assert SENHA not in repr(cofre)
    assert repr(cofre) == "<Cofre aberto>"


def test_senha_vazia_recusada():
    with pytest.raises(ValueError):
        Cofre.abrir("", gerar_salt())