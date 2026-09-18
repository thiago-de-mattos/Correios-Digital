import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from postoffice.presentation import criar_app  # noqa: E402


def endereco_na_rede(porta: int) -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("8.8.8.8", 80))
            return f"{sonda.getsockname()[0]}:{porta}"
    except OSError:
        return f"localhost:{porta}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor local do Correios Digital")
    parser.add_argument("--porta", type=int, default=5000)
    parser.add_argument("--dados", default="dados", help="pasta onde gravar os dados")
    parser.add_argument("--host", default="0.0.0.0")
    argumentos = parser.parse_args()

    app = criar_app(argumentos.dados)

    print("=" * 62)
    print("  Correios Digital")
    print("=" * 62)
    print(f"  Nesta maquina ....: http://localhost:{argumentos.porta}")
    print(f"  Para os colegas ..: {endereco_na_rede(argumentos.porta)}")
    print(f"  Dados em .........: {Path(argumentos.dados).resolve()}")
    print("=" * 62)

    app.run(host=argumentos.host, port=argumentos.porta, debug=False)


if __name__ == "__main__":
    main()