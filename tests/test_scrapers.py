"""Módulo de raspagem e coleta de dados externos."""
import httpx
import logging
import json
import re
from bs4 import BeautifulSoup
from config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

class BuscadorMercado:
    """Busca produtos no mercado brasileiro usando Tavily Search API."""

    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    def buscar(self, especificacao: str, max_resultados: int = 10) -> list:
        if not self.api_key:
            logger.error("TAVILY_API_KEY não configurada")
            return []

        try:
            query = f"{especificacao[:200]} comprar preço Brasil"

            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_resultados,
                "include_answer": True,
                "search_depth": "advanced",
            }

            with httpx.Client(timeout=30) as client:
                resp = client.post(self.base_url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            resultados = []
            for item in data.get("results", []):
                resultados.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0),
                })

            logger.info(f"Tavily retornou {len(resultados)} resultados")
            return resultados

        except Exception as e:
            logger.error(f"Erro na busca Tavily: {e}")
            return []

class ConsultorComprasMG:
    """Consulta histórico de licitações no ComprasMG e Dados Abertos."""

    def __init__(self):
        self.comprasmg_url = "https://compras.mg.gov.br"
        self.dados_abertos_url = "https://dadosabertos.compras.gov.br"

    def consultar_historico(self, codigo_siad=None, descricao_item=None) -> list:
        resultados = []

        try:
            dados_abertos = self._consultar_dados_abertos(descricao_item)
            if dados_abertos:
                resultados.extend(dados_abertos)
        except Exception as e:
            logger.error(f"Erro Dados Abertos: {e}")

        try:
            comprasmg = self._consultar_comprasmg(codigo_siad, descricao_item)
            if comprasmg:
                resultados.extend(comprasmg)
        except Exception as e:
            logger.error(f"Erro ComprasMG: {e}")

        vistos = set()
        unicos = []
        for r in resultados:
            proc = str(r.get("processo", "")).strip()
            if proc and proc not in vistos:
                vistos.add(proc)
                unicos.append(r)

        return unicos[:5]

    def _consultar_dados_abertos(self, descricao_item: str) -> list:
        if not descricao_item:
            return []

        try:
            url = f"{self.dados_abertos_url}/modulo-pesquisa-preco/0/50"
            params = {"termo": descricao_item[:150]}
            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            }

            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            resultados = []
            for item in data.get("data", [])[:5]:
                resultados.append({
                    "processo": item.get("numeroProcesso", "N/D"),
                    "orgao": item.get("orgaoEntidade", {}).get("razaoSocial", "N/D")
                             if isinstance(item.get("orgaoEntidade"), dict)
                             else str(item.get("orgaoEntidade", "N/D")),
                    "marca": item.get("marca", "N/D"),
                    "modelo": item.get("modelo", "N/D") or item.get("descricaoItem", "N/D"),
                    "valor_unitario": item.get("valorUnitarioHomologado", "N/D"),
                    "data": item.get("dataHomologacao", "N/D"),
                    "fonte": "Dados Abertos / PNCP",
                })

            return resultados

        except Exception as e:
            logger.warning(f"Dados Abertos indisponível: {e}")
            return []

    def _consultar_comprasmg(self, codigo_siad, descricao_item) -> list:
        try:
            url = f"{self.comprasmg_url}/compra/pesquisa"
            params = {}
            if codigo_siad and str(codigo_siad).strip() and str(codigo_siad) not in ("N/A", "nan", ""):
                params["codigo"] = str(codigo_siad).strip()
            if descricao_item:
                params["descricao"] = descricao_item[:100]

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html",
                "Accept-Language": "pt-BR,pt;q=0.9",
            }

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            resultados = []

            table = soup.find("table", class_="table") or soup.find("table")

            if table:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 3:
                        resultado = {
                            "processo": cols[0].get_text(strip=True) if len(cols) > 0 else "N/D",
                            "orgao": cols[1].get_text(strip=True) if len(cols) > 1 else "N/D",
                            "marca": cols[2].get_text(strip=True) if len(cols) > 2 else "N/D",
                            "modelo": cols[3].get_text(strip=True) if len(cols) > 3 else "N/D",
                            "valor_unitario": cols[4].get_text(strip=True) if len(cols) > 4 else "N/D",
                            "data": cols[5].get_text(strip=True) if len(cols) > 5 else "N/D",
                            "fonte": "ComprasMG",
                        }
                        resultados.append(resultado)

            if not resultados:
                cards = soup.find_all("div", class_=re.compile(r"result|item|card", re.I))
                for card in cards[:5]:
                    texto = card.get_text(separator=" ", strip=True)
                    if texto:
                        resultados.append({
                            "processo": "N/D", "orgao": "N/D", "marca": "N/D",
                            "modelo": texto[:200], "valor_unitario": "N/D",
                            "data": "N/D", "fonte": "ComprasMG",
                        })

            return resultados[:5]

        except Exception as e:
            logger.warning(f"ComprasMG indisponível: {e}")
            return []