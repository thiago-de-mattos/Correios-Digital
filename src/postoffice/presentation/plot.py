from __future__ import annotations

from xml.sax.saxutils import escape

from postoffice.structures import ArvoreAVL
from postoffice.structures.avl_tree import No

LARGURA_NO = 78
ALTURA_NIVEL = 74
MARGEM = 34
RAIO = 17


def _posicionar(raiz: No | None) -> tuple[list[dict], list[tuple[float, float, float, float]]]:
    nos: list[dict] = []
    ligacoes: list[tuple[float, float, float, float]] = []
    coluna = 0

    def visitar(no: No | None, profundidade: int) -> tuple[float, float] | None:
        nonlocal coluna
        if no is None:
            return None

        esquerda = visitar(no.esquerda, profundidade + 1)
        x = MARGEM + coluna * LARGURA_NO + LARGURA_NO / 2
        y = MARGEM + profundidade * ALTURA_NIVEL
        coluna += 1
        direita = visitar(no.direita, profundidade + 1)

        for filho in (esquerda, direita):
            if filho is not None:
                ligacoes.append((x, y, filho[0], filho[1]))

        nos.append(
            {
                "x": x,
                "y": y,
                "rotulo": no.chave.instante.strftime("%H:%M:%S"),
                "detalhe": str(no.chave),
                "altura": no.altura,
                "remetente": getattr(no.valor, "remetente", ""),
            }
        )
        return x, y

    visitar(raiz, 0)
    return nos, ligacoes


def arvore_para_svg(arvore: ArvoreAVL, titulo: str = "") -> str:
    if arvore.esta_vazia():
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="90" '
            'role="img" aria-label="árvore vazia">'
            '<text x="20" y="50" font-family="system-ui, sans-serif" font-size="15" '
            'fill="#5a6472">Nenhuma mensagem nesta conversa ainda.</text></svg>'
        )

    nos, ligacoes = _posicionar(arvore.raiz)
    largura = MARGEM * 2 + len(nos) * LARGURA_NO
    altura = MARGEM * 2 + arvore.altura() * ALTURA_NIVEL

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.0f} {altura:.0f}" '
        f'width="{largura:.0f}" height="{altura:.0f}" role="img" '
        f'aria-label="{escape(titulo or "árvore de mensagens")}">',
        '<style>'
        '.ligacao{stroke:#8a94a6;stroke-width:1.6;fill:none}'
        '.no{fill:#eef2f7;stroke:#2f5f96;stroke-width:2}'
        '.raiz{fill:#d7e6f7;stroke-width:3}'
        '.rotulo{font-family:ui-monospace,monospace;font-size:11px;fill:#14324f;'
        'text-anchor:middle}'
        '.altura{font-family:system-ui,sans-serif;font-size:9.5px;fill:#5a6472;'
        'text-anchor:middle}'
        '</style>',
    ]

    for x1, y1, x2, y2 in ligacoes:
        partes.append(
            f'<line class="ligacao" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )

    for indice, no in enumerate(nos):
        classe = "no raiz" if no["y"] == MARGEM else "no"
        partes.append(
            f'<circle class="{classe}" cx="{no["x"]:.1f}" cy="{no["y"]:.1f}" r="{RAIO}">'
            f'<title>{escape(no["detalhe"])} — {escape(no["remetente"])} '
            f'(altura {no["altura"]})</title></circle>'
        )
        partes.append(
            f'<text class="rotulo" x="{no["x"]:.1f}" y="{no["y"] + 4:.1f}">{indice + 1}</text>'
        )
        partes.append(
            f'<text class="altura" x="{no["x"]:.1f}" y="{no["y"] + RAIO + 13:.1f}">'
            f'{escape(no["rotulo"])}</text>'
        )

    partes.append("</svg>")
    return "".join(partes)