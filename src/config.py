"""Caminhos e constantes do projeto (fonte única)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA, OUTPUT = RAIZ / "data", RAIZ / "output"

# bbox dos endereços do IBGE (bairro Jardim Senador Vergueiro) e margem do download das ruas
LAT_MIN, LAT_MAX = -22.5715, -22.5625
LON_MIN, LON_MAX = -47.4304, -47.4185
MARGEM = 0.002  # graus (~200 m)
LOCALIDADE = "JARDIM SENADOR VERGUEIRO"
PASSO_CENTRO = 50  # m: n = ceil(L / PASSO_CENTRO) - 1 centros por quarteirão

# arquivos em data/
GRAFO_RUAS = DATA / "ruas.graphml"
NOS_CSV = DATA / "nos.csv"          # id, tipo, lat, lon, altitude (só esquinas)
ARESTAS_CSV = DATA / "arestas.csv"  # u, v, comprimento, esq_u, esq_v, comprimento_quarteirao (trecho sem direção)
ALTITUDES_CACHE = DATA / "altitudes.json"  # {"lat,lon": altitude}
CASAS_CSV = DATA / "casas.csv"
CNEFE_ZIP = DATA / "bruto" / "3526902_LIMEIRA.zip"
CNEFE_URL = ("https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
             "Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/35_SP/3526902_LIMEIRA.zip")
