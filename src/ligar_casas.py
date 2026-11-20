"""Arestas rua -> casa (data/arestas_casas.csv), pela regra de vizinhança do escopo.

Ao longo de um quarteirão os nós de rua ficam em ordem: esquina, centros, esquina. Com n centros, o nó k
(k = 0 .. n+1) está na posição relativa r_k = k / (n + 1). Cada nó de rua liga às casas entre o nó anterior
e o próximo, incluindo as que estão na frente deles:

    nó k  ->  casas com r_(k-1) <= posicao_rel <= r_(k+1)

Exemplo do escopo: centro B entre as esquinas A e C liga às casas de A até C; A liga às casas de A até B;
C às de B até C. As casas dos dois lados da rua usam os mesmos nós.

As arestas só vão da rua para a casa (a casa nunca é intermediária de rota). O comprimento é a distância
em linha reta entre o nó de rua e o ponto da casa; o multiplicador de nível dessas arestas é sempre 1,0.
O id do vértice da casa é "h" + id_casa (as esquinas começam com "e" e os centros com "c").
"""
import numpy as np
import pandas as pd
from pyproj import Transformer

from config import ARESTAS_CASAS_CSV, ARESTAS_CSV, CASAS_CSV, CRS_METROS, NOS_CSV

PARA_METROS = Transformer.from_crs("EPSG:4326", CRS_METROS, always_xy=True)


def id_vertice_casa(id_casa):
    return f"h{id_casa}"


def nos_do_quarteirao(trechos):
    """{(esq_u, esq_v): [esq_u, c.., esq_v]}, na ordem em que grafo_ruas gravou os trechos."""
    return {chave: [t.u.iloc[0], *t.v] for chave, t in trechos.groupby(["esq_u", "esq_v"], sort=False)}


def ligar(nos, trechos, casas):
    xy = dict(zip(nos.index, zip(*PARA_METROS.transform(nos.lon.values, nos.lat.values))))
    cx, cy = PARA_METROS.transform(casas.lon.values, casas.lat.values)
    casas = casas.assign(x=cx, y=cy)
    sequencia = nos_do_quarteirao(trechos)
    arestas = []
    for (esq_u, esq_v), grupo in casas.groupby(["esq_u", "esq_v"]):
        ids = sequencia[(esq_u, esq_v)]
        r = np.linspace(0, 1, len(ids))  # r_k = k / (n + 1)
        for k, no in enumerate(ids):
            ini, fim = r[max(k - 1, 0)], r[min(k + 1, len(ids) - 1)]
            for c in grupo[(grupo.posicao_rel >= ini) & (grupo.posicao_rel <= fim)].itertuples():
                x, y = xy[no]
                arestas.append(dict(u=no, v=id_vertice_casa(c.id_casa),
                                    comprimento=round(float(np.hypot(c.x - x, c.y - y)), 2)))
    return pd.DataFrame(arestas)


if __name__ == "__main__":
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    casas = pd.read_csv(CASAS_CSV)
    arestas = ligar(nos, trechos, casas)
    arestas.to_csv(ARESTAS_CASAS_CSV, index=False)
    por_casa = arestas.groupby("v").size()
    sem_aresta = set(map(id_vertice_casa, casas.id_casa)) - set(arestas.v)
    print(f"{len(arestas)} arestas rua -> casa em {ARESTAS_CASAS_CSV}")
    print(f"arestas por casa: mínimo {por_casa.min()}, mediana {por_casa.median():.0f}, máximo {por_casa.max()}")
    print(f"comprimento (m): mediana {arestas.comprimento.median():.1f}, máximo {arestas.comprimento.max():.1f}")
    print(f"casas sem aresta: {len(sem_aresta)}")
