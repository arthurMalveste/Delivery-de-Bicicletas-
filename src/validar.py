"""Validação do Dijkstra do grupo e comparação de rotas.

1. Compara com o Dijkstra do NetworkX o custo da loja até todos os vértices, nos dois modos de peso
   ("só distância" e "com níveis"), e refaz destinos sorteados com parada no destino.
2. Compara, para cada casa, a rota só por distância com a rota com níveis -> output/comparacao_rotas.csv.
3. Gera a simulação à mão de um pedaço pequeno do grafo -> output/simulacao.md.

Rodar a partir de src/:  python validar.py
"""
import math
import random

import networkx as nx
import pandas as pd

from config import LOJA_ID, OUTPUT
from dijkstra import INF, dijkstra, melhor_rota, montar_rota
from grafo import adjacencia, montar

MODOS = {"só distância": False, "com níveis": True}
TOLERANCIA = 1e-6  # m: diferença aceitável (arredondamento de ponto flutuante)


def para_networkx(grafo):
    g = nx.DiGraph()
    g.add_nodes_from(grafo)
    for u, vizinhos in grafo.items():
        for v, w in vizinhos:
            g.add_edge(u, v, weight=w)
    return g


def comparar_com_networkx(arestas, n_sorteados=200):
    print("1. Comparação com o NetworkX")
    ok = True
    for nome, com_niveis in MODOS.items():
        grafo = adjacencia(arestas, com_niveis)
        L, _, _ = dijkstra(grafo, LOJA_ID)
        ref = nx.single_source_dijkstra_path_length(para_networkx(grafo), LOJA_ID)
        dif_todos = max(abs(L[v] - ref.get(v, INF)) if L[v] != INF else 0 for v in grafo)
        mesmos_alcancaveis = {v for v in grafo if L[v] < INF} == set(ref)
        destinos = random.Random(42).sample(sorted(v for v in grafo if v != LOJA_ID), n_sorteados)
        dif_parada = max(abs(melhor_rota(grafo, LOJA_ID, d)[0] - ref[d]) for d in destinos)
        passou = dif_todos <= TOLERANCIA and dif_parada <= TOLERANCIA and mesmos_alcancaveis
        ok &= passou
        print(f"   {nome}: {len(grafo)} vértices, maior diferença {dif_todos:.2e} (todos) e "
              f"{dif_parada:.2e} ({n_sorteados} destinos com parada) -> {'OK' if passou else 'FALHOU'}")
    return ok


def custo_com_niveis(rota, peso_niveis):
    return sum(peso_niveis[(a, b)] for a, b in zip(rota, rota[1:]))


def comparar_rotas(arestas):
    print("2. Rota só por distância x rota com níveis (todas as casas)")
    distancia = {(u, v): d for u, v, d in zip(arestas.u, arestas.v, arestas.comprimento)}
    peso_niveis = {(u, v): p for u, v, p in zip(arestas.u, arestas.v, arestas.peso)}
    rotas = {}
    for nome, com_niveis in MODOS.items():
        _, anterior, _ = dijkstra(adjacencia(arestas, com_niveis), LOJA_ID)
        rotas[nome] = anterior
    linhas = []
    for casa in sorted((v for v in rotas["com níveis"] if v.startswith("h")), key=lambda v: int(v[1:])):
        r_dist = montar_rota(rotas["só distância"], casa)
        r_niv = montar_rota(rotas["com níveis"], casa)
        linhas.append(dict(
            casa=casa, rotas_iguais=r_dist == r_niv,
            dist_rota_distancia=sum(distancia[e] for e in zip(r_dist, r_dist[1:])),
            dist_rota_niveis=sum(distancia[e] for e in zip(r_niv, r_niv[1:])),
            custo_rota_distancia=custo_com_niveis(r_dist, peso_niveis),
            custo_rota_niveis=custo_com_niveis(r_niv, peso_niveis)))
    df = pd.DataFrame(linhas)
    df["metros_a_mais"] = df.dist_rota_niveis - df.dist_rota_distancia
    df["custo_economizado"] = df.custo_rota_distancia - df.custo_rota_niveis
    OUTPUT.mkdir(exist_ok=True)
    df.round(2).to_csv(OUTPUT / "comparacao_rotas.csv", index=False)
    dif = df[~df.rotas_iguais]
    print(f"   rotas diferentes em {len(dif)} de {len(df)} casas")
    if len(dif):
        print(f"   nelas, a rota com níveis anda em média {dif.metros_a_mais.mean():.1f} m a mais "
              f"e economiza {dif.custo_economizado.mean():.1f} de custo")
        print("   maiores diferenças de caminho:")
        print(dif.sort_values("metros_a_mais").tail(5).round(1).to_string(index=False))
    print(f"   tabela completa em {OUTPUT / 'comparacao_rotas.csv'}")


def simulacao(arestas, n_vertices=7):
    """Pedaço pequeno do grafo de ruas (com níveis) ao redor da loja, resolvido passo a passo."""
    print("3. Simulação à mão")
    rua = arestas[arestas.tipo != "casa"]
    grafo_rua = adjacencia(rua)
    _, _, passos = dijkstra(grafo_rua, LOJA_ID, registrar=True)
    vertices = [p["fechado"] for p in passos[:n_vertices]]  # os n primeiros fechados: um pedaço conexo
    sub = rua[rua.u.isin(vertices) & rua.v.isin(vertices)]
    destino = vertices[-1]
    _, anterior, passos = dijkstra(adjacencia(sub), LOJA_ID, destino, registrar=True)

    def celula(p, v):
        if p["L"][v] == INF:
            return "∞"
        marca = " ✔" if v in fechados else ""
        return f"{p['L'][v]:.1f} ({p['anterior'][v] or '-'}){marca}"

    linhas = [f"# Simulação do Dijkstra à mão\n",
              f"Pedaço do grafo com os {n_vertices} vértices mais próximos da loja, pesos com níveis. "
              f"Origem: `{LOJA_ID}`. Destino: `{destino}`.\n",
              "## Arestas do pedaço\n", "| u | v | comprimento (m) | inclinação (%) | nível | peso |",
              "|---|---|---|---|---|---|"]
    for a in sub.itertuples():
        inc = "-" if math.isnan(a.inclinacao) else f"{a.inclinacao:.2f}"
        linhas.append(f"| {a.u} | {a.v} | {a.comprimento:.1f} | {inc} | {a.nivel or 'sem nível'} | {a.peso:.1f} |")
    linhas += ["\n## Passos\n", "Cada célula mostra L (antecessor). ✔ marca os vértices fechados.\n",
               "| passo | fecha | " + " | ".join(vertices) + " |", "|---|---|" + "---|" * len(vertices)]
    fechados = set()
    for p in passos:
        fechados.add(p["fechado"])
        linhas.append(f"| {p['passo']} | {p['fechado']} | " + " | ".join(celula(p, v) for v in vertices) + " |")
    rota = montar_rota(anterior, destino)
    linhas.append(f"\nRota: {' → '.join(rota)}, custo {passos[-1]['L'][destino]:.1f}.")
    (OUTPUT / "simulacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"   {len(passos)} passos até fechar {destino}; tabela em {OUTPUT / 'simulacao.md'}")


if __name__ == "__main__":
    arestas = montar()
    ok = comparar_com_networkx(arestas)
    comparar_rotas(arestas)
    simulacao(arestas)
    print("Validação:", "OK" if ok else "FALHOU")
