import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from postoffice.security import keys  # noqa: E402
from postoffice.services import Autenticacao, Mensageria  # noqa: E402


def linha(titulo: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def main() -> None:
    linha("Cada maquina tem sua propria instalacao")

    maquina_1 = Autenticacao()
    maquina_2 = Autenticacao()

    thiago = maquina_1.cadastrar(
        "thiago", "Thiago", "thiago@exemplo.com", "senha-do-thiago-1"
    )
    empresa = maquina_2.cadastrar(
        "empresa", "Empresa X", "contato@empresa.com", "senha-da-empresa-1"
    )

    print(f"  maquina 1: {thiago.login:<8} par de chaves RSA-{keys.TAMANHO_CHAVE} gerado")
    print(f"  maquina 2: {empresa.login:<8} par de chaves RSA-{keys.TAMANHO_CHAVE} gerado")

    linha("Troca de chaves publicas (pode acontecer em canal aberto)")

    maquina_1.chaveiro.adicionar("empresa", empresa.chave_publica)
    maquina_2.chaveiro.adicionar("thiago", thiago.chave_publica)

    print(f"  thiago  -> {len(thiago.chave_publica)} bytes de chave publica, em texto puro")
    print(f"  empresa -> {len(empresa.chave_publica)} bytes de chave publica, em texto puro")
    print("\n  Conferencia de impressao digital (defesa contra troca de chave):")
    print(f"    thiago  {maquina_2.chaveiro.impressao_digital('thiago')}")
    print(f"    empresa {maquina_1.chaveiro.impressao_digital('empresa')}")

    sessao_1 = maquina_1.entrar("thiago", "senha-do-thiago-1")
    sessao_2 = maquina_2.entrar("empresa", "senha-da-empresa-1")

    servico_1 = Mensageria(maquina_1.chaveiro)
    servico_2 = Mensageria(maquina_2.chaveiro)
    conversa_1 = servico_1.conversa_entre("thiago", "empresa")
    conversa_2 = servico_2.conversa_entre("thiago", "empresa")

    linha("Troca de mensagens")

    roteiro = [
        (servico_1, conversa_1, "thiago", "bom dia, segue o contrato", servico_2, conversa_2),
        (servico_2, conversa_2, "empresa", "recebido, vou analisar", servico_1, conversa_1),
        (servico_1, conversa_1, "thiago", "obrigado, aguardo retorno", servico_2, conversa_2),
    ]

    for origem, conv_origem, quem, texto, destino, conv_destino in roteiro:
        enviada = origem.enviar(conv_origem, quem, texto)
        destino.receber(conv_destino, enviada)
        envelopes = len(enviada.chaves_cifradas)
        print(f"  {quem:>8} -> {enviada.destinatario:<8} "
              f"{len(enviada.conteudo_cifrado)} bytes de texto + {envelopes} envelopes de chave")

    linha("O que cada tela mostra")

    for nome, servico, conv, login, sessao in (
        ("MAQUINA 1 (thiago)", servico_1, conversa_1, "thiago", sessao_1),
        ("MAQUINA 2 (empresa)", servico_2, conversa_2, "empresa", sessao_2),
    ):
        print(f"\n  {nome}")
        for m in servico.historico(conv, login, sessao.chave_privada):
            print(f"    [{m.chave}] {m.remetente}: {m.texto}")

    linha("O que um intruso veria")

    privada_intrusa, _ = keys.gerar_par()
    print("\n  Com outra chave privada:")
    for m in servico_1.historico(conversa_1, "thiago", privada_intrusa):
        print(f"    [{m.chave}] {m.remetente}: {m.texto}")

    _, primeira = next(iter(conversa_1.arvore.em_ordem()))
    print("\n  Em disco, a primeira mensagem esta assim:")
    print(f"    {primeira.conteudo_cifrado[:58].decode('ascii', 'replace')}...")

    linha("Estado da arvore")

    print(f"\n  mensagens: {len(conversa_1)}")
    print(f"  altura da AVL: {conversa_1.arvore.altura()}")
    conversa_1.arvore.validar()
    print("  invariantes da AVL conferidas: ordem, altura e balanceamento OK")
    print("\n  Nenhuma frase foi combinada por fora. As chaves publicas")
    print("  circularam em texto puro e ninguem mais conseguiu ler.\n")


if __name__ == "__main__":
    main()