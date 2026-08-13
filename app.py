import streamlit as st
import pandas as pd
import requests
import base64
import io
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Dashboard de Entregas - Gerencial", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .st-emotion-cache-1jicfl2 {padding-top: 1rem;}
    /* Esconde menu do streamlit na hora da impressão */
    @media print {
        header {visibility: hidden;}
        .st-emotion-cache-1r6slb0 {visibility: hidden;}
        .sidebar {display: none;}
    }
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
    data = {"message": "Atualização do Dashboard (Múltiplas Planilhas)", "content": content_b64}
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

df_banco, current_sha = carregar_dados_github()

# 🔐 CONTROLE DE ACESSO
st.sidebar.markdown("### ⚙️ Admin - Torre de Controle")
senha_input = st.sidebar.text_input("Senha para atualizar dados:", type="password")
is_admin = (senha_input == "160861")

if is_admin:
    st.sidebar.success("🔓 Acesso Liberado")
    with st.sidebar.expander("📥 Subir Planilhas Diárias", expanded=True):
        # AGORA ACEITA VÁRIOS ARQUIVOS AO MESMO TEMPO
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
                            
                            # Junta todas as planilhas numa só
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
    
    # Tratamento de Valores
    if 'Vlr. Nota' in df.columns:
        df['Vlr. Nota'] = pd.to_numeric(df['Vlr. Nota'].str.replace(',', '.'), errors='coerce').fillna(0)
    
    # Tratamento de Datas
    if 'Faturamento' in df.columns:
        df['Faturamento'] = pd.to_datetime(df['Faturamento'], errors='coerce')
    
    # CORREÇÃO AQUI: Nome exato da coluna do Excel
    if 'Data Agendamento' not in df.columns: 
        df['Data Agendamento'] = pd.NaT
    df['Data Agendamento'] = pd.to_datetime(df['Data Agendamento'], errors='coerce')
    
    hoje = pd.to_datetime(datetime.now().date())
    df['Dias Faturado'] = (hoje - df['Faturamento']).dt.days
    
    # Nova métrica: Distância do Agendamento (Dias entre Faturar e Agendar)
    df['Prazo Agendado'] = (df['Data Agendamento'] - df['Faturamento']).dt.days

    # Status
    def classificar_status(row):
        entrega = str(row.get('Data Chegada Opl.', '')).strip() # Ajustei para a coluna de entrega se chamar assim, ou você pode mudar se for outra
        if entrega not in ['', 'nan', 'None', 'NaT']: return '🟢 Entregue'
        elif row.get('Dias Faturado', 0) > 5: return '🔴 Atrasado'
        else: return '🟡 Em Trânsito'
            
    df['Status'] = df.apply(classificar_status, axis=1)

    # Preencher vazios
    if 'Logística Ent.' not in df.columns: df['Logística Ent.'] = 'Não Informado'
    if 'U.F' not in df.columns: df['U.F'] = 'Não Informado'
    df['Logística Ent.'] = df['Logística Ent.'].fillna("Não Informado")
    df['U.F'] = df['U.F'].fillna("Não Informado")

    # CRIANDO AS DUAS ABAS VISUAIS
    aba1, aba2 = st.tabs(["📊 Dashboard Interativo", "🖨️ Relatório para Impressão"])

    with aba1:
        st.markdown("### 🔍 Filtros de Análise")
        col1, col2, col3 = st.columns(3)
        with col1: uf_sel = st.multiselect("Filtrar por UF:", options=sorted(df['U.F'].unique()))
        with col2: transp_sel = st.multiselect("Filtrar por Transportadora:", options=sorted(df['Logística Ent.'].unique()))
        with col3: status_sel = st.multiselect("Status da Entrega:", options=["🔴 Atrasado", "🟡 Em Trânsito", "🟢 Entregue"], default=["🔴 Atrasado", "🟡 Em Trânsito"])

        # Aplicando filtros
        df_filtrado = df.copy()
        if uf_sel: df_filtrado = df_filtrado[df_filtrado['U.F'].isin(uf_sel)]
        if transp_sel: df_filtrado = df_filtrado[df_filtrado['Logística Ent.'].isin(transp_sel)]
        if status_sel: df_filtrado = df_filtrado[df_filtrado['Status'].isin(status_sel)]

        # KPIs Matemáticos
        st.markdown("---")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_notas = len(df_filtrado)
        notas_entregues = len(df_filtrado[df_filtrado['Status'] == '🟢 Entregue'])
        notas_atrasadas = len(df_filtrado[df_filtrado['Status'] == '🔴 Atrasado'])
        valor_total = df_filtrado[df_filtrado['Status'] != '🟢 Entregue']['Vlr. Nota'].sum()
        
        perc_entregue = (notas_entregues / total_notas * 100) if total_notas > 0 else 0
        perc_pendente = 100 - perc_entregue

        kpi1.metric("💰 Valor Pendente (Na Rua)", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        kpi2.metric("📦 Notas Pendentes", f"{total_notas - notas_entregues} Notas")
        kpi3.metric("🚨 Atrasadas", f"{notas_atrasadas} Notas")
        kpi4.metric("📈 Status de Conclusão", f"{perc_entregue:.1f}% Entregue", f"-{perc_pendente:.1f}% Pendente", delta_color="inverse")
        
        st.markdown("---")

        st.subheader("📋 Painel Detalhado de Cargas")
        
        # Tabela com as colunas novas
        colunas_visiveis = ['Status', 'Dias Faturado', 'Nº Nota', 'Cliente', 'U.F', 'Vlr. Nota', 'Logística Ent.', 'Faturamento', 'Data Agendamento', 'Prazo Agendado']
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
                "Prazo Agendado": st.column_config.NumberColumn("Dias até Agendar", format="%d dias")
            },
            hide_index=True, use_container_width=True
        )

    with aba2:
        # VISÃO DE IMPRESSÃO - RELATÓRIO LIMPO
        st.markdown("## 🖨️ Relatório Executivo de Pendências Logísticas")
        st.caption(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        
        st.markdown(f"""
        **Resumo Operacional:**
        * **Valor total de mercadoria em trânsito/atraso:** R$ {valor_total:,.2f}
        * **Progresso da Operação:** {perc_entregue:.1f}% Entregue | {perc_pendente:.1f}% Falta Entregar
        """)
        
        # Filtra apenas os problemáticos (Agendamento muito distante ou Atrasados)
        st.markdown("### ⚠️ Cargas Críticas (Atrasadas ou com Agendamento Distante)")
        df_critico = df_filtrado[(df_filtrado['Status'] == '🔴 Atrasado') | (df_filtrado['Prazo Agendado'] > 10)].copy()
        
        if df_critico.empty:
            st.success("Nenhuma carga crítica no momento! Operação dentro do prazo.")
        else:
            colunas_impressao = ['Nº Nota', 'U.F', 'Logística Ent.', 'Faturamento', 'Data Agendamento', 'Prazo Agendado', 'Status']
            colunas_imp_reais = [c for c in colunas_impressao if c in df_critico.columns]
            
            st.table(df_critico[colunas_imp_reais].head(20))
            st.info("💡 Dica para o Gerente: Para imprimir ou salvar em PDF, aperte **Ctrl + P** no teclado.")

else:
    st.info("ℹ️ O painel está vazio. Faça o upload das planilhas na barra lateral.")
