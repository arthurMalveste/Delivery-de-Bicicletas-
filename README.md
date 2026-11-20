# Delivery de Bicicletas em Limeira

Projeto da disciplina TT001A. Modelamos o bairro **Jardim Senador Vergueiro**, em Limeira (SP), como um grafo ponderado e usamos o **algoritmo de Dijkstra**, implementado pelo grupo, para calcular a rota de um entregador de bicicleta da loja até a casa de entrega. O peso de cada trecho considera a **distância em metros** e um **nível de dificuldade** (fácil, moderado ou difícil), e a rota é exibida sobre a imagem real das ruas.

**Escopo completo do projeto (PDF):** [docs/escopo-do-projeto.pdf](docs/escopo-do-projeto.pdf)

## Como funciona

1. As ruas do bairro são baixadas do **OpenStreetMap** com o OSMnx, já no formato de grafo.
2. Os endereços das casas, com número e coordenada, vêm do **CNEFE 2022 do IBGE**. Entram os endereços de todos os bairros que ficam nas ruas do grafo, e cada casa é colocada no seu lote (ver [Posição das casas](#posição-das-casas)).
3. Cada vértice recebe sua **altitude** pela API Open Topo Data (modelo SRTM de 30 m).
4. O usuário escolhe o destino **digitando o endereço** (rua e número), **clicando no mapa** ou **digitando o ID do vértice**.
5. O Dijkstra calcula a rota de menor custo a partir da loja.
6. A rota é desenhada em um mapa HTML com fundo de satélite (Folium).

## Modelagem do grafo

O grafo tem três tipos de vértice. Os nós de rua (esquina e centro) se ligam entre si nos dois sentidos; as casas só recebem arestas dos nós de rua e nunca se ligam a outra casa.

| Vértice | Definição |
|---|---|
| **Esquina** | Cruzamento ou ponta de rua, vindo do OpenStreetMap. |
| **Centro** | Ponto no meio do quarteirão, criado pelo grupo: um a cada 50 m de quarteirão (`n = ⌈L / 50⌉ − 1`). |
| **Casa** | Endereço do CNEFE, colocado no lote em frente à sua rua. Os apartamentos de um prédio viram uma casa só. |

**Regra de vizinhança:** ao longo de um quarteirão os nós de rua ficam em ordem (esquina, centros, esquina). Cada nó de rua se liga às casas que ficam entre o nó de rua anterior e o próximo, incluindo as que estão na frente deles. As casas dos dois lados da rua usam os mesmos nós.

| Aresta | Sentido | Peso |
|---|---|---|
| Rua–rua | Os dois | Distância ao longo da rua × multiplicador do nível |
| Rua → casa | Só da rua para a casa | Distância em linha reta (multiplicador 1,0) |
| Loja → rua | Só da loja para a rua | Distância em linha reta (multiplicador 1,0) |
| Casa–casa | Não existe | — |

As arestas vão só da rua para a casa, então nenhuma rota passa por dentro de uma casa: a casa só pode ser o fim da rota. A exceção é a loja, que é a origem.

- **Loja (origem):** Luminarie Residence, perto da borda leste do bairro.
- **Conexidade:** o grafo é verificado para garantir que toda casa tenha rota a partir da loja.

## Níveis de dificuldade

Cada aresta de rua recebe um nível, e o peso é a distância multiplicada pelo multiplicador do nível:

```
w(u, v) = d · m(nível(u, v))
```

| Nível | Multiplicador | Critério (proposta, a calibrar) |
|---|---|---|
| Fácil | 0,9 | Descida ou plano: inclinação abaixo de 2% |
| Moderado | 1,0 | Subida leve: inclinação de 2% a 5% |
| Difícil | 1,1 | Subida forte: inclinação acima de 5% |

A inclinação é medida no sentido da aresta: `i = (h_v − h_u) / d × 100`. A mesma rua pode ser difícil na subida e fácil na descida, por isso cada rua tem duas arestas. Por enquanto o nível depende só da altitude; ele fica em uma função própria para que outras variáveis possam entrar depois sem mudar o cálculo do peso.

> **Limitação:** o SRTM tem precisão de alguns metros, então em trechos curtos a diferença de altitude pode ser ruído. Por isso as arestas de casa ficam sempre com multiplicador 1,0.

## Algoritmo

- Dijkstra na versão vista em aula: o rótulo `L` da loja começa em 0 e o dos demais vértices em infinito. A cada passo, fecha-se o vértice aberto de menor `L` e atualizam-se os vizinhos, guardando o antecessor.
- O algoritmo para quando o destino é fechado, e a rota é montada seguindo os antecessores do destino até a loja.
- **Validação:** comparação com o Dijkstra do NetworkX e simulação à mão, em tabela, de um pedaço pequeno do grafo.
- **Comparação:** para alguns destinos, a rota só por distância (multiplicador 1,0 em tudo) é mostrada ao lado da rota com níveis, para ver quando a dificuldade muda o caminho.

## Como gerar os dados

Rodar a partir de `src/`, nesta ordem, com o ambiente virtual ativo:

```
python baixar_ruas.py    # ruas do OpenStreetMap -> data/ruas.graphml
python grafo_ruas.py     # esquinas, centros e trechos -> data/nos.csv, data/arestas.csv
python altitude.py       # altitude das esquinas -> data/nos.csv
python cnefe.py          # casas posicionadas nos lotes -> data/casas.csv
python ligar_casas.py    # arestas rua -> casa -> data/arestas_casas.csv
streamlit run app.py     # interface
```

## Ferramentas e dados

| Ferramenta | Uso |
|---|---|
| Python + OSMnx | Baixar as ruas do bairro como grafo, com comprimentos e coordenadas. |
| CNEFE 2022 (IBGE) | Endereços com rua, número e coordenada: 2.405 registros e 1.703 casas nas ruas do grafo, sendo 359 do Jardim Senador Vergueiro. |
| Open Topo Data | Altitude dos vértices (SRTM 30 m). |
| Folium | Desenhar a rota em um mapa HTML com fundo de satélite. |
| NetworkX | Apenas para conferir o nosso Dijkstra, sem substituí-lo. |

O OpenStreetMap não tem o nome "Senador Vergueiro", então o grafo é recortado pela área que contém os endereços do IBGE do bairro (latitude −22,5715 a −22,5625; longitude −47,4304 a −47,4185), mais uma margem. Essa área inclui ruas de bairros vizinhos. Para nenhuma rua do grafo ficar sem casas, entram os endereços de todos os bairros a até 30 m de uma rua do grafo.

## Posição das casas

A coordenada do CNEFE é o GPS do recenseador, parado na calçada. Usada direto, ela deixa a casa no meio da rua, às vezes do lado errado, fora de ordem ou amontoada com as vizinhas. Por isso o script `src/cnefe.py` faz:

1. **Agrupar:** apartamentos de um mesmo prédio viram uma casa. Endereços sem número viram uma casa por lado de quarteirão.
2. **Associar ao quarteirão:** cada casa vai para o quarteirão (trecho de esquina a esquina) mais próximo, dando preferência ao de mesmo nome de rua. A comparação de nomes tolera diferenças de grafia, como "Stocco" e "Stoco". Endereços a mais de 30 m de qualquer quarteirão são descartados.
3. **Projetar na rua:** a casa ganha uma posição em metros desde a esquina inicial e um lado da rua. O lado é decidido por maioria na face de quadra do IBGE, que é sempre um lado só da rua.
4. **Ordenar a calçada:** as casas da mesma rua ficam em ordem de número e a pelo menos 5 m umas das outras, mexendo o mínimo nas posições medidas. Uma casa que teria de andar mais de 25 m para entrar na ordem fica onde o IBGE mediu.
5. **Colocar no lote:** o ponto da casa fica afastado do eixo da rua, do lado certo, onde está o lote.

Os parâmetros ficam em `src/config.py`. O arquivo `data/casas.csv` guarda a coordenada original do IBGE, o quarteirão (`esq_u`, `esq_v`) e a posição ao longo dele (`posicao_rel`, de 0 a 1), que é o que liga a casa aos nós de rua. Na interface, a camada "Ajuste das casas" mostra o caminho do ponto do IBGE até o lote.

**Ligação com a rua:** o script `src/ligar_casas.py` aplica a regra de vizinhança e grava `data/arestas_casas.csv`. Num quarteirão com n centros, o nó k fica na posição relativa k / (n + 1) e se liga às casas com posição entre a do nó anterior e a do próximo, inclusive. Assim cada casa recebe 2 ou 3 arestas, todas no sentido rua → casa, com a distância em linha reta como comprimento. O vértice da casa tem o id `h` seguido do `id_casa`. Na interface, a camada "Arestas rua → casa" fica desligada por padrão.

**Limitações:** o CNEFE é de 2022, então casas construídas depois não aparecem. Endereços em vias que não estão no grafo, como a marginal da rodovia na Rua Joaquim Daniel dos Santos, ficam de fora.

## Fora do escopo

- Tipo de piso e tipo de via (por enquanto)
- Sentido das ruas (mão única)
- Fadiga, ida e volta e várias entregas por viagem

## Cronograma

| Prazo | Entrega |
|---|---|
| 12/nov/2026 | Grafo extraído e revisado; altitude nos vértices; nós centro criados e casas ligadas; vértice da loja definido. |
| 19/nov/2026 | Dijkstra implementado e validado só com distância; rota desenhada sobre o mapa; entrada por endereço e por ID. |
| 27/nov/2026 | Níveis de dificuldade e seus limites; entrada por clique; comparação de rotas; relatório e apresentação. |

## Em aberto

- Limites dos níveis: a proposta é 2% e 5% de inclinação, a conferir com as inclinações reais do bairro.
- Clique no mapa: o Folium gera um HTML estático, então o clique não volta sozinho para o Python. Opções: Streamlit com streamlit-folium, rotas pré-calculadas no HTML ou copiar a coordenada do clique.
