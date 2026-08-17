"""Sistema de Inteligência de Licitações — Interface Streamlit."""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import pandas as pd

from config import setup_logging, GROQ_API_KEY, TAVILY_API_KEY
from modules.scrapers import BuscadorMercado, ConsultorLicitas, limpar_siad, limpar_texto
from modules.ai_engine import AnalisadorIA
from modules.excel_export import gerar_excel
from modules.report_generator import gerar_pdf

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Sistema de Inteligência de Licitações", page_icon="📋", layout="wide")

def init_state():
    defaults = {"resultados": [], "processado": False, "relatorio_md": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def corrigir_colunas_duplicadas(df):
    colunas = df.columns.tolist()
    vistas = {}
    novas = []
    for col in colunas:
        if col in vistas:
            vistas[col] += 1
            novas.append(f"{col}_{vistas[col]}")
        else:
            vistas[col] = 0
            novas.append(col)
    df.columns = novas
    return df

def ler_planilha(file):
    for h in range(4):
        try:
            file.seek(0)
            df = pd.read_excel(file, header=h)
            if not any("Unnamed" in str(c) for c in df.columns[:2]):
                return df
        except Exception:
            continue
    file.seek(0)
    return pd.read_excel(file, header=0)

def processar_item(codigo, espec, buscador, consultor, ia):
    try:
        if not espec or espec == "N/D":
            return _vazio(codigo, espec, "Especificação vazia")

        produtos_mercado = buscador.buscar(espec, max_resultados=10)
        produtos = ia.analisar_produtos(espec, produtos_mercado, codigo_siad=codigo)
        historico = consultor.consultar(codigo_siad=codigo, descricao=espec)
        parecer = ia.gerar_parecer(espec, produtos, historico)

        return {
            "codigo_siad": codigo or "N/A",
            "especificacao": espec,
            "produtos": produtos,
            "historico": historico,
            "parecer": parecer,
        }
    except Exception as e:
        logger.error(f"Erro ao processar {codigo}: {e}", exc_info=True)
        return _vazio(codigo, espec, f"Erro: {e}")

def _vazio(codigo, espec, motivo):
    return {
        "codigo_siad": codigo or "N/A",
        "especificacao": espec,
        "produtos": [],
        "historico": [],
        "parecer": {
            "parecer": "DESFAVORÁVEL",
            "justificativa": motivo,
            "marca_recomendada": "",
            "modelo_recomendado": "",
            "preco_recomendado": "",
            "economia_percentual": 0,
        },
    }

st.markdown("""
<div style='text-align:center; padding:10px 0 20px 0;'>
    <h1 style='color:#1A1A1A; margin-bottom:4px;'>📋 Sistema de Inteligência de Licitações</h1>
    <p style='color:#888; font-size:14px;'>Lobo Soluções em Licitações e Comércio Ltda</p>
</div>
""", unsafe_allow_html=True)

if not GROQ_API_KEY:
    st.error("⚠️ GROQ_API_KEY não configurada. Gere em https://console.groq.com/keys")
    st.stop()
if not TAVILY_API_KEY:
    st.warning("⚠️ TAVILY_API_KEY não configurada. A busca de mercado não funcionará.")

buscador = BuscadorMercado()
consultor = ConsultorLicitas()
ia = AnalisadorIA()

tab_prod, tab_hist = st.tabs(["🔍 Análise de Produtos", "📜 Histórico de Licitações"])

# ═══ ABA 1: ANÁLISE DE PRODUTOS ═══════════════════════════

with tab_prod:
    st.markdown("### 1. Upload da Planilha")
    arquivo = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx", "xls"], label_visibility="collapsed")

    if arquivo is None:
        st.info("👆 Faça upload de uma planilha para começar.")
    else:
        try:
            df = ler_planilha(arquivo)
            df = corrigir_colunas_duplicadas(df)
            df = df.dropna(how="all").reset_index(drop=True)

            if len(df) > 0 and df.shape[1] > 0:
                mask = df.iloc[:, 0].astype(str).str.contains("VALOR TOTAL|TOTAL ESTIMADO", case=False, na=False)
                df = df[~mask].reset_index(drop=True)

            st.success(f"✅ {len(df)} itens carregados.")

            with st.expander("Visualizar dados", expanded=False):
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            st.stop()

        colunas = list(df.columns)
        st.markdown("### 2. Mapeamento de Colunas")
        c1, c2 = st.columns(2)
        with c1:
            col_siad = st.selectbox("Coluna com Código SIAD:", colunas, index=0)
        with c2:
            col_espec = st.selectbox("Coluna com Especificação Técnica:", colunas, index=min(1, len(colunas)-1))

        st.markdown("### 3. Prévia dos Dados")
        df_preview = df[[col_siad, col_espec]].head(15).copy()
        df_preview[col_siad] = df_preview[col_siad].apply(limpar_siad)
        df_preview[col_espec] = df_preview[col_espec].apply(limpar_texto)
        df_preview.columns = ["Código SIAD", "Especificação Técnica"]
        st.dataframe(df_preview, use_container_width=True, height=250)

        st.markdown("### 4. Seleção de Itens")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("☑️ Selecionar Todos"):
                st.session_state.selecoes = {i: True for i in range(len(df))}
                st.rerun()
        with c2:
            if st.button("☐ Desmarcar Todos"):
                st.session_state.selecoes = {i: False for i in range(len(df))}
                st.rerun()
        with c3:
            if st.button("☑️ Primeiros 10"):
                st.session_state.selecoes = {i: (i < 10) for i in range(len(df))}
                st.rerun()

        if "selecoes" not in st.session_state:
            st.session_state.selecoes = {}

        selecionados = []
        for idx in range(len(df)):
            row = df.iloc[idx]
            siad = limpar_siad(row[col_siad])[:15]
            espec = limpar_texto(row[col_espec])[:40]
            label = f"L{idx+2} | SIAD: {siad or 'sem código'} | {espec}..."
            checked = st.checkbox(label, value=st.session_state.selecoes.get(idx, True), key=f"chk_{idx}")
            st.session_state.selecoes[idx] = checked
            if checked:
                selecionados.append(idx)

        qtd = len(selecionados)
        st.info(f"📊 **{qtd}** de **{len(df)}** itens selecionados.")

        if qtd == 0:
            st.warning("Selecione pelo menos 1 item.")
            st.stop()

        st.markdown("### 5. Configurações")
        c1, c2 = st.columns(2)
        with c1:
            max_itens = st.slider("Limite de itens:", 1, min(qtd, 50), min(qtd, 10))
        with c2:
            max_workers = st.slider("Paralelismo:", 1, 5, 3)

        itens_proc = selecionados[:max_itens]
        st.divider()

        if st.button(f"🚀 Processar {len(itens_proc)} itens (paralelo x{max_workers})", type="primary", use_container_width=True):
            st.session_state.resultados = []
            st.session_state.processado = False
            st.session_state.relatorio_md = None

            barra = st.progress(0.0)
            status = st.empty()
            container = st.container()
            t0 = time.time()

            itens_data = []
            for idx in itens_proc:
                row = df.iloc[idx]
                itens_data.append({
                    "codigo": limpar_siad(row[col_siad]),
                    "espec": limpar_texto(row[col_espec]),
                })

            total = len(itens_data)
            resultados = [None] * total
            concluidos = 0

            status.info(f"🚀 Processando {total} itens com {max_workers} workers...")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for i, item in enumerate(itens_data):
                    f = executor.submit(processar_item, item["codigo"], item["espec"], buscador, consultor, ia)
                    futures[f] = i

                for f in as_completed(futures):
                    idx_r = futures[f]
                    try:
                        resultados[idx_r] = f.result()
                    except Exception as e:
                        resultados[idx_r] = _vazio(itens_data[idx_r]["codigo"], itens_data[idx_r]["espec"], f"Erro: {e}")

                    concluidos += 1
                    barra.progress(concluidos / total)

                    t_dec = time.time() - t0
                    restam = total - concluidos
                    eta = (t_dec / concluidos * restam / max_workers) if concluidos > 0 else 0
                    status.info(f"⏳ {concluidos}/{total} concluídos | Restam: {restam} | ETA: ~{int(eta//60)}min {int(eta%60)}s")

                    r = resultados[idx_r]
                    with container:
                        cod = str(r.get("codigo_siad", ""))[:20]
                        esp = str(r.get("especificacao", ""))[:40]
                        with st.expander(f"✅ Item {idx_r+1} — SIAD: {cod} — {esp}...", expanded=False):
                            parecer = r.get("parecer", {})
                            conclusao = parecer.get("parecer", "N/D")
                            st.write(f"**Parecer:** {'🟢' if 'FAVOR' in conclusao.upper() else '🔴'} {conclusao}")
                            st.write(f"**Justificativa:** {parecer.get('justificativa', 'N/D')[:200]}")

                            for p in r.get("produtos", []):
                                conforme = p.get("conforme", False)
                                status_p = "✅ CONFORME" if conforme else "❌ NÃO CONFORME"
                                cb = p.get("custo_beneficio", 0)
                                st.write(f"---")
                                st.write(f"**{p.get('marca', 'N/D')} — {p.get('modelo', 'N/D')}**")
                                st.write(f"- 💰 **Preço:** {p.get('preco', 'N/D')}")
                                st.write(f"- 📊 **Custo-Benefício:** {cb}/10")
                                st.write(f"- ✅ **Conformidade:** {status_p} ({p.get('conformidade_percentual', 0)}%)")
                                st.write(f"- 🔗 **Catálogo:** {p.get('link_catalogo', 'N/D')}")
                                st.write(f"- 📞 **Contato Fabricante:** {p.get('contato_fabricante', 'N/D')}")

                                checklist = p.get("checklist", [])
                                if checklist:
                                    st.write(f"- 📋 **Checklist:**")
                                    for c in checklist:
                                        icon = "✅" if c.get("atendido") else "❌"
                                        st.write(f"  - {icon} {c.get('requisito', '')}: {c.get('observacao', '')}")

            barra.progress(1.0)
            t_total = time.time() - t0
            status.success(f"✅ Concluído! {total} itens em {int(t_total//60)}min {int(t_total%60)}s.")

            st.session_state.resultados = resultados
            st.session_state.processado = True
            st.rerun()

        if st.session_state.processado and st.session_state.resultados:
            st.markdown("---")
            st.markdown("### 6. Resultados")

            resultados = st.session_state.resultados
            c1, c2, c3 = st.columns(3)
            conformes = sum(1 for r in resultados if any(p.get("conforme") for p in r.get("produtos", [])))
            favoraveis = sum(1 for r in resultados if "FAVOR" in str(r.get("parecer", {}).get("parecer", "")).upper())
            c1.metric("Itens com Produto Conforme", conformes)
            c2.metric("Pareceres Favoráveis", favoraveis)
            c3.metric("Total Processado", len(resultados))

            st.markdown("### 7. Downloads")
            c1, c2, c3 = st.columns(3)

            with c1:
                try:
                    excel = gerar_excel(resultados)
                    st.download_button("📊 Baixar Excel (2 abas)", data=excel,
                                       file_name=f"analise_{int(time.time())}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)
                except Exception as e:
                    st.error(f"Erro Excel: {e}")

            with c2:
                try:
                    pdf = gerar_pdf(resultados)
                    st.download_button("📄 Baixar PDF", data=pdf,
                                       file_name=f"relatorio_{int(time.time())}.pdf",
                                       mime="application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"Erro PDF: {e}")

            with c3:
                if st.button("🤖 Gerar Relatório IA", type="secondary", use_container_width=True):
                    with st.spinner("Gerando relatório consolidado..."):
                        try:
                            dados = []
                            for r in resultados:
                                dados.append({
                                    "codigo_siad": r.get("codigo_siad", "N/A"),
                                    "especificacao": r.get("especificacao", "N/D"),
                                    "produtos": r.get("produtos", []),
                                    "parecer": r.get("parecer", {}),
                                    "historico": r.get("historico", []),
                                })
                            rel = ia.gerar_relatorio(dados)
                            st.session_state.relatorio_md = rel
                        except Exception as e:
                            st.error(f"Erro: {e}")

            if st.session_state.relatorio_md:
                st.download_button("💾 Baixar Relatório (.md)",
                                   data=st.session_state.relatorio_md.encode("utf-8"),
                                   file_name=f"relatorio_{int(time.time())}.md",
                                   mime="text/markdown")
                st.markdown("---")
                st.markdown(st.session_state.relatorio_md)

# ═══ ABA 2: HISTÓRICO DE LICITAÇÕES ═══════════════════════

with tab_hist:
    st.markdown("### 📜 Histórico de Licitações (ComprasMG / PNCP)")

    if not st.session_state.resultados:
        st.info("👆 Processe itens na aba 'Análise de Produtos' primeiro.")
    else:
        linhas = []
        for r in st.session_state.resultados:
            codigo = r.get("codigo_siad", "N/A")
            espec = r.get("especificacao", "N/D")[:80]
            for h in r.get("historico", []):
                linhas.append({
                    "Código SIAD": codigo,
                    "Especificação": espec,
                    "Nº do Processo": h.get("processo", "N/D"),
                    "Órgão": h.get("orgao", "N/D"),
                    "Marca Vencedora": h.get("marca", "N/D"),
                    "Modelo": h.get("modelo", "N/D"),
                    "Valor Unitário": h.get("valor_unitario", "N/D"),
                    "Data": h.get("data", "N/D"),
                    "Fonte": h.get("fonte", "N/D"),
                    "Link do Processo": h.get("link_processo", "N/D"),
                })

        if linhas:
            df_hist = pd.DataFrame(linhas)
            st.dataframe(df_hist, use_container_width=True)

            busca = st.text_input("🔎 Filtrar por Código SIAD:")
            if busca:
                filtrado = df_hist[df_hist["Código SIAD"].astype(str).str.contains(busca, case=False, na=False)]
                st.dataframe(filtrado, use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Processos", len(df_hist))
            c2.metric("Itens com Histórico", df_hist["Código SIAD"].nunique())
            c3.metric("Fontes", df_hist["Fonte"].nunique() if "Fonte" in df_hist.columns else 0)
        else:
            st.warning("Nenhum histórico encontrado.")

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#999; font-size:12px;'>"
    "Sistema de Inteligência de Licitações — Lobo Soluções em Licitações e Comércio Ltda"
    "</div>",
    unsafe_allow_html=True,
)