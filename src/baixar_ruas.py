"""Baixa as ruas da bbox (com margem) via OSMnx e salva em data/ruas.graphml."""
import osmnx as ox

from config import DATA, GRAFO_RUAS, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, MARGEM

ox.settings.cache_folder = DATA / "cache"


def baixar(forcar=False):
    """Ruas do bairro como grafo SEM direção: toda rua é mão dupla (mão única é ignorada)."""
    if forcar or not GRAFO_RUAS.exists():
        DATA.mkdir(exist_ok=True)
        # OSMnx 2.x: bbox = (oeste, sul, leste, norte)
        bbox = (LON_MIN - MARGEM, LAT_MIN - MARGEM, LON_MAX + MARGEM, LAT_MAX + MARGEM)
        ox.save_graphml(ox.graph_from_bbox(bbox, network_type="bike"), GRAFO_RUAS)
    return ox.convert.to_undirected(ox.load_graphml(GRAFO_RUAS))


if __name__ == "__main__":
    g = baixar()
    print(f"{g.number_of_nodes()} nós, {g.number_of_edges()} arestas")
