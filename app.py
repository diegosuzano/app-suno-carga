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

if 'rerun_needed' not in st.session_state:
    st.session_state.rerun_needed = False

if 'notification' not in st.session_state:
    st.session_state.notification = None

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
    if _worksheet is None: return pd.DataFrame(columns=COLUNAS_ESPERADAS)
    try:
        data = _worksheet.get_all_values()
        if len(data) < 2: return pd.DataFrame(columns=COLUNAS_ESPERADAS)
        df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
        for col in COLUNAS_ESPERADAS:
            if col not in df.columns: df[col] = ''
        df = df[COLUNAS_ESPERADAS]
        df["df_index"] = df.index
        return df.fillna("")
    except Exception as e:
        st.error(f"Erro ao ler dados da planilha: {e}")
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

# --- FUNÇÕES AUXILIARES ---
def calcular_tempo(inicio, fim):
    if not all([inicio, fim]) or not all(str(v).strip() for v in [inicio, fim]): return ""
    try:
        inicio_dt, fim_dt = pd.to_datetime(inicio, errors='coerce'), pd.to_datetime(fim, errors='coerce')
        if pd.isna(inicio_dt) or pd.isna(fim_dt): return ""
        diff = fim_dt - inicio_dt
        if diff.total_seconds() < 0: return "Inválido"
        horas, rem = divmod(diff.total_seconds(), 3600)
        minutos, _ = divmod(rem, 60)
        return f"{int(horas):02d}:{int(minutos):02d}"
    except: return ""

def obter_status(registro):
    for campo in reversed(campos_tempo):
        if registro.get(campo) and str(registro.get(campo)).strip(): return campo
    return "Não iniciado"

def botao_voltar():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state.pagina_atual = "Tela Inicial"
        chaves_para_manter = ["pagina_atual"]
        for key in list(st.session_state.keys()):
            if key not in chaves_para_manter:
                del st.session_state[key]
        st.rerun()

worksheet = connect_to_google_sheets()

# Título principal
st.markdown("<div class='main-header'>🚚 Suzano - Controle de Transferência de Carga</div>", unsafe_allow_html=True)

# =============================================================================
# NOTIFICAÇÃO FLUTUANTE (se houver)
# =============================================================================
if st.session_state.notification:
    msg_type, msg_text = st.session_state.notification
    icon = "✅" if msg_type == "success" else "❌"
    st.markdown(
        f"""
        <div class="floating-notification">
            <div style="background: {'#dcfce7' if msg_type == 'success' else '#fee2e2'}; 
                        border: 1px solid {'#22c55e' if msg_type == 'success' else '#ef4444'};
                        color: {'#166534' if msg_type == 'success' else '#991b1b'};
                        padding: 12px; border-radius: 8px; font-weight: 500;">
                {icon} {msg_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.session_state.notification = None

# =============================================================================
# TELA INICIAL
# =============================================================================
if st.session_state.pagina_atual == "Tela Inicial":
    st.markdown("<div class='section-header'>📋 MENU PRINCIPAL</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🆕 NOVO REGISTRO", use_container_width=True):
            st.session_state.pagina_atual = "Novo"
            st.rerun()

    with col1:
        if st.button("📊 EM OPERAÇÃO", use_container_width=True):
            st.session_state.pagina_atual = "Em Operação"
            st.rerun()

    with col2:
        if st.button("✏️ EDITAR REGISTRO", use_container_width=True):
            st.session_state.pagina_atual = "Editar"
            st.rerun()

    with col2:
        if st.button("✅ FINALIZADAS", use_container_width=True):
            st.session_state.pagina_atual = "Finalizadas"
            st.rerun()

    df = carregar_dataframe(worksheet)
    st.markdown("<div class='section-header'>📊 SITUAÇÃO ATUAL</div>", unsafe_allow_html=True)

    if not df.empty:
        em_operacao_df = df[df["Saída CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)

        m1.metric(label="🚛 Em Operação", value=len(em_operacao_df))
        m2.metric(label="🏭 Na Fábrica", value=len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))
        m3.metric(label="📦 Em Rota / No CD", value=len(em_operacao_df) - len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))

        with st.expander("Ver Detalhes dos Veículos em Operação"):
            if em_operacao_df.empty:
                st.info("Nenhum veículo em operação.")
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
    st.markdown("### 🆕 NOVO REGISTRO DE TRANSFERÊNCIA")

    if 'novo_registro_dict' not in st.session_state:
        st.session_state.novo_registro_dict = {}

    reg = st.session_state.novo_registro_dict

    reg["Placa do caminhão"] = st.text_input("🚛 Placa", reg.get("Placa do caminhão", ""), key="placa_novo").upper().strip()
    reg["Nome do conferente"] = st.text_input("👤 Conferente", reg.get("Nome do conferente", ""), key="conferente_novo")

    st.markdown("---")

    for campo in campos_tempo:
        valor_atual = reg.get(campo, "")
        if valor_atual and str(valor_atual).strip():
            st.success(f"✅ {campo}: {valor_atual}")
        else:
            if st.button(f"Registrar {campo}", key=f"btn_novo_{campo}", use_container_width=True):
                reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.novo_registro_dict = reg
                st.rerun()

    st.markdown("---")

    def salvar_novo_registro():
        if not all(k in reg and reg[k].strip() for k in ["Placa do caminhão", "Nome do conferente"]):
            st.session_state.notification = ("error", "Placa e Nome do Conferente são obrigatórios!")
            return

        with st.spinner("Salvando novo registro..."):
            reg["Data"] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")

            # Recalcula todos os tempos
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
                st.session_state.notification = ("success", "Novo registro salvo com sucesso!")
                del st.session_state.novo_registro_dict
                st.rerun()
            except Exception as e:
                st.session_state.notification = ("error", f"Falha ao salvar: {e}")

    if st.button("💾 SALVAR NOVO REGISTRO", type="primary", use_container_width=True):
        salvar_novo_registro()

    if st.session_state.notification:
        msg_type, msg_text = st.session_state.notification
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.error(msg_text)
        del st.session_state.notification

# =============================================================================
# PÁGINA DE EDIÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS INCOMPLETOS")

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

        # Carregar o registro se for novo ou mudou
        if "registro_em_edicao" not in st.session_state or st.session_state.get("df_idx_atual") != df_idx:
            st.session_state.registro_em_edicao = df.loc[df_idx].to_dict()
            st.session_state.df_idx_atual = df_idx

        reg = st.session_state.registro_em_edicao

        st.markdown(f"#### Placa: `{reg['Placa do caminhão']}` | Conferente: {reg['Nome do conferente']}")
        st.markdown("---")

        # Armazenar mudanças temporariamente
        campos_atualizados = False

        # Exibir status de cada campo e botões para registrar
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
                    # Botão para registrar AGORA esse campo específico
                    if st.button("⏰", key=f"btn_edit_{campo}", use_container_width=True):
                        # Atualiza apenas este campo com timestamp atual
                        reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                        st.session_state.registro_em_edicao = reg  # Salva no estado
                        campos_atualizados = True

        # Recalcular tempos somente se algum campo foi atualizado
        if campos_atualizados:
            with st.spinner("Atualizando tempos calculados..."):
                reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
                reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
                reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
                reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
                reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
                reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
                reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

                st.session_state.registro_em_edicao = reg
                st.rerun()  # Força atualização visual após mudança

        st.markdown("---")
        # Botão para salvar tudo
        if st.button("💾 SALVAR ALTERAÇÕES NO REGISTRO", type="primary", use_container_width=True):
            try:
                row_idx = reg["df_index"] + 2  # Linha correta na planilha
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

    # Mensagem de confirmação global
    if "notification" in st.session_state:
        msg_type, msg_text = st.session_state.notification
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.error(msg_text)
        del st.session_state.notification

# =============================================================================
# OUTRAS PÁGINAS
# =============================================================================
elif st.session_state.pagina_atual in ["Em Operação", "Finalizadas"]:
    botao_voltar()
    st.markdown(f"### {st.session_state.pagina_atual.replace('_', ' ').title()}")

    df = carregar_dataframe(worksheet)
    subset_df = df[df["Saída CD"] == ""] if st.session_state.pagina_atual == "Em Operação" else df[df["Saída CD"] != ""]
    if subset_df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        st.dataframe(subset_df, use_container_width=True)
