from __future__ import annotations

import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path


class FalhaNoEnvioError(Exception):
    pass


class BackupNaoEncontradoError(FileNotFoundError):
    pass


@dataclass(slots=True)
class ConfiguracaoEmail:
    servidor: str
    porta: int
    remetente: str
    senha: str = field(repr=False)
    usar_tls: bool = True
    tempo_limite: int = 30


def montar_mensagem(
    config: ConfiguracaoEmail,
    destinatario: str,
    caminho: Path,
    assunto: str,
    corpo: str,
) -> EmailMessage:
    mensagem = EmailMessage()
    mensagem["From"] = config.remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)
    mensagem.add_attachment(
        caminho.read_bytes(),
        maintype="application",
        subtype="zip",
        filename=caminho.name,
    )
    return mensagem


def _entregar_por_smtp(config: ConfiguracaoEmail, mensagem: EmailMessage) -> None:
    contexto = ssl.create_default_context()
    with smtplib.SMTP(config.servidor, config.porta, timeout=config.tempo_limite) as sessao:
        if config.usar_tls:
            sessao.starttls(context=contexto)
        sessao.login(config.remetente, config.senha)
        sessao.send_message(mensagem)


def enviar_backup(
    config: ConfiguracaoEmail,
    caminho: str | Path,
    destinatario: str,
    assunto: str = "Backup do Correios Digital",
    corpo: str = (
        "Segue em anexo o backup do acervo.\n\n"
        "As conversas estão cifradas: sem a senha do usuário, o arquivo é ilegível."
    ),
    entregar: Callable[[ConfiguracaoEmail, EmailMessage], None] | None = None,
) -> None:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise BackupNaoEncontradoError(f"{caminho} não existe")
    if not destinatario or "@" not in destinatario:
        raise ValueError("destinatário inválido")

    mensagem = montar_mensagem(config, destinatario, caminho, assunto, corpo)
    entrega = entregar if entregar is not None else _entregar_por_smtp

    try:
        entrega(config, mensagem)
    except smtplib.SMTPAuthenticationError as erro:
        raise FalhaNoEnvioError(
            "o servidor recusou as credenciais: verifique a senha de aplicativo"
        ) from erro
    except (smtplib.SMTPException, OSError) as erro:
        raise FalhaNoEnvioError(
            "não foi possível enviar o backup por e-mail: verifique a conexão. "
            "O backup local continua salvo."
        ) from erro