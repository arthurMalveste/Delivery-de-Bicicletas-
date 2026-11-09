"""Baixa o CNEFE 2022 de Limeira, filtra o Jardim Senador Vergueiro e agrupa em casas.

Saída: dados/casas.csv (uma linha por casa/prédio).
Uso: python src/cnefe.py
"""
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BRUTO = RAIZ / "dados" / "bruto"
ZIP_LOCAL = PASTA_BRUTO / "3526902_LIMEIRA.zip"
SAIDA = RAIZ / "dados" / "casas.csv"

URL = (
    "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
    "Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/35_SP/3526902_LIMEIRA.zip"
)

# bbox dos endereços do bairro (do escopo)
LAT_MIN, LAT_MAX = -22.5715, -22.5625
LON_MIN, LON_MAX = -47.4304, -47.4185
LOCALIDADE = "JARDIM SENADOR VERGUEIRO"


def baixar():
    """Baixa o zip do município, usando o cache em disco se já existir."""
    if ZIP_LOCAL.exists():
        return
    PASTA_BRUTO.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, timeout=120)
    resp.raise_for_status()
    ZIP_LOCAL.write_bytes(resp.content)


def carregar():
    baixar()
    with zipfile.ZipFile(ZIP_LOCAL) as z:
        nome = z.namelist()[0]
        with z.open(nome) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"), sep=";", dtype=str)
    df["LATITUDE"] = df["LATITUDE"].astype(float)
    df["LONGITUDE"] = df["LONGITUDE"].astype(float)
    return df


def filtrar_bairro(df):
    """Registros do bairro: dentro da bbox e com a localidade do bairro."""
    dentro = df["LATITUDE"].between(LAT_MIN, LAT_MAX) & df["LONGITUDE"].between(LON_MIN, LON_MAX)
    return df[dentro & (df["DSC_LOCALIDADE"] == LOCALIDADE)]


def agrupar_casas(reg):
    """Junta registros com mesma rua e número (apartamentos do mesmo prédio) em uma casa."""
    g = reg.groupby(["NOM_TIPO_SEGLOGR", "NOM_SEGLOGR", "NUM_ENDERECO"], as_index=False).agg(
        lat=("LATITUDE", "mean"),
        lon=("LONGITUDE", "mean"),
        n_registros=("COD_UNICO_ENDERECO", "size"),
    )
    g = g.rename(columns={"NOM_TIPO_SEGLOGR": "tipo", "NOM_SEGLOGR": "rua", "NUM_ENDERECO": "numero"})
    g["numero"] = g["numero"].astype(int)
    g = g.sort_values(["rua", "numero"]).reset_index(drop=True)
    g.insert(0, "id_casa", g.index + 1)
    return g


def main():
    reg = filtrar_bairro(carregar())
    casas = agrupar_casas(reg)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    casas.to_csv(SAIDA, index=False, encoding="utf-8")
    print(f"{len(reg)} registros -> {len(casas)} casas em {SAIDA}")


if __name__ == "__main__":
    main()
