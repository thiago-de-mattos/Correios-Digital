from datetime import UTC, datetime, timedelta

import pytest

from postoffice.domain.message import ChaveMensagem, Mensagem, MensagemVaziaError
from postoffice.domain.user import CredenciaisInvalidasError
from postoffice.security import keys
from postoffice.services.authentication import (
    Autenticacao,
    LoginJaExisteError,
    SessaoEncerradaError,
    UsuarioNaoEncontradoError,
)
from postoffice.services.conversation import Conversa, ParticipanteInvalidoError
from postoffice.services.keyring import Chaveiro, ContatoDesconhecidoError
from postoffice.services.messaging import (
    MARCADOR_ILEGIVEL,
    Mensageria,
    RemetenteNaoParticipaError,
)

SENHA_THIAGO = "senha-do-thiago-1"
SENHA_EMPRESA = "senha-da-empresa-1"


@pytest.fixture
def auth() -> Autenticacao:
    servico = Autenticacao()
    servico.cadastrar("thiago", "Thiago", "thiago@exemplo.com", SENHA_THIAGO)
    servico.cadastrar("empresa", "Empresa X", "contato@empresa.com", SENHA_EMPRESA)
    return servico


@pytest.fixture
def conversa() -> Conversa:
    return Conversa.criar("thiago", "empresa")


def test_conversa_normaliza_participantes():
    assert Conversa.criar("  THIAGO ", "Empresa").participantes == frozenset(
        {"thiago", "empresa"}
    )


def test_identificador_independe_da_ordem():
    assert (
        Conversa.criar("thiago", "empresa").identificador
        == Conversa.criar("empresa", "thiago").identificador
    )


def test_conversa_precisa_de_dois_participantes_diferentes():
    with pytest.raises(ParticipanteInvalidoError):
        Conversa.criar("thiago", "thiago")
    with pytest.raises(ParticipanteInvalidoError):
        Conversa.criar("thiago", "")


def test_outro_participante(conversa):
    assert conversa.outro_participante("thiago") == "empresa"
    assert conversa.outro_participante("empresa") == "thiago"
    with pytest.raises(ParticipanteInvalidoError):
        conversa.outro_participante("estranho")


def test_chaveiro_guarda_e_devolve():
    _, publica = keys.gerar_par()
    pem = keys.exportar_publica(publica)
    chaveiro = Chaveiro()
    chaveiro.adicionar("empresa", pem)

    assert "empresa" in chaveiro
    assert chaveiro.pem("empresa") == pem
    assert chaveiro.obter("empresa") is not None


def test_chaveiro_recusa_contato_desconhecido():
    with pytest.raises(ContatoDesconhecidoError):
        Chaveiro().obter("ninguem")


def test_chaveiro_recusa_chave_invalida():
    with pytest.raises(keys.ChavePublicaInvalidaError):
        Chaveiro().adicionar("empresa", b"isto nao e uma chave")


def test_chaveiro_atualiza_chave_existente():
    chaveiro = Chaveiro()
    primeira = keys.exportar_publica(keys.gerar_par()[1])
    segunda = keys.exportar_publica(keys.gerar_par()[1])

    chaveiro.adicionar("empresa", primeira)
    chaveiro.adicionar("empresa", segunda)

    assert len(chaveiro) == 1
    assert chaveiro.pem("empresa") == segunda


def test_chaveiro_lista_contatos_em_ordem():
    chaveiro = Chaveiro()
    for login in ("thiago", "ana", "empresa"):
        chaveiro.adicionar(login, keys.exportar_publica(keys.gerar_par()[1]))
    assert chaveiro.contatos() == ["ana", "empresa", "thiago"]


def test_impressao_digital_do_contato():
    chaveiro = Chaveiro()
    pem = keys.exportar_publica(keys.gerar_par()[1])
    chaveiro.adicionar("empresa", pem)
    assert chaveiro.impressao_digital("empresa") == keys.impressao_digital(pem)


def test_cadastro_alimenta_o_chaveiro(auth):
    assert auth.chaveiro.contatos() == ["empresa", "thiago"]


def test_enviar_e_ler_historico(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    servico.registrar(conversa)
    sessao = auth.entrar("thiago", SENHA_THIAGO)

    servico.enviar(conversa, "thiago", "bom dia")
    servico.enviar(conversa, "empresa", "bom dia, tudo bem?")
    servico.enviar(conversa, "thiago", "tudo, vamos ao contrato")

    historico = servico.historico(conversa, "thiago", sessao.chave_privada)
    assert [m.texto for m in historico] == [
        "bom dia",
        "bom dia, tudo bem?",
        "tudo, vamos ao contrato",
    ]
    assert [m.remetente for m in historico] == ["thiago", "empresa", "thiago"]
    assert all(m.legivel for m in historico)
    conversa.arvore.validar()


def test_os_dois_lados_leem_o_mesmo_historico(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    servico.enviar(conversa, "thiago", "segue o contrato")
    servico.enviar(conversa, "empresa", "recebido")

    thiago = auth.entrar("thiago", SENHA_THIAGO)
    empresa = auth.entrar("empresa", SENHA_EMPRESA)

    lido_thiago = [m.texto for m in servico.historico(conversa, "thiago", thiago.chave_privada)]
    lido_empresa = [
        m.texto for m in servico.historico(conversa, "empresa", empresa.chave_privada)
    ]
    assert lido_thiago == lido_empresa == ["segue o contrato", "recebido"]


def test_destinatario_e_preenchido_sozinho(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    assert servico.enviar(conversa, "thiago", "oi").destinatario == "empresa"


def test_estranho_nao_envia(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    with pytest.raises(RemetenteNaoParticipaError):
        servico.enviar(conversa, "estranho", "oi")


def test_sem_chave_do_destinatario_nao_envia(auth):
    chaveiro = Chaveiro()
    chaveiro.adicionar("thiago", auth.buscar("thiago").chave_publica)
    servico = Mensageria(chaveiro)
    with pytest.raises(ContatoDesconhecidoError):
        servico.enviar(Conversa.criar("thiago", "empresa"), "thiago", "oi")


def test_mensagem_vazia_bloqueada_pelo_servico(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    with pytest.raises(MensagemVaziaError):
        servico.enviar(conversa, "thiago", "   ")


def test_mensagens_seguidas_nao_colidem(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    sessao = auth.entrar("thiago", SENHA_THIAGO)

    for i in range(30):
        servico.enviar(conversa, "thiago", f"mensagem {i}")

    assert len(conversa) == 30
    historico = servico.historico(conversa, "thiago", sessao.chave_privada)
    assert [m.texto for m in historico] == [f"mensagem {i}" for i in range(30)]
    conversa.arvore.validar()


def test_receber_mensagem_de_outra_maquina(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    publicas = {
        "thiago": auth.chaveiro.obter("thiago"),
        "empresa": auth.chaveiro.obter("empresa"),
    }
    chave = ChaveMensagem(datetime(2026, 9, 11, 10, 0, tzinfo=UTC))
    da_rede = Mensagem.criar("empresa", "thiago", "recebi seu contrato", publicas, chave)

    servico.receber(conversa, da_rede)

    sessao = auth.entrar("thiago", SENHA_THIAGO)
    historico = servico.historico(conversa, "thiago", sessao.chave_privada)
    assert [m.texto for m in historico] == ["recebi seu contrato"]


def test_receber_recusa_remetente_de_fora(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    auth.cadastrar("invasor", "Invasor", "x@y.com", "senha-do-invasor-1")
    publicas = {
        "invasor": auth.chaveiro.obter("invasor"),
        "thiago": auth.chaveiro.obter("thiago"),
    }
    chave = ChaveMensagem(datetime(2026, 9, 11, 10, 0, tzinfo=UTC))
    forjada = Mensagem.criar("invasor", "thiago", "clique aqui", publicas, chave)

    with pytest.raises(RemetenteNaoParticipaError):
        servico.receber(conversa, forjada)


def test_buscar_por_dia(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    sessao = auth.entrar("thiago", SENHA_THIAGO)
    publicas = {
        "thiago": auth.chaveiro.obter("thiago"),
        "empresa": auth.chaveiro.obter("empresa"),
    }
    base = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)

    for dias, texto in enumerate(("dia 10", "dia 11", "dia 12")):
        chave = ChaveMensagem(base + timedelta(days=dias))
        conversa.arvore.inserir(
            chave, Mensagem.criar("thiago", "empresa", texto, publicas, chave)
        )

    achadas = servico.buscar_por_dia(
        conversa, "thiago", sessao.chave_privada, datetime(2026, 9, 11).date()
    )
    assert [m.texto for m in achadas] == ["dia 11"]


def test_buscar_em_dia_sem_mensagem(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    sessao = auth.entrar("thiago", SENHA_THIAGO)
    servico.enviar(conversa, "thiago", "oi")
    assert (
        servico.buscar_por_dia(
            conversa, "thiago", sessao.chave_privada, datetime(2020, 1, 1).date()
        )
        == []
    )


def test_excluir_mensagem(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    sessao = auth.entrar("thiago", SENHA_THIAGO)

    primeira = servico.enviar(conversa, "thiago", "erro de digitacao")
    servico.enviar(conversa, "thiago", "corrigido")
    servico.excluir(conversa, primeira.chave)

    assert len(conversa) == 1
    historico = servico.historico(conversa, "thiago", sessao.chave_privada)
    assert [m.texto for m in historico] == ["corrigido"]
    conversa.arvore.validar()


def test_intruso_com_outra_chave_ve_marcador(auth, conversa):
    servico = Mensageria(auth.chaveiro)
    servico.enviar(conversa, "thiago", "confidencial")

    privada_intrusa, _ = keys.gerar_par()
    historico = servico.historico(conversa, "thiago", privada_intrusa)

    assert historico[0].texto == MARCADOR_ILEGIVEL
    assert historico[0].legivel is False


def test_conversa_entre_reaproveita_a_mesma(auth):
    servico = Mensageria(auth.chaveiro)
    assert servico.conversa_entre("thiago", "empresa") is servico.conversa_entre(
        "empresa", "thiago"
    )


def test_conversas_de_um_usuario(auth):
    servico = Mensageria(auth.chaveiro)
    servico.conversa_entre("thiago", "empresa")
    servico.conversa_entre("thiago", "colega")
    servico.conversa_entre("empresa", "colega")

    assert len(servico.conversas_de("thiago")) == 2
    assert len(servico.conversas_de("colega")) == 2


def test_cadastro_e_login(auth):
    with auth.entrar("thiago", SENHA_THIAGO) as sessao:
        assert sessao.login == "thiago"
        assert sessao.ativa
    assert not sessao.ativa


def test_sessao_encerrada_recusa_chave(auth):
    sessao = auth.entrar("thiago", SENHA_THIAGO)
    sessao.sair()
    with pytest.raises(SessaoEncerradaError):
        _ = sessao.chave_privada


def test_login_duplicado_recusado(auth):
    with pytest.raises(LoginJaExisteError):
        auth.cadastrar("thiago", "Outro", "outro@exemplo.com", "senha-diferente-1")


def test_login_inexistente(auth):
    with pytest.raises(CredenciaisInvalidasError):
        auth.entrar("ninguem", SENHA_THIAGO)


def test_senha_errada(auth):
    with pytest.raises(CredenciaisInvalidasError):
        auth.entrar("thiago", "senha-errada-mesmo")


def test_buscar_usuario_inexistente(auth):
    with pytest.raises(UsuarioNaoEncontradoError):
        auth.buscar("ninguem")


def test_logins_saem_em_ordem_alfabetica(auth):
    auth.cadastrar("ana", "Ana", "ana@exemplo.com", "senha-da-ana-1")
    assert auth.logins() == ["ana", "empresa", "thiago"]


def test_impressao_digital_da_sessao_bate_com_o_chaveiro(auth):
    sessao = auth.entrar("thiago", SENHA_THIAGO)
    assert sessao.impressao_digital() == auth.chaveiro.impressao_digital("thiago")


def test_conversa_completa_entre_duas_maquinas():
    maquina_1 = Autenticacao()
    maquina_2 = Autenticacao()

    thiago = maquina_1.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA_THIAGO)
    empresa = maquina_2.cadastrar("empresa", "Empresa", "c@exemplo.com", SENHA_EMPRESA)

    maquina_1.chaveiro.adicionar("empresa", empresa.chave_publica)
    maquina_2.chaveiro.adicionar("thiago", thiago.chave_publica)

    sessao_1 = maquina_1.entrar("thiago", SENHA_THIAGO)
    sessao_2 = maquina_2.entrar("empresa", SENHA_EMPRESA)

    servico_1 = Mensageria(maquina_1.chaveiro)
    servico_2 = Mensageria(maquina_2.chaveiro)
    conversa_1 = servico_1.conversa_entre("thiago", "empresa")
    conversa_2 = servico_2.conversa_entre("thiago", "empresa")

    enviada = servico_1.enviar(conversa_1, "thiago", "segue o contrato em anexo")
    servico_2.receber(conversa_2, enviada)

    lido = servico_2.historico(conversa_2, "empresa", sessao_2.chave_privada)
    assert lido[0].texto == "segue o contrato em anexo"
    assert lido[0].remetente == "thiago"
    assert lido[0].legivel

    resposta = servico_2.enviar(conversa_2, "empresa", "recebido, obrigado")
    servico_1.receber(conversa_1, resposta)

    assert [
        m.texto for m in servico_1.historico(conversa_1, "thiago", sessao_1.chave_privada)
    ] == ["segue o contrato em anexo", "recebido, obrigado"]


def test_impressoes_digitais_conferem_entre_maquinas():
    maquina_1 = Autenticacao()
    maquina_2 = Autenticacao()
    thiago = maquina_1.cadastrar("thiago", "Thiago", "t@exemplo.com", SENHA_THIAGO)
    maquina_2.chaveiro.adicionar("thiago", thiago.chave_publica)

    assert maquina_2.chaveiro.impressao_digital("thiago") == thiago.impressao_digital()