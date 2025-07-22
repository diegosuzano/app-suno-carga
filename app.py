import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÕES GERAIS ---
NOME_PLANILHA = "Controle de Carga Suzano"
FUSO_HORARIO = timezone(timedelta(hours=-3))

# Campos na ordem correta de acontecimento
campos_tempo = [
    "Entrada na Fábrica",
    "Encostou na doca Fábrica",
    "Início carregamento",
    "Fim carregamento",
    "Faturado",
    "Amarração carga",
    "Saída do pátio",
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

if 'rerun_needed' not in st.session_state:
    st.session_state.rerun_needed = False

if 'notification' not in st.session_state:
    st.session_state.notification = None

# --- CONFIGURAÇÃO DA PÁGINA E CSS PERSONALIZADO ---
st.set_page_config(
    page_title="Suzano - Controle de Carga",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Fundo suave */
    .main { background-color: #f8fafc; }

    /* Cabeçalho principal */
    .main-header {
        text-align: center;
        color: #1e40af;
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 20px;
        padding: 25px;
        background: linear-gradient(90deg, #dbeafe 0%, #eff6ff 100%);
        border-radius: 16px;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }

    /* Seções */
    .section-header {
        color: #1e3a8a;
        font-size: 24px;
        font-weight: 700;
        margin: 30px 0 15px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #bfdbfe;
    }

    /* Cards métricas */
    .stMetric {
        background-color: white;
        border: 1px solid #e0e7ff;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        transition: transform 0.2s ease;
    }
    .stMetric:hover { transform: translateY(-2px); }

    /* Botões principais */
    .main-button {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 10px;
        font-size: 18px;
        font-weight: 600;
        height: 60px;
        border-radius: 12px;
        border: none;
        background: linear-gradient(90deg, #3b82f6, #60a5fa);
        color: white;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
        transition: all 0.3s ease;
    }
    .main-button:hover {
        background: linear-gradient(90deg, #2563eb, #3b82f6);
        transform: scale(1.02);
        box-shadow: 0 6px 15px rgba(59, 130, 246, 0.4);
    }

    /* Botão de registro */
    .btn-registro {
        background: #f1f5f9;
        border: 1px dashed #94a3b8;
        color: #475569;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .btn-registro:hover {
        background: #e2e8f0;
        border-color: #64748b;
        color: #1e293b;
    }

    /* Status tags */
    .status-pendente { color: #94a3b8; background-color: #f1f5f9; padding: 4px 10px; border-radius: 20px; font-size: 13px; }
    .status-concluido { color: #047857; background-color: #d1fae5; padding: 4px 10px; border-radius: 20px; font-size: 13px; }
    .status-atual { color: #7c2d12; background-color: #fef3c7; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: 600; }

    /* Linha do tempo */
    .timeline {
        position: relative;
        margin: 20px 0;
        padding-left: 30px;
        border-left: 2px solid #bfdbfe;
    }
    .timeline-item {
        position: relative;
        margin-bottom: 20px;
    }
    .timeline-dot {
        position: absolute;
        left: -33px;
        top: 5px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #cbd5e1;
    }
    .timeline-dot.ativo { background: #10b981; }
    .timeline-dot.atual { background: #f59e0b; }

    /* Campo concluído */
    .campo-concluido {
        font-weight: 600;
        color: #059669;
    }
    .campo-pendente {
        color: #64748b;
    }

    /* Notificação flutuante */
    .floating-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        animation: slideIn 0.5s ease;
    }
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
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
        st.error(f"❌ Erro de conexão com o Google Sheets: {e}")
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
        st.error(f"❌ Erro ao ler dados da planilha: {e}")
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
        chaves_para_manter = ["pagina_atual", "rerun_needed"]
        for key in list(st.session_state.keys()):
            if key not in chaves_para_manter:
                del st.session_state[key]
        st.rerun()

# Conecta à planilha
worksheet = connect_to_google_sheets()

# Título principal
st.markdown("<div class='main-header'>🚚 SUZANO - CONTROLE DE CARGA INTELIGENTE</div>", unsafe_allow_html=True)

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
        st.markdown("""
        <button class="main-button">🆕 NOVO REGISTRO</button>
        """, unsafe_allow_html=True)
        if st.button("Trigger Novo Registro"):
            st.session_state.pagina_atual = "Novo"
            st.rerun()

    with col1:
        st.markdown("""
        <button class="main-button">✏️ EDITAR REGISTRO</button>
        """, unsafe_allow_html=True)
        if st.button("Trigger Editar Registro"):
            st.session_state.pagina_atual = "Editar"
            st.rerun()

    with col2:
        st.markdown("""
        <button class="main-button">📊 EM OPERAÇÃO</button>
        """, unsafe_allow_html=True)
        if st.button("Trigger Em Operação"):
            st.session_state.pagina_atual = "Em Operação"
            st.rerun()

    with col2:
        st.markdown("""
        <button class="main-button">✅ FINALIZADAS</button>
        """, unsafe_allow_html=True)
        if st.button("Trigger Finalizadas"):
            st.session_state.pagina_atual = "Finalizadas"
            st.rerun()

    df = carregar_dataframe(worksheet)
    st.markdown("<div class='section-header'>📊 SITUAÇÃO GERAL</div>", unsafe_allow_html=True)

    if not df.empty:
        em_operacao_df = df[df["Saída CD"] == ""].copy()
        m1, m2, m3 = st.columns(3)

        m1.metric(label="🚛 Em Operação", value=len(em_operacao_df))
        m2.metric(label="🏭 Na Fábrica", value=len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))
        m3.metric(label="📦 No CD / Em Rota", value=len(em_operacao_df) - len(em_operacao_df[em_operacao_df["Saída do pátio"] == ""]))

        with st.expander("🔍 Detalhes dos Veículos em Operação"):
            if em_operacao_df.empty:
                st.info("Nenhum veículo em operação.")
            else:
                for _, row in em_operacao_df.iterrows():
                    st.markdown(f"""
                    <div style="padding: 10px; background: #f8fafc; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #3b82f6;">
                        <b>Placa:</b> `{row['Placa do caminhão']}` | 
                        <b>Conferente:</b> {row['Nome do conferente']} | 
                        <span class='status-atual'>▶️ {obter_status(row)}</span>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("<div class='section-header'>📈 INDICADORES DO DIA</div>", unsafe_allow_html=True)
    if not df.empty:
        hoje_str = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
        df_hoje = df[pd.to_datetime(df["Data"], errors='coerce').dt.strftime("%Y-%m-%d") == hoje_str].copy()
        if df_hoje.empty:
            st.info("Nenhum registro hoje para análise.")
        else:
            def hhmm_para_minutos(t): return int(t.split(":")[0]) * 60 + int(t.split(":")[1]) if isinstance(t, str) and ":" in t else np.nan
            def media_formatada(s): m = s.apply(hhmm_para_minutos).mean(); return f"{int(m//60):02d}:{int(m%60):02d}" if not pd.isna(m) else "—"

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🏭 Fábrica")
                st.metric("⏳ Espera na Doca", media_formatada(df_hoje["Tempo Espera Doca"]))
                st.metric("📦 Carregamento", media_formatada(df_hoje["Tempo de Carregamento"]))
            with c2:
                st.subheader("📦 Centro de Distribuição")
                st.metric("🚗 Percurso até CD", media_formatada(df_hoje["Tempo Percurso Para CD"]))
                st.metric("📤 Descarregamento", media_formatada(df_hoje["Tempo de Descarregamento CD"]))

# =============================================================================
# PÁGINA DE NOVO REGISTRO
# =============================================================================
elif st.session_state.pagina_atual == "Novo":
    botao_voltar()
    st.markdown("### 🆕 NOVO REGISTRO DE CARGA")

    if 'novo_registro_dict' not in st.session_state:
        st.session_state.novo_registro_dict = {}

    reg = st.session_state.novo_registro_dict

    col1, col2 = st.columns(2)
    with col1:
        reg["Placa do caminhão"] = st.text_input("🚛 Placa do Caminhão", reg.get("Placa do caminhão", ""), placeholder="Ex: ABC1D23").upper().strip()
    with col2:
        reg["Nome do conferente"] = st.text_input("👤 Nome do Conferente", reg.get("Nome do conferente", ""), placeholder="Digite o nome completo")

    st.markdown("---")

    st.markdown("### ⏳ ETAPAS DA OPERAÇÃO")
    st.markdown('<div class="timeline">', unsafe_allow_html=True)

    for i, campo in enumerate(campos_tempo):
        valor_atual = reg.get(campo, "").strip()
        st.markdown('<div class="timeline-item">', unsafe_allow_html=True)

        # Status do ponto
        if not valor_atual:
            st.markdown('<span class="timeline-dot"></span>', unsafe_allow_html=True)
            st.markdown(f'<span class="campo-pendente">⚪ {campo}</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="timeline-dot ativo"></span>', unsafe_allow_html=True)
            st.markdown(f'<span class="campo-concluido">✅ {campo}: <code>{valor_atual}</code></span>', unsafe_allow_html=True)

        # Botão de registro
        if not valor_atual:
            if st.button("⏰ Registrar Agora", key=f"btn_novo_{campo}", use_container_width=True):
                # Confirmação modal
                st.session_state.confirm_action = ("registrar_novo", campo)
                st.session_state.rerun_needed = True

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Botão de salvar
    if st.button("💾 FINALIZAR E SALVAR REGISTRO", type="primary", use_container_width=True, disabled=len([k for k in ["Placa do caminhão", "Nome do conferente"] if not reg.get(k)]) > 0):
        reg["Data"] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
        reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
        reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
        reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
        reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
        reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
        reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
        reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))

        try:
            worksheet.append_row([reg.get(col, "") or None for col in COLUNAS_ESPERADAS], value_input_option='USER_ENTERED')
            st.cache_data.clear()
            st.session_state.notification = ("success", "✅ Novo registro salvo com sucesso!")
            del st.session_state.novo_registro_dict
            st.rerun()
        except Exception as e:
            st.session_state.notification = ("error", f"❌ Falha ao salvar: {e}")

# =============================================================================
# CONFIRMAÇÃO MODAL (usada nas duas telas)
# =============================================================================
if hasattr(st.session_state, 'confirm_action') and st.session_state.confirm_action:
    tipo, campo = st.session_state.confirm_action
    placa = st.session_state.get('novo_registro_dict', {}).get('Placa do caminhão', '') or \
            st.session_state.get('registro_em_edicao', {}).get('Placa do caminhão', '')

    st.markdown(
        """
        <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                    width: 400px; background: white; padding: 20px; border-radius: 16px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2); z-index: 9999; border: 1px solid #e5e7eb;">
            <h3 style="margin-top: 0;">Confirmar Registro</h3>
            <p>Você deseja registrar <strong>agora</strong> o evento:</p>
            <div style="background: #f0fdf4; padding: 12px; border-radius: 8px; margin: 10px 0; font-family: monospace;">
                %s
            </div>
            <p><strong>Placa:</strong> %s</p>
            <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                <button id="cancel-btn" style="padding: 8px 16px; border: 1px solid #d1d5db; border-radius: 6px; background: white;">Cancelar</button>
                <button id="confirm-btn" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 6px;">Confirmar</button>
            </div>
        </div>
        <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9998;"></div>
        """ % (campo, placa),
        unsafe_allow_html=True
    )

    # JavaScript para capturar os cliques
    confirm_js = st_javascript("""
    document.getElementById("confirm-btn").onclick = () => {
        window.parent.postMessage({type: "streamlit:setComponentValue", value: true}, "*");
    };
    document.getElementById("cancel-btn").onclick = () => {
        window.parent.postMessage({type: "streamlit:setComponentValue", value: false}, "*");
    };
    """, key="confirm_modal")

    if confirm_js == True:
        tipo, campo = st.session_state.confirm_action
        if tipo == "registrar_novo":
            st.session_state.novo_registro_dict[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
        elif tipo == "registrar_edit":
            st.session_state.registro_em_edicao[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.confirm_action = None
        st.session_state.rerun_needed = True
    elif confirm_js == False:
        st.session_state.confirm_action = None
        st.session_state.rerun_needed = True

# =============================================================================
# PÁGINA DE EDIÇÃO (COM PROGRESSO VISUAL)
# =============================================================================
elif st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ EDITAR REGISTROS EM ANDAMENTO")

    df = carregar_dataframe(worksheet)
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!")
        st.stop()

    opcoes = {f"🚛 {row['Placa do caminhão']} | 📅 {row['Data']} | ▶️ {obter_status(row)}": idx for idx, row in incompletos.iterrows()}
    selecao = st.selectbox("Selecione um registro:", ["Selecione..."] + list(opcoes.keys()), key="select_registro_edicao")

    if selecao != "Selecione..." and selecao in opcoes:
        df_idx = opcoes[selecao]

        if "registro_em_edicao" not in st.session_state or st.session_state.df_idx_atual != df_idx:
            st.session_state.registro_em_edicao = df.loc[df_idx].to_dict()
            st.session_state.df_idx_atual = df_idx

        reg = st.session_state.registro_em_edicao

        st.markdown(f"### Placa: `{reg['Placa do caminhão']}` | Conferente: {reg['Nome do conferente']}")
        st.markdown("---")

        st.markdown("### 🔄 LINHA DO TEMPO DE EDIÇÃO")
        st.markdown('<div class="timeline">', unsafe_allow_html=True)

        for i, campo in enumerate(campos_tempo):
            valor_atual = reg.get(campo, "").strip()
            st.markdown('<div class="timeline-item">', unsafe_allow_html=True)

            if valor_atual:
                st.markdown('<span class="timeline-dot ativo"></span>', unsafe_allow_html=True)
                st.markdown(f'<span class="campo-concluido">✅ {campo}: <code>{valor_atual}</code></span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="timeline-dot"></span>', unsafe_allow_html=True)
                st.markdown(f'<span class="campo-pendente">⚪ {campo}</span>', unsafe_allow_html=True)

            if not valor_atual:
                if st.button("➕ Registrar Agora", key=f"btn_edit_{campo}", use_container_width=True):
                    st.session_state.confirm_action = ("registrar_edit", campo)
                    st.session_state.rerun_needed = True

            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Recalcular tempos se necessário
        if st.session_state.rerun_needed and 'confirm_action' not in st.session_state:
            reg["Tempo Espera Doca"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Encostou na doca Fábrica"))
            reg["Tempo de Carregamento"] = calcular_tempo(reg.get("Início carregamento"), reg.get("Fim carregamento"))
            reg["Tempo Total"] = calcular_tempo(reg.get("Entrada na Fábrica"), reg.get("Saída do pátio"))
            reg["Tempo Percurso Para CD"] = calcular_tempo(reg.get("Saída do pátio"), reg.get("Entrada CD"))
            reg["Tempo Espera Doca CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Encostou na doca CD"))
            reg["Tempo de Descarregamento CD"] = calcular_tempo(reg.get("Início Descarregamento CD"), reg.get("Fim Descarregamento CD"))
            reg["Tempo Total CD"] = calcular_tempo(reg.get("Entrada CD"), reg.get("Saída CD"))
            st.session_state.rerun_needed = False
            st.rerun()

        # Botão de salvar
        if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
            try:
                row_idx = reg["df_index"] + 2
                valores = [reg.get(col, "") or None for col in COLUNAS_ESPERADAS]
                worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.session_state.notification = ("success", "✅ Alterações salvas com sucesso!")
                del st.session_state.registro_em_edicao
                del st.session_state.df_idx_atual
                st.session_state.select_registro_edicao = "Selecione..."
                st.rerun()
            except Exception as e:
                st.session_state.notification = ("error", f"❌ Erro ao salvar: {e}")

# =============================================================================
# OUTRAS PÁGINAS
# =============================================================================
elif st.session_state.pagina_atual in ["Em Operação", "Finalizadas"]:
    botao_voltar()
    df = carregar_dataframe(worksheet)
    titulo = "### 📊 Registros em Operação" if st.session_state.pagina_atual == "Em Operação" else "### ✅ Registros Finalizados"
    filtro = df["Saída CD"] == "" if st.session_state.pagina_atual == "Em Operação" else df["Saída CD"] != ""
    subset_df = df[filtro].copy()

    st.markdown(titulo)
    if subset_df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        st.dataframe(subset_df, use_container_width=True, hide_index=True)

# Força rerun se necessário
if st.session_state.rerun_needed and 'confirm_action' not in st.session_state:
    st.session_state.rerun_needed = False
    st.rerun()
