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

# ORDEM FINAL DAS COLUNAS (IGUAL À SUA PLANILHA)
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
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
        valor = str(registro.get(campo, "")).strip()
        if valor and valor not in ["00:00", "00", "0"]:
            return campo
    return "Não iniciado"

def obter_ultimo_evento_real(registro):
    for campo in reversed(campos_tempo):  # Itera nos eventos reais
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
        valor = reg.get(campo, "")
        anterior_preenchido = True if i == 0 else bool(reg.get(campos_tempo[i-1]))
        if valor:
            st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor}`</span>", unsafe_allow_html=True)
        elif anterior_preenchido:
            if st.button(f"⏰ Registrar {campo}", key=f"btn_{campo}", use_container_width=True):
                reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                # SALVAR NA PLANILHA IMEDIATAMENTE
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
                st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor}`</span>", unsafe_allow_html=True)
            else:
                if st.button(f"⏰ Registrar {campo}", key=f"edit_{campo}", use_container_width=True):
                    reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                    # ATUALIZAR LINHA NA PLANILHA
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
# EM OPERAÇÃO (versão visual)
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    st.markdown("<div class='section-header'>🚛 EM OPERAÇÃO</div>", unsafe_allow_html=True)
    df = carregar_dados()
    operacao = df[df["Saída CD"] == ""].copy()

    if operacao.empty:
        st.info("✅ Não há caminhões em operação.")
    else:
        # --- DASHBOARD: Fábrica e CD ---
        st.markdown("#### 🏭 OPERAÇÃO FÁBRICA")
        fabrica = operacao[operacao["Saída do pátio"] == ""].copy()
        if not fabrica.empty:
            for _, row in fabrica.iterrows():
                ultima_etapa = obter_ultimo_evento_real(row)
                horario = row[ultima_etapa] if ultima_etapa != "Não iniciado" else ""
                st.markdown(f"""
                <div style='background:#f0f8ff; padding:10px; border-radius:8px; margin:5px 0; border-left: 4px solid #3b82f6;'>
                    <b>🚛 {row['Placa do caminhão']}</b><br>
                    {ultima_etapa} — <span style='color:#059669'>{horario}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#9ca3af; font-style:italic;'>Nenhum caminhão na fábrica</div>", unsafe_allow_html=True)

        st.markdown("#### 📦 OPERAÇÃO CD")
        cd = operacao[operacao["Saída do pátio"] != ""].copy()
        if not cd.empty:
            for _, row in cd.iterrows():
                ultima_etapa = obter_ultimo_evento_real(row)
                horario = row[ultima_etapa] if ultima_etapa != "Não iniciado" else ""
                st.markdown(f"""
                <div style='background:#f0fff0; padding:10px; border-radius:8px; margin:5px 0; border-left: 4px solid #10b981;'>
                    <b>🚛 {row['Placa do caminhão']}</b><br>
                    {ultima_etapa} — <span style='color:#059669'>{horario}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#9ca3af; font-style:italic;'>Nenhum caminhão no CD</div>", unsafe_allow_html=True)

        # --- TABELA COMPLETA DO FLUXO ---
        st.markdown("#### 📋 FLUXO COMPLETO DOS CAMINHÕES")
        cols_exibidas = [
            "Placa do caminhão", "Entrada na Balança Fábrica", "Saída balança Fábrica",
            "Entrada na Fábrica", "Encostou na doca Fábrica", "Início carregamento",
            "Fim carregamento", "Saída do pátio", "Entrada na Balança sair Fábrica", "Saída balança sair Fábrica",
            "Entrada na Balança CD", "Saída balança CD", "Entrada CD", "Encostou na doca CD",
            "Início Descarregamento CD", "Fim Descarregamento CD", "Saída CD",
            "Entrada na Balança Sair CD", "Saída balança Sair CD"
        ]
        df_exibicao = operacao[cols_exibidas].copy()
        df_exibicao = df_exibicao.rename(columns={"Placa do caminhão": "Placa"})
        st.dataframe(df_exibicao, use_container_width=True)

# =============================================================================
# VISUALIZAÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] != ""], use_container_width=True)

# App desenvolvido com Diego de Oliveira - Controle de Carga Suzano
