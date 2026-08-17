"""Motor de IA (Groq): análise de conformidade + parecer + relatório."""
import json
import time
import logging
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODELS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Você é um Pregoeiro e Analista de Licitações públicas com 20 anos de experiência "
    "nas Leis 8.666/93 e 14.133/21. Sua função é analisar especificações técnicas de "
    "produtos para compras governamentais, validando conformidade técnica RIGOROSA "
    "(100% de atendimento ao edital).\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Os produtos DEVEM ter venda em território brasileiro (Mercado Livre, Amazon BR, "
    "Magazine Luiza, Americanas, ou site oficial do fabricante).\n"
    "2. Selecione exatamente 3 produtos de MARCAS DIFERENTES com os MENORES PREÇOS.\n"
    "3. Só marque conforme=true se o produto atender 100% da especificação do edital.\n"
    "4. Para cada produto, forneça o link do catálogo/ficha técnica oficial do fabricante.\n"
    "5. Para cada produto, forneça o contato do fabricante (site, e-mail ou telefone).\n"
    "6. Faça um CHECKLIST detalhado comparando cada requisito da especificação com o produto.\n"
    "7. Não há preferência por nenhuma marca específica.\n"
    "8. Identifique se a especificação do edital apresenta direcionamento de marca.\n"
    "9. Sempre responda em português brasileiro com precisão técnica.\n"
    "10. Se não encontrar o produto exato nos resultados, use seu CONHECIMENTO TÉCNICO "
    "para indicar produtos equivalentes que atendam à especificação, com preços reais "
    "praticados no mercado brasileiro.\n"
    "11. Para cada produto, forneça SEMPRE: marca, modelo, preço em R$, link do catálogo "
    "do fabricante e contato do fabricante. NUNCA deixe campos vazios ou N/D."
)

class AnalisadorIA:
    def __init__(self):
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY não configurada. Gere em https://console.groq.com/keys")
        self.client = Groq(api_key=GROQ_API_KEY)
        self._modelo_ativo = None

    def _chamar(self, prompt: str, json_mode: bool = True, max_tokens: int = 10000) -> str:
        """Chama o Groq com fallback automático de modelo."""
        modelos = GROQ_MODELS if self._modelo_ativo is None else (
            [self._modelo_ativo] + [m for m in GROQ_MODELS if m != self._modelo_ativo]
        )

        ultimo_erro = None

        for modelo in modelos:
            for tentativa in range(3):
                try:
                    kwargs = {
                        "model": modelo,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": max_tokens,
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    resp = self.client.chat.completions.create(**kwargs)
                    self._modelo_ativo = modelo
                    logger.info(f"Groq OK: {modelo}")
                    return resp.choices[0].message.content

                except Exception as e:
                    err = str(e)
                    ultimo_erro = e

                    # 401 = chave inválida
                    if "401" in err or "invalid_api_key" in err:
                        raise RuntimeError(
                            "CHAVE GROQ INVÁLIDA (401). Gere uma nova chave em "
                            "https://console.groq.com/keys e atualize no .env"
                        ) from e

                    # 404 = modelo não existe OU chave inválida disfarçada
                    if "404" in err or "model_not_found" in err or "not_found" in err:
                        logger.warning(f"Modelo {modelo} não acessível (404). Tentando próximo...")
                        break

                    # 429 = rate limit
                    if "429" in err or "rate" in err:
                        espera = 10 * (tentativa + 1)
                        logger.warning(f"Rate limit. Aguardando {espera}s...")
                        time.sleep(espera)
                        continue

                    # 503 = indisponível
                    if "503" in err or "unavailable" in err:
                        time.sleep(5 * (tentativa + 1))
                        continue

                    if tentativa < 2:
                        time.sleep(3)
                    else:
                        break

        raise RuntimeError(f"Todos os modelos Groq falharam. Último erro: {ultimo_erro}")

    def analisar_produtos(self, especificacao: str, produtos_mercado: list[dict], codigo_siad: str = "") -> list[dict]:
        prompt = f"""ESPECIFICAÇÃO TÉCNICA DO EDITAL:
{especificacao}

CÓDIGO SIAD: {codigo_siad or "Não informado"}

PRODUTOS ENCONTRADOS NO MERCADO BRASILEIRO:
{json.dumps(produtos_mercado, ensure_ascii=False, indent=2)[:20000]}

INSTRUÇÕES:
1. Selecione os 3 produtos com MENORES PREÇOS, de MARCAS DIFERENTES.
2. Se nenhum produto dos resultados atender 100%, use seu CONHECIMENTO TÉCNICO para indicar
   3 produtos de marcas diferentes que atendam à especificação e são vendidos no Brasil.
3. Informe preços REAIS de mercado brasileiro (ex: R$ 1.299,00).
4. Para cada produto, monte um CHECKLIST verificando CADA requisito da especificação.
5. Forneça o link do catálogo/ficha técnica oficial do fabricante.
6. Forneça o contato do fabricante (site oficial, e-mail ou telefone).
7. Atribua nota de custo-benefício (0 a 10, onde 10 = melhor relação preço/qualidade).
8. Verifique se a especificação do edital direciona para alguma marca.
9. NÃO deixe nenhum campo vazio ou N/D. Se não souber, infira o valor mais provável.

Retorne JSON:
{{
  "produtos": [
    {{
      "marca": "nome da marca",
      "modelo": "modelo ou descrição do produto",
      "preco": "preço em R$ (ex: R$ 1.299,00)",
      "link_catalogo": "link do catálogo ou site do fabricante",
      "contato_fabricante": "site, e-mail ou telefone do fabricante",
      "conforme": true,
      "conformidade_percentual": 100,
      "custo_beneficio": 8.5,
      "checklist": [
        {{"requisito": "descrição do requisito da especificação", "atendido": true, "observacao": "explicação técnica"}}
      ],
      "observacoes": "observações gerais sobre o produto",
      "alerta_direcionamento": "se houver direcionamento de marca na especificação, descreva; senão, string vazia"
    }}
  ]
}}"""

        try:
            texto = self._chamar(prompt, json_mode=True, max_tokens=10000)
            data = json.loads(texto)
        except (json.JSONDecodeError, RuntimeError) as e:
            logger.error(f"Erro ao analisar: {e}")
            return []

        produtos = data.get("produtos", [])

        for p in produtos:
            p["conforme"] = bool(p.get("conforme", False))
            try:
                p["conformidade_percentual"] = int(p.get("conformidade_percentual", 0))
            except (ValueError, TypeError):
                p["conformidade_percentual"] = 0
            try:
                p["custo_beneficio"] = float(p.get("custo_beneficio", 0))
            except (ValueError, TypeError):
                p["custo_beneficio"] = 0.0

        return produtos[:3] if produtos else []

    def gerar_parecer(self, especificacao: str, produtos: list[dict], historico: list[dict]) -> dict:
        prompt = f"""ESPECIFICAÇÃO DO ITEM:
{especificacao}

PRODUTOS ANALISADOS:
{json.dumps(produtos, ensure_ascii=False, indent=2)[:15000]}

HISTÓRICO DE LICITAÇÕES (últimas 5):
{json.dumps(historico, ensure_ascii=False, indent=2) if historico else "Sem histórico"}

INSTRUÇÕES:
1. Emita parecer FAVORÁVEL ou DESFAVORÁVEL.
2. Cite conformidades e não conformidades.
3. Recomende o modelo com melhor custo-benefício que atenda 100%.
4. Calcule a economia percentual estimada.
5. Se nenhum produto atender 100%, o parecer deve ser DESFAVORÁVEL.

Retorne JSON:
{{
  "parecer": "FAVORÁVEL ou DESFAVORÁVEL",
  "justificativa": "análise técnica detalhada (mínimo 3 parágrafos)",
  "marca_recomendada": "marca do produto recomendado",
  "modelo_recomendado": "modelo do produto recomendado",
  "preco_recomendado": "preço do produto recomendado",
  "economia_percentual": 15.0
}}"""

        try:
            texto = self._chamar(prompt, json_mode=True, max_tokens=4000)
            return json.loads(texto)
        except (json.JSONDecodeError, RuntimeError) as e:
            logger.error(f"Erro ao gerar parecer: {e}")
            return {
                "parecer": "DESFAVORÁVEL",
                "justificativa": str(e),
                "marca_recomendada": "",
                "modelo_recomendado": "",
                "preco_recomendado": "",
                "economia_percentual": 0,
            }

    def gerar_relatorio(self, resultados: list[dict]) -> str:
        prompt = f"""Gere um RELATÓRIO EXECUTIVO em Markdown sobre os itens processados.

Para CADA item, inclua:
1. Código SIAD e especificação técnica
2. Tabela com os 3 produtos: marca, modelo, preço, link do catálogo, contato do fabricante
3. Status de conformidade de cada produto
4. Checklist resumido (X/Y requisitos)
5. Nota de custo-benefício (0-10)
6. Alerta de direcionamento (se houver)
7. Parecer técnico (FAVORÁVEL ou DESFAVORÁVEL)
8. Recomendação final (melhor custo-benefício)

Ao final, inclua um RESUMO EXECUTIVO com estatísticas.

Dados:
{json.dumps(resultados, ensure_ascii=False, indent=2)[:30000]}

Retorne apenas o texto em Markdown."""

        try:
            return self._chamar(prompt, json_mode=False, max_tokens=8000)
        except Exception as e:
            return f"# Relatório de Licitações\n\nErro ao gerar relatório: {e}"