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
    .stButton {
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE CONEXÃO E DADOS ---
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def connect_to_google_sheets():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
          )
        client = gspread.authorize(creds)
        spreadsheet = client.open(NOME_PLANILHA)
        return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Erro de conexão com o Google Sheets: {e}. Verifique suas credenciais, o nome da planilha e se você a compartilhou com o e-mail do robô.")
        return None

@st.cache_data(ttl=30, show_spinner="Carregando dados...")
def carregar_dataframe(_worksheet):
    if _worksheet is None: return pd.DataFrame(columns=COLUNAS_ESPERADAS)
    try:
        data = _worksheet.get_all_values()
        if len(data) < 2:
            return pd.DataFrame(columns=COLUNAS_ESPERADAS)

        df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
        for col in COLUNAS_ESPERADAS:
            if col not in df.columns: df[col] = ''

        df = df[COLUNAS_ESPERADAS]
        # <<< CORREÇÃO 1: Manter a data como string, sem converter para objeto date.
        # A linha abaixo foi removida:
        # df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.date
        df['df_index'] = df.index
        return df.fillna('')
    except Exception as e:
        st.error(f"Erro ao ler dados da planilha: {e}")
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

# --- FUNÇÕES AUXILIARES ---
def calcular_tempo(inicio, fim):
    if not inicio or not fim or str(inicio).strip() == '' or str(fim).strip() == '':
        return ""
    try:
        inicio_dt = pd.to_datetime(inicio, errors='coerce')
        fim_dt = pd.to_datetime(fim, errors='coerce')

        if pd.isna(inicio_dt) or pd.isna(fim_dt):
            return ""

        diff = fim_dt - inicio_dt
        if diff.total_seconds() < 0: return "Inválido"
        horas = int(diff.total_seconds() // 3600)
        minutos = int((diff.total_seconds() % 3600) // 60)
        return f"{horas:02d}:{minutos:02d}"
    except: return ""

def obter_status(registro):
    for campo in reversed(campos_tempo):
        valor = registro.get(campo)
        if valor and str(valor).strip() != '': return campo
    return "Não iniciado"

def botao_voltar():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state.pagina_atual = "Tela Inicial"
        for key in list(st.session_state.keys()):
            if key not in ['pagina_atual']:
                del st.session_state[key]
        st.rerun()

# --- CONEXÃO INICIAL ---
worksheet = connect_to_google_sheets()

# --- LAYOUT PRINCIPAL ---
st.markdown("<div class='main-header'>🚚 Suzano - Controle de Transferência de Carga</div>", unsafe_allow_html=True)

# =============================================================================
# TELA INICIAL
# =============================================================================
if st.session_state.pagina_atual == "Tela Inicial":
    st.markdown("<div class='section-header'>MENU DE AÇÕES</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🆕 NOVO REGISTRO", use_container_width=True):
            st.session_state.pagina_atual = "Novo"
            st.rerun()
        if st.button("📊 EM OPERAÇÃO", use_container_width=True):
            st.session_state.pagina_atual = "Em Operação"
            st.rerun()
    with col2:
        if st.button("✏️ EDITAR REGISTRO", use_container_width=True):
            st.session_state.pagina_atual = "Editar"
            st.rerun()
        if st.button("✅ FINALIZADAS", use_container_width=True):
            st.session_state.pagina_atual = "Finalizadas"
            st.rerun()

    df = carregar_dataframe(worksheet)

    st.markdown("<div class='section-header'>SITUAÇÃO ATUAL</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("Nenhum registro encontrado para exibir as métricas.")
    else:
        em_operacao_df = df[df["Saída CD"] == ''].copy()
        total_em_operacao = len(em_operacao_df)
        na_fabrica = len(em_operacao_df[em_operacao_df["Saída do pátio"] == ''])
        no_cd_ou_rota = total_em_operacao - na_fabrica

        m1, m2, m3 = st.columns(3)
        m1.metric(label="🚛 Em Operação (Total)", value=total_em_operacao)
        m2.metric(label="🏭 Na Fábrica", value=na_fabrica)
        m3.metric(label="📦 Em Rota / No CD", value=no_cd_ou_rota)

        with st.expander("Ver Detalhes dos Veículos em Operação"):
            if em_operacao_df.empty:
                st.write("Nenhum veículo em operação no momento.")
            else:
                for _, row in em_operacao_df.iterrows():
                    status = obter_status(row)
                    st.info(f"**Placa:** {row['Placa do caminhão']} | **Status Atual:** {status}")

    st.markdown("<div class='section-header'>📈 INDICADORES DE PERFORMANCE (HOJE)</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("Nenhum registro hoje para calcular as médias.")
    else:
        # <<< CORREÇÃO 2: Comparar a data como string.
        hoje_str = datetime.now(FUSO_HORARIO).strftime('%Y-%m-%d')
        df_hoje = df[df['Data'] == hoje_str].copy()

        if df_hoje.empty:
            st.info("Nenhum registro encontrado com a data de hoje.")
        else:
            def hhmm_para_minutos(tempo_str):
                if not tempo_str or ':' not in str(tempo_str): return np.nan
                try:
                    h, m = map(int, str(tempo_str).split(':'))
                    return h * 60 + m
                except: return np.nan

            def calcular_media_tempo(series):
                minutos = series.apply(hhmm_para_minutos).mean()
                if pd.isna(minutos): return "N/D"
                horas_media = int(minutos // 60)
                minutos_media = int(minutos % 60)
                return f"{horas_media:02d}:{minutos_media:02d}"

            col_fabrica, col_cd = st.columns(2)
            with col_fabrica:
                st.subheader("Métricas da Fábrica")
                st.metric(label="Tempo Médio Esperando Doca", value=calcular_media_tempo(df_hoje['Tempo Espera Doca']))
                st.metric(label="Tempo Médio de Carregamento", value=calcular_media_tempo(df_hoje['Tempo de Carregamento']))
                st.metric(label="Tempo Médio Total na Fábrica", value=calcular_media_tempo(df_hoje['Tempo Total']))
            with col_cd:
                st.subheader("Métricas do CD")
                st.metric(label="Tempo Médio de Percurso", value=calcular_media_tempo(df_hoje['Tempo Percurso Para CD']))
                st.metric(label="Tempo Médio Esperando Doca (CD)", value=calcular_media_tempo(df_hoje['Tempo Espera Doca CD']))
                st.metric(label="Tempo Médio de Descarregamento", value=calcular_media_tempo(df_hoje['Tempo de Descarregamento CD']))
                st.metric(label="Tempo Médio Total no CD", value=calcular_media_tempo(df_hoje['Tempo Total CD']))

# =============================================================================
# PÁGINA DE NOVO REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 Novo Registro de Transferência")

    if 'novo_registro_dict' not in st.session_state:
        st.session_state.novo_registro_dict = {}

    def registrar_agora_novo(campo):
        st.session_state.novo_registro_dict[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")

    def salvar_novo_registro():
        placa = st.session_state.novo_registro_dict.get("Placa do caminhão")
        conferente = st.session_state.novo_registro_dict.get("Nome do conferente")

        if not placa or not conferente:
            st.session_state.notification = ("error", "Placa e Conferente são obrigatórios para salvar.")
            return

        with st.spinner("Salvando no Google Sheets..."):
            st.session_state.novo_registro_dict['Data'] = datetime.now(FUSO_HORARIO).strftime('%Y-%m-%d')

            for campo in campos_calculados:
                st.session_state.novo_registro_dict[campo] = ""

            st.session_state.novo_registro_dict['Tempo Espera Doca'] = calcular_tempo(st.session_state.novo_registro_dict.get("Entrada na Fábrica"), st.session_state.novo_registro_dict.get("Encostou na doca Fábrica"))
            st.session_state.novo_registro_dict['Tempo de Carregamento'] = calcular_tempo(st.session_state.novo_registro_dict.get("Início carregamento"), st.session_state.novo_registro_dict.get("Fim carregamento"))
            st.session_state.novo_registro_dict['Tempo Total'] = calcular_tempo(st.session_state.novo_registro_dict.get("Entrada na Fábrica"), st.session_state.novo_registro_dict.get("Saída do pátio"))
            st.session_state.novo_registro_dict['Tempo Percurso Para CD'] = calcular_tempo(st.session_state.novo_registro_dict.get("Saída do pátio"), st.session_state.novo_registro_dict.get("Entrada CD"))
            st.session_state.novo_registro_dict['Tempo Espera Doca CD'] = calcular_tempo(st.session_state.novo_registro_dict.get("Entrada CD"), st.session_state.novo_registro_dict.get("Encostou na doca CD"))
            st.session_state.novo_registro_dict['Tempo de Descarregamento CD'] = calcular_tempo(st.session_state.novo_registro_dict.get("Início Descarregamento CD"), st.session_state.novo_registro_dict.get("Fim Descarregamento CD"))
            st.session_state.novo_registro_dict['Tempo Total CD'] = calcular_tempo(st.session_state.novo_registro_dict.get("Entrada CD"), st.session_state.novo_registro_dict.get("Saída CD"))

            nova_linha_lista = [st.session_state.novo_registro_dict.get(col, '') for col in COLUNAS_ESPERADAS]

            try:
                worksheet.append_row(nova_linha_lista, value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.session_state.notification = ("success", "Novo registro salvo com sucesso!")
                del st.session_state.novo_registro_dict
            except Exception as e:
                st.session_state.notification = ("error", f"Falha ao salvar: {e}")

    placa = st.text_input("🚛 Placa do Caminhão", value=st.session_state.novo_registro_dict.get("Placa do caminhão", ""), key="placa_novo")
    conferente = st.text_input("👤 Nome do Conferente", value=st.session_state.novo_registro_dict.get("Nome do conferente", ""), key="conferente_novo")
    st.session_state.novo_registro_dict["Placa do caminhão"] = placa
    st.session_state.novo_registro_dict["Nome do conferente"] = conferente
    st.markdown("---")

    for campo in campos_tempo:
        if st.session_state.novo_registro_dict.get(campo):
            st.success(f"✅ {campo}: {st.session_state.novo_registro_dict[campo]}")
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
# PÁGINA DE EDIÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ Editar Registros Incompletos")

    df = carregar_dataframe(worksheet)
    incompletos = df[df["Saída CD"] == ''].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!")
        st.stop()

    opcoes = {f"🚛 {row['Placa do caminhão']} | 📅 {row['Data']}": idx for idx, row in incompletos.iterrows()}

    def carregar_registro_para_edicao():
        selecao_atual = st.session_state.selectbox_edicao
        if selecao_atual != "Selecione...":
            df_index_filtrado = opcoes[selecao_atual]
            df_index_real = incompletos.loc[df_index_filtrado, 'df_index']
            st.session_state.registro_em_edicao = df.loc[df_index_real].to_dict()
        else:
            if 'registro_em_edicao' in st.session_state:
                del st.session_state.registro_em_edicao

    selecao_label = st.selectbox(
        "Selecione um registro para editar:",
        options=["Selecione..."] + list(opcoes.keys()),
        key="selectbox_edicao",
        on_change=carregar_registro_para_edicao
    )

    if 'registro_em_edicao' in st.session_state:
        reg = st.session_state.registro_em_edicao
        st.markdown(f"#### Editando Placa: **{reg['Placa do caminhão']}**")

        def registrar_agora_edit(campo_a_registrar):
            st.session_state.registro_em_edicao[campo_a_registrar] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")

        def salvar_alteracoes():
            with st.spinner("Salvando no Google Sheets..."):
                registro_para_salvar = st.session_state.registro_em_edicao

                # A conversão de data não é mais necessária aqui, pois ela já é uma string.

                if registro_para_salvar.get("Entrada na Fábrica") and registro_para_salvar.get("Encostou na doca Fábrica"):
                    registro_para_salvar['Tempo Espera Doca'] = calcular_tempo(registro_para_salvar.get("Entrada na Fábrica"), registro_para_salvar.get("Encostou na doca Fábrica"))
                if registro_para_salvar.get("Início carregamento") and registro_para_salvar.get("Fim carregamento"):
                    registro_para_salvar['Tempo de Carregamento'] = calcular_tempo(registro_para_salvar.get("Início carregamento"), registro_para_salvar.get("Fim carregamento"))
                if registro_para_salvar.get("Entrada na Fábrica") and registro_para_salvar.get("Saída do pátio"):
                    registro_para_salvar['Tempo Total'] = calcular_tempo(registro_para_salvar.get("Entrada na Fábrica"), registro_para_salvar.get("Saída do pátio"))
                if registro_para_salvar.get("Saída do pátio") and registro_para_salvar.get("Entrada CD"):
                    registro_para_salvar['Tempo Percurso Para CD'] = calcular_tempo(registro_para_salvar.get("Saída do pátio"), registro_para_salvar.get("Entrada CD"))
                if registro_para_salvar.get("Entrada CD") and registro_para_salvar.get("Encostou na doca CD"):
                    registro_para_salvar['Tempo Espera Doca CD'] = calcular_tempo(registro_para_salvar.get("Entrada CD"), registro_para_salvar.get("Encostou na doca CD"))
                if registro_para_salvar.get("Início Descarregamento CD") and registro_para_salvar.get("Fim Descarregamento CD"):
                    registro_para_salvar['Tempo de Descarregamento CD'] = calcular_tempo(registro_para_salvar.get("Início Descarregamento CD"), registro_para_salvar.get("Fim Descarregamento CD"))
                if registro_para_salvar.get("Entrada CD") and registro_para_salvar.get("Saída CD"):
                    registro_para_salvar['Tempo Total CD'] = calcular_tempo(registro_para_salvar.get("Entrada CD"), registro_para_salvar.get("Saída CD"))

                try:
                    gsheet_row_index = reg['df_index'] + 2
                    valores_para_salvar = [registro_para_salvar.get(col) if registro_para_salvar.get(col, '') else None for col in COLUNAS_ESPERADAS]

                    worksheet.update(f'A{gsheet_row_index}', [valores_para_salvar], value_input_option='USER_ENTERED')
                    st.cache_data.clear()
                    st.session_state.notification = ("success", "Registro atualizado com sucesso!")
                    del st.session_state.registro_em_edicao
                    st.session_state.selectbox_edicao = "Selecione..."
                    st.rerun()
                except Exception as e:
                    st.session_state.notification = ("error", f"Falha ao salvar: {e}")

        for campo in campos_tempo:
            valor_atual = reg.get(campo, '')
            if isinstance(valor_atual, str) and valor_atual.strip():
                st.success(f"✅ {campo}: {valor_atual}")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text_input(f"📋 {campo}", value="Pendente...", disabled=True, key=f"placeholder_{campo}")
                with col2:
                    st.button(
                        "⏰ Agora",
                        key=f"btn_now_edit_{campo}",
                        on_click=registrar_agora_edit,
                        args=(campo,),
                        use_container_width=True
                    )

        st.markdown("---")

        col_btn_edit, col_msg_edit = st.columns([1, 2])
        with col_btn_edit:
            st.button("💾 SALVAR ALTERAÇÕES", on_click=salvar_alteracoes, use_container_width=True, type="primary")
        with col_msg_edit:
            if st.session_state.get("notification"):
                msg_type, msg_text = st.session_state.notification
                if msg_type == "success": st.success(msg_text)
                else: st.error(msg_text)
                del st.session_state.notification

# =============================================================================
# OUTRAS PÁGINAS
# =============================================================================
elif st.session_state.pagina_atual in ["Em Operação", "Finalizadas"]:
    botao_voltar()
    df = carregar_dataframe(worksheet)

    if st.session_state.pagina_atual == "Em Operação":
        st.markdown("### 📊 Registros em Operação")
        subset_df = df[df["Saída CD"] == ''].copy()
        st.dataframe(subset_df)

    elif st.session_state.pagina_atual == "Finalizadas":
        st.markdown("### ✅ Registros Finalizados")
        subset_df = df[df["Saída CD"] != ''].copy()
        st.dataframe(subset_df)
