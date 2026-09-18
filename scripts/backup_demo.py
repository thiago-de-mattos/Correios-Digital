import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from postoffice.persistence import (  # noqa: E402
    ArquivoCorrompidoError,
    ConfiguracaoEmail,
    Repositorio,
    conferir,
    enviar_backup,
    exportar,
    importar,
)
from postoffice.services import Autenticacao, Mensageria  # noqa: E402

SENHA = "senha-do-thiago-1"


def linha(titulo: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def main() -> None:
    trabalho = Path(tempfile.mkdtemp(prefix="correios-demo-"))
    try:
        executar(trabalho)
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)


def executar(trabalho: Path) -> None:
    linha("Sessao de uso normal")

    auth = Autenticacao()
    auth.cadastrar("thiago", "Thiago", "thiago@exemplo.com", SENHA)
    auth.cadastrar("empresa", "Empresa X", "contato@empresa.com", "senha-da-empresa-1")
    sessao = auth.entrar("thiago", SENHA)

    servico = Mensageria(auth.chaveiro)
    conversa = servico.conversa_entre("thiago", "empresa")
    for quem, texto in (
        ("thiago", "bom dia, segue o contrato"),
        ("empresa", "recebido, vou analisar"),
        ("thiago", "obrigado, aguardo retorno"),
    ):
        servico.enviar(conversa, quem, texto)
    print(f"  {len(conversa)} mensagens na conversa {conversa.identificador}")

    linha("Gravando em disco")

    repo = Repositorio(trabalho / "dados")
    repo.salvar_usuarios(auth.usuarios)
    repo.salvar_chaveiro(auth.chaveiro)
    repo.salvar_conversa("thiago", conversa, sessao.cofre)

    for arquivo in sorted(repo.pasta.rglob("*")):
        if arquivo.is_file():
            print(f"  {arquivo.relative_to(repo.pasta).as_posix():<40} "
                  f"{arquivo.stat().st_size:>6} bytes")

    bruto = repo.caminho_da_conversa("thiago", conversa.identificador).read_bytes()
    print("\n  Inicio do arquivo de conversa, aberto como texto:")
    print(f"    {bruto[:58].decode('ascii', 'replace')}...")
    print(f"    a palavra 'contrato' aparece nele? {b'contrato' in bruto}")

    linha("Exportando para o pen drive")

    pendrive = trabalho / "pendrive"
    pendrive.mkdir()
    pacote = exportar(repo.pasta, pendrive)
    print(f"  {pacote.name}  ({pacote.stat().st_size} bytes)")
    for nome in conferir(pacote):
        print(f"    {nome}")

    linha("Restaurando em outra maquina")

    outra = Repositorio(trabalho / "outra-maquina")
    importar(pacote, outra.pasta)

    restaurada = Autenticacao.restaurar(
        outra.carregar_usuarios(), outra.carregar_chaveiro()
    )
    nova_sessao = restaurada.entrar("thiago", SENHA)
    servico_restaurado = Mensageria(restaurada.chaveiro)
    conversas = outra.carregar_conversas("thiago", nova_sessao.cofre)

    print(f"  usuarios restaurados: {restaurada.logins()}")
    print(f"  conversas restauradas: {len(conversas)}\n")
    for m in servico_restaurado.historico(conversas[0], "thiago", nova_sessao.chave_privada):
        print(f"    [{m.chave}] {m.remetente}: {m.texto}")

    linha("Pen drive nas maos erradas")

    intrusa = restaurada.entrar("empresa", "senha-da-empresa-1")
    try:
        outra.carregar_conversa("thiago", conversa.identificador, intrusa.cofre)
    except ArquivoCorrompidoError as erro:
        print(f"  {erro}")

    linha("Envio por e-mail (sem sair da maquina)")

    entregues = []
    config = ConfiguracaoEmail("smtp.exemplo.com", 587, "thiago@exemplo.com", "segredo")
    enviar_backup(
        config,
        pacote,
        "contato@empresa.com",
        entregar=lambda _c, mensagem: entregues.append(mensagem),
    )
    mensagem = entregues[0]
    anexo = next(iter(mensagem.iter_attachments()))
    print(f"  De.......: {mensagem['From']}")
    print(f"  Para.....: {mensagem['To']}")
    print(f"  Assunto..: {mensagem['Subject']}")
    print(f"  Anexo....: {anexo.get_filename()}")
    print(f"  Senha no repr da config? {'segredo' in repr(config)}\n")


if __name__ == "__main__":
    main()