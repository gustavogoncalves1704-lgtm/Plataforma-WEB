Sistema web em Python (Streamlit) que automatiza pesquisa mercadológica e validação técnica para licitações públicas com base no portal ComprasMG (compras.mg.gov.br). O sistema recebe uma planilha Excel com itens (Código SIAD + Especificação Técnica), busca 3 modelos de marcas diferentes com menores preços no mercado brasileiro, valida conformidade técnica via IA (Google Gemini), consulta histórico de licitações homologadas e gera relatório consolidado em Excel e PDF.1. 🎯 ObjetivoPara cada item da planilha de entrada, o sistema executa:
Busca no mercado brasileiro de 3 modelos de produtos de MARCAS DIFERENTES com os menores preços disponíveis
Validação de conformidade técnica (checklist 100%) comparando especificação do edital com ficha técnica do produto encontrado
Extração dos links diretos dos catálogos/fichas técnicas oficiais do fabricante
Consulta ao portal ComprasMG e API de Dados Abertos para extrair histórico dos últimos 5 pregões/licitações homologadas (número do processo, órgão, marca/modelo vencedor e valor unitário homologado)
Geração de relatório final consolidado exportável em Excel (.xlsx) e PDF com parecer técnico conclusivo
2. 🏗️ Arquitetura do SistemaO projeto é estruturado em 4 módulos principais:2.1 Módulo A: Interface Web (Streamlit)
Upload do arquivo Excel (.xlsx)
Mapeamento dinâmico de colunas (usuário seleciona qual coluna contém o Código SIAD e a Especificação)
Barra de progresso em tempo real mostrando qual item está sendo processado
Exibição de prévia dos resultados e botão de download da planilha preenchida e relatório PDF
2.2 Módulo B: Raspagem e Coleta de Dados Externa
Consulta ao ComprasMG via Playwright (scraping de conteúdo dinâmico)
Consulta à API de Dados Abertos de Compras Governamentais (dadosabertos.compras.gov.br) com dados de MG via PNCP (Lei 14.133/2021)
Busca mercadológica via API Serper (Google Search) restrita a e-commerces brasileiros
2.3 Módulo C: Processamento e Inteligência Artificial (Google Gemini)
SDK google-genai com modelo gemini-2.5-flash
Structured Outputs com Pydantic Schema para respostas JSON válidas sem alucinações
Prompt do sistema configurado com perfil de Pregoeiro/Analista de Licitações
Batimento do checklist técnico comparando especificação do edital com ficha técnica encontrada
2.4 Módulo D: Exportação de Resultados
Consolidação em Excel com colunas organizadas (dados do item, modelos 1-3 com marca/modelo/preço/link/checklist, histórico ComprasMG, parecer técnico)
Geração de relatório PDF formatado com ReportLab
3. 📁 Estrutura de PastasCódigolicitacao-inteligente/
├── requirements.txt
├── .env.example
├── config.py
├── app.py
├── modules/
│   ├── __init__.py
│   ├── scrapers.py
│   ├── ai_engine.py
│   ├── excel_processor.py
│   └── report_generator.py
└── tests/
    ├── __init__.py
    ├── test_scrapers.py
    └── test_ai_engine.py4. 📦 Dependências
streamlit==1.45.1 — Interface web
pandas==2.2.3 — Manipulação de dados
openpyxl==3.1.5 — Leitura/escrita Excel
google-genai==1.14.0 — SDK do Google Gemini
pydantic==2.10.4 — Schemas estruturados
httpx==0.28.1 — Cliente HTTP
beautifulsoup4==4.12.3 — Parsing HTML
lxml==5.3.0 — Parser XML/HTML
playwright==1.49.1 — Browser automation para scraping
reportlab==4.2.5 — Geração de PDF
python-dotenv==1.0.1 — Variáveis de ambiente
5. ⚙️ Configuração5.1 Variáveis de AmbienteCrie um arquivo .env na raiz do projeto baseado no .env.example:
```env
GEMINI_API_KEY=sua_chave_aqui
SERPER_API_KEY=sua_chave_serper_aqui
COMPRASMG_BASE_URL=https://compras.mg.gov.br
DADOS_ABERTOS_URL=https://dadosabertos.compras.gov.br
```5.2 Onde obter as chaves de APIAPIURL para obtençãoGoogle Geminihttps://aistudio.google.com/apikeySerper.devhttps://serper.dev (1.000 buscas grátis no plano trial)6. 🚀 Instalação e Execução6.1 Pré-requisitos
Python 3.11+
Chaves de API: Google Gemini e Serper.dev
6.2 Passo a passo (local)Código1234567891011121314151617181920212223# 1. Clonar/criar a estrutura de pastas
mkdir licitacao-inteligente && cd licitacao-inteligente

# 2. Criar ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Instalar browsers do Playwright
playwright install chromium

# 5. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env e insira suas chaves

# 6. Executar testes (opcional)
pytest tests/ -v

# 7. Iniciar a aplicação
streamlit run app.pyAcesse http://localhost:8501 no navegador.6.3 Deploy na NuvemOpção A — Streamlit Cloud
Faça push do projeto para um repositório GitHub
Acesse https://share.streamlit.io e conecte o repositório
Defina as secrets (GEMINI_API_KEY, SERPER_API_KEY) em Settings → Secrets
Nota: O Playwright não roda no Streamlit Cloud. Para produção, use Docker
Opção B — Docker (recomendado para produção)Código12345678910111213FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libnspr4 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]Código12docker build -t licitacao-inteligente .
docker run -p 8501:8501 --env-file .env licitacao-inteligente7. 📊 Formato da Planilha de EntradaA planilha Excel (.xlsx) de entrada deve conter no mínimo duas colunas:
Uma coluna com o Código SIAD (ex: 123456)
Uma coluna com a Especificação Técnica (descrição detalhada do item)
O sistema permite mapeamento dinâmico de colunas, então os nomes das colunas podem ser qualquer um.8. 📋 Colunas do Relatório de Saída (Excel)ColunaDescriçãoCódigo SIADCódigo do itemEspecificaçãoEspecificação técnica originalModelo 1 - MarcaMarca do 1º produto encontradoModelo 1 - ModeloModelo/descrição do 1º produtoModelo 1 - Preço R$Preço encontradoModelo 1 - LinkLink do catálogo/ficha técnicaModelo 1 - ConformidadeStatus do checklist (100% CONFORME ou NÃO CONFORME)Modelos 2 e 3Dados equivalentes para os demais produtosHistórico ComprasMGÚltimas 5 licitações homologadasParecer ConclusivoFAVORÁVEL ou DESFAVORÁVEL à aquisiçãoJustificativaJustificativa técnica detalhada9. 🔧 Fluxo de Funcionamento
Usuário faz upload da planilha Excel na interface web
Sistema lê as colunas e permite mapeamento dinâmico
Para cada item da planilha:

BuscaMercadoScraper busca 3 produtos de marcas diferentes com menores preços via Serper API
ComprasMGScraper e DadosAbertosAPI consultam histórico de licitações
AI Engine (Gemini) analisa conformidade técnica de cada produto encontrado
AI Engine (Gemini) gera parecer técnico conclusivo


Sistema consolida todos os resultados
Usuário baixa planilha Excel formatada e relatório PDF
10. ⚠️ Pontos de Atenção
Atenção: O portal ComprasMG pode usar JavaScript pesado e proteções anti-bot. O scraper usa Playwright (headless), mas se bloqueado, a fallback automática é a API Dados Abertos.

Código SIAD vs CATMAT/PDM: A API federal usa códigos CATMAT/PDM, não SIAD diretamente. O sistema tenta ambos.
Rate limits: O Gemini 2.5 Flash tem limite de requisições. O processamento é sequencial por item para evitar erro 429.
Estrutura do ComprasMG: O portal pode mudar sua estrutura HTML. Os seletores CSS podem precisar de ajuste.
11. 🧪 TestesCódigo123456# Executar todos os testes
pytest tests/ -v

# Executar testes específicos
pytest tests/test_scrapers.py -v
pytest tests/test_ai_engine.py -v12. 📜 LicençaEste projeto é de uso privado. Todos os direitos reservados.Autor: Alan Emanuel Lobo de Sousa
Lobo Soluções em Licitações e Comércio Ltda
Especialista em Inteligência de Mercado e Licitações Públicas13. 📚 Referências
ComprasMG — Portal de Compras de Minas Gerais
API Dados Abertos de Compras Governamentais
Google Gemini API — Structured Outputs
Google Gen AI SDK para Python
Lei nº 14.133/2021 — Nova Lei de Licitações
Lei nº 8.666/1993 — Lei de Licitações anterior
