"""Altitude (SRTM 30 m, Open Topo Data) de cada nó de data/nos.csv, com cache por coordenada (a altitude depende só da posição, não do id)."""
import json
import time

import pandas as pd
import requests

from config import ALTITUDES_CACHE, NOS_CSV

URL = "https://api.opentopodata.org/v1/srtm30m"
LOTE = 100  # limite da API pública: 100 pontos/requisição, 1 req/s


def chave(lat, lon):
    return f"{lat:.6f},{lon:.6f}"


def consultar(lote):
    loc = "|".join(lote)
    for espera in (5, 10, 20, 0):
        r = requests.get(URL, params={"locations": loc}, timeout=60)
        if r.status_code != 429:
            r.raise_for_status()
            return {k: x["elevation"] for k, x in zip(lote, r.json()["results"])}
        time.sleep(espera)
    raise RuntimeError("Open Topo Data recusou o lote (429)")


if __name__ == "__main__":
    nos = pd.read_csv(NOS_CSV)
    cache = json.loads(ALTITUDES_CACHE.read_text()) if ALTITUDES_CACHE.exists() else {}
    chaves = [chave(la, lo) for la, lo in zip(nos.lat, nos.lon)]
    faltam = sorted(set(chaves) - cache.keys())
    for i in range(0, len(faltam), LOTE):
        cache.update(consultar(faltam[i:i + LOTE]))
        ALTITUDES_CACHE.write_text(json.dumps(cache))
        time.sleep(1.1)
    nos["altitude"] = [cache[k] for k in chaves]
    nos.to_csv(NOS_CSV, index=False)
    print(f"{len(faltam)} baixadas; sem altitude: {nos.altitude.isna().sum()}")
