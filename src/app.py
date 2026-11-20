"""Interface web (Streamlit) do projeto: escolher o destino e ver a melhor rota a partir da loja.

Rodar a partir da raiz do projeto:
    streamlit run src/app.py

Reaproveita os dados gerados pelo grupo em data/ e as constantes de config.py. A rota é calculada
pelo Dijkstra do grupo (dijkstra.py) sobre o grafo com pesos de grafo.py.
"""
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import grafo
from config import (ARESTAS_CASAS_CSV, ARESTAS_CSV, CASAS_CSV, LAT_MAX, LAT_MIN, LOJA_ID, LOJA_NOME, LOJA_NUMERO,
                    LOJA_RUA, LON_MAX, LON_MIN, NOS_CSV)
from dijkstra import INF, melhor_rota

SATELITE = "Satélite + grafo"
SO_GRAFO = "Só o grafo (fundo branco)"

# cor das ruas por fundo: amarelo contrasta com o satélite, azul-escuro com o branco
COR_RUA = {SATELITE: "#ffd400", SO_GRAFO: "#1f4e79"}
COR_NO = {"esquina": "red", "centro": "cyan"}
COR_RUA_CASA = {SATELITE: "#ffffff", SO_GRAFO: "#999999"}  # arestas rua -> casa, discretas
COR_NIVEL = {"fácil": "#00c853", "moderado": "#ff6d00", "difícil": "#d50000"}
COR_SEM_NIVEL = {SATELITE: "#ffffff", SO_GRAFO: "#555555"}  # trechos loja -> rua e rua -> casa da rota
COR_ROTA_DISTANCIA = "#e040fb"  # rota só por distância (comparação), tracejada
TILES_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


@st.cache_data
def _ler(versao):
    """`versao` (datas de modificação dos CSVs) faz o cache ser refeito quando os dados são gerados de novo."""
    nos = pd.read_csv(NOS_CSV).set_index("id")
    trechos = pd.read_csv(ARESTAS_CSV)
    casas = pd.read_csv(CASAS_CSV).set_index("id_casa")
    rua_casa = pd.read_csv(ARESTAS_CASAS_CSV)
    arestas = grafo.montar()
    grafos = {com_niveis: grafo.adjacencia(arestas, com_niveis) for com_niveis in (True, False)}
    loja = grafo.coordenadas_loja(casas.reset_index())
    return nos, trechos, casas, rua_casa, arestas.set_index(["u", "v"]), grafos, loja


def carregar():
    return _ler(tuple(p.stat().st_mtime_ns for p in (NOS_CSV, ARESTAS_CSV, CASAS_CSV, ARESTAS_CASAS_CSV)))


def coordenada(v, nos, casas, loja):
    """[lat, lon] de qualquer vértice: loja, casa ("h<id_casa>") ou nó de rua."""
    if v == LOJA_ID:
        return list(loja)
    c = casas.loc[int(v[1:])] if v.startswith("h") else nos.loc[v]
    return [c.lat, c.lon]


def rotulo_vertice(v, casas):
    if v == LOJA_ID:
        return f"Loja {LOJA_NOME}"
    if v.startswith("h"):
        return rotulo_casa(int(v[1:]), casas.loc[int(v[1:])])
    return f"vértice {v}"


def rotulo_casa(id_casa, casa):
    numero = "s/n" if casa.numero == 0 else int(casa.numero)
    return f"{casa.rua}, {numero} · {casa.bairro.title()} (casa {id_casa})"


def nome_rua(casa):
    return casa.rua if casa.tipo == "RUA" else f"{casa.tipo} {casa.rua}"


def rotulo_numero(numero):
    return "s/n" if numero == 0 else str(int(numero))


def seletor_endereco(chave, casas, indice_padrao=0):
    """Duas caixas (rua e número); devolve o id_casa escolhido."""
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


def seletor_destino(casas, vertices):
    """Destino por endereço (rua e número) ou pelo ID do vértice; devolve o id do vértice ou None."""
    forma = st.radio("Buscar por", ["Endereço", "ID do vértice"], horizontal=True)
    if forma == "Endereço":
        return f"h{seletor_endereco('destino', casas)}"
    v = st.text_input("ID do vértice", placeholder="ex.: h45, c104, e2479554862").strip()
    st.caption("Casas começam com **h** (h45 = casa 45), centros com **c** e esquinas com **e**. "
               "Passe o mouse sobre um ponto do mapa para ver o ID.")
    if not v:
        return None
    if v == LOJA_ID:
        st.warning("A loja é a origem; escolha outro destino.")
        return None
    if v not in vertices:
        st.error(f"Não existe vértice com ID {v!r}.")
        return None
    st.caption(f"Destino: {rotulo_vertice(v, casas)}")
    return v


def resumo_rota(rota, arestas):
    """Uma linha por aresta da rota, com distância, inclinação, nível e peso."""
    linhas = []
    for u, v in zip(rota, rota[1:]):
        a = arestas.loc[(u, v)]
        linhas.append(dict(de=u, para=v, tipo=a.tipo, comprimento_m=round(a.comprimento, 1),
                           inclinacao_pct=None if pd.isna(a.inclinacao) else round(a.inclinacao, 2),
                           nivel=a.nivel if isinstance(a.nivel, str) else "sem nível",
                           multiplicador=a.multiplicador, peso=round(a.peso, 1)))
    return pd.DataFrame(linhas)


def desenhar_rota(m, modo, rota, arestas, coord, por_nivel=True):
    """Rota com níveis: cada aresta na cor do seu nível. Rota só por distância: tracejada, numa cor só."""
    grupo = folium.FeatureGroup("Rota com níveis" if por_nivel else "Rota só por distância").add_to(m)
    for u, v in zip(rota, rota[1:]):
        a = arestas.loc[(u, v)]
        pontos = [coord(u), coord(v)]
        if por_nivel:
            cor = COR_NIVEL.get(a.nivel, COR_SEM_NIVEL[modo])
            inc = "" if pd.isna(a.inclinacao) else f", inclinação {a.inclinacao:+.1f}%"
            nivel = a.nivel if isinstance(a.nivel, str) else "sem nível"
            dica = f"{u} → {v}: {a.comprimento:.1f} m{inc} ({nivel}), peso {a.peso:.1f}"
            folium.PolyLine(pontos, color="black", weight=10, opacity=0.5).add_to(grupo)  # contorno
            folium.PolyLine(pontos, color=cor, weight=6, opacity=1, tooltip=dica).add_to(grupo)
        else:
            folium.PolyLine(pontos, color=COR_ROTA_DISTANCIA, weight=4, opacity=0.95, dash_array="8 8",
                            tooltip=f"Rota só por distância: {u} → {v}, {a.comprimento:.1f} m").add_to(grupo)


def construir_mapa(modo, nos, trechos, casas, rua_casa, mostrar, loja, destino, rota, rota_distancia, arestas,
                   etapa=lambda msg: None):
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
    if mostrar["rua_casa"]:
        etapa(f"Traçando {len(rua_casa)} arestas rua → casa…")
        grupo = folium.FeatureGroup("Arestas rua → casa").add_to(m)
        for a in rua_casa.itertuples():
            n, c = nos.loc[a.u], casas.loc[int(a.v[1:])]
            folium.PolyLine([[n.lat, n.lon], [c.lat, c.lon]], color=COR_RUA_CASA[modo], weight=1, opacity=0.7,
                            tooltip=f"{a.u} → {a.v} ({rotulo_casa(int(a.v[1:]), c)}): {a.comprimento:.1f} m"
                            ).add_to(grupo)
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

    def coord(v):
        return coordenada(v, nos, casas, loja)

    if rota:
        etapa("Desenhando a rota…")
        desenhar_rota(m, modo, rota, arestas, coord)
    if rota_distancia:
        desenhar_rota(m, modo, rota_distancia, arestas, coord, por_nivel=False)

    etapa("Marcando a loja e o destino…")
    folium.Marker(list(loja), tooltip=f"Origem: loja {LOJA_NOME}",
                  icon=folium.Icon(color="green", icon="shopping-cart")).add_to(m)
    if destino:
        folium.Marker(coord(destino), tooltip=f"Destino: {rotulo_vertice(destino, casas)}",
                      icon=folium.Icon(color="red", icon="flag")).add_to(m)

    etapa("Ajustando o enquadramento…")
    if rota:
        pontos = [coord(v) for v in rota + (rota_distancia or [])]
        lats, lons = [p[0] for p in pontos], [p[1] for p in pontos]
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(40, 40))
    else:
        m.fit_bounds([[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]])
    return m


def painel_rota(rota, custo, rota_dist, arestas):
    """Números da rota (e da comparação) na coluna ao lado do mapa."""
    tabela = resumo_rota(rota, arestas)
    distancia = tabela.comprimento_m.sum()
    st.metric("Distância", f"{distancia:.0f} m")
    st.metric("Custo (com níveis)", f"{custo:.1f}")
    por_nivel = tabela.groupby("nivel").comprimento_m.sum()
    st.caption("Metros por nível: " + " · ".join(
        f"{n} {por_nivel.get(n, 0):.0f}" for n in ("fácil", "moderado", "difícil", "sem nível")))
    if rota_dist is not None:
        t_dist = resumo_rota(rota_dist, arestas)
        st.markdown("**Rota só por distância** (tracejada)")
        if rota_dist == rota:
            st.success("É a mesma rota: os níveis não mudaram o caminho.")
        else:
            st.metric("Distância", f"{t_dist.comprimento_m.sum():.0f} m",
                      delta=f"{t_dist.comprimento_m.sum() - distancia:+.0f} m", delta_color="off")
            st.metric("Custo dela com níveis", f"{t_dist.peso.sum():.1f}",
                      delta=f"{t_dist.peso.sum() - custo:+.1f}", delta_color="inverse")
            st.caption("A rota com níveis é mais longa, mas evita subidas: o custo dela é menor.")


def ajuda():
    st.markdown("""
### Como usar a interface

**1. Escolha o destino** (barra lateral). A origem é sempre a loja (Luminarie Residence).
- *Endereço*: primeiro a **rua**, depois o **número**. A lista mostra só os números que existem na base
  do IBGE (CNEFE 2022) para aquela rua, então não é possível escolher um endereço inexistente.
- *ID do vértice*: digite o ID de qualquer vértice (h45 = casa 45, c104 = centro, e… = esquina).

A melhor rota é calculada na hora pelo **Dijkstra do grupo** e desenhada no mapa, com cada trecho na cor
do seu nível de dificuldade. Ao lado do mapa aparecem a distância, o custo e os metros em cada nível.
Abaixo do mapa, "Passo a passo da rota" lista cada aresta com inclinação, nível e peso.

**Comparar com a rota só por distância** (barra lateral) desenha, tracejada em rosa, a rota que ignora
os níveis (multiplicador 1,0 em tudo), para ver quando a dificuldade muda o caminho.

**2. Escolha o fundo do mapa.**
- *Satélite + grafo*: imagem de satélite com o grafo desenhado por cima (ruas em amarelo).
- *Só o grafo (fundo branco)*: apenas o grafo, sem imagem (ruas em azul), bom para ver a estrutura.

**3. Ligue ou desligue camadas**: trechos, arestas rua → casa, esquinas, centros, casas e o ajuste das casas
(traço branco do ponto original do IBGE, em roxo, até o ponto usado no grafo).

**4. Explore o mapa.** Arraste para mover, use a roda do mouse ou os botões +/− para dar zoom e
passe o mouse sobre um ponto para ver detalhes (ID e altitude do vértice, comprimento do trecho,
endereço da casa, nível e peso de cada trecho da rota). O marcador verde é a loja e o vermelho é o destino.

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
| Linha fina | **Aresta rua → casa**: liga o nó de rua à casa (só nesse sentido) |
| Rota verde | Trecho **fácil**: descida ou plano, inclinação abaixo de 2% (peso = 0,9 × distância) |
| Rota laranja | Trecho **moderado**: subida de 2% a 5% (peso = 1,0 × distância) |
| Rota vermelha | Trecho **difícil**: subida acima de 5% (peso = 1,1 × distância) |
| Rota branca/cinza | Saída da loja ou chegada na casa: sem nível (peso = distância) |
| Rosa tracejado | Rota só por distância (comparação) |

### Como o peso é calculado
Cada aresta tem peso **w(u, v) = d · m(nível(u, v))**, em que d é a distância em metros e m o multiplicador
do nível. A inclinação é medida no sentido da aresta, de esquina a esquina do quarteirão:
**i = (h_v − h_u) / d × 100**. Por isso a mesma rua pode ser difícil na subida e fácil na descida.

### Como a casa se liga à rua
Ao longo de um quarteirão os nós de rua ficam em ordem: esquina, centros, esquina. Cada nó de rua se liga
às casas que ficam entre o nó anterior e o próximo, incluindo as que estão na frente deles. Por isso cada
casa recebe 2 ou 3 arestas. O comprimento é a distância em linha reta do nó até a casa. O vértice da casa
tem o id "h" seguido do número da casa (por exemplo, h45 é a casa 45).

### O que é "s/n"?
**s/n significa "sem número".** Algumas casas, condomínios ou lotes constam no IBGE sem numeração.
Como não dá para distingui-los, os registros sem número de um mesmo lado de quarteirão viram **uma única casa**
no grafo. Por isso uma rua pode ter mais de um "s/n" na lista, cada um com o bairro e o número da casa.

### Por que a casa não fica exatamente no ponto do IBGE?
O IBGE registra a coordenada com o GPS do recenseador, parado na calçada: o ponto cai perto do meio da rua,
às vezes do lado errado, fora de ordem ou com várias casas no mesmo lugar. Por isso cada casa é associada ao
seu quarteirão, posta em ordem de número ao longo da calçada e colocada no lote, do lado certo da rua
(detalhes em `src/cnefe.py`).

""")


def main():
    st.set_page_config(page_title="Delivery de Bicicletas — Limeira", layout="wide")
    st.title("Delivery de Bicicletas — Jardim Senador Vergueiro e arredores")
    nos, trechos, casas, rua_casa, arestas, grafos, loja = carregar()

    with st.sidebar:
        st.header("Destino")
        st.caption(f"Origem fixa: loja **{LOJA_NOME}** ({LOJA_RUA.title()}, {LOJA_NUMERO}).")
        destino = seletor_destino(casas, grafos[True])

        st.header("Visualização")
        comparar = st.checkbox("Comparar com a rota só por distância", False)
        modo = st.radio("Fundo do mapa", [SATELITE, SO_GRAFO])
        st.caption("Camadas")
        mostrar = {
            "trechos": st.checkbox("Trechos (ruas)", True),
            "rua_casa": st.checkbox("Arestas rua → casa", False),
            "esquina": st.checkbox("Esquinas", True),
            "centro": st.checkbox("Centros", True),
            "casas": st.checkbox("Casas", True),
            "ajuste": st.checkbox("Ajuste das casas (IBGE → lote)", False),
        }

    rota, custo, rota_dist = [], INF, None
    if destino:
        custo, rota = melhor_rota(grafos[True], LOJA_ID, destino)
        if comparar and rota:
            rota_dist = melhor_rota(grafos[False], LOJA_ID, destino)[1]

    aba_mapa, aba_ajuda = st.tabs(["Mapa", "Ajuda"])
    with aba_ajuda:
        ajuda()
    with aba_mapa:
        col_mapa, col_info = st.columns([4, 1])
        with col_info:
            if not destino:
                st.info("Escolha um destino na barra lateral.")
            elif not rota:
                st.error("Não há rota da loja até esse destino.")
            else:
                painel_rota(rota, custo, rota_dist, arestas)
            with st.expander("Números do grafo"):
                st.write(f"{len(nos)} vértices de rua, {len(casas)} casas e a loja; "
                         f"{len(trechos)} trechos de rua (2 arestas cada), {len(rua_casa)} arestas rua → casa.")

        with col_mapa:
            with st.spinner("Montando o mapa…"):
                mapa = construir_mapa(modo, nos, trechos, casas, rua_casa, mostrar, loja, destino, rota,
                                      rota_dist, arestas)
            with st.spinner("Desenhando o mapa na tela…"):
                st_folium(mapa, use_container_width=True, height=650, returned_objects=[],
                          key=f"mapa-{modo}-{sorted(mostrar.items())}-{destino}-{comparar}")
            if rota:
                with st.expander("Passo a passo da rota"):
                    st.caption(f"{len(rota)} vértices: {' → '.join(rota)}")
                    st.dataframe(resumo_rota(rota, arestas), hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
