"""Mapa de conferência: trechos, esquinas e centros (de data/) sobre satélite."""
import folium
import pandas as pd

from config import (ARESTAS_CSV, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, MARGEM, NOS_CSV, OUTPUT)

COR = {"esquina": "red", "centro": "cyan"}


def main():
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    m = folium.Map(location=[(LAT_MIN + LAT_MAX) / 2, (LON_MIN + LON_MAX) / 2], zoom_start=17, tiles=None)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite").add_to(m)

    ruas = folium.FeatureGroup("Trechos").add_to(m)
    for t in trechos.itertuples():
        a, b = nos.loc[t.u], nos.loc[t.v]
        folium.PolyLine([[a.lat, a.lon], [b.lat, b.lon]], color="#ffd400", weight=3,
                        tooltip=f"{t.u} — {t.v}: {t.comprimento:.1f} m").add_to(ruas)
    for tipo, cor in COR.items():
        grupo = folium.FeatureGroup(f"{tipo.capitalize()}s").add_to(m)
        for i, n in nos[nos.tipo == tipo].iterrows():
            alt = "" if pd.isna(n.altitude) else f" | {n.altitude:.0f} m"
            folium.CircleMarker([n.lat, n.lon], radius=4 if tipo == "esquina" else 3, color=cor,
                                fill=True, fill_opacity=1, tooltip=f"{i}{alt}").add_to(grupo)

    folium.Rectangle([[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]], color="white", fill=False,
                     tooltip="Área dos endereços IBGE").add_to(m)
    folium.Rectangle([[LAT_MIN - MARGEM, LON_MIN - MARGEM], [LAT_MAX + MARGEM, LON_MAX + MARGEM]],
                     color="white", dash_array="6", fill=False, tooltip="Área baixada").add_to(m)
    folium.LayerControl().add_to(m)
    m.save(OUTPUT / "ruas.html")
    print(f"{len(nos)} nós, {len(trechos)} trechos em {OUTPUT / 'ruas.html'}")


if __name__ == "__main__":
    main()
