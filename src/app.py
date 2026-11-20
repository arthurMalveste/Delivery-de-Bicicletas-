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
def _ler(versao):
    """`versao` (datas de modificação dos CSVs) faz o cache ser refeito quando os dados são gerados de novo."""
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    casas = pd.read_csv(CASAS_CSV).set_index("id_casa")
    return nos, trechos, casas


def carregar():
    return _ler(tuple(p.stat().st_mtime_ns for p in (NOS_CSV, ARESTAS_CSV, CASAS_CSV)))


def rotulo_casa(id_casa, casa):
    numero = "s/n" if casa.numero == 0 else int(casa.numero)
    return f"{casa.rua}, {numero} · {casa.bairro.title()} (casa {id_casa})"


def nome_rua(casa):
    return casa.rua if casa.tipo == "RUA" else f"{casa.tipo} {casa.rua}"


def rotulo_numero(numero):
    return "s/n" if numero == 0 else str(int(numero))


def seletor_endereco(titulo, chave, casas, indice_padrao=0):
    """Duas caixas (rua e número); devolve o id_casa escolhido."""
    st.subheader(titulo)
    ruas = sorted(casas.apply(nome_rua, axis=1).unique())
    rua = st.selectbox("Rua", ruas, index=indice_padrao if indice_padrao < len(ruas) else 0, key=f"{chave}-rua")
    da_rua = casas[casas.apply(nome_rua, axis=1) == rua].sort_values("numero", key=lambda n: n.where(n > 0, 10**9))  # s/n por último
    repetido = da_rua.numero.duplicated(keep=False)  # s/n em vários trechos, ou mesmo número em dois bairros

    def rotulo(id_casa):
        c = da_rua.loc[id_casa]
        texto = rotulo_numero(c.numero)
        return f"{texto} · {c.bairro.title()} (casa {id_casa})" if repetido[id_casa] else texto

    id_casa = st.selectbox("Número", list(da_rua.index), key=f"{chave}-num-{rua}", format_func=rotulo)
    if da_rua.loc[id_casa].numero == 0:
        st.caption("**s/n** = sem número: o IBGE registrou endereços sem numeração nesse trecho da rua; "
                   "os de um mesmo lado de quarteirão ficam representados por um único ponto no mapa.")
    return int(id_casa)


def construir_mapa(modo, nos, trechos, casas, mostrar, origem, destino, etapa=lambda msg: None):
    """`etapa(msg)` é chamado a cada fase, para a interface mostrar o andamento."""
    etapa("Preparando o fundo do mapa…")
    m = folium.Map(location=[(LAT_MIN + LAT_MAX) / 2, (LON_MIN + LON_MAX) / 2], zoom_start=17,
                   tiles=None, max_zoom=19)
    if modo == SATELITE:
        folium.TileLayer(TILES_ESRI, attr="Esri World Imagery", name="Satélite", max_zoom=19).add_to(m)
    else:  # sem tiles: o fundo do Leaflet passa a ser branco
        m.get_root().header.add_child(
            folium.Element("<style>.leaflet-container{background:#ffffff !important;}</style>"))

    if mostrar["trechos"]:
        etapa(f"Traçando {len(trechos)} trechos de rua…")
        grupo = folium.FeatureGroup("Trechos").add_to(m)
        for t in trechos.itertuples():
            a, b = nos.loc[t.u], nos.loc[t.v]
            folium.PolyLine([[a.lat, a.lon], [b.lat, b.lon]], color=COR_RUA[modo], weight=3,
                            tooltip=f"{t.u} — {t.v}: {t.comprimento:.1f} m").add_to(grupo)
    for tipo, cor in COR_NO.items():
        if not mostrar[tipo]:
            continue
        etapa(f"Definindo os nós do tipo {tipo}…")
        grupo = folium.FeatureGroup(f"{tipo.capitalize()}s").add_to(m)
        for i, n in nos[nos.tipo == tipo].iterrows():
            alt = "" if pd.isna(n.altitude) else f" | {n.altitude:.0f} m"
            folium.CircleMarker([n.lat, n.lon], radius=4 if tipo == "esquina" else 3, color=cor,
                                fill=True, fill_opacity=1, tooltip=f"{i}{alt}").add_to(grupo)
    if mostrar["casas"]:
        etapa(f"Posicionando {len(casas)} casas…")
        grupo = folium.FeatureGroup("Casas").add_to(m)
        for i, c in casas.iterrows():
            folium.CircleMarker([c.lat, c.lon], radius=3, color="#ff8c00", fill=True, fill_opacity=1,
                                tooltip=rotulo_casa(i, c)).add_to(grupo)

    if mostrar["ajuste"]:
        etapa("Desenhando o ajuste das casas…")
        grupo = folium.FeatureGroup("Ajuste das casas").add_to(m)
        for i, c in casas.iterrows():
            folium.PolyLine([[c.lat_ibge, c.lon_ibge], [c.lat, c.lon]], color="white", weight=1,
                            tooltip=f"casa {i}: {c.deslocamento:.0f} m do ponto do IBGE").add_to(grupo)
            folium.CircleMarker([c.lat_ibge, c.lon_ibge], radius=2, color="#a000c8", fill=True,
                                fill_opacity=1, tooltip=f"Ponto do IBGE da casa {i}").add_to(grupo)

    etapa("Marcando origem e destino…")
    for id_casa, nome, cor, icone in ((origem, "Origem", "green", "play"), (destino, "Destino", "red", "flag")):
        c = casas.loc[id_casa]
        folium.Marker([c.lat, c.lon], tooltip=f"{nome}: {rotulo_casa(id_casa, c)}",
                      icon=folium.Icon(color=cor, icon=icone)).add_to(m)

    etapa("Ajustando o enquadramento…")
    m.fit_bounds([[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]])
    return m


def ajuda():
    st.markdown("""
### Como usar a interface

**1. Escolha origem e destino** (barra lateral). Cada endereço tem duas caixas: primeiro a **rua**,
depois o **número**. A lista de números mostra só os que existem na base do IBGE (CNEFE 2022) para
aquela rua, então não é possível digitar um endereço inexistente.

**2. Escolha o fundo do mapa.**
- *Satélite + grafo*: imagem de satélite com o grafo desenhado por cima (ruas em amarelo).
- *Só o grafo (fundo branco)*: apenas o grafo, sem imagem (ruas em azul), bom para ver a estrutura.

**3. Ligue ou desligue camadas**: trechos, esquinas, centros, casas e o ajuste das casas
(traço branco do ponto original do IBGE, em roxo, até o ponto usado no grafo).

**4. Explore o mapa.** Arraste para mover, use a roda do mouse ou os botões +/− para dar zoom e
passe o mouse sobre um ponto para ver detalhes (ID e altitude do vértice, comprimento do trecho,
endereço da casa). O marcador verde é a origem e o vermelho é o destino.

**5. Acompanhe o carregamento.** Ao mudar qualquer opção, aparece o andamento ("Traçando trechos…",
"Posicionando casas…") e um círculo girando enquanto o mapa é desenhado. É normal levar alguns segundos.

### Legenda do grafo
| Elemento | O que é |
|---|---|
| Ponto vermelho | **Esquina**: cruzamento ou ponta de rua (OpenStreetMap) |
| Ponto ciano | **Centro**: ponto no meio do quarteirão, um a cada 50 m |
| Ponto laranja | **Casa**: endereço do IBGE, colocado no lote em frente à sua rua |
| Ponto roxo | Coordenada original do IBGE (camada "Ajuste das casas") |
| Linha | **Trecho** de rua entre dois vértices |

### O que é "s/n"?
**s/n significa "sem número".** Algumas casas, condomínios ou lotes constam no IBGE sem numeração.
Como não dá para distingui-los, os registros sem número de um mesmo lado de quarteirão viram **uma única casa**
no grafo. Por isso uma rua pode ter mais de um "s/n" na lista, cada um com o bairro e o número da casa.

### Por que a casa não fica exatamente no ponto do IBGE?
O IBGE registra a coordenada com o GPS do recenseador, parado na calçada: o ponto cai perto do meio da rua,
às vezes do lado errado, fora de ordem ou com várias casas no mesmo lugar. Por isso cada casa é associada ao
seu quarteirão, posta em ordem de número ao longo da calçada e colocada no lote, do lado certo da rua
(detalhes em `src/cnefe.py`).

### Estado atual
O cálculo da rota (Dijkstra) ainda não está integrado a esta interface: por ora o mapa mostra
origem e destino. A rota será desenhada aqui quando o algoritmo for conectado.
""")


def main():
    st.set_page_config(page_title="Delivery de Bicicletas — Limeira", layout="wide")
    st.title("Delivery de Bicicletas — Jardim Senador Vergueiro e arredores")
    nos, trechos, casas = carregar()

    with st.sidebar:
        st.header("Rota")
        origem = seletor_endereco("De (origem)", "origem", casas, 0)
        destino = seletor_endereco("Para (destino)", "destino", casas, 1)

        st.header("Visualização")
        modo = st.radio("Fundo do mapa", [SATELITE, SO_GRAFO])
        st.caption("Camadas")
        mostrar = {
            "trechos": st.checkbox("Trechos (ruas)", True),
            "esquina": st.checkbox("Esquinas", True),
            "centro": st.checkbox("Centros", True),
            "casas": st.checkbox("Casas", True),
            "ajuste": st.checkbox("Ajuste das casas (IBGE → lote)", False),
        }

    aba_mapa, aba_ajuda = st.tabs(["Mapa", "Ajuda"])
    with aba_ajuda:
        ajuda()
    with aba_mapa:
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
            with st.spinner("Montando o mapa…"):
                mapa = construir_mapa(modo, nos, trechos, casas, mostrar, origem, destino)
            with st.spinner("Desenhando o mapa na tela…"):
                st_folium(mapa, use_container_width=True, height=650, returned_objects=[],
                          key=f"mapa-{modo}-{sorted(mostrar.items())}-{origem}-{destino}")


if __name__ == "__main__":
    main()
