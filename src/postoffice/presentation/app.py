from __future__ import annotations

import secrets
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from postoffice.domain.message import Mensagem
from postoffice.domain.user import CredenciaisInvalidasError, DadosDeCadastroInvalidosError
from postoffice.persistence.backup import (
    BackupInvalidoError,
    PastaDeDadosVaziaError,
    exportar,
    importar,
)
from postoffice.persistence.mailer import (
    ConfiguracaoEmail,
    FalhaNoEnvioError,
    enviar_backup,
)
from postoffice.persistence.repository import ArquivoCorrompidoError, Repositorio
from postoffice.persistence.serializer import (
    FormatoInvalidoError,
    dicionario_para_mensagem,
    mensagem_para_dicionario,
)
from postoffice.presentation.network import (
    ClienteRede,
    FalhaDeRedeError,
    RespostaInvalidaError,
)
from postoffice.presentation.plot import arvore_para_svg
from postoffice.services.authentication import Autenticacao, LoginJaExisteError, Sessao
from postoffice.services.conversation import Conversa
from postoffice.services.keyring import ContatoDesconhecidoError
from postoffice.services.messaging import Mensageria, RemetenteNaoParticipaError

PASTA_PADRAO = Path("dados")


class Aplicacao:
    def __init__(self, pasta: str | Path = PASTA_PADRAO, rede: ClienteRede | None = None):
        self.repositorio = Repositorio(pasta)
        self.autenticacao = Autenticacao.restaurar(
            self.repositorio.carregar_usuarios(), self.repositorio.carregar_chaveiro()
        )
        self.mensageria = Mensageria(self.autenticacao.chaveiro)
        self.rede = rede if rede is not None else ClienteRede()
        self.sessoes: dict[str, Sessao] = {}

    def gravar_cadastro(self) -> None:
        self.repositorio.salvar_usuarios(self.autenticacao.usuarios)
        self.repositorio.salvar_chaveiro(self.autenticacao.chaveiro)

    def gravar_conversa(self, sessao: Sessao, conversa: Conversa) -> None:
        self.repositorio.salvar_conversa(sessao.login, conversa, sessao.cofre)

    def carregar_conversas(self, sessao: Sessao) -> None:
        for conversa in self.repositorio.carregar_conversas(sessao.login, sessao.cofre):
            self.mensageria.registrar(conversa)


def criar_app(pasta: str | Path = PASTA_PADRAO, rede: ClienteRede | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config["APLICACAO"] = Aplicacao(pasta, rede)

    def aplicacao() -> Aplicacao:
        return app.config["APLICACAO"]

    def sessao_atual() -> Sessao | None:
        identificador = session.get("sessao")
        if identificador is None:
            return None
        return aplicacao().sessoes.get(identificador)

    def exigir_sessao() -> Sessao:
        sessao = sessao_atual()
        if sessao is None or not sessao.ativa:
            abort(redirect(url_for("login")))
        return sessao

    @app.context_processor
    def variaveis_do_template():
        sessao = sessao_atual()
        return {
            "sessao": sessao,
            "contatos": aplicacao().autenticacao.chaveiro.todos() if sessao else [],
        }

    # ------------------------------------------------------------------ contas

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            try:
                aplicacao().autenticacao.cadastrar(
                    request.form.get("login", ""),
                    request.form.get("nome", ""),
                    request.form.get("email", ""),
                    request.form.get("senha", ""),
                )
                aplicacao().gravar_cadastro()
                flash("Conta criada. Agora é só entrar.", "sucesso")
                return redirect(url_for("login"))
            except (DadosDeCadastroInvalidosError, LoginJaExisteError) as erro:
                flash(str(erro), "erro")

        return render_template("cadastro.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            try:
                nova = aplicacao().autenticacao.entrar(
                    request.form.get("login", ""), request.form.get("senha", "")
                )
            except CredenciaisInvalidasError as erro:
                flash(str(erro), "erro")
                return render_template("login.html")

            identificador = secrets.token_hex(16)
            aplicacao().sessoes[identificador] = nova
            session["sessao"] = identificador

            try:
                aplicacao().carregar_conversas(nova)
            except ArquivoCorrompidoError as erro:
                flash(f"Algumas conversas não puderam ser abertas: {erro}", "erro")

            return redirect(url_for("inicio"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        identificador = session.pop("sessao", None)
        if identificador is not None:
            guardada = aplicacao().sessoes.pop(identificador, None)
            if guardada is not None:
                guardada.sair()
        flash("Você saiu. A chave privada foi descartada da memória.", "sucesso")
        return redirect(url_for("login"))

    # ------------------------------------------------------------------ telas

    @app.route("/")
    def inicio():
        sessao = exigir_sessao()
        conversas = aplicacao().mensageria.conversas_de(sessao.login)
        return render_template("conversas.html", conversas=conversas)

    @app.route("/conversa/<outro>", methods=["GET", "POST"])
    def conversa(outro: str):
        sessao = exigir_sessao()
        app_ = aplicacao()

        try:
            contato = app_.autenticacao.chaveiro.contato(outro)
        except ContatoDesconhecidoError as erro:
            flash(str(erro), "erro")
            return redirect(url_for("contatos"))

        conversa = app_.mensageria.conversa_entre(sessao.login, contato.login)

        if request.method == "POST":
            texto = request.form.get("texto", "")
            try:
                mensagem = app_.mensageria.enviar(conversa, sessao.login, texto)
            except Exception as erro:
                flash(str(erro) or "não foi possível enviar", "erro")
                return redirect(url_for("conversa", outro=contato.login))

            app_.gravar_conversa(sessao, conversa)

            if contato.alcancavel:
                try:
                    app_.rede.entregar(
                        contato.endereco, mensagem_para_dicionario(mensagem)
                    )
                except (FalhaDeRedeError, RespostaInvalidaError) as erro:
                    flash(f"{erro} A mensagem ficou salva aqui.", "erro")
            else:
                flash(
                    f"{contato.login} não tem endereço cadastrado: "
                    "a mensagem ficou só nesta máquina.",
                    "erro",
                )

            return redirect(url_for("conversa", outro=contato.login))

        historico = app_.mensageria.historico(conversa, sessao.login, sessao.chave_privada)
        return render_template(
            "conversa.html", contato=contato, conversa=conversa, historico=historico
        )

    @app.route("/contatos", methods=["GET", "POST"])
    def contatos():
        sessao = exigir_sessao()
        app_ = aplicacao()
        descoberto = None

        if request.method == "POST":
            acao = request.form.get("acao", "descobrir")

            if acao == "descobrir":
                try:
                    resposta = app_.rede.identidade(request.form.get("endereco", ""))
                    descoberto = {
                        "login": resposta["login"],
                        "chave_publica": resposta["chave_publica"],
                        "endereco": request.form.get("endereco", "").strip(),
                        "impressao_digital": resposta.get("impressao_digital", ""),
                    }
                except (FalhaDeRedeError, RespostaInvalidaError) as erro:
                    flash(str(erro), "erro")

            elif acao == "confirmar":
                try:
                    contato = app_.autenticacao.chaveiro.adicionar(
                        request.form.get("login", ""),
                        request.form.get("chave_publica", "").encode("ascii"),
                        request.form.get("endereco", ""),
                    )
                    app_.gravar_cadastro()
                    flash(f"{contato.login} adicionado ao chaveiro.", "sucesso")
                    return redirect(url_for("contatos"))
                except (ValueError, UnicodeEncodeError) as erro:
                    flash(str(erro), "erro")

        return render_template(
            "contatos.html", descoberto=descoberto, eu=sessao.usuario
        )

    @app.route("/arvore/<outro>")
    def arvore(outro: str):
        sessao = exigir_sessao()
        app_ = aplicacao()
        try:
            contato = app_.autenticacao.chaveiro.contato(outro)
        except ContatoDesconhecidoError as erro:
            flash(str(erro), "erro")
            return redirect(url_for("contatos"))

        conversa = app_.mensageria.conversa_entre(sessao.login, contato.login)
        return render_template(
            "arvore.html",
            contato=contato,
            conversa=conversa,
            svg=arvore_para_svg(conversa.arvore, f"conversa com {contato.login}"),
            altura_de_lista=len(conversa),
        )

    @app.route("/backup", methods=["GET", "POST"])
    def backup():
        sessao = exigir_sessao()
        app_ = aplicacao()

        if request.method == "POST":
            acao = request.form.get("acao", "")
            destino = request.form.get("destino", "").strip()

            try:
                if acao == "exportar":
                    pacote = exportar(app_.repositorio.pasta, destino or ".")
                    flash(f"Backup gravado em {pacote}", "sucesso")

                elif acao == "importar":
                    importar(destino, app_.repositorio.pasta, substituir=True)
                    flash("Backup restaurado. Entre de novo para recarregar.", "sucesso")
                    return redirect(url_for("logout"))

                elif acao == "email":
                    config = ConfiguracaoEmail(
                        servidor=request.form.get("servidor", ""),
                        porta=int(request.form.get("porta") or 587),
                        remetente=request.form.get("remetente", ""),
                        senha=request.form.get("senha_email", ""),
                    )
                    pacote = exportar(app_.repositorio.pasta, destino or ".")
                    enviar_backup(config, pacote, request.form.get("para", ""))
                    flash("Backup enviado por e-mail.", "sucesso")

            except (
                PastaDeDadosVaziaError,
                BackupInvalidoError,
                FalhaNoEnvioError,
                ValueError,
                OSError,
            ) as erro:
                flash(str(erro), "erro")

        return render_template(
            "backup.html",
            pasta=app_.repositorio.pasta.resolve(),
            conversas=app_.repositorio.conversas_salvas(sessao.login),
        )

    # -------------------------------------------------------------------- api

    @app.route("/api/identidade")
    def api_identidade():
        app_ = aplicacao()
        logins = app_.autenticacao.logins()
        if not logins:
            return jsonify({"erro": "nenhum usuário cadastrado nesta máquina"}), 404

        usuario = app_.autenticacao.buscar(logins[0])
        return jsonify(
            {
                "login": usuario.login,
                "nome": usuario.nome,
                "chave_publica": usuario.chave_publica.decode("ascii"),
                "impressao_digital": usuario.impressao_digital(),
            }
        )

    @app.route("/api/mensagens", methods=["POST"])
    def api_mensagens():
        app_ = aplicacao()
        corpo = request.get_json(silent=True) or {}

        try:
            mensagem: Mensagem = dicionario_para_mensagem(corpo.get("mensagem", {}))
        except FormatoInvalidoError as erro:
            return jsonify({"erro": str(erro)}), 400

        if mensagem.remetente not in app_.autenticacao.chaveiro:
            return jsonify({"erro": "remetente desconhecido nesta máquina"}), 403

        conversa = app_.mensageria.conversa_entre(
            mensagem.remetente, mensagem.destinatario
        )
        try:
            app_.mensageria.receber(conversa, mensagem)
        except RemetenteNaoParticipaError as erro:
            return jsonify({"erro": str(erro)}), 403

        for sessao in app_.sessoes.values():
            if sessao.ativa and conversa.inclui(sessao.login):
                app_.gravar_conversa(sessao, conversa)

        return jsonify({"recebida": True, "chave": str(mensagem.chave)})

    return app