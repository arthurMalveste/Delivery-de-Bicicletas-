"""CNEFE 2022 de Limeira -> data/casas.csv: uma casa por endereço, posicionada no lote, ao longo do seu quarteirão.

A coordenada do IBGE é o GPS do recenseador, parado na calçada: cai perto do eixo da rua, às vezes do lado errado,
fora de ordem ou com várias casas no mesmo ponto. Por isso a casa não usa a coordenada direto:

1. Entram os endereços do IBGE na área do grafo de ruas, de todos os bairros.
2. Apartamentos de um mesmo prédio (bairro, rua, número) viram uma casa só. Endereços sem número (s/n)
   viram uma casa por face de quadra do IBGE.
3. Cada casa é associada ao quarteirão (trecho esquina–esquina do grafo) mais próximo, dando preferência
   aos quarteirões com o mesmo nome de rua. Casa a mais de CASA_DIST_MAX m de qualquer quarteirão é descartada.
4. A casa é projetada no eixo do quarteirão: posição (metros desde a esquina esq_u) e lado da rua
   (E = esquerda, D = direita, olhando de esq_u para esq_v). Como uma face de quadra do IBGE é um lado da rua,
   o lado é decidido por maioria entre as casas da mesma face.
5. Em cada calçada (quarteirão + lado), as casas da mesma rua são postas em ordem de número e afastadas pelo
   menos CASA_ESPACO_MIN m uma da outra, mexendo o mínimo possível nas posições medidas (regressão isotônica).
   Casa que teria de andar mais de CASA_DESVIO_MAX m fica onde o IBGE mediu (número ou GPS inconsistente).
6. O ponto final fica na posição ajustada, afastado do eixo da rua para o lado certo, dentro do lote.

As colunas esq_u, esq_v e posicao_rel (0 a 1 ao longo do quarteirão) servem para ligar a casa aos nós
de rua: o centro i de um quarteirão com n centros fica em posicao_rel = i / (n + 1).
"""
import difflib
import re
import unicodedata

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import LineString, Point

from baixar_ruas import baixar
from config import (CASA_DESVIO_MAX, CASA_DIST_MAX, CASA_ESPACO_MIN, CASA_MARGEM_ESQUINA, CASA_PENALIDADE_NOME,
                    CASA_PENALIDADE_SEM_NOME, CASA_RECUO_EXTRA, CASA_RECUO_MAX, CASA_RECUO_MIN,
                    CASA_SIMILARIDADE_NOME, CASAS_CSV, CNEFE_URL, CNEFE_ZIP, CRS_METROS)
from grafo_ruas import quarteiroes

PARA_METROS = Transformer.from_crs("EPSG:4326", CRS_METROS, always_xy=True)
PARA_GRAUS = Transformer.from_crs(CRS_METROS, "EPSG:4326", always_xy=True)

# palavras ignoradas ao comparar nomes de rua (o OSM costuma trazer tipo e título, o IBGE não)
PALAVRAS_IGNORADAS = {"RUA", "AVENIDA", "TRAVESSA", "PRACA", "RODOVIA", "VIA", "ALAMEDA", "ESTRADA", "VIELA",
                      "DOUTOR", "DOUTORA", "PROFESSOR", "PROFESSORA", "COMENDADOR", "DEPUTADO", "ARQUITETA",
                      "ARQUITETO", "DONA", "SENHOR", "ENGENHEIRO", "PADRE", "VEREADOR", "CORONEL", "PREFEITO",
                      "DR", "PROF", "DE", "DA", "DO", "DOS", "DAS", "E"}


def carregar():
    if not CNEFE_ZIP.exists():
        CNEFE_ZIP.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(CNEFE_URL, timeout=120)
        r.raise_for_status()
        CNEFE_ZIP.write_bytes(r.content)
    return pd.read_csv(CNEFE_ZIP, sep=";", dtype=str, encoding="utf-8")


# ---------------------------------------------------------------- nomes de rua

def nome_base(nome):
    """'Rua Arnaldo Stoco' e 'ARNALDO STOCCO' viram 'ARNALDO STOCO': sem acento, tipo, título e letra dobrada."""
    s = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode().upper()
    palavras = [p for p in re.sub(r"[^A-Z ]", " ", s).split() if p not in PALAVRAS_IGNORADAS]
    palavras = [re.sub(r"(.)\1", r"\1", p.replace("TH", "T").replace("Y", "I")) for p in palavras]
    return " ".join(palavras)


def mesmo_nome(a, b):
    """Nomes já em nome_base. Iguais, um contido no outro (abreviações) ou parecidos o bastante."""
    if not a or not b:
        return False
    pa, pb = set(a.split()), set(b.split())
    if pa <= pb or pb <= pa:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= CASA_SIMILARIDADE_NOME


# ---------------------------------------------------------------- quarteirões

def blocos(g):
    """Quarteirões do grafo, na mesma ordem e orientação de grafo_ruas.construir, com geometria em metros."""
    lista = []
    for u, v, d in quarteiroes(g):
        if u == v and d["length"] == 0:
            continue
        geom = d.get("geometry") or LineString(
            [(g.nodes[u]["x"], g.nodes[u]["y"]), (g.nodes[v]["x"], g.nodes[v]["y"])])
        pu = Point(g.nodes[u]["x"], g.nodes[u]["y"])
        if Point(geom.coords[0]).distance(pu) > Point(geom.coords[-1]).distance(pu):
            geom = LineString(list(geom.coords)[::-1])
        x, y = PARA_METROS.transform(*np.array(geom.coords).T)
        nomes = d.get("name") or []
        nomes = [nome_base(n) for n in (nomes if isinstance(nomes, list) else [nomes])]
        lista.append(dict(esq_u=f"e{u}", esq_v=f"e{v}", geom=LineString(np.column_stack([x, y])), nomes=nomes))
    return lista


def tangente(geom, s):
    """Vetor unitário na direção do quarteirão (esq_u -> esq_v) na posição s."""
    a = geom.interpolate(max(s - 1, 0))
    b = geom.interpolate(min(s + 1, geom.length))
    t = np.array([b.x - a.x, b.y - a.y])
    return t / (np.linalg.norm(t) or 1)


# ---------------------------------------------------------------- etapas

def enderecos(df, g):
    """Etapa 1: registros do IBGE na área do grafo (todos os bairros), com x, y em metros."""
    lat, lon = df.LATITUDE.astype(float), df.LONGITUDE.astype(float)
    ys = [d["y"] for _, d in g.nodes(data=True)]
    xs = [d["x"] for _, d in g.nodes(data=True)]
    m = 0.0005  # ~50 m, para pegar casas das ruas da borda
    df = df.assign(lat=lat, lon=lon)[lat.between(min(ys) - m, max(ys) + m) & lon.between(min(xs) - m, max(xs) + m)]
    x, y = PARA_METROS.transform(df.lon.values, df.lat.values)
    return df.assign(x=x, y=y, numero=df.NUM_ENDERECO.astype(int),
                     face=df.COD_SETOR + "-" + df.NUM_QUADRA + "-" + df.NUM_FACE)


def agrupar(df):
    """Etapa 2: uma linha por casa. Prédios juntam pelo número; s/n juntam por face de quadra."""
    df = df.assign(chave_sn=df.face.where(df.numero == 0, ""))
    g = df.groupby(["DSC_LOCALIDADE", "NOM_TIPO_SEGLOGR", "NOM_SEGLOGR", "numero", "chave_sn"], as_index=False,
                   dropna=False).agg(x=("x", "median"), y=("y", "median"), lat_ibge=("lat", "median"),
                                     lon_ibge=("lon", "median"), face=("face", lambda f: f.mode().iloc[0]),
                                     n_registros=("COD_UNICO_ENDERECO", "size"))
    return g.rename(columns={"DSC_LOCALIDADE": "bairro", "NOM_TIPO_SEGLOGR": "tipo", "NOM_SEGLOGR": "rua"}) \
            .drop(columns="chave_sn")


def associar(casas, bl):
    """Etapa 3 e 4: quarteirão, posição ao longo dele, distância ao eixo e lado de cada casa."""
    arvore = STRtree([b["geom"] for b in bl])
    nome_casa = {r: nome_base(r) for r in casas.rua.unique()}
    res = []
    for c in casas.itertuples():
        p = Point(c.x, c.y)
        melhor = None
        for i in arvore.query(p, predicate="dwithin", distance=CASA_DIST_MAX):
            b = bl[i]
            d = b["geom"].distance(p)
            if not b["nomes"]:
                custo = d + CASA_PENALIDADE_SEM_NOME
            elif any(mesmo_nome(nome_casa[c.rua], n) for n in b["nomes"]):
                custo = d
            else:
                custo = d + CASA_PENALIDADE_NOME
            if melhor is None or custo < melhor[0]:
                melhor = (custo, i, d)
        if melhor is None:
            res.append((None, np.nan, np.nan, 0))
            continue
        _, i, d = melhor
        geom = bl[i]["geom"]
        s = geom.project(p)
        t = tangente(geom, s)
        q = geom.interpolate(s)
        lado = 1 if t[0] * (c.y - q.y) - t[1] * (c.x - q.x) > 0 else -1  # +1 = esquerda
        res.append((i, s, d, lado))
    casas = casas.assign(**dict(zip(["bloco", "posicao", "dist_ibge", "lado"], map(list, zip(*res)))))
    descartadas = casas.bloco.isna()
    casas = casas[~descartadas].astype({"bloco": int})
    # uma face de quadra é um lado da rua: o lado vale por maioria (ponderada pelos registros) na face
    voto = (casas.lado * casas.n_registros).groupby([casas.face, casas.bloco]).transform("sum")
    casas = casas.assign(lado=np.where(voto != 0, np.sign(voto), casas.lado).astype(int))
    return casas, int(descartadas.sum())


def isotonica(y):
    """Regressão isotônica (pool adjacent violators): sequência não decrescente mais próxima de y."""
    blocos_ = []  # [soma, quantidade]
    for v in y:
        blocos_.append([v, 1])
        while len(blocos_) > 1 and blocos_[-2][0] / blocos_[-2][1] > blocos_[-1][0] / blocos_[-1][1]:
            s, n = blocos_.pop()
            blocos_[-1][0] += s
            blocos_[-1][1] += n
    return np.concatenate([np.full(n, s / n) for s, n in blocos_])


def espacar(p, gap, lo, hi):
    """Posições p (já na ordem dos números) -> não decrescentes, a pelo menos `gap` m, dentro de [lo, hi]."""
    k = len(p)
    i = np.arange(k)
    # x_(i+1) - x_i >= gap  <=>  z_i = x_i - i * gap não decrescente
    x = isotonica(p - i * gap) + i * gap
    x = np.clip(x, lo + i * gap, hi - (k - 1 - i) * gap)  # cabe no quarteirão sem perder o espaçamento
    return x


def ordenar_calcada(pos, numeros, L):
    """Etapa 5: posições em ordem de número, a pelo menos CASA_ESPACO_MIN m, dentro do quarteirão.

    Casa que precisaria andar mais de CASA_DESVIO_MAX m para entrar na ordem tem número ou GPS
    inconsistente: fica onde o IBGE mediu e sai da ordenação (uma por vez, a pior primeiro).
    """
    margem = min(CASA_MARGEM_ESQUINA, L / 4)
    lo, hi = margem, L - margem
    pos = np.clip(np.asarray(pos, float), lo, hi)
    numeros = np.asarray(numeros)
    ativos = np.flatnonzero(numeros > 0)
    while len(ativos) >= 2:
        p, n = pos[ativos], numeros[ativos]
        crescente = np.sum((n - n.mean()) * (p - p.mean())) >= 0  # numeração cresce de esq_u para esq_v?
        if not crescente:
            p = L - p
        ordem = np.argsort(n, kind="stable")
        gap = min(CASA_ESPACO_MIN, (hi - lo) / (len(ativos) - 1))
        x = np.empty(len(ativos))
        x[ordem] = espacar(p[ordem], gap, lo, hi)
        desvio = np.abs(x - p)
        if desvio.max() <= CASA_DESVIO_MAX:
            pos[ativos] = x if crescente else L - x
            break
        ativos = np.delete(ativos, desvio.argmax())
    return pos


def posicionar(casas, bl):
    """Etapas 5 e 6: ajusta a posição em cada calçada e coloca o ponto no lote."""
    casas = casas.copy()
    casas["x_final"] = np.nan
    casas["y_final"] = np.nan
    for (i, lado), calcada in casas.groupby(["bloco", "lado"]):
        geom = bl[i]["geom"]
        recuo = np.clip(calcada.dist_ibge.median() + CASA_RECUO_EXTRA, CASA_RECUO_MIN, CASA_RECUO_MAX)
        # a numeração só é contínua dentro da mesma rua (a casa de esquina pode ser da rua transversal)
        for _, grupo in calcada.groupby("rua"):
            casas.loc[grupo.index, "posicao"] = ordenar_calcada(grupo.posicao.values, grupo.numero.values,
                                                                geom.length)
        # passada final na calçada inteira: mantém a ordem e só afasta pontos colados (s/n, esquinas, exceções)
        grupo = casas.loc[calcada.index].sort_values("posicao")
        pos = grupo.posicao.values
        if len(pos) >= 2:
            margem = min(CASA_MARGEM_ESQUINA, geom.length / 4)
            lo, hi = margem, geom.length - margem
            pos = espacar(pos, min(CASA_ESPACO_MIN, (hi - lo) / (len(pos) - 1)), lo, hi)
        for idx, s in zip(grupo.index, pos):
            q = geom.interpolate(s)
            t = tangente(geom, s)
            normal = np.array([-t[1], t[0]]) * lado  # esquerda de t, ou direita se lado = -1
            casas.loc[idx, ["posicao", "x_final", "y_final"]] = [s, q.x + normal[0] * recuo,
                                                                  q.y + normal[1] * recuo]
    lon, lat = PARA_GRAUS.transform(casas.x_final.values, casas.y_final.values)
    comprimento = np.array([bl[i]["geom"].length for i in casas.bloco])
    return casas.assign(
        lat=lat, lon=lon,
        esq_u=[bl[i]["esq_u"] for i in casas.bloco], esq_v=[bl[i]["esq_v"] for i in casas.bloco],
        posicao_rel=casas.posicao / comprimento,
        deslocamento=np.hypot(casas.x_final - casas.x, casas.y_final - casas.y),
        lado=np.where(casas.lado > 0, "E", "D"))


def casas_do_bairro(df, g):
    bl = blocos(g)
    reg = enderecos(df, g)
    casas, descartadas = associar(agrupar(reg), bl)
    casas = posicionar(casas, bl)
    casas = casas.sort_values(["rua", "numero", "bairro"]).reset_index(drop=True)
    casas.insert(0, "id_casa", casas.index + 1)
    colunas = ["id_casa", "tipo", "rua", "numero", "bairro", "lat", "lon", "n_registros", "esq_u", "esq_v",
               "posicao", "posicao_rel", "lado", "lat_ibge", "lon_ibge", "dist_ibge", "deslocamento", "face"]
    return casas[colunas].round({"lat": 7, "lon": 7, "posicao": 2, "posicao_rel": 4, "dist_ibge": 2,
                                 "deslocamento": 2}), len(reg), descartadas


if __name__ == "__main__":
    casas, n_reg, descartadas = casas_do_bairro(carregar(), baixar())
    casas.to_csv(CASAS_CSV, index=False)
    print(f"{n_reg} registros do IBGE na área do grafo")
    print(f"{len(casas)} casas ({casas.n_registros.sum()} registros) em {CASAS_CSV}")
    print(f"{descartadas} endereços descartados (a mais de {CASA_DIST_MAX} m de qualquer quarteirão)")
    print(f"{casas.groupby(['esq_u', 'esq_v']).ngroups} quarteirões com casa")
    print("deslocamento do ponto do IBGE até o lote (m), quantis 50/90/99:",
          np.percentile(casas.deslocamento, [50, 90, 99]).round(1))
    print(casas.bairro.value_counts().to_string())
