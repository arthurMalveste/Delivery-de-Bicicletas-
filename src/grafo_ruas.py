"""Constrói os nós de rua (esquinas + centros) e os trechos entre eles.

Cada quarteirão (aresta do OSM) de comprimento L ganha n = ceil(L / PASSO_CENTRO) - 1 centros (PASSO_CENTRO = 50 m),
igualmente espaçados ao longo da rua; o quarteirão vira n+1 trechos de L/(n+1).
Cada trecho guarda as esquinas (esq_u, esq_v) e o comprimento do quarteirão a que pertence:
a inclinação (nível) é calculada de esquina a esquina, não por trecho.
Os trechos são sem direção aqui; na etapa de pesos viram duas arestas.
"""
import math

import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point

from baixar_ruas import baixar
from config import ARESTAS_CSV, DATA, NOS_CSV, PASSO_CENTRO


def quarteiroes(g):
    """Uma entrada por par de esquinas (a mais curta, se houver paralelas)."""
    melhores = {}
    for u, v, d in g.edges(data=True):
        chave = tuple(sorted((u, v)))
        if chave not in melhores or d["length"] < melhores[chave][2]["length"]:
            melhores[chave] = (u, v, d)
    return [melhores[k] for k in sorted(melhores)]


def construir(g):
    nos = {}  # id -> dict
    for n, d in g.nodes(data=True):
        nos[f"e{n}"] = dict(id=f"e{n}", tipo="esquina", lat=d["y"], lon=d["x"])
    trechos = []
    k = 0
    for u, v, d in quarteiroes(g):
        L = d["length"]
        if u == v and L == 0:
            continue
        geom = d.get("geometry") or LineString(
            [(g.nodes[u]["x"], g.nodes[u]["y"]), (g.nodes[v]["x"], g.nodes[v]["y"])])
        # garante que a geometria comece em u
        pu = Point(g.nodes[u]["x"], g.nodes[u]["y"])
        if Point(geom.coords[0]).distance(pu) > Point(geom.coords[-1]).distance(pu):
            geom = LineString(list(geom.coords)[::-1])
        n = math.ceil(L / PASSO_CENTRO) - 1
        ids = [f"e{u}"]
        for i in range(1, n + 1):
            p = geom.interpolate(i / (n + 1), normalized=True)
            k += 1
            cid = f"c{k}"
            nos[cid] = dict(id=cid, tipo="centro", lat=p.y, lon=p.x)
            ids.append(cid)
        ids.append(f"e{v}")
        for a, b in zip(ids, ids[1:]):
            trechos.append(dict(u=a, v=b, comprimento=L / (n + 1),
                                esq_u=f"e{u}", esq_v=f"e{v}", comprimento_quarteirao=L))
    return nos, trechos


def salvar(nos, trechos):
    DATA.mkdir(exist_ok=True)
    pd.DataFrame(nos.values()).to_csv(NOS_CSV, index=False)
    pd.DataFrame(trechos).to_csv(ARESTAS_CSV, index=False)


if __name__ == "__main__":
    nos, trechos = construir(baixar())
    salvar(nos, trechos)
    tipos = pd.Series([n["tipo"] for n in nos.values()]).value_counts().to_dict()
    print(tipos, f"{len(trechos)} trechos")
