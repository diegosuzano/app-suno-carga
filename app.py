import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÕES GERAIS ---
NOME_PLANILHA = "Controle de Carga Suzano"
FUSO_HORARIO = timezone(timedelta(hours=-3))  # Horário de Brasília

# ORDEM COMPLETA DOS EVENTOS
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
    "Tempo Espera Doca",          # Entrada na Fábrica → Encostou na doca Fábrica
    "Tempo de Carregamento",      # Início → Fim carregamento
    "Tempo Total",                # Entrada na Fábrica → Saída do pátio
    "Tempo Percurso Para CD",     # Saída do pátio → Entrada CD
    "Tempo Espera Doca CD",       # Entrada CD → Encostou na doca CD
    "Tempo de Descarregamento CD", # Início → Fim descarga CD
    "Tempo Total CD"              # Entrada CD → Saída CD
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
        if registro.get(campo) and str(registro.get(campo)).strip():
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
# NOVO REGISTRO (APENAS ENTRADA NA BALANÇA FÁBRICA)
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 NOVO REGISTRO - Entrada na Fábrica")

    if 'novo_registro_dict' not in st.session_state:
        st.session_state.novo_registro_dict = {"Data": datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")}

    reg = st.session_state.novo_registro_dict

    reg["Placa do caminhão"] = st.text_input("🚛 Placa do Caminhão", reg.get("Placa do caminhão", ""), key="placa_novo").upper().strip()
    reg["Nome do conferente"] = st.text_input("👤 Nome do Conferente", reg.get("Nome do conferente", ""), key="conferente_novo")

    st.markdown("---")
    
    # Único campo registrado aqui
    campo_inicio = "Entrada na Balança Fábrica"
    valor_atual = reg.get(campo_inicio, "")

    if valor_atual:
        st.success(f"✅ {campo_inicio}: `{valor_atual}`")
    else:
        if st.button(f"📌 Registrar {campo_inicio}", type="primary", use_container_width=True):
            reg[campo_inicio] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

    st.markdown("---")

    if st.button("💾 FINALIZAR E CRIAR REGISTRO", 
                 type="secondary", 
                 use_container_width=True,
                 disabled=not all(reg.get(k) for k in ["Placa do caminhão", "Nome do conferente", campo_inicio])):
        
        with st.spinner("Criando registro..."):
            # Preencher apenas os dados iniciais
            reg["Data"] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
            
            # Deixar todos os outros campos vazios
            for campo in campos_tempo + campos_calculados:
                if campo not in reg:
                    reg[campo] = ""
            
            try:
                worksheet.append_row([reg.get(col, "") or None for col in COLUNAS_ESPERADAS], value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.success("✅ Registro criado com sucesso! Agora você pode editar as próximas etapas.")
                
                del st.session_state.novo_registro_dict
                st.session_state.notification = ("success", "Registro inicial criado.")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Falha ao salvar: {e}")

# =============================================================================
# EDITAR REGISTRO (FORÇA ORDEM DOS EVENTOS)
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS EM ANDAMENTO")

    df = carregar_dados()
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!")
        st.stop()

    opcoes = {
        f"🚛 {row['Placa do caminhão']} | {obter_status(row)}": idx
        for idx, row in incompletos.iterrows()
    }

    selecao = st.selectbox("Selecione:", ["Selecione..."] + list(opcoes.keys()))

    if selecao != "Selecione..." and selecao in opcoes:
        idx = opcoes[selecao]
        if "registro_edit" not in st.session_state or st.session_state.idx_edit != idx:
            st.session_state.registro_edit = df.loc[idx].to_dict()
            st.session_state.idx_edit = idx

        reg = st.session_state.registro_edit
        st.markdown(f"**Placa:** `{reg['Placa do caminhão']}` | **Conferente:** {reg['Nome do conferente']}")
        st.markdown("---")

        # Força a ordem dos eventos
        for i, campo in enumerate(campos_tempo):
            valor = reg.get(campo, "")
            anterior_preenchido = True if i == 0 else bool(reg.get(campos_tempo[i-1]))

            if valor:
                st.markdown(f"<span class='etapa-concluida'>✅ {campo}: `{valor}`</span>", unsafe_allow_html=True)
            elif anterior_preenchido:
                if st.button(f"⏰ Registrar {campo}", key=f"edit_{campo}", use_container_width=True):
                    reg[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
                    # Atualiza cálculos automáticos
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
                        st.error(f"❌ Erro ao salvar: {e}")
            else:
                st.markdown(f"<span class='etapa-bloqueada'>🔴 {campo} (aguarde etapa anterior)</span>", unsafe_allow_html=True)

# =============================================================================
# VISUALIZAÇÃO
# =============================================================================
elif st.session_state.pagina_atual == "Em Operação":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] == ""], use_container_width=True, hide_index=True)

elif st.session_state.pagina_atual == "Finalizadas":
    botao_voltar()
    df = carregar_dados()
    st.dataframe(df[df["Saída CD"] != ""], use_container_width=True, hide_index=True)
