from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class ChaveDuplicadaError(KeyError):
    pass


class No:
    __slots__ = ("chave", "valor", "esquerda", "direita", "altura")

    def __init__(self, chave: Any, valor: Any) -> None:
        self.chave = chave
        self.valor = valor
        self.esquerda: No | None = None
        self.direita: No | None = None
        self.altura: int = 1

    def __repr__(self) -> str:
        return f"No({self.chave!r}, altura={self.altura})"


def _altura(no: No | None) -> int:
    return 0 if no is None else no.altura


def _fator(no: No | None) -> int:
    if no is None:
        return 0
    return _altura(no.esquerda) - _altura(no.direita)


def _atualizar_altura(no: No) -> None:
    no.altura = 1 + max(_altura(no.esquerda), _altura(no.direita))


def _rotacionar_direita(y: No) -> No:
    x = y.esquerda
    assert x is not None, "rotação à direita exige filho esquerdo"
    t2 = x.direita

    x.direita = y
    y.esquerda = t2

    _atualizar_altura(y)
    _atualizar_altura(x)
    return x


def _rotacionar_esquerda(x: No) -> No:
    y = x.direita
    assert y is not None, "rotação à esquerda exige filho direito"
    t2 = y.esquerda

    y.esquerda = x
    x.direita = t2

    _atualizar_altura(x)
    _atualizar_altura(y)
    return y


def _rebalancear(no: No) -> No:
    _atualizar_altura(no)
    fb = _fator(no)

    if fb > 1:
        if _fator(no.esquerda) < 0:
            no.esquerda = _rotacionar_esquerda(no.esquerda)
        return _rotacionar_direita(no)

    if fb < -1:
        if _fator(no.direita) > 0:
            no.direita = _rotacionar_direita(no.direita)
        return _rotacionar_esquerda(no)

    return no


class ArvoreAVL:
    def __init__(self) -> None:
        self.raiz: No | None = None
        self._tamanho: int = 0

    def __len__(self) -> int:
        return self._tamanho

    def __contains__(self, chave: Any) -> bool:
        return self._localizar(chave) is not None

    def esta_vazia(self) -> bool:
        return self.raiz is None

    def altura(self) -> int:
        return _altura(self.raiz)

    def _localizar(self, chave: Any) -> No | None:
        atual = self.raiz
        while atual is not None:
            if chave < atual.chave:
                atual = atual.esquerda
            elif chave > atual.chave:
                atual = atual.direita
            else:
                return atual
        return None

    def buscar(self, chave: Any, padrao: Any = None) -> Any:
        no = self._localizar(chave)
        return padrao if no is None else no.valor

    def inserir(self, chave: Any, valor: Any) -> None:
        self.raiz = self._inserir(self.raiz, chave, valor)
        self._tamanho += 1

    def _inserir(self, no: No | None, chave: Any, valor: Any) -> No:
        if no is None:
            return No(chave, valor)

        if chave < no.chave:
            no.esquerda = self._inserir(no.esquerda, chave, valor)
        elif chave > no.chave:
            no.direita = self._inserir(no.direita, chave, valor)
        else:
            raise ChaveDuplicadaError(chave)

        return _rebalancear(no)

    def remover(self, chave: Any) -> None:
        self.raiz = self._remover(self.raiz, chave)
        self._tamanho -= 1

    def _remover(self, no: No | None, chave: Any) -> No | None:
        if no is None:
            raise KeyError(chave)

        if chave < no.chave:
            no.esquerda = self._remover(no.esquerda, chave)
        elif chave > no.chave:
            no.direita = self._remover(no.direita, chave)
        else:
            if no.esquerda is None:
                return no.direita
            if no.direita is None:
                return no.esquerda

            sucessor = self._minimo(no.direita)
            no.chave, no.valor = sucessor.chave, sucessor.valor
            no.direita = self._remover_minimo(no.direita)

        return _rebalancear(no)

    @staticmethod
    def _minimo(no: No) -> No:
        while no.esquerda is not None:
            no = no.esquerda
        return no

    def _remover_minimo(self, no: No) -> No | None:
        if no.esquerda is None:
            return no.direita
        no.esquerda = self._remover_minimo(no.esquerda)
        return _rebalancear(no)

    def em_ordem(self) -> Iterator[tuple[Any, Any]]:
        pilha: list[No] = []
        atual = self.raiz
        while pilha or atual is not None:
            while atual is not None:
                pilha.append(atual)
                atual = atual.esquerda
            atual = pilha.pop()
            yield atual.chave, atual.valor
            atual = atual.direita

    def pre_ordem(self) -> Iterator[tuple[Any, Any]]:
        def visitar(no: No | None):
            if no is None:
                return
            yield no.chave, no.valor
            yield from visitar(no.esquerda)
            yield from visitar(no.direita)

        yield from visitar(self.raiz)

    def pos_ordem(self) -> Iterator[tuple[Any, Any]]:
        def visitar(no: No | None):
            if no is None:
                return
            yield from visitar(no.esquerda)
            yield from visitar(no.direita)
            yield no.chave, no.valor

        yield from visitar(self.raiz)

    def intervalo(self, inicio: Any, fim: Any) -> list[tuple[Any, Any]]:
        resultado: list[tuple[Any, Any]] = []

        def visitar(no: No | None) -> None:
            if no is None:
                return
            if inicio < no.chave:
                visitar(no.esquerda)
            if inicio <= no.chave <= fim:
                resultado.append((no.chave, no.valor))
            if no.chave < fim:
                visitar(no.direita)

        visitar(self.raiz)
        return resultado

    def validar(self) -> int:
        def checar(no: No | None, minimo: Any, maximo: Any) -> int:
            if no is None:
                return 0

            if minimo is not None and not (minimo < no.chave):
                raise ValueError(f"ordem quebrada em {no.chave!r}")
            if maximo is not None and not (no.chave < maximo):
                raise ValueError(f"ordem quebrada em {no.chave!r}")

            he = checar(no.esquerda, minimo, no.chave)
            hd = checar(no.direita, no.chave, maximo)

            real = 1 + max(he, hd)
            if no.altura != real:
                raise ValueError(
                    f"altura errada em {no.chave!r}: guardada {no.altura}, real {real}"
                )

            if abs(he - hd) > 1:
                raise ValueError(f"desbalanceado em {no.chave!r}: fb={he - hd}")

            return real

        return checar(self.raiz, None, None)