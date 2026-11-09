"""Baixa as ruas da bbox (com margem) via OSMnx e salva em data/ruas.graphml."""
import osmnx as ox

from config import (DATA, GRAFO_RUAS, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN,
                    MARGEM)


def baixar(forcar=False):
    DATA.mkdir(exist_ok=True)
    if GRAFO_RUAS.exists() and not forcar:
        print(f"Cache encontrado: {GRAFO_RUAS}")
        return ox.load_graphml(GRAFO_RUAS)
    # OSMnx 2.x: bbox = (esquerda, baixo, direita, cima) = (oeste, sul, leste, norte)
    bbox = (LON_MIN - MARGEM, LAT_MIN - MARGEM, LON_MAX + MARGEM, LAT_MAX + MARGEM)
    g = ox.graph_from_bbox(bbox, network_type="bike", simplify=True)
    ox.save_graphml(g, GRAFO_RUAS)
    print(f"Salvo em {GRAFO_RUAS}")
    return g


if __name__ == "__main__":
    g = baixar()
    print(f"{g.number_of_nodes()} nós, {g.number_of_edges()} arestas")
