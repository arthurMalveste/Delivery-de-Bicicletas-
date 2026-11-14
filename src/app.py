"""Interface web (Streamlit) do projeto: escolher origem/destino e ver o grafo do bairro.

Rodar a partir da raiz do projeto:
    streamlit run src/app.py

Reaproveita os dados gerados pelo grupo em data/ (nos.csv, arestas.csv, casas.csv) e as
constantes de config.py; não altera nenhum dos scripts de geração.
"""
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from config import ARESTAS_CSV, CASAS_CSV, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, NOS_CSV

SATELITE = "Satélite + grafo"
SO_GRAFO = "Só o grafo (fundo branco)"

# cor das ruas por fundo: amarelo contrasta com o satélite, azul-escuro com o branco
COR_RUA = {SATELITE: "#ffd400", SO_GRAFO: "#1f4e79"}
COR_NO = {"esquina": "red", "centro": "cyan"}
TILES_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


@st.cache_data
def carregar():
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    casas = pd.read_csv(CASAS_CSV).set_index("id_casa")
    return nos, trechos, casas


def rotulo_casa(id_casa, casa):
    numero = "s/n" if casa.numero == 0 else int(casa.numero)
    return f"{casa.rua}, {numero} (casa {id_casa})"


def construir_mapa(modo, nos, trechos, casas, mostrar, origem, destino):
    m = folium.Map(location=[(LAT_MIN + LAT_MAX) / 2, (LON_MIN + LON_MAX) / 2], zoom_start=17,
                   tiles=None, max_zoom=19)
    if modo == SATELITE:
        folium.TileLayer(TILES_ESRI, attr="Esri World Imagery", name="Satélite", max_zoom=19).add_to(m)
    else:  # sem tiles: o fundo do Leaflet passa a ser branco
        m.get_root().header.add_child(
            folium.Element("<style>.leaflet-container{background:#ffffff !important;}</style>"))

    if mostrar["trechos"]:
        grupo = folium.FeatureGroup("Trechos").add_to(m)
        for t in trechos.itertuples():
            a, b = nos.loc[t.u], nos.loc[t.v]
            folium.PolyLine([[a.lat, a.lon], [b.lat, b.lon]], color=COR_RUA[modo], weight=3,
                            tooltip=f"{t.u} — {t.v}: {t.comprimento:.1f} m").add_to(grupo)
    for tipo, cor in COR_NO.items():
        if not mostrar[tipo]:
            continue
        grupo = folium.FeatureGroup(f"{tipo.capitalize()}s").add_to(m)
        for i, n in nos[nos.tipo == tipo].iterrows():
            alt = "" if pd.isna(n.altitude) else f" | {n.altitude:.0f} m"
            folium.CircleMarker([n.lat, n.lon], radius=4 if tipo == "esquina" else 3, color=cor,
                                fill=True, fill_opacity=1, tooltip=f"{i}{alt}").add_to(grupo)
    if mostrar["casas"]:
        grupo = folium.FeatureGroup("Casas").add_to(m)
        for i, c in casas.iterrows():
            folium.CircleMarker([c.lat, c.lon], radius=3, color="#ff8c00", fill=True, fill_opacity=1,
                                tooltip=rotulo_casa(i, c)).add_to(grupo)

    for id_casa, nome, cor, icone in ((origem, "Origem", "green", "play"), (destino, "Destino", "red", "flag")):
        c = casas.loc[id_casa]
        folium.Marker([c.lat, c.lon], tooltip=f"{nome}: {rotulo_casa(id_casa, c)}",
                      icon=folium.Icon(color=cor, icon=icone)).add_to(m)

    m.fit_bounds([[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]])
    return m


def main():
    st.set_page_config(page_title="Delivery de Bicicletas — Limeira", layout="wide")
    st.title("Delivery de Bicicletas — Jardim Senador Vergueiro")
    nos, trechos, casas = carregar()

    ids = list(casas.index)
    rotulos = {i: rotulo_casa(i, casas.loc[i]) for i in ids}

    with st.sidebar:
        st.header("Rota")
        origem = st.selectbox("De (origem)", ids, index=0, format_func=rotulos.get)
        destino = st.selectbox("Para (destino)", ids, index=min(1, len(ids) - 1), format_func=rotulos.get)

        st.header("Visualização")
        modo = st.radio("Fundo do mapa", [SATELITE, SO_GRAFO])
        st.caption("Camadas")
        mostrar = {
            "trechos": st.checkbox("Trechos (ruas)", True),
            "esquina": st.checkbox("Esquinas", True),
            "centro": st.checkbox("Centros", True),
            "casas": st.checkbox("Casas", True),
        }

    col_mapa, col_info = st.columns([4, 1])
    with col_info:
        st.metric("Vértices de rua", len(nos))
        st.metric("Trechos", len(trechos))
        st.metric("Casas", len(casas))
        if origem == destino:
            st.warning("Origem e destino são o mesmo lugar.")
        # TODO: chamar o Dijkstra do grupo aqui e desenhar a rota no mapa (construir_mapa)
        st.info("Cálculo da rota ainda não integrado: por enquanto o mapa mostra origem e destino.")

    with col_mapa:
        mapa = construir_mapa(modo, nos, trechos, casas, mostrar, origem, destino)
        st_folium(mapa, use_container_width=True, height=650, returned_objects=[],
                  key=f"mapa-{modo}-{sorted(mostrar.items())}-{origem}-{destino}")


if __name__ == "__main__":
    main()
