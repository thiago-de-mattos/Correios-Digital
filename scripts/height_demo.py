import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from postoffice.structures.avl_tree import ArvoreAVL


class NoBST:
    __slots__ = ("chave", "esquerda", "direita")

    def __init__(self, chave):
        self.chave = chave
        self.esquerda = None
        self.direita = None


class ArvoreBST:
    def __init__(self):
        self.raiz = None

    def inserir(self, chave):
        novo = NoBST(chave)
        if self.raiz is None:
            self.raiz = novo
            return
        atual = self.raiz
        while True:
            if chave < atual.chave:
                if atual.esquerda is None:
                    atual.esquerda = novo
                    return
                atual = atual.esquerda
            else:
                if atual.direita is None:
                    atual.direita = novo
                    return
                atual = atual.direita

    def altura(self):
        maior, pilha = 0, [(self.raiz, 1)]
        while pilha:
            no, prof = pilha.pop()
            if no is None:
                continue
            maior = max(maior, prof)
            pilha.append((no.esquerda, prof + 1))
            pilha.append((no.direita, prof + 1))
        return maior


def comparar(n: int) -> None:
    bst = ArvoreBST()
    avl = ArvoreAVL()

    for k in range(1, n + 1):
        bst.inserir(k)
        avl.inserir(k, f"mensagem {k}")

    h_bst, h_avl = bst.altura(), avl.altura()
    ideal = math.ceil(math.log2(n + 1))

    print(f"\n  {n:,} mensagens inseridas em ordem crescente".replace(",", "."))
    print(f"    BST comum ....... altura {h_bst:>6}   "
          f"(até {h_bst} comparações para achar uma mensagem)")
    print(f"    AVL ............. altura {h_avl:>6}   "
          f"(até {h_avl} comparações)")
    print(f"    altura ideal .... {ideal:>13}")
    print(f"    a AVL é {h_bst / h_avl:.0f}x mais rasa")

    avl.validar()


if __name__ == "__main__":
    print("=" * 62)
    print("  Correios Digital — demonstração da Sprint 1")
    print("  Por que a árvore precisa se rebalancear")
    print("=" * 62)

    for n in (100, 1_000, 10_000):
        comparar(n)

    print("\n  Conclusão: com chaves crescentes a BST vira uma lista")
    print("  encadeada (altura = n). A AVL mantém a altura em O(log n).\n")