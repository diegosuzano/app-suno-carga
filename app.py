import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
from google.oauth2.service_account import Credentials
import io

# --- CONFIGURAÇÕES GERAIS ---
NOME_PLANILHA = "Controle de Carga Suzano"
FUSO_HORARIO = timezone(timedelta(hours=-3))
HOJE = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")

# ORDEM DOS EVENTOS (exatamente como na sua planilha)
eventos_fabrica_entrada = [
    "Entrada na Balança Fábrica",
    "Entrada na Fábrica",
    "Encostou na doca Fábrica",
    "Início carregamento",
    "Fim carregamento",
    "Amarração carga",
    "Entrada na Balança sair Fábrica",
    "Saída balança sair Fábrica"
]
eventos_cd_entrada = [
    "Entrada na Balança CD",
    "Entrada CD",
    "Encostou na doca CD",
    "Início Descarregamento CD",
    "Fim Descarregamento CD",
    "Entrada na Balança Sair CD",
    "Saída balança Sair CD"
]

campos_calculados = [
    "Tempo de Carregamento",
    "Tempo Espera Doca",
    "Tempo Total",
    "Tempo de Descarregamento CD",
    "Tempo Espera Doca CD",
    "Tempo Total CD",
    "Tempo Percurso Para CD",
    "tempo balança fábrica",
    "tempo balança CD"
]

# ORDEM FINAL DAS COLUNAS (IGUAL À SUA PLANILHA)
COLUNAS_ESPERADAS = (
    ["Data", "Placa do caminhão", "Nome do conferente"] +
    eventos_fabrica_entrada +
    eventos_cd_entrada +
    campos_calculados
)

# --- INICIALIZAÇÃO DO ESTADO ---
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "Tela Inicial"
if 'modo_escuro' not in st.session_state:
    st.session_state.modo_escuro = False

# --- ESTILO (modo escuro) ---
def aplicar_estilo():
    cor_fundo = "#1e1e1e" if st.session_state.modo_escuro else "#f8fafc"
    cor_texto = "white" if st.session_state.modo_escuro else "#1f4e79"
    cor_card = "#2d2d2d" if st.session_state.modo_escuro else "white"
    borda_card = "#404040" if st.session_state.modo_escuro else "#e0e0e0"
    st.markdown(f"""
    <style>
        .main {{ background-color: {cor_fundo}; color: {cor_texto}; }}
        .main-header {{
            text-align: center;
            color: {cor_texto};
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 20px;
            padding: 20px;
            background: {'#2563eb' if st.session_state.modo_escuro else '#dbeafe'};
            border-radius: 12px;
            border-left: 6px solid #3b82f6;
        }}
        .section-header {{
            color: {cor_texto};
            font-size: 22px;
            font-weight: bold;
            margin: 25px 0 15px 0;
            padding-bottom: 5px;
            border-bottom: 2px solid #3b82f6;
        }}
        .stMetric {{
            background-color: {cor_card};
            border: 1px solid {borda_card};
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }}
        .etapa-concluida {{ color: #059669; }}
        .etapa-bloqueada {{ color: #9ca3af; opacity: 0.6; }}
    </style>
    """, unsafe_allow_html=True)
aplicar_estilo()

# --- BOTÃO MODO ESCURO ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🌙" if st.session_state.modo_escuro else "🌞", key="btn_modo"):
        st.session_state.modo_escuro = not st.session_state.modo_escuro
        st.rerun()

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
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
        return client.open(NOME_PLANILHA).sheet1
    except Exception as e:
        st.error(f"❌ Erro ao conectar: {e}")
        return None

worksheet = connect_to_google_sheets()
if not worksheet:
    st.stop()

# --- CARREGAR DADOS ---
@st.cache_data(ttl=30)
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

def calcular_tempos(reg):
    # Função auxiliar para verificar se o valor é válido
    def is_valid(value):
        return bool(value) and value not in ["00:00", "00", "0"]

    # Fábrica
    reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Encostou na doca Fábrica", ""), reg.get("Entrada na Fábrica", ""))
    reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Fim carregamento", ""), reg.get("Início carregamento", ""))

    # CD
    reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Encostou na doca CD", ""), reg.get("Entrada CD", ""))
    reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Fim Descarregamento CD", ""), reg.get("Início Descarregamento CD", ""))

    # Rota
    reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Entrada na Balança CD", ""), reg.get("Saída balança sair Fábrica", ""))

    # Tempo Balança Fábrica
    reg["tempo balança fábrica"] = calcular_tempo(reg.get("Entrada na Fábrica", ""), reg.get("Entrada na Balança Fábrica", ""))

    # Tempo Balança CD
    reg["tempo balança CD"] = calcular_tempo(reg.get("Entrada CD", ""), reg.get("Entrada na Balança CD", ""))

    # Tempo Total (só calcula se Saída balança Sair CD estiver preenchido)
    if is_valid(reg.get("Saída balança Sair CD", "")):
        reg["Tempo Total"] = calcular_tempo(reg.get("Saída balança Sair CD", ""), reg.get("Entrada na Balança Fábrica", ""))
        reg["Tempo Total CD"] = calcular_tempo(reg.get("Saída balança Sair CD", ""), reg.get("Entrada na Balança CD", ""))
    else:
        reg["Tempo Total"] = ""
        reg["Tempo Total CD"] = ""

def obter_status(registro):
    for campo in reversed(COLUNAS_ESPERADAS[3:]):
        valor = str(registro.get(campo, "")).strip()
        if valor and valor not in ["00:00", "00", "0"]:
            return campo
    return "Não iniciado"

def botao_voltar():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state.pagina_atual = "Tela Inicial"
        chaves_para_manter = ["pagina_atual", "modo_escuro"]
        for key in list(st.session_state.keys()):
            if key not in chaves_para_manter:
                del st.session_state[key]
        st.rerun()

# Função para converter DataFrame para Excel
def converter_para_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    buffer.seek(0)
    return buffer

# Título principal
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
        operacao = df[df["Saída balança Sair CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)
        m1.metric("🚛 Em Operação", len(operacao))
        m2.metric("🏭 Na Fábrica", len(operacao[operacao["Entrada na Balança sair Fábrica"] == ""]))
        m3.metric("📦 No CD / Rota", len(operacao) - len(operacao[operacao["Entrada na Balança sair Fábrica"] == ""]))

    # --- MÉDIAS DO DIA ---
    st.markdown("<div class='section-header'>📊 MÉDIAS DO DIA</div>", unsafe_allow_html=True)
    df_hoje = df[df["Data"] == HOJE].copy()
    if df_hoje.empty:
        st.info("⏳ Nenhum registro do dia ainda.")
    else:
        medias = {}
        for campo in campos_calculados:
            tempos = []
            for _, row in df_hoje.iterrows():
                valor = row[campo]
                if valor and valor != "Inválido" and ":" in valor:
                    try:
                        h, m = map(int, valor.split(":"))
                        minutos = h * 60 + m
                        tempos.append(minutos)
                    except:
                        continue
            if tempos:
                media_min = sum(tempos) / len(tempos)
                h, m = divmod(int(media_min), 60)
                medias[campo] = f"{h:02d}:{m:02d}"
            else:
                medias[campo] = "–"
        st.markdown("#### 🏭 TEMPOS NA FÁBRICA")
        col1, col2, col3 = st.columns(3)
        col1.metric("🕐 Tempo de Carregamento", medias["Tempo de Carregamento"])
        col2.metric("🚪 Tempo Espera Doca", medias["Tempo Espera Doca"])
        col3.metric("⏱️ Tempo Total", medias["Tempo Total"])
        st.markdown("#### 📦 TEMPOS NO CD")
        col4, col5, col6 = st.columns(3)
        col4.metric("📦 Tempo Descarregamento CD", medias["Tempo de Descarregamento CD"])
        col5.metric("🚪 Tempo Espera Doca CD", medias["Tempo Espera Doca CD"])
        col6.metric("⏱️ Tempo Total CD", medias["Tempo Total CD"])
        col7, _, _ = st.columns(3)
        col7.metric("🛣️ Tempo Percurso Para CD", medias["Tempo Percurso Para CD"])
        col8, col9 = st.columns(2)
        col8.metric("⚖️ Tempo Balança Fábrica", medias["tempo balança fábrica"])
        col9.metric("⚖️ Tempo Balança CD", medias["tempo balança CD"])

    # --- BAIXAR COMO EXCEL ---
    st.markdown("<div class='section-header'>📥 BAIXAR PLANILHA</div>", unsafe_allow_html=True)
    excel_data = converter_para_excel(df)
    st.download_button(
        label="📘 Baixar como Excel (.xlsx)",
        data=excel_data,
        file_name=f"controle_carga_suzano_{HOJE}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# =============================================================================
# NOVO REGISTRO (só permite o primeiro evento)
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 NOVO REGISTRO")
    if 'novo_registro' not in st.session_state:
        st.session_state.novo_registro = {col: "" for col in COLUNAS_ESPERADAS}
        st.session_state.novo_registro["Data"] = HOJE
    reg = st.session_state.novo_registro
    reg["Placa do caminhão"] = st.text_input("🚛 Placa", reg.get("Placa do caminhão", ""))
    reg["Nome do conferente"] = st.text_input("👤 Conferente", reg.get("Nome do conferente", ""))
    st.markdown("---")
    st.markdown("### ⏳ ETAPAS DA OPERAÇÃO")
    campo = "Entrada na Balança Fábrica"
    valor = str(reg.get(campo, "")).strip()
    if valor and valor not in ["00:00", "00", "0"]:
        st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor}`</span>", unsafe_allow_html=True)
    else:
        if st.button(f"⏰ Registrar {campo}", key=f"btn_{campo}", use_container_width=True):
            reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
            try:
                worksheet.append_row([reg.get(col, "") or None for col in COLUNAS_ESPERADAS], value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.success(f"✅ {campo} registrado! Edite para continuar.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falha ao salvar: {e}")
    st.info("ℹ️ Os demais eventos devem ser registrados no modo **Editar**.")

# =============================================================================
# EDITAR REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS")
    df = carregar_dados()
    incompletos = df[df["Saída balança Sair CD"] == ""].copy()
    if incompletos.empty:
        st.info("✅ Todos os caminhões estão finalizados.")
        st.stop()
    opcoes = {
        f"🚛 {r['Placa do caminhão']} | {obter_status(r)}": idx
        for idx, r in incompletos.iterrows()
    }
    selecao = st.selectbox("Selecione um caminhão:", ["Selecione..."] + list(opcoes.keys()))
    if selecao == "Selecione...":
        st.info("Selecione um caminhão acima para editar.")
    else:
        idx = opcoes[selecao]
        if "registro_edit" not in st.session_state or st.session_state.idx_edit != idx:
            st.session_state.registro_edit = df.loc[idx].to_dict()
            st.session_state.idx_edit = idx
        reg = st.session_state.registro_edit
        st.markdown(f"**📅 Data:** `{reg['Data']}`")
        st.markdown(f"**🚛 Placa:** `{reg['Placa do caminhão']}`")
        st.markdown(f"**👤 Conferente:** `{reg['Nome do conferente']}`")
        st.markdown("---")
        st.markdown("### ⏳ ETAPAS DA OPERAÇÃO")
        todos_eventos = (
            eventos_fabrica_entrada +
            eventos_cd_entrada
        )
        for i, campo in enumerate(todos_eventos):
            valor_atual = str(reg.get(campo, "")).strip()
            if valor_atual and valor_atual not in ["00:00", "00", "0"]:
                st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor_atual}`</span>", unsafe_allow_html=True)
            else:
                anterior_ok = (i == 0) or (
                    i > 0 and
                    str(reg.get(todos_eventos[i-1], "")).strip() and
                    reg.get(todos_eventos[i-1]) not in ["00:00", "00", "0"]
                )
                if anterior_ok:
                    if st.button(f"⏰ Registrar {campo}", key=f"edit_btn_{idx}_{campo}"):
                        reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                        calcular_tempos(reg)
                        try:
                            row_idx = idx + 2
                            valores = [reg.get(col, "") or None for col in COLUNAS_ESPERADAS]
                            worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                            st.cache_data.clear()
                            st.success(f"✅ {campo} atualizado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar: {e}")
                else:
                    st.markdown(f"<span class='etapa-bloqueada'>🔴 {campo} (aguarde etapa anterior)</span>", unsafe_allow_html=True)

# =============================================================================
# EM OPERAÇÃO (com nova visualização detalhada)
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    st.markdown("<div class='section-header'>🚛 OPERAÇÃO EM ANDAMENTO</div>", unsafe_allow_html=True)
    df = carregar_dados()
    df_op = df[df["Saída balança Sair CD"] == ""].copy()

    if df_op.empty:
        st.info("✅ Não há caminhões em operação no momento.")
    else:
        # Separar por local
        df_fabrica = df_op[df_op["Entrada na Balança sair Fábrica"] == ""]
        df_cd = df_op[df_op["Entrada na Balança sair Fábrica"] != ""]

        # Seção Fábrica
        st.markdown("### 🏭 OPERAÇÃO FÁBRICA")
        st.markdown(f"**🚛 Total: {len(df_fabrica)} caminhões em processo**")
        if not df_fabrica.empty:
            for _, row in df_fabrica.iterrows():
                status = obter_status(row)
                st.markdown(f"<span class='etapa-concluida'>🚛 `{row['Placa do caminhão']}` | {status}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='etapa-bloqueada'>Nenhum caminhão na fábrica.</span>", unsafe_allow_html=True)

        st.markdown("---")

        # Seção CD
        st.markdown("### 📦 OPERAÇÃO CD")
        st.markdown(f"**🚛 Total: {len(df_cd)} caminhões em processo**")
        if not df_cd.empty:
            for _, row in df_cd.iterrows():
                status = obter_status(row)
                st.markdown(f"<span class='etapa-concluida'>🚛 `{row['Placa do caminhão']}` | {status}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='etapa-bloqueada'>Nenhum caminhão no CD.</span>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🔍 DETALHES COMPLETOS")
        st.dataframe(df_op, use_container_width=True)

# =============================================================================
# FINALIZADAS
# =============================================================================
elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    st.markdown("### ✅ CAMINHÕES FINALIZADOS")
    df = carregar_dados()
    df_finalizados = df[df["Saída balança Sair CD"] != ""]
    if df_finalizados.empty:
        st.info("Ainda não há caminhões finalizados.")
    else:
        st.dataframe(df_finalizados, use_container_width=True)

# App desenvolvido com Diego de Oliveira - Controle de Carga Suzano
