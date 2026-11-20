"""Grafo dirigido completo, pronto para o Dijkstra, com os pesos w(u, v) = d · m(nível(u, v)).

Arestas
- rua–rua: cada trecho de data/arestas.csv vira duas arestas, uma por sentido. A inclinação é a do
  quarteirão inteiro (de esquina a esquina, pois só as esquinas têm altitude), com o sinal do sentido:
  a mesma rua pode ser difícil na subida e fácil na descida.
- rua -> casa: data/arestas_casas.csv, sem nível (multiplicador 1,0).
- loja -> rua: a loja sai para os mesmos nós de rua que ligam à casa do seu endereço (LOJA_RUA, LOJA_NUMERO),
  com a mesma distância em linha reta, sem nível (multiplicador 1,0).

Rodar `python grafo.py` grava data/grafo.csv (todas as arestas, com nível e peso) e confere a conexidade.
"""
import pandas as pd

from config import (ARESTAS_CASAS_CSV, ARESTAS_CSV, CASAS_CSV, GRAFO_CSV, LIMITE_DIFICIL, LIMITE_FACIL, LOJA_ID,
                    LOJA_NUMERO, LOJA_RUA, MULTIPLICADOR, MULTIPLICADOR_SEM_NIVEL, NOS_CSV)


def inclinacao(h_u, h_v, d):
    """Inclinação em % no sentido u -> v: positiva na subida, negativa na descida."""
    return (h_v - h_u) / d * 100


def nivel(u, v, inclinacoes):
    """Nível de dificuldade da aresta u -> v ("fácil", "moderado" ou "difícil").

    Por enquanto depende só da inclinação. Outras variáveis (tipo de piso, de via...) entram aqui,
    sem mexer no cálculo do peso.
    """
    i = inclinacoes[(u, v)]
    if i < LIMITE_FACIL:
        return "fácil"
    if i <= LIMITE_DIFICIL:
        return "moderado"
    return "difícil"


def multiplicador(nivel_, com_niveis=True):
    """m(nível). Sem nível (casa, loja) ou no modo "só distância", vale 1,0."""
    if not com_niveis or nivel_ is None:
        return MULTIPLICADOR_SEM_NIVEL
    return MULTIPLICADOR[nivel_]


def peso(d, nivel_, com_niveis=True):
    """w(u, v) = d · m(nível(u, v))."""
    return d * multiplicador(nivel_, com_niveis)


def id_loja_casa(casas):
    """id_casa do endereço da loja."""
    achou = casas[(casas.rua == LOJA_RUA) & (casas.numero == LOJA_NUMERO)]
    if len(achou) != 1:
        raise ValueError(f"endereço da loja não encontrado (ou repetido) em casas.csv: {LOJA_RUA}, {LOJA_NUMERO}")
    return int(achou.id_casa.iloc[0])


def montar():
    """Todas as arestas dirigidas: u, v, tipo, comprimento, inclinacao, nivel, multiplicador, peso."""
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    casas = pd.read_csv(CASAS_CSV)
    rua_casa = pd.read_csv(ARESTAS_CASAS_CSV)

    h = nos.altitude
    i = inclinacao(h[trechos.esq_u].values, h[trechos.esq_v].values, trechos.comprimento_quarteirao.values)
    ida = pd.DataFrame(dict(u=trechos.u, v=trechos.v, comprimento=trechos.comprimento, inclinacao=i))
    volta = pd.DataFrame(dict(u=trechos.v, v=trechos.u, comprimento=trechos.comprimento, inclinacao=-i))
    rua = pd.concat([ida, volta], ignore_index=True).assign(tipo="rua")
    inclinacoes = dict(zip(zip(rua.u, rua.v), rua.inclinacao))
    rua["nivel"] = [nivel(u, v, inclinacoes) for u, v in zip(rua.u, rua.v)]

    casa = rua_casa.assign(tipo="casa", inclinacao=float("nan"), nivel=None)
    da_loja = rua_casa[rua_casa.v == f"h{id_loja_casa(casas)}"]
    loja = pd.DataFrame(dict(u=LOJA_ID, v=da_loja.u, comprimento=da_loja.comprimento, tipo="loja",
                             inclinacao=float("nan"), nivel=None))

    arestas = pd.concat([rua, casa, loja], ignore_index=True)
    arestas["multiplicador"] = [multiplicador(n) for n in arestas.nivel]
    arestas["peso"] = arestas.comprimento * arestas.multiplicador
    return arestas[["u", "v", "tipo", "comprimento", "inclinacao", "nivel", "multiplicador", "peso"]]


def adjacencia(arestas, com_niveis=True):
    """{vértice: [(vizinho, peso), ...]}, com todos os vértices como chave (casas sem vizinhos).

    com_niveis=False dá o grafo "só distância" (multiplicador 1,0 em tudo), para comparar rotas.
    """
    grafo = {v: [] for v in pd.concat([arestas.u, arestas.v]).unique()}
    for u, v, d, n in zip(arestas.u, arestas.v, arestas.comprimento, arestas.nivel):
        grafo[u].append((v, peso(d, n, com_niveis)))
    return grafo


def coordenadas_loja(casas):
    """A loja fica no ponto da casa do seu endereço."""
    c = casas[casas.id_casa == id_loja_casa(casas)].iloc[0]
    return float(c.lat), float(c.lon)


if __name__ == "__main__":
    from dijkstra import dijkstra

    arestas = montar()
    arestas.round({"comprimento": 2, "inclinacao": 2, "peso": 2}).to_csv(GRAFO_CSV, index=False)
    grafo = adjacencia(arestas)
    L, _, _ = dijkstra(grafo, LOJA_ID)
    casas = [v for v in grafo if v.startswith("h")]
    inalcancaveis = [v for v in grafo if L[v] == float("inf")]
    print(f"{len(grafo)} vértices, {len(arestas)} arestas em {GRAFO_CSV}")
    print(arestas.tipo.value_counts().to_string())
    print("arestas de rua por nível:")
    print(arestas[arestas.tipo == "rua"].nivel.value_counts().to_string())
    print(f"loja sai para: {', '.join(arestas[arestas.tipo == 'loja'].v)}")
    print(f"vértices inalcançáveis a partir da loja: {len(inalcancaveis)} (casas: "
          f"{sum(v.startswith('h') for v in inalcancaveis)} de {len(casas)})")
