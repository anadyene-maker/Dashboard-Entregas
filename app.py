import streamlit as st
import pandas as pd
import requests
import base64
import io
import tempfile
import os
from datetime import datetime
from fpdf import FPDF

# Configuração da página
st.set_page_config(page_title="Dashboard de Entregas - Gerencial", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .st-emotion-cache-1jicfl2 {padding-top: 1rem;}
    </style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard Gerencial de Entregas")

# Configurações do Repositório via Secrets
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
REPO = "anadyene-maker/Dashboard-Entregas"
FILE_PATH = "base_dados_entregas.csv"
URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# Funções GitHub
def salvar_dados_github(df_salvar, sha=None):
    csv_string = df_salvar.to_csv(index=False, sep=';')
    content_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
    data = {"message": "Atualização do Dashboard", "content": content_b64}
    if sha: data["sha"] = sha
    return requests.put(URL, headers=headers, json=data)

def carregar_dados_github():
    try:
        response = requests.get(URL, headers=headers)
        if response.status_code == 200:
            content = response.json()
            sha = content.get('sha')
            csv_data = base64.b64decode(content['content']).decode('utf-8', errors='ignore')
            if not csv_data.strip(): return pd.DataFrame(), sha
            df = pd.read_csv(io.StringIO(csv_data), sep=';', dtype=str)
            return df, sha
        else:
            return pd.DataFrame(), None
    except:
        return pd.DataFrame(), None

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_arquivo_pdf(df_print, valor_total, total_notas):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    
    # Título
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Relatorio Executivo de Pendencias Logisticas", align="C", ln=True)
    pdf.ln(5)
    
    # Resumo
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", ln=True)
    pdf.cell(0, 6, f"Valor total em transito/atraso: R$ {valor_total:,.2f}", ln=True)
    pdf.cell(0, 6, f"Total de notas pendentes: {total_notas}", ln=True)
    pdf.ln(8)
    
    # Subtítulo da Tabela
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, "Cargas Criticas (Atrasadas ou com Gargalo)", ln=True)
    
    if df_print.empty:
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 10, "Nenhuma carga critica no momento. Tudo no prazo!", ln=True)
    else:
        # Cabeçalhos da Tabela
        pdf.set_font("helvetica", "B", 8)
        colunas = ['N. Nota', 'UF', 'Transportadora', 'Faturamento', 'Agendamento', 'Demora', 'Status']
        larguras = [15, 8, 65, 22, 25, 25, 25] # Largura total = 185mm (cabe perfeitamente no A4)
        
        for i in range(len(colunas)):
            pdf.cell(larguras[i], 8, colunas[i], border=1, align="C")
        pdf.ln()
        
        # Linhas da Tabela
        pdf.set_font("helvetica", "", 7)
        for _, row in df_print.iterrows():
            # Tratamento de texto para o PDF não quebrar
            nota = str(row.get('Nº Nota', '')).encode('latin-1', 'ignore').decode('latin-1')
            uf = str(row.get('U.F', '')).encode('latin-1', 'ignore').decode('latin-1')
            transp = str(row.get('Logística Ent.', ''))[:35].encode('latin-1', 'ignore').decode('latin-1')
            fat = str(row.get('Faturamento', '')).encode('latin-1', 'ignore').decode('latin-1')
            agend = str(row.get('Data Agendamento', '')).encode('latin-1', 'ignore').decode('latin-1')
            demora = str(row.get('Tempo até Agendar', '')).encode('latin-1', 'ignore').decode('latin-1')
            
            # Removemos a "bolinha colorida" pro PDF ficar corporativo
            status_limpo = str(row.get('Status', '')).replace('🔴', '').replace('🟡', '').strip()
            
            pdf.cell(larguras[0], 6, nota, border=1, align="C")
            pdf.cell(larguras[1], 6, uf, border=1, align="C")
            pdf.cell(larguras[2], 6, transp, border=1)
            pdf.cell(larguras[3], 6, fat, border=1, align="C")
            pdf.cell(larguras[4], 6, agend, border=1, align="C")
            pdf.cell(larguras[5], 6, demora, border=1, align="C")
            pdf.cell(larguras[6], 6, status_limpo, border=1, align="C")
            pdf.ln()
            
    # Salva o arquivo em memória para download
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()
    os.remove(tmp.name)
    return pdf_bytes
# --------------------------------

df_banco, current_sha = carregar_dados_github()

# 🔐 CONTROLE DE ACESSO
st.sidebar.markdown("### ⚙️ Admin - Torre de Controle")
senha_input = st.sidebar.text_input("Senha para atualizar dados:", type="password")
is_admin = (senha_input == "1234")

if is_admin:
    st.sidebar.success("🔓 Acesso Liberado")
    with st.sidebar.expander("📥 Subir Planilhas Diárias", expanded=True):
        uploaded_files = st.file_uploader("Arraste os relatórios do Sankhya", type=["xlsx", "csv"], accept_multiple_files=True)
        if uploaded_files:
            if st.button("💾 Unir e Substituir Dados"):
                if not GITHUB_TOKEN:
                    st.error("❌ ERRO: GITHUB_TOKEN não encontrado!")
                else:
                    with st.spinner("Unindo planilhas e atualizando painel..."):
                        try:
                            dfs = []
                            for file in uploaded_files:
                                df_temp = pd.read_excel(file, dtype=str) if file.name.lower().endswith('.xlsx') else pd.read_csv(file, sep=';', dtype=str)
                                dfs.append(df_temp)
                            
                            df_novo = pd.concat(dfs, ignore_index=True)
                            resposta_github = salvar_dados_github(df_novo, current_sha)
                            if resposta_github.status_code in [200, 201]:
                                st.success(f"✅ {len(uploaded_files)} planilhas unidas e salvas com sucesso!")
                                st.rerun()
                            else:
                                st.error(f"❌ ERRO {resposta_github.status_code}: {resposta_github.text}")
                        except Exception as e:
                            st.error(f"❌ Erro ao ler as planilhas: {e}")
elif senha_input != "":
    st.sidebar.error("❌ Senha Incorreta")

# 📊 ÁREA GERENCIAL E TRATAMENTO DE DADOS
if df_banco is not None and not df_banco.empty:
    df = df_banco.copy()
    
    if 'Vlr. Nota' in df.columns:
        df['Vlr. Nota'] = pd.to_numeric(df['Vlr. Nota'].str.replace(',', '.'), errors='coerce').fillna(0)
    if 'Faturamento' in df.columns:
        df['Faturamento'] = pd.to_datetime(df['Faturamento'], errors='coerce')
    if 'Data Agendamento' not in df.columns: 
        df['Data Agendamento'] = pd.NaT
    df['Data Agendamento'] = pd.to_datetime(df['Data Agendamento'], errors='coerce')
    
    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Faturado'] = (hoje - df['Faturamento']).dt.days
    df['Tempo até Agendar'] = (df['Data Agendamento'] - df['Faturamento']).dt.days

    def classificar_status(row):
        agendamento = row.get('Data Agendamento')
        dias_fat = row.get('Dias Faturado', 0)
        if pd.notna(agendamento): 
            if hoje > agendamento: return '🔴 Atrasado' 
            else: return '🟡 Em Trânsito'
        else:
            if dias_fat > 5: return '🔴 Atrasado'
            else: return '🟡 Em Trânsito'
            
    df['Status'] = df.apply(classificar_status, axis=1)

    if 'Logística Ent.' not in df.columns: df['Logística Ent.'] = 'Não Informado'
    if 'U.F' not in df.columns: df['U.F'] = 'Não Informado'
    df['Logística Ent.'] = df['Logística Ent.'].fillna("Não Informado")
    df['U.F'] = df['U.F'].fillna("Não Informado")

    aba1, aba2 = st.tabs(["📊 Dashboard Interativo", "🖨️ Relatório em PDF"])

    with aba1:
        st.markdown("### 🔍 Filtros de Análise")
        col1, col2, col3 = st.columns(3)
        with col1: uf_sel = st.multiselect("Filtrar por UF:", options=sorted(df['U.F'].unique()))
        with col2: transp_sel = st.multiselect("Filtrar por Transportadora:", options=sorted(df['Logística Ent.'].unique()))
        with col3: status_sel = st.multiselect("Status da Entrega:", options=["🔴 Atrasado", "🟡 Em Trânsito"], default=["🔴 Atrasado", "🟡 Em Trânsito"])

        df_filtrado = df.copy()
        if uf_sel: df_filtrado = df_filtrado[df_filtrado['U.F'].isin(uf_sel)]
        if transp_sel: df_filtrado = df_filtrado[df_filtrado['Logística Ent.'].isin(transp_sel)]
        if status_sel: df_filtrado = df_filtrado[df_filtrado['Status'].isin(status_sel)]

        st.markdown("---")
        kpi1, kpi2, kpi3 = st.columns(3)
        
        total_notas = len(df_filtrado)
        notas_atrasadas = len(df_filtrado[df_filtrado['Status'] == '🔴 Atrasado'])
        valor_total = df_filtrado['Vlr. Nota'].sum()
        
        kpi1.metric("💰 Valor Total na Rua", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        kpi2.metric("📦 Total de Notas Pendentes", f"{total_notas} Notas")
        kpi3.metric("🚨 Cargas Críticas (Atrasadas)", f"{notas_atrasadas} Notas")
        
        st.markdown("---")
        st.subheader("📋 Painel Detalhado de Cargas")
        
        colunas_visiveis = ['Status', 'Dias Faturado', 'Nº Nota', 'Cliente', 'U.F', 'Vlr. Nota', 'Logística Ent.', 'Faturamento', 'Data Agendamento', 'Tempo até Agendar']
        colunas_reais = [c for c in colunas_visiveis if c in df_filtrado.columns]
        
        df_exibir = df_filtrado[colunas_reais].copy()
        if 'Dias Faturado' in df_exibir.columns: df_exibir = df_exibir.sort_values(by='Dias Faturado', ascending=False)

        st.dataframe(
            df_exibir,
            column_config={
                "Vlr. Nota": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "Dias Faturado": st.column_config.NumberColumn("Dias na Rua"),
                "Faturamento": st.column_config.DateColumn("Dt. Faturamento", format="DD/MM/YYYY"),
                "Data Agendamento": st.column_config.DateColumn("Dt. Agendada", format="DD/MM/YYYY"),
                "Tempo até Agendar": st.column_config.NumberColumn("Tempo até Agendar", format="%d dias")
            },
            hide_index=True, use_container_width=True
        )

    with aba2:
        st.markdown("## 🖨️ Relatório Executivo de Pendências Logísticas")
        st.caption(f"Os dados abaixo estão focados apenas nas cargas em atraso ou com gargalo no agendamento.")
        
        df_critico = df_filtrado[(df_filtrado['Status'] == '🔴 Atrasado') | (df_filtrado['Tempo até Agendar'] > 10)].copy()
        
        # Preparando a visualização em tela e os dados do PDF
        if df_critico.empty:
            st.success("Nenhuma carga crítica no momento! Operação dentro do prazo esperado.")
            df_print = pd.DataFrame()
        else:
            colunas_impressao = ['Nº Nota', 'U.F', 'Logística Ent.', 'Faturamento', 'Data Agendamento', 'Tempo até Agendar', 'Status']
            colunas_imp_reais = [c for c in colunas_impressao if c in df_critico.columns]
            
            df_print = df_critico[colunas_imp_reais].copy()
            
            # Limpeza visual das datas e textos
            if 'Faturamento' in df_print.columns:
                df_print['Faturamento'] = df_print['Faturamento'].dt.strftime('%d/%m/%Y')
            if 'Data Agendamento' in df_print.columns:
                df_print['Data Agendamento'] = df_print['Data Agendamento'].dt.strftime('%d/%m/%Y').fillna('-')
            if 'Tempo até Agendar' in df_print.columns:
                df_print['Tempo até Agendar'] = df_print['Tempo até Agendar'].fillna(0).astype(int).astype(str) + " dias"
            
            # Mostra na tela uma prévia
            st.table(df_print.head(30))
            
        # O BOTÃO MÁGICO DO PDF
        st.markdown("---")
        st.subheader("📥 Exportar Relatório Oficial")
        
        # Gera o arquivo em memória
        arquivo_pdf = gerar_arquivo_pdf(df_print, valor_total, total_notas)
        
        # Exibe o botão de Download
        st.download_button(
            label="📄 Clique aqui para Baixar o Arquivo em PDF",
            data=arquivo_pdf,
            file_name=f"Relatorio_Logistica_{datetime.now().strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf",
            type="primary"
        )

else:
    st.info("ℹ️ O painel está vazio. Faça o upload das planilhas na barra lateral.")
