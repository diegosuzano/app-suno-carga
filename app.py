import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÕES GERAIS ---
NOME_PLANILHA = "Controle de Carga Suzano"
FUSO_HORARIO = timezone(timedelta(hours=-3))

campos_tempo = [
    "Entrada na Fábrica", "Encostou na doca Fábrica", "Início carregamento",
    "Fim carregamento", "Faturado", "Amarração carga", "Saída do pátio",
    "Entrada CD", "Encostou na doca CD", "Início Descarregamento CD",
    "Fim Descarregamento CD", "Saída CD"
]

campos_calculados = [
    "Tempo Espera Doca", "Tempo de Carregamento", "Tempo Total", 
    "Tempo Percurso Para CD", "Tempo Espera Doca CD", "Tempo de Descarregamento CD", "Tempo Total CD"
]

COLUNAS_ESPERADAS = ["Data", "Placa do caminhão", "Nome do conferente"] + campos_tempo + campos_calculados

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "Tela Inicial"

# --- CONFIGURAÇÃO DA PÁGINA E CSS ---
st.set_page_config(
    page_title="Suzano - Controle de Carga", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f4e79;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 30px;
        padding: 20px;
        background: linear-gradient(90deg, #e8f4f8 0%, #f0f8ff 100%);
        border-radius: 10px;
        border-left: 5px solid #1f4e79;
    }
    .section-header {
        color: #1f4e79;
        font-size: 22px;
        font-weight: bold;
        margin: 25px 0 15px 0;
        padding-bottom: 5px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stMetric {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True) 

# --- FUNÇÕES DE CONEXÃO E DADOS ---
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def connect_to_google_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets ", "https://www.googleapis.com/auth/drive "]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open(NOME_PLANILHA)
        return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Erro de conexão com o Google Sheets: {e}.")
        return None

@st.cache_data(ttl=30, show_spinner="Carregando dados...")
def carregar_dataframe(_worksheet):
    if _worksheet is None: 
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)
    try:
        data = _worksheet.get_all_values()
        if len(data) < 2: 
            return pd.DataFrame(columns=COLUNAS_ESPERADAS)
        df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
        for col in COLUNAS_ESPERADAS:
            if col not in df.columns: 
                df[col] = ''
        df = df[COLUNAS_ESPERADAS]
        df["df_index"] = df.index
        return df.fillna("")
    except Exception as e:
        st.error(f"Erro ao ler dados da planilha: {e}")
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

# --- FUNÇÕES AUXILIARES ---
def calcular_tempo(inicio, fim):
    if not all([inicio, fim]) or not all(str(v).strip() for v in [inicio, fim]): 
        return ""
    try:
        inicio_dt = pd.to_datetime(inicio, errors='coerce')
        fim_dt = pd.to_datetime(fim, errors='coerce')
        if pd.isna(inicio_dt) or pd.isna(fim_dt): 
            return ""
        diff = fim_dt - inicio_dt
        if diff.total_seconds() < 0: 
            return "Inválido"
        horas, rem = divmod(diff.total_seconds(), 3600)
        minutos, _ = divmod(rem, 60)
        return f"{int(horas):02d}:{int(minutos):02d}"
    except:
        return ""

def obter_status(registro):
    for campo in reversed(campos_tempo):
        if registro.get(campo) and str(registro.get(campo)).strip(): 
            return campo
    return "Não iniciado"

def botao_voltar():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state.pagina_atual = "Tela Inicial"
        keys_to_keep = ["pagina_atual"]
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]
        st.rerun()

# Conecta à planilha
worksheet = connect_to_google_sheets()

# Título principal
st.markdown("<div class='main-header'>🚚 Suzano - Controle de Transferência de Carga</div>", unsafe_allow_html=True)

# =============================================================================
# TELA INICIAL
# =============================================================================
if st.session_state.pagina_atual == "Tela Inicial":
    st.markdown("<div class='section-header'>MENU DE AÇÕES</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    if col1.button("🆕 NOVO REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Novo"
        st.rerun()
    if col1.button("📊 EM OPERAÇÃO", use_container_width=True):
        st.session_state.pagina_atual = "Em Operação"
        st.rerun()
    if col2.button("✏️ EDITAR REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Editar"
        st.rerun()
    if col2.button("✅ FINALIZADAS", use_container_width=True):
        st.session_state.pagina_atual = "Finalizadas"
        st.rerun()

    df = carregar_dataframe(worksheet)
    st.markdown("<div class='section-header'>SITUAÇÃO ATUAL</div>", unsafe_allow_html=True)
    
    if not df.empty:
        em_operacao_df = df[df["Saída CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)
        m1.metric(label="🚛 Em Operação (Total)", value=len(em_operacao_df))
        m2.metric(label="🏭 Na Fábrica", value=len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))
        m3.metric(label="📦 Em Rota / No CD", value=len(em_operacao_df) - len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))

        with st.expander("Ver Detalhes dos Veículos em Operação"):
            if em_operacao_df.empty:
                st.write("Nenhum veículo em operação.")
            else:
                for _, row in em_operacao_df.iterrows():
                    st.info(f"**Placa:** {row['Placa do caminhão']} | **Status Atual:** {obter_status(row)}")

    st.markdown("<div class='section-header'>📈 INDICADORES DE PERFORMANCE (HOJE)</div>", unsafe_allow_html=True)
    if not df.empty:
        hoje_str = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
        df_hoje = df[pd.to_datetime(df["Data"], errors='coerce').dt.strftime("%Y-%m-%d") == hoje_str].copy()
        
        if df_hoje.empty:
            st.info("Nenhum registro hoje para calcular as médias.")
        else:
            def hhmm_para_minutos(t):
                return int(t.split(":")[0]) * 60 + int(t.split(":")[1]) if isinstance(t, str) and ":" in t else np.nan

            def calcular_media_tempo(s):
                m = s.apply(hhmm_para_minutos).mean()
                return f"{int(m // 60):02d}:{int(m % 60):02d}" if not pd.isna(m) else "N/D"

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Métricas da Fábrica")
                st.metric("Tempo Médio Esperando Doca", calcular_media_tempo(df_hoje["Tempo Espera Doca"]))
                st.metric("Tempo Médio de Carregamento", calcular_media_tempo(df_hoje["Tempo de Carregamento"]))
            with c2:
                st.subheader("Métricas do CD")
                st.metric("Tempo Médio de Percurso", calcular_media_tempo(df_hoje["Tempo Percurso Para CD"]))
                st.metric("Tempo Médio de Descarregamento", calcular_media_tempo(df_hoje["Tempo de Descarregamento CD"]))


# =============================================================================
# PÁGINA DE NOVO REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 Novo Registro de Transferência")

    if 'novo_registro_dict' not in st.session_state:
        st.session_state.novo_registro_dict = {}

    reg = st.session_state.novo_registro_dict

    reg["Placa do caminhão"] = st.text_input("🚛 Placa", reg.get("Placa do caminhão", ""), key="placa_novo")
    reg["Nome do conferente"] = st.text_input("👤 Conferente", reg.get("Nome do conferente", ""), key="conferente_novo")

    st.markdown("---")

    for campo in campos_tempo:
        valor_atual = reg.get(campo, "")
        if valor_atual and str(valor_atual).strip():
            st.success(f"✅ {campo}: {valor_atual}")
        else:
            if st.button(f"📌 Registrar {campo}", key=f"btn_novo_{campo}", use_container_width=True):
                reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()

    st.markdown("---")

    if st.button("💾 SALVAR NOVO REGISTRO", type="primary", use_container_width=True):
        if not all(k in reg and reg[k].strip() for k in ["Placa do caminhão", "Nome do conferente"]):
            st.error("⚠️ Placa e Nome do Conferente são obrigatórios!")
        else:
            with st.spinner("Salvando novo registro..."):
                reg["Data"] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
                reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
                reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
                reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
                reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
                reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
                reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
                reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

                try:
                    worksheet.append_row([
                        reg.get(col, "") or None for col in COLUNAS_ESPERADAS
                    ], value_input_option='USER_ENTERED')
                    st.cache_data.clear()
                    st.success("✅ Novo registro salvo com sucesso!")
                    del st.session_state.novo_registro_dict
                    st.session_state.notification = ("success", "Registro criado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Falha ao salvar: {e}")

    if "notification" in st.session_state:
        del st.session_state.notification


# =============================================================================
# PÁGINA DE EDIÇÃO (VERSÃO QUE FUNCIONA DE VERDADE)
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ Editar Registros Incompletos")

    df = carregar_dataframe(worksheet)
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!")
        st.stop()

    opcoes = {
        f"🚛 {row['Placa do caminhão']} | 📅 {row['Data']} | Último: {obter_status(row)}": idx 
        for idx, row in incompletos.iterrows()
    }

    selecao = st.selectbox(
        "Selecione um registro para editar:",
        options=["Selecione..."] + list(opcoes.keys()),
        key="select_registro_edicao"
    )

    if selecao != "Selecione..." and selecao in opcoes:
        df_idx = opcoes[selecao]

        # Carrega o registro apenas se for novo ou mudou
        if "registro_em_edicao" not in st.session_state or st.session_state.get("df_idx_atual") != df_idx:
            st.session_state.registro_em_edicao = df.loc[df_idx].to_dict()
            st.session_state.df_idx_atual = df_idx

        reg = st.session_state.registro_em_edicao
        st.markdown(f"#### Placa: `{reg['Placa do caminhão']}` | Conferente: {reg['Nome do conferente']}")
        st.markdown("---")

        # Vai armazenar se algum campo foi alterado
        houve_alteracao = False

        # Exibe cada campo
        for campo in campos_tempo:
            valor_atual = reg.get(campo, "").strip()

            col1, col2 = st.columns([4, 1])
            with col1:
                if valor_atual:
                    st.success(f"✅ **{campo}:** `{valor_atual}`")
                else:
                    st.write(f"⚪ {campo}: Não registrado")

            with col2:
                if not valor_atual:
                    if st.button("⏰", key=f"btn_edit_{campo}", help=f"Registrar horário atual para '{campo}'"):
                        # Armazena temporariamente qual campo quer registrar
                        st.session_state.campo_para_registrar = campo
                        st.warning(f"Você deseja registrar o horário atual para **'{campo}'**?")
                        # Botão de confirmação explícita
                        if st.button(f"✅ Sim, registrar '{campo}'", key=f"conf_{campo}"):
                            hora_atual = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                            reg[campo] = hora_atual
                            st.session_state.registro_em_edicao = reg
                            houve_alteracao = True
                            st.success(f"✅ Registrado: **{campo}** → {hora_atual}")
                            st.rerun()

        # Se houve alteração, recalcular tempos
        if houve_alteracao:
            reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
            reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
            reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
            reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
            reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
            reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
            reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))
            st.session_state.registro_em_edicao = reg

        st.markdown("---")

        # Botão para salvar tudo
        if st.button("💾 SALVAR ALTERAÇÕES NO REGISTRO", type="primary", use_container_width=True):
            try:
                row_idx = reg["df_index"] + 2
                valores = [reg.get(col, "") or None for col in COLUNAS_ESPERADAS]
                worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.success("✅ Registro salvo com sucesso!")
                
                # Limpar estado
                del st.session_state.registro_em_edicao
                del st.session_state.df_idx_atual
                st.session_state.select_registro_edicao = "Selecione..."
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falha ao salvar: {e}")


# =============================================================================
# PÁGINAS DE VISUALIZAÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    st.markdown("### 📊 Registros em Operação")
    df = carregar_dataframe(worksheet)
    df_filtro = df[df["Saída CD"] == ""].copy()
    if df_filtro.empty:
        st.info("Nenhum registro em operação.")
    else:
        st.dataframe(df_filtro, use_container_width=True)

elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    st.markdown("### ✅ Registros Finalizados")
    df = carregar_dataframe(worksheet)
    df_filtro = df[df["Saída CD"] != ""].copy()
    if df_filtro.empty:
        st.info("Nenhum registro finalizado.")
    else:
        st.dataframe(df_filtro, use_container_width=True)
