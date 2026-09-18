import pytest

from postoffice.security import keys
from postoffice.security.vault import Cofre

SENHA = "senha-de-teste-123"


@pytest.fixture(scope="module")
def par():
    return keys.gerar_par()


def test_chave_simetrica_vai_e_volta(par):
    privada, publica = par
    chave = Cofre.gerar_chave()
    envelope = keys.cifrar_chave(publica, chave)
    assert keys.decifrar_chave(privada, envelope) == chave


def test_envelope_nao_contem_a_chave(par):
    _, publica = par
    chave = Cofre.gerar_chave()
    assert chave not in keys.cifrar_chave(publica, chave)


def test_mesma_chave_gera_envelopes_diferentes(par):
    _, publica = par
    chave = Cofre.gerar_chave()
    assert keys.cifrar_chave(publica, chave) != keys.cifrar_chave(publica, chave)


def test_outra_privada_nao_abre(par):
    _, publica = par
    outra_privada, _ = keys.gerar_par()
    envelope = keys.cifrar_chave(publica, Cofre.gerar_chave())
    with pytest.raises(keys.ChaveIlegivelError):
        keys.decifrar_chave(outra_privada, envelope)


def test_publica_exporta_e_importa(par):
    _, publica = par
    pem = keys.exportar_publica(publica)
    assert pem.startswith(b"-----BEGIN PUBLIC KEY-----")

    chave = Cofre.gerar_chave()
    envelope = keys.cifrar_chave(keys.importar_publica(pem), chave)
    assert keys.decifrar_chave(par[0], envelope) == chave


def test_publica_invalida_recusada():
    with pytest.raises(keys.ChavePublicaInvalidaError):
        keys.importar_publica(b"isto nao e uma chave")


def test_privada_e_exportada_cifrada(par):
    privada, _ = par
    pem = keys.exportar_privada(privada, SENHA)
    assert pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")


def test_privada_abre_com_a_senha_certa(par):
    privada, publica = par
    pem = keys.exportar_privada(privada, SENHA)
    recuperada = keys.importar_privada(pem, SENHA)

    chave = Cofre.gerar_chave()
    envelope = keys.cifrar_chave(publica, chave)
    assert keys.decifrar_chave(recuperada, envelope) == chave


def test_privada_nao_abre_com_senha_errada(par):
    pem = keys.exportar_privada(par[0], SENHA)
    with pytest.raises(keys.ChavePrivadaBloqueadaError):
        keys.importar_privada(pem, "senha-errada-mesmo")


def test_privada_corrompida_e_detectada():
    with pytest.raises(keys.ChavePrivadaBloqueadaError):
        keys.importar_privada(b"lixo", SENHA)


def test_impressao_digital_e_estavel(par):
    pem = keys.exportar_publica(par[1])
    assert keys.impressao_digital(pem) == keys.impressao_digital(pem)


def test_chaves_diferentes_tem_impressoes_diferentes(par):
    _, outra_publica = keys.gerar_par()
    assert keys.impressao_digital(keys.exportar_publica(par[1])) != keys.impressao_digital(
        keys.exportar_publica(outra_publica)
    )


def test_impressao_digital_e_legivel_em_voz_alta(par):
    impressao = keys.impressao_digital(keys.exportar_publica(par[1]))
    grupos = impressao.split(" ")
    assert len(grupos) == 8
    assert all(len(g) == 4 for g in grupos)