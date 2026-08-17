"""Coleta de dados: busca de mercado (Tavily) + histórico de licitações (PNCP/ComprasMG)."""
import httpx
import logging
import json
import re
import time
from bs4 import BeautifulSoup
from config import TAVILY_API_KEY, COMPRASMG_URL, PNCP_URL, TIMEOUT

logger = logging.getLogger(__name__)

# ─── LIMPEZA ──────────────────────────────────────────────

def limpar_siad(valor) -> str:
    """Remove .0, nan, None do código SIAD."""
    if valor is None:
        return ""
    s = str(valor).strip()
    if s.lower() in ("nan", "none", "nat", ""):
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s

def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    s = str(valor).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    return s

# ─── BUSCA DE MERCADO ─────────────────────────────────────

class BuscadorMercado:
    """Busca produtos no mercado brasileiro via Tavily Search API."""

    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.url = "https://api.tavily.com/search"

    def buscar(self, especificacao: str, max_resultados: int = 10) -> list[dict]:
        if not self.api_key:
            logger.error("TAVILY_API_KEY não configurada")
            return []

        query = (
            f"{especificacao[:200]} "
            f"comprar preço site:mercadolivre.com.br OR site:amazon.com.br "
            f"OR site:magazineluiza.com.br OR site:lojasamericanas.com.br"
        )

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_resultados,
            "include_answer": True,
            "search_depth": "advanced",
        }

        for tentativa in range(3):
            try:
                with httpx.Client(timeout=TIMEOUT) as client:
                    resp = client.post(self.url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                resultados = []
                for item in data.get("results", []):
                    resultados.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                    })

                logger.info(f"Tavily: {len(resultados)} resultados")
                return resultados

            except Exception as e:
                if tentativa < 2:
                    time.sleep(2 * (tentativa + 1))
                else:
                    logger.error(f"Tavily falhou: {e}")
                    return []
        return []

# ─── HISTÓRICO DE LICITAÇÕES ─────────────────────────────

class ConsultorLicitas:
    """Consulta histórico no PNCP (Dados Abertos) e ComprasMG."""

    def consultar(self, codigo_siad: str = "", descricao: str = "") -> list[dict]:
        codigo_siad = limpar_siad(codigo_siad)
        descricao = limpar_texto(descricao)
        resultados = []

        # Fonte 1: PNCP / Dados Abertos (API federal)
        try:
            r = self._pncp(descricao)
            resultados.extend(r)
        except Exception as e:
            logger.warning(f"PNCP falhou: {e}")

        # Fonte 2: ComprasMG (scraping HTML)
        if len(resultados) < 5:
            try:
                r = self._comprasmg(codigo_siad, descricao)
                resultados.extend(r)
            except Exception as e:
                logger.warning(f"ComprasMG falhou: {e}")

        # Deduplica por número de processo
        vistos = set()
        unicos = []
        for r in resultados:
            proc = str(r.get("processo", "")).strip()
            if proc and proc not in vistos:
                vistos.add(proc)
                unicos.append(r)

        return unicos[:5]

    def _pncp(self, descricao: str) -> list[dict]:
        """API de Dados Abertos de Compras Governamentais."""
        if not descricao:
            return []

        url = f"{PNCP_URL}/modulo-pesquisa-preco/0/50"
        params = {"termo": descricao[:150]}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }

        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        resultados = []
        for item in data.get("data", [])[:5]:
            orgao = item.get("orgaoEntidade", "N/D")
            if isinstance(orgao, dict):
                orgao = orgao.get("razaoSocial", "N/D")

            valor = item.get("valorUnitarioHomologado", "N/D")
            if valor and valor != "N/D":
                try:
                    valor = f"R$ {float(valor):.2f}"
                except (ValueError, TypeError):
                    valor = str(valor)

            # Link do processo no PNCP
            num_pncp = item.get("numeroControlePNCP", "")
            link = f"https://pncp.gov.br/app/editais/{num_pncp}" if num_pncp else "N/D"

            resultados.append({
                "processo": item.get("numeroProcesso", "N/D"),
                "orgao": orgao,
                "marca": item.get("marca", "N/D"),
                "modelo": item.get("modelo", "N/D") or item.get("descricaoItem", "N/D"),
                "valor_unitario": valor,
                "data": item.get("dataHomologacao", "N/D"),
                "fonte": "PNCP",
                "link_processo": link,
            })

        logger.info(f"PNCP: {len(resultados)} registros")
        return resultados

    def _comprasmg(self, codigo_siad: str, descricao: str) -> list[dict]:
        """Scraping do portal ComprasMG."""
        url = f"{COMPRASMG_URL}/compra/pesquisa"
        params = {}
        if codigo_siad:
            params["codigo"] = codigo_siad
        if descricao:
            params["descricao"] = descricao[:100]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }

        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        resultados = []

        table = soup.find("table", class_="table") or soup.find("table")
        if table:
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    proc = cols[0].get_text(strip=True) if len(cols) > 0 else "N/D"

                    # Extrai link do processo
                    link = "N/D"
                    a = cols[0].find("a")
                    if a and a.get("href"):
                        link = a["href"]
                        if not link.startswith("http"):
                            link = f"{COMPRASMG_URL}{link}"

                    resultados.append({
                        "processo": proc,
                        "orgao": cols[1].get_text(strip=True) if len(cols) > 1 else "N/D",
                        "marca": cols[2].get_text(strip=True) if len(cols) > 2 else "N/D",
                        "modelo": cols[3].get_text(strip=True) if len(cols) > 3 else "N/D",
                        "valor_unitario": cols[4].get_text(strip=True) if len(cols) > 4 else "N/D",
                        "data": cols[5].get_text(strip=True) if len(cols) > 5 else "N/D",
                        "fonte": "ComprasMG",
                        "link_processo": link,
                    })

        logger.info(f"ComprasMG: {len(resultados)} registros")
        return resultados[:5]