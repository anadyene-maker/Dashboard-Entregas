import streamlit as st
import pandas as pd
import requests
import base64
import io
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Dashboard de Entregas - Gerencial", layout="wide", page_icon="📊")

# Esconder botões de ação para quem não é Admin
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
    return requests.put(URL, headers=headers, json=data).status_code in [200, 201]

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

df_banco, current_sha = carregar_dados_github()

# 🔐 CONTROLE DE ACESSO DA TORRE DE CONTROLE
st.sidebar.markdown("### ⚙️ Admin - Torre de Controle")
senha_input = st.sidebar.text_input("Senha para atualizar dados:", type="password")
is_admin = (senha_input == "1234") # Sua senha de atualização

if is_admin:
    st.sidebar.success("🔓 Acesso Liberado")
    with st.sidebar.expander("📥 Subir Planilha Diária", expanded=True):
        uploaded_file = st.file_uploader("Arraste o relatório de entregas do Sankhya", type=["xlsx", "csv"])
        if uploaded_file:
            if st.button("💾 Substituir Dados no Painel"):
                with st.spinner("Atualizando painel do gerente..."):
                    try:
                        df_novo = pd.read_excel(uploaded_file, dtype=str) if uploaded_file.name.lower().endswith('.xlsx') else pd.read_csv(uploaded_file, sep=';', dtype=str)
                        if salvar_dados_github(df_novo, current_sha):
                            st.success("Dashboard atualizado com sucesso!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao processar: {e}")
elif senha_input != "":
    st.sidebar.error("❌ Senha Incorreta")

# 📊 ÁREA GERENCIAL (Visível para todos)
if df_banco is not None and not df_banco.empty:
    df = df_banco.copy()
    
    # Tratamento de dados (Valores e Datas)
    df['Vlr. Nota'] = pd.to_numeric(df['Vlr. Nota'].str.replace(',', '.'), errors='coerce').fillna(0)
    df['Faturamento'] = pd.to_datetime(df['Faturamento'], errors='coerce')
    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Faturado'] = (hoje - df['Faturamento']).dt.days

    # Inteligência de Status (Atrasos)
    def classificar_status(row):
        entrega = str(row.get('Entrega', '')).strip()
        if entrega not in ['', 'nan', 'None']:
            return '🟢 Entregue'
        elif row.get('Dias Faturado', 0) > 5: # Considera atrasado se passou de 5 dias do faturamento
            return '🔴 Atrasado'
        else:
            return '🟡 Em Trânsito'
            
    df['Status'] = df.apply(classificar_status, axis=1)

    # Preencher vazios para filtros
    if 'Logística Ent.' not in df.columns: df['Logística Ent.'] = 'Não Informado'
    if 'U.F' not in df.columns: df['U.F'] = 'Não Informado'
    df['Logística Ent.'] = df['Logística Ent.'].fillna("Não Informado")
    df['U.F'] = df['U.F'].fillna("Não Informado")

    # FILTROS GERENCIAIS
    st.markdown("### 🔍 Filtros de Análise")
    col1, col2, col3 = st.columns(3)
    with col1:
        uf_sel = st.multiselect("Filtrar por UF:", options=sorted(df['U.F'].unique()))
    with col2:
        transp_sel = st.multiselect("Filtrar por Transportadora:", options=sorted(df['Logística Ent.'].unique()))
    with col3:
        status_sel = st.multiselect("Status da Entrega:", options=["🔴 Atrasado", "🟡 Em Trânsito", "🟢 Entregue"], default=["🔴 Atrasado", "🟡 Em Trânsito"])

    # Aplicando filtros
    df_filtrado = df.copy()
    if uf_sel: df_filtrado = df_filtrado[df_filtrado['U.F'].isin(uf_sel)]
    if transp_sel: df_filtrado = df_filtrado[df_filtrado['Logística Ent.'].isin(transp_sel)]
    if status_sel: df_filtrado = df_filtrado[df_filtrado['Status'].isin(status_sel)]

    # INDICADORES PRINCIPAIS (KPIs)
    st.markdown("---")
    kpi1, kpi2, kpi3 = st.columns(3)
    
    valor_total = df_filtrado[df_filtrado['Status'] != '🟢 Entregue']['Vlr. Nota'].sum()
    notas_pendentes = len(df_filtrado[df_filtrado['Status'] != '🟢 Entregue'])
    notas_atrasadas = len(df_filtrado[df_filtrado['Status'] == '🔴 Atrasado'])

    # Formatando dinheiro (R$)
    valor_formatado = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    kpi1.metric("💰 Valor Total Pendente na Rua", valor_formatado)
    kpi2.metric("📦 Notas Fiscais Pendentes", f"{notas_pendentes} Notas")
    kpi3.metric("🚨 Cargas Críticas (Atrasadas)", f"{notas_atrasadas} Notas")
    st.markdown("---")

    # TABELA VISUAL
    st.subheader("📋 Relatório Detalhado de Cargas")
    
    # Organizando as colunas para o gerente ver melhor
    colunas_visiveis = ['Status', 'Dias Faturado', 'Nº Nota', 'Cliente', 'U.F', 'Vlr. Nota', 'Logística Ent.', 'Faturamento']
    colunas_reais = [c for c in colunas_visiveis if c in df_filtrado.columns]
    
    df_exibir = df_filtrado[colunas_reais].copy()
    
    # Ordenar pelas mais atrasadas primeiro
    if 'Dias Faturado' in df_exibir.columns:
        df_exibir = df_exibir.sort_values(by='Dias Faturado', ascending=False)

    st.dataframe(
        df_exibir,
        column_config={
            "Vlr. Nota": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "Dias Faturado": st.column_config.NumberColumn("Dias na Rua"),
            "Faturamento": st.column_config.DateColumn("Dt. Faturamento", format="DD/MM/YYYY")
        },
        hide_index=True, use_container_width=True
    )
else:
    st.info("ℹ️ O painel está vazio. O setor de Torre de Controle precisa fazer o upload da primeira planilha diária.")
