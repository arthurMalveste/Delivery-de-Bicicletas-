"""Caminhos e constantes do projeto (fonte única)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA, OUTPUT = RAIZ / "data", RAIZ / "output"

# bbox dos endereços do IBGE (bairro Jardim Senador Vergueiro) e margem do download das ruas
LAT_MIN, LAT_MAX = -22.5715, -22.5625
LON_MIN, LON_MAX = -47.4304, -47.4185
MARGEM = 0.002  # graus (~200 m)
PASSO_CENTRO = 50  # m: n = ceil(L / PASSO_CENTRO) - 1 centros por quarteirão
CRS_METROS = "EPSG:31983"  # SIRGAS 2000 / UTM 23S: coordenadas em metros para medir distâncias

# casas (CNEFE): como cada endereço vira um ponto no lote, ao longo do seu quarteirão (ver cnefe.py)
CASA_DIST_MAX = 30           # m: endereço mais longe que isso do eixo de qualquer quarteirão é descartado
CASA_PENALIDADE_NOME = 25    # m somados à distância de um quarteirão com outro nome de rua
CASA_PENALIDADE_SEM_NOME = 5 # m somados à distância de um quarteirão sem nome no OSM
CASA_SIMILARIDADE_NOME = 0.8 # 0 a 1: semelhança mínima entre o nome do IBGE e o do OSM
CASA_ESPACO_MIN = 5          # m entre casas vizinhas na mesma calçada (frente de casa geminada)
CASA_DESVIO_MAX = 25         # m: casa que precisaria andar mais que isso para entrar na ordem fica onde está
CASA_MARGEM_ESQUINA = 6      # m: nenhuma casa fica mais perto que isso da esquina
CASA_RECUO_EXTRA = 5         # m além da calçada (onde o recenseador registrou o ponto) até a casa
CASA_RECUO_MIN, CASA_RECUO_MAX = 9, 20  # m: limites da distância do ponto da casa ao eixo da rua

# arquivos em data/
GRAFO_RUAS = DATA / "ruas.graphml"
NOS_CSV = DATA / "nos.csv"          # id, tipo, lat, lon, altitude (só esquinas)
ARESTAS_CSV = DATA / "arestas.csv"  # u, v, comprimento, esq_u, esq_v, comprimento_quarteirao (trecho sem direção)
ALTITUDES_CACHE = DATA / "altitudes.json"  # {"lat,lon": altitude}
CASAS_CSV = DATA / "casas.csv"
ARESTAS_CASAS_CSV = DATA / "arestas_casas.csv"  # u (nó de rua) -> v (casa "h<id_casa>"), comprimento em linha reta
CNEFE_ZIP = DATA / "bruto" / "3526902_LIMEIRA.zip"
CNEFE_URL = ("https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
             "Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/35_SP/3526902_LIMEIRA.zip")
