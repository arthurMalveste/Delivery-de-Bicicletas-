"""Busca a altitude (SRTM 30 m) de cada esquina na Open Topo Data, em lotes, com cache.

Entrada: data/ruas.graphml. Saída/cache: data/altitudes.json ({id_do_no: altitude_m}).
A API pública permite 100 pontos por requisição, 1 requisição/s e 1000/dia.
Uso: python src/altitudes.py
"""
import json
import time

import osmnx as ox
import requests

from config import DATA, GRAFO_RUAS

ARQ_ALTITUDES = DATA / "altitudes.json"
URL = "https://api.opentopodata.org/v1/srtm30m"
TAM_LOTE = 100
PAUSA_S = 1.1
TENTATIVAS = 4


def _consultar_lote(pontos):
    """pontos: lista de (id, lat, lon). Retorna {id: altitude}."""
    locais = "|".join(f"{lat:.6f},{lon:.6f}" for _, lat, lon in pontos)
    for tentativa in range(TENTATIVAS):
        resp = requests.get(URL, params={"locations": locais}, timeout=60)
        if resp.status_code == 429:  # limite de taxa: espera e tenta de novo
            time.sleep(5 * (tentativa + 1))
            continue
        resp.raise_for_status()
        resultados = resp.json()["results"]
        return {pid: r["elevation"] for (pid, _, _), r in zip(pontos, resultados)}
    raise RuntimeError("Open Topo Data recusou o lote (429) após várias tentativas")


def _salvar(altitudes):
    DATA.mkdir(exist_ok=True)
    ARQ_ALTITUDES.write_text(json.dumps(altitudes, indent=0), encoding="utf-8")


def buscar(forcar=False):
    """Retorna {id_no: altitude}; só consulta a API para nós ainda sem altitude."""
    g = ox.load_graphml(GRAFO_RUAS)
    altitudes = {}
    if ARQ_ALTITUDES.exists() and not forcar:
        altitudes = json.loads(ARQ_ALTITUDES.read_text(encoding="utf-8"))

    faltam = [(str(n), d["y"], d["x"]) for n, d in g.nodes(data=True) if str(n) not in altitudes]
    print(f"{g.number_of_nodes()} nós, {len(faltam)} sem altitude no cache")

    for i in range(0, len(faltam), TAM_LOTE):
        lote = faltam[i:i + TAM_LOTE]
        altitudes.update(_consultar_lote(lote))
        _salvar(altitudes)  # salva a cada lote: uma falha não perde o que já veio
        print(f"  lote {i // TAM_LOTE + 1}: {len(lote)} pontos")
        if i + TAM_LOTE < len(faltam):
            time.sleep(PAUSA_S)
    return altitudes


if __name__ == "__main__":
    alt = buscar()
    sem_dado = [n for n, h in alt.items() if h is None]
    vals = [h for h in alt.values() if h is not None]
    print(f"{len(alt)} altitudes em {ARQ_ALTITUDES}")
    if vals:
        print(f"mín {min(vals):.0f} m, máx {max(vals):.0f} m")
    if sem_dado:
        print(f"ATENÇÃO: {len(sem_dado)} nós sem dado SRTM: {sem_dado[:10]}")
