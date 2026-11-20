"""Algoritmo de Dijkstra implementado pelo grupo (versão vista em aula).

    1. L(origem) = 0 e L(v) = ∞ para os demais vértices; todos começam abertos.
    2. Fecha-se o vértice aberto u de menor L.
    3. Para cada vizinho v de u ainda aberto: se L(u) + w(u, v) < L(v), então L(v) = L(u) + w(u, v)
       e o antecessor de v passa a ser u.
    4. Repete-se 2 e 3 até o destino ser fechado (ou, sem destino, até não sobrar vértice alcançável).
    5. A rota é montada seguindo os antecessores do destino até a origem.

O grafo é um dicionário {vértice: [(vizinho, peso), ...]} com todos os vértices como chave
(ver grafo.adjacencia). O NetworkX é usado só em validar.py, para conferir o resultado.
"""
INF = float("inf")


def dijkstra(grafo, origem, destino=None, registrar=False):
    """Devolve (L, anterior, passos).

    L[v] é o custo da melhor rota da origem até v e anterior[v] o vértice antes de v nessa rota.
    Com `destino`, para assim que ele é fechado (os rótulos dos vértices ainda abertos ficam provisórios).
    Com `registrar=True`, `passos` guarda, a cada vértice fechado, uma cópia de L e de anterior:
    é a tabela da simulação à mão.
    """
    L = {v: INF for v in grafo}
    anterior = {v: None for v in grafo}
    L[origem] = 0
    fechados = set()
    # Só os abertos com rótulo finito podem ser escolhidos (um vértice com L = ∞ nunca é o menor
    # enquanto houver outro alcançável); guardá-los à parte evita percorrer o grafo inteiro a cada passo.
    candidatos = {origem}
    passos = []

    while candidatos:
        u = min(candidatos, key=lambda v: (L[v], v))  # aberto de menor L (empate: menor id, para ser reproduzível)
        candidatos.remove(u)
        fechados.add(u)
        if u != destino:
            for v, w in grafo[u]:
                if v not in fechados and L[u] + w < L[v]:
                    L[v] = L[u] + w
                    anterior[v] = u
                    candidatos.add(v)
        if registrar:
            passos.append(dict(passo=len(passos) + 1, fechado=u, L=dict(L), anterior=dict(anterior)))
        if u == destino:
            break
    return L, anterior, passos


def montar_rota(anterior, destino):
    """Segue os antecessores do destino até a origem e devolve a rota na ordem origem -> destino."""
    rota = []
    v = destino
    while v is not None:
        rota.append(v)
        v = anterior[v]
    return rota[::-1]


def melhor_rota(grafo, origem, destino):
    """(custo, rota) da origem ao destino; (∞, []) se o destino for inalcançável."""
    L, anterior, _ = dijkstra(grafo, origem, destino)
    if L[destino] == INF:
        return INF, []
    return L[destino], montar_rota(anterior, destino)
