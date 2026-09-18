import json
import smtplib
import zipfile
from pathlib import Path

import pytest

from postoffice.persistence.backup import (
    BackupInvalidoError,
    PastaDeDadosVaziaError,
    conferir,
    exportar,
    importar,
    nome_sugerido,
)
from postoffice.persistence.mailer import (
    BackupNaoEncontradoError,
    ConfiguracaoEmail,
    FalhaNoEnvioError,
    enviar_backup,
)
from postoffice.persistence.repository import (
    ArquivoCorrompidoError,
    ConversaNaoEncontradaError,
    Repositorio,
)
from postoffice.persistence.serializer import (
    FormatoInvalidoError,
    dicionario_para_mensagem,
    mensagem_para_dicionario,
)
from postoffice.services import Autenticacao, Mensageria

SENHA_THIAGO = "senha-do-thiago-1"
SENHA_EMPRESA = "senha-da-empresa-1"


@pytest.fixture
def sistema():
    auth = Autenticacao()
    auth.cadastrar("thiago", "Thiago", "thiago@exemplo.com", SENHA_THIAGO)
    auth.cadastrar("empresa", "Empresa X", "contato@empresa.com", SENHA_EMPRESA)
    sessao = auth.entrar("thiago", SENHA_THIAGO)
    servico = Mensageria(auth.chaveiro)
    conversa = servico.conversa_entre("thiago", "empresa")
    servico.enviar(conversa, "thiago", "segue o contrato")
    servico.enviar(conversa, "empresa", "recebido, vou analisar")
    servico.enviar(conversa, "thiago", "obrigado")
    return auth, sessao, servico, conversa


@pytest.fixture
def repo(tmp_path) -> Repositorio:
    return Repositorio(tmp_path / "dados")


def test_mensagem_vai_e_volta_pelo_dicionario(sistema):
    _, sessao, _, conversa = sistema
    _, original = next(iter(conversa.arvore.em_ordem()))

    copia = dicionario_para_mensagem(mensagem_para_dicionario(original))

    assert copia.chave == original.chave
    assert copia.remetente == original.remetente
    assert copia.ler("thiago", sessao.chave_privada) == original.ler(
        "thiago", sessao.chave_privada
    )


def test_dicionario_invalido_e_recusado():
    with pytest.raises(FormatoInvalidoError):
        dicionario_para_mensagem({"instante": "nao e uma data"})


def test_usuarios_vao_e_voltam(sistema, repo):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)

    recuperados = repo.carregar_usuarios()
    assert [login for login, _ in recuperados.em_ordem()] == ["empresa", "thiago"]
    assert recuperados.buscar("thiago").senha_confere(SENHA_THIAGO)
    recuperados.validar()


def test_usuario_recuperado_ainda_abre_a_chave_privada(sistema, repo):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)

    thiago = repo.carregar_usuarios().buscar("thiago")
    assert thiago.abrir_chave_privada(SENHA_THIAGO) is not None


def test_carregar_de_pasta_vazia_devolve_arvore_vazia(repo):
    assert len(repo.carregar_usuarios()) == 0
    assert len(repo.carregar_chaveiro()) == 0


def test_chaveiro_vai_e_volta(sistema, repo):
    auth, _, _, _ = sistema
    repo.salvar_chaveiro(auth.chaveiro)

    recuperado = repo.carregar_chaveiro()
    assert recuperado.contatos() == ["empresa", "thiago"]
    assert recuperado.impressao_digital("thiago") == auth.chaveiro.impressao_digital(
        "thiago"
    )


def test_conversa_vai_e_volta(sistema, repo):
    _, sessao, servico, conversa = sistema
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    recuperada = repo.carregar_conversa("thiago", conversa.identificador, sessao.cofre)

    assert len(recuperada) == len(conversa)
    assert recuperada.participantes == conversa.participantes
    lidas = [m.texto for m in servico.historico(recuperada, "thiago", sessao.chave_privada)]
    assert lidas == ["segue o contrato", "recebido, vou analisar", "obrigado"]
    recuperada.arvore.validar()


def test_pre_ordem_preserva_a_forma_da_arvore(sistema, repo):
    _, sessao, _, conversa = sistema
    repo.salvar_conversa("thiago", conversa, sessao.cofre)
    recuperada = repo.carregar_conversa("thiago", conversa.identificador, sessao.cofre)

    antes = [str(chave) for chave, _ in conversa.arvore.pre_ordem()]
    depois = [str(chave) for chave, _ in recuperada.arvore.pre_ordem()]
    assert antes == depois


def test_arquivo_de_conversa_fica_ilegivel_em_disco(sistema, repo):
    _, sessao, _, conversa = sistema
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    bruto = repo.caminho_da_conversa("thiago", conversa.identificador).read_bytes()
    assert b"contrato" not in bruto
    assert b"thiago" not in bruto


def test_senha_errada_nao_abre_a_conversa(sistema, repo):
    auth, sessao, _, conversa = sistema
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    intrusa = auth.entrar("empresa", SENHA_EMPRESA)
    with pytest.raises(ArquivoCorrompidoError):
        repo.carregar_conversa("thiago", conversa.identificador, intrusa.cofre)


def test_arquivo_adulterado_e_detectado(sistema, repo):
    _, sessao, _, conversa = sistema
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    caminho = repo.caminho_da_conversa("thiago", conversa.identificador)
    dados = bytearray(caminho.read_bytes())
    dados[-5] ^= 0xFF
    caminho.write_bytes(bytes(dados))

    with pytest.raises(ArquivoCorrompidoError):
        repo.carregar_conversa("thiago", conversa.identificador, sessao.cofre)


def test_conversa_inexistente(sistema, repo):
    _, sessao, _, _ = sistema
    with pytest.raises(ConversaNaoEncontradaError):
        repo.carregar_conversa("thiago", "ninguem-ninguem", sessao.cofre)


def test_json_invalido_no_arquivo_de_usuarios(repo):
    repo.arquivo_usuarios.parent.mkdir(parents=True, exist_ok=True)
    repo.arquivo_usuarios.write_text("{isto nao e json", encoding="utf-8")
    with pytest.raises(ArquivoCorrompidoError):
        repo.carregar_usuarios()


def test_json_sem_a_chave_esperada(repo):
    repo.arquivo_usuarios.parent.mkdir(parents=True, exist_ok=True)
    repo.arquivo_usuarios.write_text(json.dumps({"outra": []}), encoding="utf-8")
    with pytest.raises(ArquivoCorrompidoError):
        repo.carregar_usuarios()


def test_listar_conversas_salvas(sistema, repo):
    _, sessao, servico, conversa = sistema
    outra = servico.conversa_entre("thiago", "empresa")
    repo.salvar_conversa("thiago", conversa, sessao.cofre)
    repo.salvar_conversa("thiago", outra, sessao.cofre)

    assert repo.conversas_salvas("thiago") == ["empresa-thiago"]
    assert repo.conversas_salvas("ninguem") == []


def test_ciclo_completo_de_reinicio(sistema, repo):
    auth, sessao, _, conversa = sistema
    repo.salvar_usuarios(auth.usuarios)
    repo.salvar_chaveiro(auth.chaveiro)
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    outra_execucao = Autenticacao.restaurar(
        repo.carregar_usuarios(), repo.carregar_chaveiro()
    )
    nova_sessao = outra_execucao.entrar("thiago", SENHA_THIAGO)
    servico = Mensageria(outra_execucao.chaveiro)
    recuperadas = repo.carregar_conversas("thiago", nova_sessao.cofre)

    assert len(recuperadas) == 1
    historico = servico.historico(recuperadas[0], "thiago", nova_sessao.chave_privada)
    assert [m.texto for m in historico] == [
        "segue o contrato",
        "recebido, vou analisar",
        "obrigado",
    ]
    assert all(m.legivel for m in historico)


def test_exportar_gera_zip(sistema, repo, tmp_path):
    auth, sessao, _, conversa = sistema
    repo.salvar_usuarios(auth.usuarios)
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    destino = exportar(repo.pasta, tmp_path / "backup.zip")

    assert destino.exists()
    with zipfile.ZipFile(destino) as pacote:
        nomes = pacote.namelist()
    assert "usuarios.json" in nomes
    assert "thiago/conversas/empresa-thiago.cofre" in nomes


def test_exportar_para_pasta_usa_nome_com_data(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)

    pendrive = tmp_path / "pendrive"
    pendrive.mkdir()
    destino = exportar(repo.pasta, pendrive)

    assert destino.parent == pendrive
    assert destino.name.startswith("correios-digital-")
    assert destino.suffix == ".zip"


def test_nome_sugerido_tem_data():
    assert nome_sugerido().endswith(".zip")
    assert len(nome_sugerido()) > len("correios-digital-.zip")


def test_exportar_pasta_inexistente(tmp_path):
    with pytest.raises(PastaDeDadosVaziaError):
        exportar(tmp_path / "nao-existe", tmp_path / "backup.zip")


def test_exportar_sem_usuarios(tmp_path):
    vazia = tmp_path / "dados"
    vazia.mkdir()
    with pytest.raises(PastaDeDadosVaziaError):
        exportar(vazia, tmp_path / "backup.zip")


def test_conferir_backup_valido(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    destino = exportar(repo.pasta, tmp_path / "backup.zip")

    assert "usuarios.json" in conferir(destino)


def test_conferir_arquivo_que_nao_e_zip(tmp_path):
    falso = tmp_path / "backup.zip"
    falso.write_bytes(b"isto nao e um zip")
    with pytest.raises(BackupInvalidoError):
        conferir(falso)


def test_conferir_zip_de_outra_coisa(tmp_path):
    intruso = tmp_path / "outro.zip"
    with zipfile.ZipFile(intruso, "w") as pacote:
        pacote.writestr("foto.jpg", "conteudo")
    with pytest.raises(BackupInvalidoError):
        conferir(intruso)


def test_importar_restaura_tudo(sistema, repo, tmp_path):
    auth, sessao, _, conversa = sistema
    repo.salvar_usuarios(auth.usuarios)
    repo.salvar_chaveiro(auth.chaveiro)
    repo.salvar_conversa("thiago", conversa, sessao.cofre)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    outra_maquina = Repositorio(tmp_path / "outra")
    importar(pacote, outra_maquina.pasta)

    restaurada = Autenticacao.restaurar(
        outra_maquina.carregar_usuarios(), outra_maquina.carregar_chaveiro()
    )
    nova_sessao = restaurada.entrar("thiago", SENHA_THIAGO)
    recuperada = outra_maquina.carregar_conversa(
        "thiago", conversa.identificador, nova_sessao.cofre
    )
    assert len(recuperada) == 3


def test_importar_recusa_pasta_ocupada(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    with pytest.raises(BackupInvalidoError):
        importar(pacote, repo.pasta)


def test_importar_substituindo(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    importar(pacote, repo.pasta, substituir=True)
    assert len(repo.carregar_usuarios()) == 2


def test_enviar_backup_monta_anexo(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    enviados = []
    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")

    enviar_backup(
        config,
        pacote,
        "contato@empresa.com",
        entregar=lambda _c, mensagem: enviados.append(mensagem),
    )

    assert len(enviados) == 1
    mensagem = enviados[0]
    assert mensagem["To"] == "contato@empresa.com"
    anexos = [p for p in mensagem.iter_attachments()]
    assert anexos[0].get_filename() == "backup.zip"


def test_config_nao_vaza_a_senha():
    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")
    assert "segredo" not in repr(config)


def test_falha_de_rede_vira_erro_tratado(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    def cair(_config, _mensagem):
        raise OSError("sem conexão")

    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")
    with pytest.raises(FalhaNoEnvioError) as erro:
        enviar_backup(config, pacote, "contato@empresa.com", entregar=cair)
    assert "backup local continua salvo" in str(erro.value)


def test_senha_recusada_pelo_servidor(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    def recusar(_config, _mensagem):
        raise smtplib.SMTPAuthenticationError(535, b"credenciais invalidas")

    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "errada")
    with pytest.raises(FalhaNoEnvioError) as erro:
        enviar_backup(config, pacote, "contato@empresa.com", entregar=recusar)
    assert "senha de aplicativo" in str(erro.value)


def test_enviar_backup_inexistente(tmp_path):
    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")
    with pytest.raises(BackupNaoEncontradoError):
        enviar_backup(config, tmp_path / "nao-existe.zip", "a@b.com", entregar=lambda *_: None)


def test_destinatario_invalido(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    pacote = exportar(repo.pasta, tmp_path / "backup.zip")

    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")
    with pytest.raises(ValueError):
        enviar_backup(config, pacote, "isto-nao-e-email", entregar=lambda *_: None)


def test_backup_nao_leva_arquivos_temporarios(sistema, repo, tmp_path):
    auth, _, _, _ = sistema
    repo.salvar_usuarios(auth.usuarios)
    (repo.pasta / "sobra.tmp").write_text("lixo", encoding="utf-8")

    pacote = exportar(repo.pasta, tmp_path / "backup.zip")
    assert not any(Path(n).suffix == ".tmp" for n in conferir(pacote))