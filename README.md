# Delivery de Bicicletas em Limeira

Projeto da disciplina TT001A. Modelamos o bairro **Jardim Senador Vergueiro**, em Limeira (SP), como um grafo ponderado e usamos o **algoritmo de Dijkstra**, implementado pelo grupo, para calcular a rota de um entregador de bicicleta da loja até a casa de entrega. O peso de cada trecho considera a **distância em metros** e um **nível de dificuldade** (fácil, moderado ou difícil), e a rota é exibida sobre a imagem real das ruas.

**Escopo completo do projeto (PDF):** [docs/escopo-do-projeto.pdf](docs/escopo-do-projeto.pdf)

## Como funciona

1. As ruas do bairro são baixadas do **OpenStreetMap** com o OSMnx, já no formato de grafo.
2. Os endereços das casas, com número e coordenada, vêm do **CNEFE 2022 do IBGE**.
3. Cada vértice recebe sua **altitude** pela API Open Topo Data (modelo SRTM de 30 m).
4. O usuário escolhe o destino **digitando o endereço** (rua e número), **clicando no mapa** ou **digitando o ID do vértice**.
5. O Dijkstra calcula a rota de menor custo a partir da loja.
6. A rota é desenhada em um mapa HTML com fundo de satélite (Folium).

## Modelagem do grafo

O grafo tem três tipos de vértice. Os nós de rua (esquina e centro) se ligam entre si nos dois sentidos; as casas só recebem arestas dos nós de rua e nunca se ligam a outra casa.

| Vértice | Definição |
|---|---|
| **Esquina** | Cruzamento ou ponta de rua, vindo do OpenStreetMap. |
| **Centro** | Ponto no meio do quarteirão, criado pelo grupo: um a cada 150 m de quarteirão (`n = ⌈L / 150⌉`). |
| **Casa** | Endereço do CNEFE. Os apartamentos de um prédio viram uma casa só. |

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

## Ferramentas e dados

| Ferramenta | Uso |
|---|---|
| Python + OSMnx | Baixar as ruas do bairro como grafo, com comprimentos e coordenadas. |
| CNEFE 2022 (IBGE) | Endereços do bairro com rua, número e coordenada (704 registros, 365 endereços). |
| Open Topo Data | Altitude dos vértices (SRTM 30 m). |
| Folium | Desenhar a rota em um mapa HTML com fundo de satélite. |
| NetworkX | Apenas para conferir o nosso Dijkstra, sem substituí-lo. |

O OpenStreetMap não tem o nome "Senador Vergueiro", então o grafo é recortado pela área que contém os endereços do IBGE (latitude −22,5715 a −22,5625; longitude −47,4304 a −47,4185), mais uma margem.

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
