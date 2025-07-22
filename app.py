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
    "Entrada na Balança Fábrica",
    "Saída balança Fábrica",
    "Entrada na Fábrica",
    "Encostou na doca Fábrica",
    "Início carregamento",
    "Fim carregamento",
    "Faturado",
    "Amarração carga",
    "Saída do pátio",
    "Entrada na Balança CD",
    "Saída balança CD",
    "Entrada CD",
    "Encostou na doca CD",
    "Início Descarregamento CD",
    "Fim Descarregamento CD",
    "Saída CD"
]

campos_calculados = [
    "Tempo Espera Doca", "Tempo de Carregamento", "Tempo Total",
    "Tempo Percurso Para CD", "Tempo Espera Doca CD", "Tempo de Descarregamento CD", "Tempo Total CD"
]

COLUNAS_ESPERADAS = ["Data", "Placa do caminhão", "Nome do conferente"] + campos_tempo + campos_calculados

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "Tela Inicial"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Suzano - Controle de Carga",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS PARA CELULAR (BOTÕES GRANDES) ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f4e79;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 20px;
        padding: 20px;
        background: linear-gradient(90deg, #e8f4f8, #f0f8ff);
        border-radius: 12px;
        border-left: 6px solid #1f4e79;
    }
    .section-header {
        color: #1f4e79;
        font-size: 22px;
        font-weight: bold;
        margin: 25px 0 15px 0;
        padding-bottom: 5px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stButton button {
        height: 55px;
        font-size: 18px;
        font-weight: 600;
    }
    .stMetric {
        background-color: white;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def connect_to_google_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets ", "https://www.googleapis.com/auth/drive "]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        return client.open(NOME_PLANILHA).sheet1
    except Exception as e:
        st.error(f"❌ Erro ao conectar: {e}")
        return None

worksheet = connect_to_google_sheets()
if not worksheet:
    st.stop()

# --- CARREGAR DADOS ---
@st.cache_data(ttl=10)
def carregar_dados():
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        for col in COLUNAS_ESPERADAS:
            if col not in df.columns:
                df[col] = ''
        return df[COLUNAS_ESPERADAS].fillna("")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

# --- FUNÇÕES AUXILIARES ---
def calcular_tempo(inicio, fim):
    if not inicio or not fim:
        return ""
    try:
        i = pd.to_datetime(inicio)
        f = pd.to_datetime(fim)
        diff = f - i
        if diff.total_seconds() < 0:
            return "Inválido"
        h, rem = divmod(diff.total_seconds(), 3600)
        m, _ = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}"
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
        chaves_para_manter = ["pagina_atual"]
        for key in list(st.session_state.keys()):
            if key not in chaves_para_manter:
                del st.session_state[key]
        st.rerun()

# ============================================================================= 
# TÍTULO PRINCIPAL
# =============================================================================
st.markdown("<div class='main-header'>🚛 SUZANO - CONTROLE DE CARGA</div>", unsafe_allow_html=True)

# =============================================================================
# TELA INICIAL
# =============================================================================
if st.session_state.pagina_atual == "Tela Inicial":
    st.markdown("<div class='section-header'>MENU PRINCIPAL</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    if col1.button("🆕 NOVO REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Novo"
        st.rerun()
    if col1.button("✏️ EDITAR REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Editar"
        st.rerun()
    if col2.button("📊 EM OPERAÇÃO", use_container_width=True):
        st.session_state.pagina_atual = "Em Operação"
        st.rerun()
    if col2.button("✅ FINALIZADAS", use_container_width=True):
        st.session_state.pagina_atual = "Finalizadas"
        st.rerun()

    df = carregar_dados()
    st.markdown("<div class='section-header'>SITUAÇÃO ATUAL</div>", unsafe_allow_html=True)
    if not df.empty:
        operacao = df[df["Saída CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)
        m1.metric("🚛 Em Operação", len(operacao))
        m2.metric("🏭 Na Fábrica", len(operacao[operacao["Saída do pátio"] == ""]))
        m3.metric("📦 No CD / Rota", len(operacao) - len(operacao[operacao["Saída do pátio"] == ""]))

        with st.expander("Ver Veículos"):
            for _, row in operacao.iterrows():
                st.info(f"**{row['Placa do caminhão']}** | {obter_status(row)}")

    # INDICADORES - CORRIGIDO PARA EVITAR ERROS DE NaN
    st.markdown("<div class='section-header'>📈 MÉDIAS DO DIA</div>", unsafe_allow_html=True)
    if not df.empty:
        hoje_str = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
        df_hoje = df[pd.to_datetime(df["Data"], errors='coerce').dt.strftime("%Y-%m-%d") == hoje_str].copy()

        def hhmm_para_minutos(t):
            if pd.isna(t) or not isinstance(t, str) or ":" not in t:
                return np.nan
            try:
                h, m = t.split(":")
                return int(h) * 60 + int(m)
            except:
                return np.nan

        def media_formatada(s):
            m = s.dropna().apply(hhmm_para_minutos).mean()
            if pd.isna(m):
                return "N/D"
            return f"{int(m//60):02d}:{int(m%60):02d}"

        if not df_hoje.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("⏱️ Espera na Doca", media_formatada(df_hoje["Tempo Espera Doca"]))
                st.metric("📦 Carregamento", media_formatada(df_hoje["Tempo de Carregamento"]))
            with c2:
                st.metric("🚗 Percurso até CD", media_formatada(df_hoje["Tempo Percurso Para CD"]))
                st.metric("📤 Descarregamento", media_formatada(df_hoje["Tempo de Descarregamento CD"]))

# =============================================================================
# NOVO REGISTRO (APENAS ENTRADA NA BALANÇA)
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 NOVO REGISTRO - Entrada na Fábrica")

    if 'novo_registro' not in st.session_state:
        st.session_state.novo_registro = {"Data": datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")}

    reg = st.session_state.novo_registro

    reg["Placa do caminhão"] = st.text_input("🚛 Placa do Caminhão", reg.get("Placa do caminhão", "")).upper().strip()
    reg["Nome do conferente"] = st.text_input("👤 Nome do Conferente", reg.get("Nome do conferente", ""))

    st.markdown("---")

    campo_balanca = "Entrada na Balança Fábrica"
    valor = reg.get(campo_balanca, "")

    if valor:
        st.success(f"✅ {campo_balanca}: `{valor}`")
    else:
        if st.button(f"📌 Registrar {campo_balanca}", type="primary", use_container_width=True):
            reg[campo_balanca] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

    st.markdown("---")

    if st.button("💾 SALVAR REGISTRO INICIAL", disabled=not all(reg.get(k) for k in ["Placa do caminhão", "Nome do conferente", campo_balanca]), use_container_width=True):
        try:
            worksheet.append_row([reg.get(col, "") or None for col in COLUNAS_ESPERADAS], value_input_option='USER_ENTERED')
            st.cache_data.clear()
            st.success("✅ Registro criado! Use 'Editar' para continuar.")
            del st.session_state.novo_registro
            st.session_state.pagina_atual = "Tela Inicial"
            st.rerun()
        except Exception as e:
            st.error(f"❌ Falha ao salvar: {e}")

# =============================================================================
# EDITAR REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS")

    df = carregar_dados()
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos completos!")
        st.stop()

    opcoes = {
        f"🚛 {r['Placa do caminhão']} | {obter_status(r)}": idx
        for idx, r in incompletos.iterrows()
    }

    selecao = st.selectbox("Selecione:", ["Selecione..."] + list(opcoes.keys()))

    if selecao != "Selecione..." and selecao in opcoes:
        idx = opcoes[selecao]
        if "registro_edit" not in st.session_state or st.session_state.idx_edit != idx:
            st.session_state.registro_edit = df.loc[idx].to_dict()
            st.session_state.idx_edit = idx

        reg = st.session_state.registro_edit
        st.markdown(f"**Placa:** `{reg['Placa do caminhão']}`")

        for campo in campos_tempo:
            valor = reg.get(campo, "")
            if valor:
                st.success(f"✅ {campo}: `{valor}`")
            else:
                if st.button(f"⏰ Registrar {campo}", key=f"edit_{campo}", use_container_width=True):
                    reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                    # Recalcular tempos
                    reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
                    reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
                    reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
                    reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
                    reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
                    reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
                    reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

                    try:
                        row_idx = idx + 2
                        valores = [reg.get(col, "") or None for col in COLUNAS_ESPERADAS]
                        worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                        st.cache_data.clear()
                        st.success(f"✅ {campo} atualizado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")

# =============================================================================
# VISUALIZAÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] == ""], hide_index=True, use_container_width=True)

elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] != ""], hide_index=True, use_container_width=True)
