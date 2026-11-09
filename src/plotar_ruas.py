"""Plota o grafo de ruas sobre satélite, com a bbox dos endereços, para conferência."""
import folium
import osmnx as ox

from baixar_ruas import baixar
from config import (LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, MARGEM, OUTPUT)


def main():
    OUTPUT.mkdir(exist_ok=True)
    g = baixar()
    nos, arestas = ox.graph_to_gdfs(g)
    centro = [(LAT_MIN + LAT_MAX) / 2, (LON_MIN + LON_MAX) / 2]
    m = folium.Map(location=centro, zoom_start=16, tiles=None)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite").add_to(m)
    folium.GeoJson(arestas[["geometry"]], name="Ruas",
                   style_function=lambda _: {"color": "#ffd400", "weight": 3}).add_to(m)
    for _, n in nos.iterrows():
        folium.CircleMarker([n.y, n.x], radius=3, color="red", fill=True).add_to(m)
    folium.Rectangle([[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]], color="cyan",
                     fill=False, tooltip="Área dos endereços IBGE").add_to(m)
    folium.Rectangle([[LAT_MIN - MARGEM, LON_MIN - MARGEM], [LAT_MAX + MARGEM, LON_MAX + MARGEM]],
                     color="white", dash_array="6", fill=False, tooltip="Área baixada").add_to(m)
    folium.LayerControl().add_to(m)
    saida = OUTPUT / "ruas.html"
    m.save(saida)
    print(f"Mapa salvo em {saida}")


if __name__ == "__main__":
    main()
