"""Busca a altitude (SRTM 30 m, Open Topo Data) dos nós em data/nos.csv, com cache."""
import json
import time

import pandas as pd
import requests

from config import ALTITUDES_CACHE, NOS_CSV

URL = "https://api.opentopodata.org/v1/srtm30m"
LOTE = 100  # máximo por requisição na API pública


def chave(lat, lon):
    return f"{lat:.6f},{lon:.6f}"


def buscar(pontos):
    cache = json.loads(ALTITUDES_CACHE.read_text()) if ALTITUDES_CACHE.exists() else {}
    faltam = [p for p in pontos if chave(*p) not in cache]
    for i in range(0, len(faltam), LOTE):
        lote = faltam[i:i + LOTE]
        loc = "|".join(f"{la:.6f},{lo:.6f}" for la, lo in lote)
        r = requests.get(URL, params={"locations": loc}, timeout=60)
        r.raise_for_status()
        for p, res in zip(lote, r.json()["results"]):
            cache[chave(*p)] = res["elevation"]
        ALTITUDES_CACHE.write_text(json.dumps(cache))
        print(f"{min(i + LOTE, len(faltam))}/{len(faltam)} altitudes baixadas")
        time.sleep(1.1)  # limite: 1 req/s
    return cache


if __name__ == "__main__":
    nos = pd.read_csv(NOS_CSV)
    cache = buscar(list(zip(nos.lat, nos.lon)))
    nos["altitude"] = [cache[chave(la, lo)] for la, lo in zip(nos.lat, nos.lon)]
    nos.to_csv(NOS_CSV, index=False)
    print(nos.altitude.describe().round(1).to_string())
    print("sem altitude:", int(nos.altitude.isna().sum()))
