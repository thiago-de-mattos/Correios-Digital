from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from postoffice.domain.message import (
    ChaveMensagem,
    DestinatarioSemChaveError,
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
from postoffice.security import keys
from postoffice.security.vault import ConteudoIlegivelError
from postoffice.structures import ArvoreAVL

SENHA = "senha-de-teste-123"
MOMENTO = datetime(2026, 9, 11, 14, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def par_thiago():
    return keys.gerar_par()


@pytest.fixture(scope="module")
def par_empresa():
    return keys.gerar_par()


@pytest.fixture
def publicas(par_thiago, par_empresa):
    return {"thiago": par_thiago[1], "empresa": par_empresa[1]}


@pytest.fixture
def privada_thiago(par_thiago):
    return par_thiago[0]


@pytest.fixture
def privada_empresa(par_empresa):
    return par_empresa[0]


def test_chaves_ordenam_por_instante():
    assert ChaveMensagem(MOMENTO) < ChaveMensagem(MOMENTO + timedelta(seconds=1))


def test_contador_desempata_mesmo_instante():
    primeira = ChaveMensagem(MOMENTO)
    segunda = primeira.proxima()
    assert primeira < segunda
    assert segunda.instante == primeira.instante
    assert segunda.sequencia == 1


def test_gerar_chave_pula_as_ocupadas():
    ocupadas = {ChaveMensagem(MOMENTO, 0), ChaveMensagem(MOMENTO, 1)}
    assert gerar_chave(MOMENTO, ocupadas.__contains__) == ChaveMensagem(MOMENTO, 2)


def test_agora_tem_fuso():
    assert agora().tzinfo is not None


def test_remetente_le_a_propria_mensagem(publicas, privada_thiago):
    m = Mensagem.criar("thiago", "empresa", "bom dia", publicas, ChaveMensagem(MOMENTO))
    assert m.ler("thiago", privada_thiago) == "bom dia"


def test_destinatario_le_a_mensagem(publicas, privada_empresa):
    m = Mensagem.criar("thiago", "empresa", "bom dia", publicas, ChaveMensagem(MOMENTO))
    assert m.ler("empresa", privada_empresa) == "bom dia"


def test_mensagem_tem_um_envelope_para_cada_lado(publicas):
    m = Mensagem.criar("thiago", "empresa", "oi", publicas, ChaveMensagem(MOMENTO))
    assert set(m.chaves_cifradas) == {"thiago", "empresa"}
    assert m.destinada_a("thiago")
    assert not m.destinada_a("estranho")


def test_estranho_nao_le(publicas):
    m = Mensagem.criar("thiago", "empresa", "segredo", publicas, ChaveMensagem(MOMENTO))
    outra_privada, _ = keys.gerar_par()
    with pytest.raises(ConteudoIlegivelError):
        m.ler("estranho", outra_privada)


def test_chave_privada_errada_nao_le(publicas):
    m = Mensagem.criar("thiago", "empresa", "segredo", publicas, ChaveMensagem(MOMENTO))
    outra_privada, _ = keys.gerar_par()
    with pytest.raises(ConteudoIlegivelError):
        m.ler("thiago", outra_privada)


def test_mensagem_guarda_conteudo_cifrado(publicas):
    m = Mensagem.criar(
        "thiago", "empresa", "contrato vence dia 30", publicas, ChaveMensagem(MOMENTO)
    )
    assert b"contrato" not in m.conteudo_cifrado


def test_repr_nao_vaza_conteudo(publicas):
    m = Mensagem.criar(
        "thiago", "empresa", "assunto sigiloso", publicas, ChaveMensagem(MOMENTO)
    )
    assert "sigiloso" not in repr(m)


def test_mensagem_vazia_e_bloqueada(publicas):
    with pytest.raises(MensagemVaziaError):
        Mensagem.criar("thiago", "empresa", "", publicas, ChaveMensagem(MOMENTO))
    with pytest.raises(MensagemVaziaError):
        Mensagem.criar("thiago", "empresa", "   ", publicas, ChaveMensagem(MOMENTO))


def test_sem_a_chave_publica_nao_da_para_enviar(par_thiago):
    with pytest.raises(DestinatarioSemChaveError):
        Mensagem.criar(
            "thiago", "empresa", "oi", {"thiago": par_thiago[1]}, ChaveMensagem(MOMENTO)
        )


def test_espacos_das_pontas_sao_removidos(publicas, privada_thiago):
    m = Mensagem.criar("thiago", "empresa", "  oi  ", publicas, ChaveMensagem(MOMENTO))
    assert m.ler("thiago", privada_thiago) == "oi"


def test_mensagem_e_imutavel(publicas):
    m = Mensagem.criar("thiago", "empresa", "oi", publicas, ChaveMensagem(MOMENTO))
    with pytest.raises(FrozenInstanceError):
        m.remetente = "outro"


def test_cada_mensagem_usa_uma_chave_nova(publicas):
    primeira = Mensagem.criar("thiago", "empresa", "oi", publicas, ChaveMensagem(MOMENTO))
    segunda = Mensagem.criar(
        "thiago", "empresa", "oi", publicas, ChaveMensagem(MOMENTO + timedelta(seconds=1))
    )
    assert primeira.chaves_cifradas["thiago"] != segunda.chaves_cifradas["thiago"]
    assert primeira.conteudo_cifrado != segunda.conteudo_cifrado


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


def test_cadastro_gera_par_de_chaves():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    assert u.chave_publica.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert u.chave_privada_cifrada.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")


def test_chave_privada_so_abre_com_a_senha():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    assert u.abrir_chave_privada(SENHA) is not None
    with pytest.raises(CredenciaisInvalidasError):
        u.abrir_chave_privada("senha-errada-mesmo")


def test_cada_usuario_tem_impressao_digital_propria():
    um = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    outro = Usuario.cadastrar("empresa", "Empresa", "c@exemplo.com", SENHA)
    assert um.impressao_digital() != outro.impressao_digital()


def test_entrar_devolve_cofre_pessoal():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    with u.entrar(SENHA) as cofre:
        assert cofre.decifrar(cofre.cifrar("oi")) == "oi"


def test_entrar_com_senha_errada():
    u = Usuario.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA)
    with pytest.raises(CredenciaisInvalidasError):
        u.entrar("senha-errada-mesmo")


def test_historico_sai_em_ordem_cronologica(publicas, privada_thiago):
    arvore = ArvoreAVL()
    textos = ["primeira", "segunda", "terceira", "quarta"]

    for i, texto in enumerate(textos):
        chave = gerar_chave(MOMENTO + timedelta(seconds=i), lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("thiago", "empresa", texto, publicas, chave))

    assert [m.ler("thiago", privada_thiago) for _, m in arvore.em_ordem()] == textos
    arvore.validar()


def test_mensagens_no_mesmo_instante_nao_se_perdem(publicas, privada_thiago):
    arvore = ArvoreAVL()
    for texto in ("primeira", "segunda", "terceira"):
        chave = gerar_chave(MOMENTO, lambda c: c in arvore)
        arvore.inserir(chave, Mensagem.criar("thiago", "empresa", texto, publicas, chave))

    assert len(arvore) == 3
    assert [m.ler("thiago", privada_thiago) for _, m in arvore.em_ordem()] == [
        "primeira",
        "segunda",
        "terceira",
    ]


def test_busca_por_dia_usa_intervalo(publicas, privada_thiago):
    arvore = ArvoreAVL()
    for dia in (10, 11, 12):
        instante = datetime(2026, 9, dia, 12, 0, tzinfo=UTC)
        chave = gerar_chave(instante, lambda c: c in arvore)
        arvore.inserir(
            chave, Mensagem.criar("thiago", "empresa", f"dia {dia}", publicas, chave)
        )

    inicio = ChaveMensagem(datetime(2026, 9, 11, 0, 0, tzinfo=UTC))
    fim = ChaveMensagem(datetime(2026, 9, 11, 23, 59, 59, tzinfo=UTC))
    achadas = [m.ler("thiago", privada_thiago) for _, m in arvore.intervalo(inicio, fim)]
    assert achadas == ["dia 11"]