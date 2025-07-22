import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÕES GERAIS ---
NOME_PLANILHA = "Controle de Carga Suzano"
FUSO_HORARIO = timezone(timedelta(hours=-3))

# ORDEM COMPLETA DOS EVENTOS (respeitando seu fluxo)
eventos_fabrica = [
    "Entrada na Balança Fábrica",
    "Saída balança Fábrica",
    "Entrada na Fábrica",
    "Encostou na doca Fábrica",
    "Início carregamento",
    "Fim carregamento",
    "Faturado",
    "Amarração carga",
    "Saída do pátio"
]

eventos_cd = [
    "Entrada na Balança CD",
    "Saída balança CD",
    "Entrada CD",
    "Encostou na doca CD",
    "Início Descarregamento CD",
    "Fim Descarregamento CD",
    "Saída CD"
]

campos_tempo = eventos_fabrica + eventos_cd

campos_calculados = [
    "Tempo Espera Doca",          # Fábrica: Entrada → Encostou
    "Tempo de Carregamento",      # Fábrica: Início → Fim
    "Tempo Total",                # Fábrica: Entrada → Saída do pátio
    "Tempo Percurso Para CD",     # Saída do pátio → Entrada CD
    "Tempo Espera Doca CD",       # CD: Entrada CD → Encostou CD
    "Tempo de Descarregamento CD", # CD: Início → Fim descarga
    "Tempo Total CD"              # CD: Entrada CD → Saída CD
]

COLUNAS_ESPERADAS = (
    ["Data", "Placa do caminhão", "Nome do conferente"] +
    campos_tempo +
    campos_calculados
)

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = "Tela Inicial"
if 'modo_escuro' not in st.session_state:
    st.session_state.modo_escuro = False

# --- CSS PERSONALIZADO (com modo escuro) ---
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
        .etapa-pendente {{ color: #6b7280; }}
        .etapa-bloqueada {{ color: #9ca3af; opacity: 0.6; }}
        .btn-registro {{
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px;
            font-weight: 500;
        }}
        .btn-registro:disabled {{
            background: #9ca3af;
            color: #ffffff;
        }}
    </style>
    """, unsafe_allow_html=True)

aplicar_estilo()

# --- BOTÃO DE MODO ESCURO ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🌙" if st.session_state.modo_escuro else "🌞", key="btn_modo"):
        st.session_state.modo_escuro = not st.session_state.modo_escuro
        st.rerun()

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def connect_to_google_sheets():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets ",
            "https://www.googleapis.com/auth/drive "
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

def obter_status(registro):
    for campo in reversed(campos_tempo):
        valor = registro.get(campo, "").strip()
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
        operacao = df[df["Saída CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)
        m1.metric("🚛 Em Operação", len(operacao))
        m2.metric("🏭 Na Fábrica", len(operacao[operacao["Saída do pátio"] == ""]))
        m3.metric("📦 No CD / Rota", len(operacao) - len(operacao[operacao["Saída do pátio"] == ""]))

# =============================================================================
# NOVO REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 NOVO REGISTRO")
    if 'novo_registro' not in st.session_state:
        st.session_state.novo_registro = {"Data": datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")}

    reg = st.session_state.novo_registro
    reg["Placa do caminhão"] = st.text_input("🚛 Placa", reg.get("Placa do caminhão", ""))
    reg["Nome do conferente"] = st.text_input("👤 Conferente", reg.get("Nome do conferente", ""))

    st.markdown("---")
    st.markdown("### ⏳ ETAPAS DA OPERAÇÃO")

    for i, campo in enumerate(campos_tempo):
        valor_atual = reg.get(campo, "").strip()
        ha_anterior = i > 0
        anterior_preenchida = ha_anterior and bool(reg.get(campos_tempo[i-1], "").strip())

        if valor_atual and valor_atual not in ["00:00", "00", "0"]:
            st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor_atual}`</span>", unsafe_allow_html=True)
        else:
            if i == 0 or anterior_preenchida:
                if st.button(f"⏰ Registrar {campo}", key=f"btn_{campo}_{i}", use_container_width=True):
                    reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        worksheet.append_row([reg.get(col, "") or None for col in COLUNAS_ESPERADAS], value_input_option='USER_ENTERED')
                        st.cache_data.clear()
                        st.success(f"✅ {campo} registrado e salvo!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Falha ao salvar: {e}")
            else:
                st.markdown(f"<span class='etapa-bloqueada'>🔴 {campo} (aguarde etapa anterior)</span>", unsafe_allow_html=True)

# =============================================================================
# EDITAR REGISTRO (CORRIGIDO)
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS")
    df = carregar_dados()
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.info("✅ Não há registros em andamento para editar.")
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

        # Reinicializa o estado do editor apenas se mudar de caminhão
        if "registro_edit" not in st.session_state or st.session_state.idx_edit != idx:
            st.session_state.registro_edit = df.loc[idx].to_dict()
            st.session_state.idx_edit = idx

        reg = st.session_state.registro_edit

        st.markdown(f"**📅 Data:** `{reg['Data']}`")
        st.markdown(f"**🚛 Placa:** `{reg['Placa do caminhão']}`")
        st.markdown(f"**👤 Conferente:** `{reg['Nome do conferente']}`")
        st.markdown("---")
        st.markdown("### ⏳ ETAPAS DA OPERAÇÃO")

        for i, campo in enumerate(campos_tempo):
            valor_atual = reg.get(campo, "").strip()

            # Ignora valores inválidos
            valor_valido = valor_atual and valor_atual not in ["00:00", "00", "0"]

            if valor_valido:
                st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor_atual}`</span>", unsafe_allow_html=True)
            else:
                # Habilita apenas se for o primeiro ou o anterior estiver válido
                anterior_preenchido = True
                if i > 0:
                    anterior = reg.get(campos_tempo[i-1], "").strip()
                    anterior_preenchido = bool(anterior and anterior not in ["00:00", "00", "0"])

                if anterior_preenchido:
                    if st.button(f"⏰ Registrar {campo}", key=f"edit_btn_{idx}_{campo}"):
                        reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                        try:
                            row_idx = idx + 2
                            valores = [reg.get(col, "") or None for col in COLUNAS_ESPERADAS]
                            worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                            st.cache_data.clear()
                            st.success(f"✅ {campo} atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Falha ao salvar: {e}")
                else:
                    st.markdown(f"<span class='etapa-bloqueada'>🔴 {campo} (aguarde etapa anterior)</span>", unsafe_allow_html=True)

# =============================================================================
# VISUALIZAÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] == ""], use_container_width=True)

elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] != ""], use_container_width=True)
