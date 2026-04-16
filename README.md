# 🏛️ Observatório Casa José Mariano | Painel de Inteligência Legislativa - Recife

Um dashboard interativo, moderno e dinâmico desenvolvido para monitorar e analisar a atuação, a produção legislativa e a evolução salarial dos vereadores da cidade do Recife.

Produzido por **[@pablohscarvalho](https://instagram.com/pablohscarvalho)**.

---

## 🚀 Funcionalidades (Features)

* **📊 KPIs Dinâmicos:** Visão geral em tempo real de proposições protocoladas (24/25), vereadores ativos, partidos representados e a soma da remuneração bruta.
* **🔵 Gráficos Interativos (Chart.js):**
    * **Distribuição Partidária:** Separação visual inteligente entre Base do Governo (Verde) e Oposição (Vermelho). O gráfico atua como um filtro interativo: clique em um partido para filtrar a grade de vereadores instantaneamente.
    * **Volume de Matérias:** Gráfico de barras horizontais limpo e direto exibindo os tipos de projetos mais protocolados.
* **👤 Perfil Detalhado do Parlamentar:**
    * **Raio-X Salarial:** Gráfico de linha comparando o salário Bruto vs. Líquido, com filtro por ano (2024, 2025, 2026).
    * **Perfil de Produção:** Gráfico de rosca (Doughnut) mostrando exatamente onde o vereador foca sua atuação (Requerimentos, Projetos de Lei, Indicações, etc.).
    * **Lista de Proposições:** Timeline completa com o teor do projeto em destaque. Inclui botões de filtro dinâmicos para isolar rapidamente documentos específicos e link direto para o PDF oficial.
* **🧠 Inteligência de Dados (Backend):** Algoritmo customizado em Python que padroniza nomes, remove acentos, ignora títulos (Ex: "Pastor", "Professora") e cruza apelidos de urna com nomes civis de contracheques oficiais da prefeitura.

---

## 🛠️ Tecnologias Utilizadas

**Frontend (Tela):**
* HTML5 & CSS3 (Layout Responsivo e Customizado)
* JavaScript Vanilla (Lógica assíncrona, Fetch API, manipulação de DOM)
* [Chart.js](https://www.chartjs.org/) (Gráficos visuais e interativos)
* [FontAwesome](https://fontawesome.com/) (Ícones)

**Backend (API & Dados):**
* [Python 3](https://www.python.org/)
* [FastAPI](https://fastapi.tiangolo.com/) (Construção da API RESTful)
* [Uvicorn](https://www.uvicorn.org/) (Servidor ASGI)
* Processamento local de dados em formato `.json` e `.csv`

---

## 📁 Estrutura de Pastas

Para que o projeto funcione perfeitamente (tanto localmente quanto na nuvem), certifique-se de que a estrutura esteja organizada assim:

```text
meu_projeto/
│
├── data/                   # Arquivos JSON extraídos do sistema (vereadores, materias_por_tipo, etc)
├── dados_extras/           # Arquivos CSV de remuneração extraídos do Portal da Transparência
│
├── frontend/               # Arquivos da Interface Visual (Deploy no Vercel/Netlify)
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── app.py                  # Código-fonte principal do Backend (FastAPI)
└── requirements.txt        # Dependências do Python (Para o Render)