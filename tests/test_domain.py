from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from postoffice.domain.message import (
    ChaveMensagem,
    Mensagem,
    MensagemVaziaError,
    agora,
    gerar_chave,
)
from postoffice.domain.user import (
    CredenciaisInvalidasError,
    DadosDeCadastroInvalidosError,
    Usuario,
)
from postoffice.security.vault import Cofre, ConteudoIlegivelError, gerar_salt
from postoffice.structures import ArvoreAVL

SENHA = "senha-de-teste-123"
INSTANTE = datetime(2026, 9, 11, 14, 30, tzinfo=UTC)


@pytest.fixture
def cofre() -> Cofre:
    return Cofre.abrir(SENHA, gerar_salt())


def test_chaves_ordenam_por_instante():
    antes = ChaveMensagem(INSTANTE)
    depois = ChaveMensagem(INSTANTE + timedelta(seconds=1))
    assert antes < depois


def test_contador_desempata_mesmo_instante():
    primeira = ChaveMensagem(INSTANTE)
    segunda = primeira.proxima()
    assert primeira < segunda
    assert segunda.instante == primeira.instante
    assert segunda.sequencia == 1


def test_gerar_chave_pula_as_ocupadas():
    ocupadas = {ChaveMensagem(INSTANTE, 0), ChaveMensagem(INSTANTE, 1)}
    chave = gerar_chave(INSTANTE, ocupadas.__contains__)
    assert chave == ChaveMensagem(INSTANTE, 2)


def test_agora_tem_fuso():
    assert agora().tzinfo is not None


def test_criar_e_ler_mensagem(cofre):
    msg = Mensagem.criar("thiago", "professor", "bom dia", cofre, ChaveMensagem(INSTANTE))
    assert msg.ler(cofre) == "bom dia"
    assert msg.remetente == "thiago"


def test_mensagem_guarda_conteudo_cifrado(cofre):
    msg = Mensagem.criar("a", "b", "contrato vence dia 30", cofre, ChaveMensagem(INSTANTE))
    assert b"contrato" not in msg.conteudo_cifrado


def test_repr_nao_vaza_conteudo(cofre):
    msg = Mensagem.criar("a", "b", "assunto sigiloso", cofre, ChaveMensagem(INSTANTE))
    assert "sigiloso" not in repr(msg)


def test_mensagem_vazia_e_bloqueada(cofre):
    with pytest.raises(MensagemVaziaError):
        Mensagem.criar("a", "b", "", cofre, ChaveMensagem(INSTANTE))
    with pytest.raises(MensagemVaziaError):
        Mensagem.criar("a", "b", "   ", cofre, ChaveMensagem(INSTANTE))


def test_espacos_das_pontas_sao_removidos(cofre):
    msg = Mensagem.criar("a", "b", "  oi  ", cofre, ChaveMensagem(INSTANTE))
    assert msg.ler(cofre) == "oi"


def test_mensagem_e_imutavel(cofre):
    msg = Mensagem.criar("a", "b", "oi", cofre, ChaveMensagem(INSTANTE))
    with pytest.raises(FrozenInstanceError):
        msg.remetente = "outro"


def test_outro_cofre_nao_le_a_mensagem(cofre):
    msg = Mensagem.criar("a", "b", "segredo", cofre, ChaveMensagem(INSTANTE))
    intruso = Cofre.abrir("outra-senha-qualquer", gerar_salt())
    with pytest.raises(ConteudoIlegivelError):
        msg.ler(intruso)


def test_cadastro_valido():
    u = Usuario.cadastrar("Thiago", "Thiago", "THIAGO@exemplo.com", SENHA)
    assert u.login == "thiago"
    assert u.email == "thiago@exemplo.com"
    assert u.senha_confere(SENHA)


def test_cadastro_recusa_dados_invalidos():
    with pytest.raises(DadosDeCadastroInvalidosError):
        Usuario.cadastrar("", "Nome", "a@b.com", SENHA)
    with pytest.raises(DadosDeCadastroInvalidosError):
        Usuario.cadastrar("login", "Nome", "email-sem-arroba", SENHA)
    with pytest.raises(DadosDeCadastroInvalidosError):
        Usuario.cadastrar("login", "Nome", "a@b.com", "curta")


def test_usuario_nao_guarda_a_senha():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    assert SENHA not in repr(u)
    assert SENHA.encode() not in u.hash_senha


def test_salts_de_autenticacao_e_cofre_sao_diferentes():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    assert u.salt_autenticacao != u.salt_cofre


def test_entrar_devolve_cofre_funcional():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    with u.entrar(SENHA) as cofre:
        assert cofre.decifrar(cofre.cifrar("oi")) == "oi"


def test_entrar_com_senha_errada():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    with pytest.raises(CredenciaisInvalidasError):
        u.entrar("senha-errada-mesmo")


def test_login_em_duas_sessoes_le_as_mesmas_mensagens():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)

    primeira = u.entrar(SENHA)
    msg = Mensagem.criar("thiago", "prof", "até amanhã", primeira, ChaveMensagem(INSTANTE))
    primeira.fechar()

    segunda = u.entrar(SENHA)
    assert msg.ler(segunda) == "até amanhã"


def test_historico_sai_em_ordem_cronologica(cofre):
    arvore = ArvoreAVL()
    textos = ["primeira", "segunda", "terceira", "quarta"]

    for i, texto in enumerate(textos):
        instante = INSTANTE + timedelta(seconds=i)
        chave = gerar_chave(instante, lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("a", "b", texto, cofre, chave))

    lidas = [msg.ler(cofre) for _, msg in arvore.em_ordem()]
    assert lidas == textos
    arvore.validar()


def test_mensagens_no_mesmo_instante_nao_se_perdem(cofre):
    arvore = ArvoreAVL()

    for texto in ("primeira", "segunda", "terceira"):
        chave = gerar_chave(INSTANTE, lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("a", "b", texto, cofre, chave))

    assert len(arvore) == 3
    assert [m.ler(cofre) for _, m in arvore.em_ordem()] == [
        "primeira",
        "segunda",
        "terceira",
    ]


def test_busca_por_dia_usa_intervalo(cofre):
    arvore = ArvoreAVL()
    for dia in (10, 11, 12):
        instante = datetime(2026, 9, dia, 12, 0, tzinfo=UTC)
        chave = gerar_chave(instante, lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("a", "b", f"dia {dia}", cofre, chave))

    inicio = ChaveMensagem(datetime(2026, 9, 11, 0, 0, tzinfo=UTC))
    fim = ChaveMensagem(datetime(2026, 9, 11, 23, 59, 59, tzinfo=UTC))
    achadas = [m.ler(cofre) for _, m in arvore.intervalo(inicio, fim)]
    assert achadas == ["dia 11"]


def test_mensagem_ilegivel_nao_derruba_o_historico(cofre):
    arvore = ArvoreAVL()
    for i, texto in enumerate(("ok 1", "corrompida", "ok 2")):
        instante = INSTANTE + timedelta(seconds=i)
        chave = gerar_chave(instante, lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("a", "b", texto, cofre, chave))

    alvo = ChaveMensagem(INSTANTE + timedelta(seconds=1))
    original = arvore.buscar(alvo)
    quebrada = bytearray(original.conteudo_cifrado)
    quebrada[-3] ^= 0xFF
    arvore.remover(alvo)
    arvore.inserir(alvo, Mensagem(alvo, "a", "b", bytes(quebrada)))

    exibidas = []
    for _, msg in arvore.em_ordem():
        try:
            exibidas.append(msg.ler(cofre))
        except ConteudoIlegivelError:
            exibidas.append("[mensagem ilegível]")

    assert exibidas == ["ok 1", "[mensagem ilegível]", "ok 2"]
    arvore.validar()