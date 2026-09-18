import json
import urllib.error

import pytest

from postoffice.presentation import criar_app
from postoffice.presentation.network import (
    ClienteRede,
    EnderecoInvalidoError,
    FalhaDeRedeError,
    RespostaInvalidaError,
)
from postoffice.presentation.plot import arvore_para_svg
from postoffice.services import Autenticacao, Mensageria

SENHA = "senha-do-thiago-1"


class RedeFalsa:
    def __init__(self, maquinas=None):
        self.maquinas = maquinas or {}
        self.entregues = []
        self.cair = False

    def identidade(self, endereco):
        if self.cair:
            raise FalhaDeRedeError("não foi possível falar com a outra máquina")
        if endereco not in self.maquinas:
            raise FalhaDeRedeError(f"não foi possível falar com {endereco}")
        return self.maquinas[endereco].get("/api/identidade").get_json()

    def entregar(self, endereco, mensagem):
        if self.cair:
            raise FalhaDeRedeError("a máquina está desligada?")
        self.entregues.append((endereco, mensagem))
        if endereco in self.maquinas:
            return self.maquinas[endereco].post(
                "/api/mensagens", json={"mensagem": mensagem}
            ).get_json()
        return {"recebida": True}


def montar(tmp_path, nome, rede=None):
    app = criar_app(tmp_path / nome, rede=rede)
    app.config["TESTING"] = True
    return app


def cadastrar_e_entrar(cliente, login, nome, senha=SENHA):
    cliente.post(
        "/cadastro",
        data={"login": login, "nome": nome, "email": f"{login}@exemplo.com", "senha": senha},
        follow_redirects=True,
    )
    return cliente.post(
        "/login", data={"login": login, "senha": senha}, follow_redirects=True
    )


@pytest.fixture
def cliente(tmp_path):
    return montar(tmp_path, "maquina1").test_client()


def test_sem_login_vai_para_a_tela_de_entrada(cliente):
    resposta = cliente.get("/", follow_redirects=True)
    assert "Entrar" in resposta.get_data(as_text=True)


def test_cadastro_e_login(cliente):
    resposta = cadastrar_e_entrar(cliente, "thiago", "Thiago")
    texto = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "Conversas" in texto
    assert "thiago" in texto


def test_cadastro_recusa_senha_curta(cliente):
    resposta = cliente.post(
        "/cadastro",
        data={"login": "thiago", "nome": "T", "email": "t@e.com", "senha": "curta"},
        follow_redirects=True,
    )
    assert "pelo menos 8 caracteres" in resposta.get_data(as_text=True)


def test_login_com_senha_errada(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    cliente.get("/logout")
    resposta = cliente.post(
        "/login", data={"login": "thiago", "senha": "errada-mesmo"}, follow_redirects=True
    )
    assert "login ou senha incorretos" in resposta.get_data(as_text=True)


def test_logout_descarta_a_chave(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    resposta = cliente.get("/logout", follow_redirects=True)
    assert "chave privada foi descartada" in resposta.get_data(as_text=True)
    assert "Entrar" in cliente.get("/", follow_redirects=True).get_data(as_text=True)


def test_api_identidade_expoe_a_chave_publica(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    dados = cliente.get("/api/identidade").get_json()

    assert dados["login"] == "thiago"
    assert dados["chave_publica"].startswith("-----BEGIN PUBLIC KEY-----")
    assert len(dados["impressao_digital"].split(" ")) == 8


def test_api_identidade_sem_usuario(cliente):
    assert cliente.get("/api/identidade").status_code == 404


def test_descobrir_e_adicionar_contato(tmp_path):
    outra = montar(tmp_path, "maquina2").test_client()
    cadastrar_e_entrar(outra, "empresa", "Empresa X", "senha-da-empresa-1")

    rede = RedeFalsa({"192.168.0.15:5000": outra})
    cliente = montar(tmp_path, "maquina1", rede=rede).test_client()
    cadastrar_e_entrar(cliente, "thiago", "Thiago")

    achado = cliente.post(
        "/contatos", data={"acao": "descobrir", "endereco": "192.168.0.15:5000"}
    )
    texto = achado.get_data(as_text=True)
    assert "empresa" in texto
    assert "Confira antes de adicionar" in texto

    identidade = outra.get("/api/identidade").get_json()
    confirmado = cliente.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "192.168.0.15:5000",
            "chave_publica": identidade["chave_publica"],
        },
        follow_redirects=True,
    )
    assert "empresa adicionado ao chaveiro" in confirmado.get_data(as_text=True)


def test_descobrir_maquina_desligada(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    cliente.application.config["APLICACAO"].rede = RedeFalsa()
    resposta = cliente.post(
        "/contatos", data={"acao": "descobrir", "endereco": "192.168.0.99:5000"}
    )
    assert "não foi possível falar" in resposta.get_data(as_text=True)


def test_conversa_completa_entre_duas_maquinas(tmp_path):
    app_empresa = montar(tmp_path, "maquina2")
    empresa = app_empresa.test_client()
    cadastrar_e_entrar(empresa, "empresa", "Empresa X", "senha-da-empresa-1")

    rede = RedeFalsa({"127.0.0.1:5001": empresa})
    app_thiago = montar(tmp_path, "maquina1", rede=rede)
    thiago = app_thiago.test_client()
    cadastrar_e_entrar(thiago, "thiago", "Thiago")

    identidade_empresa = empresa.get("/api/identidade").get_json()
    identidade_thiago = thiago.get("/api/identidade").get_json()

    thiago.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "127.0.0.1:5001",
            "chave_publica": identidade_empresa["chave_publica"],
        },
        follow_redirects=True,
    )
    empresa.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "thiago",
            "endereco": "127.0.0.1:5000",
            "chave_publica": identidade_thiago["chave_publica"],
        },
        follow_redirects=True,
    )

    enviada = thiago.post(
        "/conversa/empresa", data={"texto": "segue o contrato"}, follow_redirects=True
    )
    assert "segue o contrato" in enviada.get_data(as_text=True)
    assert len(rede.entregues) == 1

    recebida = empresa.get("/conversa/thiago").get_data(as_text=True)
    assert "segue o contrato" in recebida
    assert "mensagem ilegível" not in recebida


def test_envio_para_contato_sem_endereco(cliente, tmp_path):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    outra = montar(tmp_path, "maquina3").test_client()
    cadastrar_e_entrar(outra, "empresa", "Empresa", "senha-da-empresa-1")
    identidade = outra.get("/api/identidade").get_json()

    cliente.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "",
            "chave_publica": identidade["chave_publica"],
        },
        follow_redirects=True,
    )
    resposta = cliente.post(
        "/conversa/empresa", data={"texto": "oi"}, follow_redirects=True
    )
    texto = resposta.get_data(as_text=True)
    assert "não tem endereço cadastrado" in texto
    assert "oi" in texto


def test_mensagem_vazia_e_recusada(cliente, tmp_path):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    outra = montar(tmp_path, "maquina4").test_client()
    cadastrar_e_entrar(outra, "empresa", "Empresa", "senha-da-empresa-1")
    cliente.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "",
            "chave_publica": outra.get("/api/identidade").get_json()["chave_publica"],
        },
        follow_redirects=True,
    )
    resposta = cliente.post(
        "/conversa/empresa", data={"texto": "   "}, follow_redirects=True
    )
    assert "não pode ser vazia" in resposta.get_data(as_text=True)


def test_conversa_com_contato_desconhecido(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    resposta = cliente.get("/conversa/ninguem", follow_redirects=True)
    assert "não está no chaveiro" in resposta.get_data(as_text=True)


def test_api_recusa_remetente_desconhecido(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    resposta = cliente.post(
        "/api/mensagens",
        json={
            "mensagem": {
                "instante": "2026-09-11T14:30:00+00:00",
                "sequencia": 0,
                "remetente": "invasor",
                "destinatario": "thiago",
                "conteudo": "AAAA",
                "envelopes": {},
            }
        },
    )
    assert resposta.status_code == 403


def test_api_recusa_formato_invalido(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    resposta = cliente.post("/api/mensagens", json={"mensagem": {"instante": "lixo"}})
    assert resposta.status_code == 400


def test_dados_sobrevivem_ao_reinicio(tmp_path):
    pasta = tmp_path / "maquina1"
    primeira = criar_app(pasta).test_client()
    cadastrar_e_entrar(primeira, "thiago", "Thiago")

    segunda = criar_app(pasta).test_client()
    resposta = segunda.post(
        "/login", data={"login": "thiago", "senha": SENHA}, follow_redirects=True
    )
    assert "Conversas" in resposta.get_data(as_text=True)


def test_tela_de_backup(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    assert "Exportar" in cliente.get("/backup").get_data(as_text=True)


def test_exportar_pelo_navegador(cliente, tmp_path):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    destino = tmp_path / "pendrive"
    destino.mkdir()

    resposta = cliente.post(
        "/backup", data={"acao": "exportar", "destino": str(destino)}, follow_redirects=True
    )
    assert "Backup gravado" in resposta.get_data(as_text=True)
    assert list(destino.glob("*.zip"))


def test_tela_da_arvore(cliente, tmp_path):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    outra = montar(tmp_path, "maquina5").test_client()
    cadastrar_e_entrar(outra, "empresa", "Empresa", "senha-da-empresa-1")
    cliente.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "",
            "chave_publica": outra.get("/api/identidade").get_json()["chave_publica"],
        },
        follow_redirects=True,
    )
    for i in range(5):
        cliente.post("/conversa/empresa", data={"texto": f"mensagem {i}"})

    resposta = cliente.get("/arvore/empresa")
    texto = resposta.get_data(as_text=True)
    assert "<svg" in texto
    assert "altura da AVL" in texto


def test_svg_de_arvore_vazia():
    from postoffice.structures import ArvoreAVL

    assert "Nenhuma mensagem" in arvore_para_svg(ArvoreAVL())


def test_svg_desenha_um_no_por_mensagem():
    auth = Autenticacao()
    auth.cadastrar("thiago", "T", "t@e.com", SENHA)
    auth.cadastrar("empresa", "E", "c@e.com", "senha-da-empresa-1")
    servico = Mensageria(auth.chaveiro)
    conversa = servico.conversa_entre("thiago", "empresa")
    for i in range(6):
        servico.enviar(conversa, "thiago", f"mensagem {i}")

    svg = arvore_para_svg(conversa.arvore)
    assert svg.count("<circle") == 6
    assert svg.count("<line") == 5


def test_cliente_de_rede_trata_maquina_fora_do_ar():
    def recusar(_requisicao, _tempo):
        raise urllib.error.URLError("conexão recusada")

    with pytest.raises(FalhaDeRedeError):
        ClienteRede(abrir=recusar).identidade("192.168.0.99:5000")


def test_cliente_de_rede_trata_resposta_estranha():
    def responder_html(_requisicao, _tempo):
        return b"<html>nao sou uma api</html>"

    with pytest.raises(RespostaInvalidaError):
        ClienteRede(abrir=responder_html).identidade("192.168.0.15:5000")


def test_cliente_de_rede_monta_a_url():
    vistas = []

    def espiar(requisicao, _tempo):
        vistas.append(requisicao.full_url)
        return json.dumps({"login": "empresa", "chave_publica": "x"}).encode()

    ClienteRede(abrir=espiar).identidade("192.168.0.15:5000/")
    assert vistas == ["http://192.168.0.15:5000/api/identidade"]


def test_impressao_digital_colada_no_lugar_do_endereco(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    cliente.application.config["APLICACAO"].rede = ClienteRede()

    resposta = cliente.post(
        "/contatos",
        data={"acao": "descobrir", "endereco": "CA65 95AA 4A23 544E 1DA4 9057 9AA9 046C"},
    )

    assert resposta.status_code == 200
    assert "não parece um endereço de máquina" in resposta.get_data(as_text=True)


def test_endereco_vazio_avisa_em_vez_de_quebrar(cliente):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    cliente.application.config["APLICACAO"].rede = ClienteRede()

    resposta = cliente.post("/contatos", data={"acao": "descobrir", "endereco": "   "})

    assert resposta.status_code == 200
    assert "Informe o endereço" in resposta.get_data(as_text=True)


def test_endereco_com_caracteres_de_controle_e_recusado():
    with pytest.raises(EnderecoInvalidoError):
        ClienteRede().identidade("192.168.0.15:5000\ncom quebra de linha")


def test_endereco_valido_passa_da_validacao():
    vistas = []

    def espiar(requisicao, _tempo):
        vistas.append(requisicao.full_url)
        return json.dumps({"login": "empresa", "chave_publica": "x"}).encode()

    ClienteRede(abrir=espiar).identidade("http://192.168.0.15:5000")
    assert vistas == ["http://192.168.0.15:5000/api/identidade"]


def test_trilha_de_navegacao_na_arvore(cliente, tmp_path):
    cadastrar_e_entrar(cliente, "thiago", "Thiago")
    outra = montar(tmp_path, "maquina6").test_client()
    cadastrar_e_entrar(outra, "empresa", "Empresa", "senha-da-empresa-1")
    cliente.post(
        "/contatos",
        data={
            "acao": "confirmar",
            "login": "empresa",
            "endereco": "",
            "chave_publica": outra.get("/api/identidade").get_json()["chave_publica"],
        },
        follow_redirects=True,
    )

    texto = cliente.get("/arvore/empresa").get_data(as_text=True)
    assert 'class="trilha"' in texto
    assert "Conversa com empresa" in texto