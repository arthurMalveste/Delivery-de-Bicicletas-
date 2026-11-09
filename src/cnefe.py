"""CNEFE 2022 de Limeira -> data/casas.csv (uma linha por casa/prédio do bairro)."""
import requests
import pandas as pd

from config import (CASAS_CSV, CNEFE_URL, CNEFE_ZIP, LAT_MAX, LAT_MIN, LOCALIDADE,
                    LON_MAX, LON_MIN)


def carregar():
    if not CNEFE_ZIP.exists():
        CNEFE_ZIP.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(CNEFE_URL, timeout=120)
        r.raise_for_status()
        CNEFE_ZIP.write_bytes(r.content)
    return pd.read_csv(CNEFE_ZIP, sep=";", dtype=str, encoding="utf-8")


def casas(df):
    """Filtra o bairro e junta registros de mesma rua e número (apartamentos) em uma casa."""
    lat, lon = df.LATITUDE.astype(float), df.LONGITUDE.astype(float)
    df = df.assign(lat=lat, lon=lon)[lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX)
                                     & (df.DSC_LOCALIDADE == LOCALIDADE)]
    g = df.groupby(["NOM_TIPO_SEGLOGR", "NOM_SEGLOGR", "NUM_ENDERECO"], as_index=False).agg(
        lat=("lat", "mean"), lon=("lon", "mean"), n_registros=("COD_UNICO_ENDERECO", "size"))
    g.columns = ["tipo", "rua", "numero", "lat", "lon", "n_registros"]
    g["numero"] = g.numero.astype(int)
    g = g.sort_values(["rua", "numero"]).reset_index(drop=True)
    g.insert(0, "id_casa", g.index + 1)
    return g


if __name__ == "__main__":
    c = casas(carregar())
    c.to_csv(CASAS_CSV, index=False)
    print(f"{len(c)} casas ({c.n_registros.sum()} registros) em {CASAS_CSV}")
