"""Constantes do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
OUTPUT = RAIZ / "output"

# Área dos endereços do IBGE (bairro Jardim Senador Vergueiro)
LAT_MIN, LAT_MAX = -22.5715, -22.5625
LON_MIN, LON_MAX = -47.4304, -47.4185
MARGEM = 0.002  # graus (~200 m)

GRAFO_RUAS = DATA / "ruas.graphml"
