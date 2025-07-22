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
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes )
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
        inicio_dt = pd.to_datetime(inicio, errors='coerce')
        fim_dt = pd.to_datetime(fim, errors='coerce')
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
        for key in list(st.session_state.keys()):
            if key not in ["pagina_atual"]: del st.session_state[key]
        st.rerun()

worksheet = connect_to_google_sheets()
st.markdown("<div class='main-header'>🚚 Suzano - Controle de Transferência de Carga</div>", unsafe_allow_html=True)

# =============================================================================
# TELA INICIAL
# =============================================================================
if st.session_state.pagina_atual == "Tela Inicial":
    st.markdown("<div class='section-header'>MENU DE AÇÕES</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button("🆕 NOVO REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Novo"; st.rerun()
    if col1.button("📊 EM OPERAÇÃO", use_container_width=True):
        st.session_state.pagina_atual = "Em Operação"; st.rerun()
    if col2.button("✏️ EDITAR REGISTRO", use_container_width=True):
        st.session_state.pagina_atual = "Editar"; st.rerun()
    if col2.button("✅ FINALIZADAS", use_container_width=True):
        st.session_state.pagina_atual = "Finalizadas"; st.rerun()

    df = carregar_dataframe(worksheet)
    st.markdown("<div class='section-header'>SITUAÇÃO ATUAL</div>", unsafe_allow_html=True)
    if not df.empty:
        em_operacao_df = df[df["Saída CD"] == ""].copy()
        na_fabrica = len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""])
        m1, m2, m3 = st.columns(3)
        m1.metric(label="🚛 Em Operação (Total)", value=len(em_operacao_df))
        m2.metric(label="🏭 Na Fábrica", value=na_fabrica)
        m3.metric(label="📦 Em Rota / No CD", value=len(em_operacao_df) - na_fabrica)
        with st.expander("Ver Detalhes dos Veículos em Operação"):
            if em_operacao_df.empty: st.write("Nenhum veículo em operação.")
            else:
                for _, row in em_operacao_df.iterrows():
                    st.info(f"**Placa:** {row['Placa do caminhão']} | **Status Atual:** {obter_status(row)}")

    st.markdown("<div class='section-header'>📈 INDICADORES DE PERFORMANCE (HOJE)</div>", unsafe_allow_html=True)
    if not df.empty:
        df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
        hoje = datetime.now(FUSO_HORARIO).date()
        df_hoje = df[df['Data_dt'] == hoje].copy()
        
        if df_hoje.empty: st.info("Nenhum registro hoje para calcular as médias.")
        else:
            def hhmm_para_minutos(t):
                if isinstance(t, str) and ":" in t and t != "Inválido":
                    parts = t.split(":")
                    return int(parts[0]) * 60 + int(parts[1])
                return np.nan

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
    if 'novo_registro_dict' not in st.session_state: st.session_state.novo_registro_dict = {}
    
    def registrar_agora_novo(campo):
        st.session_state.novo_registro_dict[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")

    def salvar_novo_registro():
        if not all(st.session_state.novo_registro_dict.get(k) for k in ["Placa do caminhão", "Nome do conferente"]):
            st.session_state.notification = ("error", "Placa e Conferente são obrigatórios.")
            return
        with st.spinner("Salvando..."):
            reg = st.session_state.novo_registro_dict
            reg["Data"] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
            
            reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
            reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
            reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
            reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
            reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
            reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
            reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

            try:
                valores = [reg.get(col) if reg.get(col, '') != '' else None for col in COLUNAS_ESPERADAS]
                worksheet.append_row(valores, value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.session_state.notification = ("success", "Novo registro salvo!")
                del st.session_state.novo_registro_dict
            except Exception as e: st.session_state.notification = ("error", f"Falha: {e}")

    reg = st.session_state.novo_registro_dict
    reg["Placa do caminhão"] = st.text_input("🚛 Placa", reg.get("Placa do caminhão", ""), key="placa_novo")
    reg["Nome do conferente"] = st.text_input("👤 Conferente", reg.get("Nome do conferente", ""), key="conferente_novo")
    st.markdown("---")
    for campo in campos_tempo:
        if reg.get(campo):
            st.success(f"✅ {campo}: {reg[campo]}")
        else:
            st.button(f"Registrar {campo}", key=f"btn_novo_{campo}", on_click=registrar_agora_novo, args=(campo,))
    
    st.markdown("---")
    
    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        st.button("💾 SALVAR NOVO REGISTRO", on_click=salvar_novo_registro, use_container_width=True, type="primary")
    with col_msg:
        if st.session_state.get("notification"):
            msg_type, msg_text = st.session_state.notification
            if msg_type == "success": st.success(msg_text)
            else: st.error(msg_text)
            del st.session_state.notification

# =============================================================================
# PÁGINA DE EDIÇÃO (LÓGICA NOVA E ROBUSTA)
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ Editar Registros Incompletos")

    df = carregar_dataframe(worksheet)
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!"); st.stop()

    opcoes = {
        f"🚛 {row['Placa do caminhão']} | 📅 {pd.to_datetime(row['Data']).strftime('%Y-%m-%d')}": row.name
        for _, row in incompletos.iterrows()
    }
    
    # Limpa o estado de edição se a seleção mudar
    def on_selection_change():
        if 'registro_em_edicao' in st.session_state:
            del st.session_state.registro_em_edicao
        if 'campo_para_registrar' in st.session_state:
            del st.session_state.campo_para_registrar

    selecao = st.selectbox(
        "Selecione um registro:", 
        options=["Selecione..."] + list(opcoes.keys()), 
        key="selectbox_edicao",
        on_change=on_selection_change
    )

    if selecao != "Selecione...":
        # Carrega o registro para a sessão se ainda não estiver lá
        if 'registro_em_edicao' not in st.session_state:
            df_index_real = opcoes[selecao]
            st.session_state.registro_em_edicao = df.loc[df_index_real].to_dict()

        reg = st.session_state.registro_em_edicao
        st.markdown(f"#### Editando Placa: **{reg['Placa do caminhão']}**")

        # Se um campo foi marcado para registro, mostra a confirmação
        if st.session_state.get('campo_para_registrar'):
            campo_a_registrar = st.session_state.campo_para_registrar
            st.warning(f"Confirmar horário atual para **'{campo_a_registrar}'**?")
            
            col1, col2 = st.columns(2)
            if col1.button("✅ Sim, registrar agora", use_container_width=True, type="primary"):
                with st.spinner("Registrando e salvando..."):
                    # Atualiza o campo com a hora atual
                    reg[campo_a_registrar] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Recalcula todos os tempos derivados
                    reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
                    reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
                    reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
                    reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
                    reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
                    reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
                    reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

                    # Salva a linha inteira na planilha
                    try:
                        row_idx = reg["df_index"] + 2
                        valores = [reg.get(col, "") for col in COLUNAS_ESPERADAS]
                        worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                        st.cache_data.clear()
                        st.success(f"✅ '{campo_a_registrar}' registrado com sucesso!")
                        
                        # Limpa o estado para a próxima ação
                        del st.session_state.campo_para_registrar
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Falha ao salvar: {e}")

            if col2.button("❌ Cancelar", use_container_width=True):
                del st.session_state.campo_para_registrar
                st.rerun()
        
        # Se nenhum campo estiver marcado para registro, mostra a lista de botões
        else:
            for campo in campos_tempo:
                valor_atual = reg.get(campo, "")
                if valor_atual and str(valor_atual).strip():
                    st.success(f"✅ {campo}: {valor_atual}")
                else:
                    # Este botão apenas marca qual campo queremos registrar
                    if st.button(f"⏰ Registrar {campo}", key=f"btn_edit_{campo}"):
                        st.session_state.campo_para_registrar = campo
                        st.rerun()

# =============================================================================
# OUTRAS PÁGINAS
# =============================================================================
elif st.session_state.pagina_atual in ["Em Operação", "Finalizadas"]:
    botao_voltar()
    df = carregar_dataframe(worksheet)
    
    if st.session_state.pagina_atual == "Em Operação":
        st.markdown("### 📊 Registros em Operação")
        subset_df = df[df["Saída CD"] == ""].copy()
        st.dataframe(subset_df) 
            
    elif st.session_state.pagina_atual == "Finalizadas":
        st.markdown("### ✅ Registros Finalizados")
        subset_df = df[df["Saída CD"] != ""].copy()
        st.dataframe(subset_df)
