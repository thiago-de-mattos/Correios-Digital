import math
import random

import pytest

from postoffice.structures.avl_tree import ArvoreAVL, ChaveDuplicadaError


def test_arvore_nova_esta_vazia():
    a = ArvoreAVL()
    assert a.esta_vazia()
    assert len(a) == 0
    assert a.altura() == 0
    assert list(a.em_ordem()) == []


def test_inserir_e_buscar():
    a = ArvoreAVL()
    a.inserir(10, "dez")
    a.inserir(5, "cinco")
    a.inserir(15, "quinze")

    assert len(a) == 3
    assert a.buscar(5) == "cinco"
    assert a.buscar(99) is None
    assert 10 in a
    assert 99 not in a
    a.validar()


def test_chave_duplicada_e_recusada():
    a = ArvoreAVL()
    a.inserir(1, "primeira")
    with pytest.raises(ChaveDuplicadaError):
        a.inserir(1, "segunda")
    assert len(a) == 1
    assert a.buscar(1) == "primeira"


def test_rotacao_LL():
    a = ArvoreAVL()
    for k in (30, 20, 10):
        a.inserir(k, k)
    assert a.raiz.chave == 20
    assert a.raiz.esquerda.chave == 10
    assert a.raiz.direita.chave == 30
    assert a.altura() == 2
    a.validar()


def test_rotacao_RR():
    a = ArvoreAVL()
    for k in (10, 20, 30):
        a.inserir(k, k)
    assert a.raiz.chave == 20
    assert a.raiz.esquerda.chave == 10
    assert a.raiz.direita.chave == 30
    assert a.altura() == 2
    a.validar()


def test_rotacao_LR():
    a = ArvoreAVL()
    for k in (30, 10, 20):
        a.inserir(k, k)
    assert a.raiz.chave == 20
    assert a.raiz.esquerda.chave == 10
    assert a.raiz.direita.chave == 30
    a.validar()


def test_rotacao_RL():
    a = ArvoreAVL()
    for k in (10, 30, 20):
        a.inserir(k, k)
    assert a.raiz.chave == 20
    assert a.raiz.esquerda.chave == 10
    assert a.raiz.direita.chave == 30
    a.validar()


def test_em_ordem_devolve_ordenado():
    a = ArvoreAVL()
    chaves = [50, 30, 70, 20, 40, 60, 80]
    for k in chaves:
        a.inserir(k, f"v{k}")
    assert [c for c, _ in a.em_ordem()] == sorted(chaves)


def test_pre_ordem_comeca_pela_raiz():
    a = ArvoreAVL()
    for k in (50, 30, 70):
        a.inserir(k, k)
    assert [c for c, _ in a.pre_ordem()] == [50, 30, 70]


def test_pos_ordem_termina_na_raiz():
    a = ArvoreAVL()
    for k in (50, 30, 70):
        a.inserir(k, k)
    assert [c for c, _ in a.pos_ordem()] == [30, 70, 50]


def test_remover_folha():
    a = ArvoreAVL()
    for k in (20, 10, 30):
        a.inserir(k, k)
    a.remover(10)
    assert [c for c, _ in a.em_ordem()] == [20, 30]
    assert len(a) == 2
    a.validar()


def test_remover_no_com_um_filho():
    a = ArvoreAVL()
    for k in (20, 10, 30, 25):
        a.inserir(k, k)
    a.remover(30)
    assert [c for c, _ in a.em_ordem()] == [10, 20, 25]
    a.validar()


def test_remover_no_com_dois_filhos_usa_sucessor():
    a = ArvoreAVL()
    for k in (50, 30, 70, 60, 80):
        a.inserir(k, f"v{k}")
    a.remover(70)
    assert [c for c, _ in a.em_ordem()] == [30, 50, 60, 80]
    assert a.buscar(60) == "v60"
    a.validar()


def test_remover_a_raiz():
    a = ArvoreAVL()
    for k in (50, 30, 70):
        a.inserir(k, k)
    a.remover(50)
    assert [c for c, _ in a.em_ordem()] == [30, 70]
    a.validar()


def test_remover_chave_inexistente_levanta_erro():
    a = ArvoreAVL()
    a.inserir(1, "um")
    with pytest.raises(KeyError):
        a.remover(42)
    assert len(a) == 1


def test_remover_provoca_rebalanceamento():
    a = ArvoreAVL()
    for k in (50, 30, 70, 20, 40, 60, 80, 10):
        a.inserir(k, k)
    a.remover(60)
    a.remover(80)
    a.validar()


def test_mil_chaves_em_ordem_crescente_nao_degenera():
    a = ArvoreAVL()
    for k in range(1, 1001):
        a.inserir(k, f"msg{k}")

    limite = 1.44 * math.log2(1001) + 2
    assert a.altura() <= limite
    assert a.altura() <= 12
    assert len(a) == 1000
    assert [c for c, _ in a.em_ordem()] == list(range(1, 1001))
    a.validar()


def test_dez_mil_mensagens():
    a = ArvoreAVL()
    for k in range(10_000):
        a.inserir(k, k)
    assert a.altura() <= 1.44 * math.log2(10_001) + 2
    a.validar()


def test_intervalo():
    a = ArvoreAVL()
    for k in range(0, 100, 5):
        a.inserir(k, f"v{k}")
    achados = [c for c, _ in a.intervalo(20, 40)]
    assert achados == [20, 25, 30, 35, 40]


def test_intervalo_vazio():
    a = ArvoreAVL()
    for k in (10, 20, 30):
        a.inserir(k, k)
    assert a.intervalo(11, 19) == []


def test_chave_composta_desempata_mensagens_do_mesmo_instante():
    a = ArvoreAVL()
    instante = "2026-09-11T14:30:00"
    a.inserir((instante, 0), "primeira")
    a.inserir((instante, 1), "segunda")
    a.inserir(("2026-09-11T14:30:01", 0), "terceira")

    assert [v for _, v in a.em_ordem()] == ["primeira", "segunda", "terceira"]
    a.validar()


def test_estresse_insercao_e_remocao_aleatorias():
    random.seed(42)
    a = ArvoreAVL()
    espelho = set()

    for _ in range(4000):
        k = random.randint(0, 500)
        if k in espelho:
            a.remover(k)
            espelho.remove(k)
        else:
            a.inserir(k, k)
            espelho.add(k)

    assert len(a) == len(espelho)
    assert [c for c, _ in a.em_ordem()] == sorted(espelho)
    a.validar()