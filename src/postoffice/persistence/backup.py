from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from postoffice.persistence.repository import ARQUIVO_USUARIOS

EXTENSAO_BACKUP = ".zip"


class BackupInvalidoError(Exception):
    pass


class PastaDeDadosVaziaError(FileNotFoundError):
    pass


def nome_sugerido(prefixo: str = "correios-digital") -> str:
    marca = datetime.now().strftime("%Y-%m-%d-%H%M")
    return f"{prefixo}-{marca}{EXTENSAO_BACKUP}"


def exportar(pasta_dados: str | Path, destino: str | Path) -> Path:
    pasta_dados = Path(pasta_dados)
    destino = Path(destino)

    if not pasta_dados.is_dir():
        raise PastaDeDadosVaziaError(f"{pasta_dados} não existe")
    if not (pasta_dados / ARQUIVO_USUARIOS).exists():
        raise PastaDeDadosVaziaError("não há nada para exportar: cadastre um usuário antes")

    if destino.is_dir():
        destino = destino / nome_sugerido()
    destino.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        for arquivo in sorted(pasta_dados.rglob("*")):
            if arquivo.is_file() and not arquivo.name.endswith(".tmp"):
                pacote.write(arquivo, arquivo.relative_to(pasta_dados).as_posix())

    return destino


def conferir(origem: str | Path) -> list[str]:
    origem = Path(origem)
    if not origem.is_file():
        raise BackupInvalidoError(f"{origem} não existe")

    try:
        with zipfile.ZipFile(origem) as pacote:
            if pacote.testzip() is not None:
                raise BackupInvalidoError(f"{origem.name} está corrompido")
            nomes = pacote.namelist()
    except zipfile.BadZipFile as erro:
        raise BackupInvalidoError(f"{origem.name} não é um backup válido") from erro

    if ARQUIVO_USUARIOS not in nomes:
        raise BackupInvalidoError(
            f"{origem.name} não parece um backup do Correios Digital"
        )
    return sorted(nomes)


def importar(origem: str | Path, pasta_dados: str | Path, substituir: bool = False) -> Path:
    origem = Path(origem)
    pasta_dados = Path(pasta_dados)

    conferir(origem)

    if pasta_dados.exists() and any(pasta_dados.iterdir()):
        if not substituir:
            raise BackupInvalidoError(
                f"{pasta_dados} não está vazia: use substituir=True para sobrescrever"
            )
        shutil.rmtree(pasta_dados)

    pasta_dados.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(origem) as pacote:
        for nome in pacote.namelist():
            alvo = (pasta_dados / nome).resolve()
            if not alvo.is_relative_to(pasta_dados.resolve()):
                raise BackupInvalidoError(f"caminho suspeito dentro do backup: {nome}")
        pacote.extractall(pasta_dados)

    return pasta_dados