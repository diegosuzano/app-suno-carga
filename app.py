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

def botao_voltar():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state.pagina_atual = "Tela Inicial"
        for key in list(st.session_state.keys()):
            if key not in ["pagina_atual"]: del st.session_state[key]
        st.rerun()

# --- CONEXÃO GOOGLE SHEETS ---
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def connect_to_google_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open(NOME_PLANILHA)
        return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Erro de conexão com o Google Sheets: {e}.")
        return None

@st.cache_data(ttl=30)
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

# --- INTERFACE EDITAR ---
worksheet = connect_to_google_sheets()

if st.session_state.pagina_atual == "Editar":
    botao_voltar()
    st.markdown("### ✏️ Editar Registros Incompletos")
    df = carregar_dataframe(worksheet)
    incompletos = df[df["Saída CD"] == ""].copy()

    if incompletos.empty:
        st.success("🎉 Todos os registros estão completos!"); st.stop()

    opcoes = {f"🚛 {row['Placa do caminhão']} | 📅 {row['Data']}": idx for idx, row in incompletos.iterrows()}

    def carregar_registro_para_edicao():
        selecao = st.session_state.selectbox_edicao
        if selecao != "Selecione...":
            df_idx = opcoes[selecao]
            st.session_state.registro_em_edicao = df.loc[df_idx].to_dict()
        elif "registro_em_edicao" in st.session_state:
            del st.session_state.registro_em_edicao

    st.selectbox("Selecione um registro:", ["Selecione..."] + list(opcoes.keys()), key="selectbox_edicao", on_change=carregar_registro_para_edicao)

    if "registro_em_edicao" in st.session_state:
        reg = st.session_state.registro_em_edicao
        st.markdown(f"#### Editando Placa: **{reg['Placa do caminhão']}**")

        def registrar_agora_edit(campo):
            st.session_state.registro_em_edicao[campo] = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.rerun_needed = True

        def salvar_alteracoes():
            with st.spinner("Salvando alterações..."):
                r = st.session_state.registro_em_edicao

                r["Tempo Espera Doca"] = calcular_tempo(r.get("Entrada na Fábrica"), r.get("Encostou na doca Fábrica"))
                r["Tempo de Carregamento"] = calcular_tempo(r.get("Início carregamento"), r.get("Fim carregamento"))
                r["Tempo Total"] = calcular_tempo(r.get("Entrada na Fábrica"), r.get("Saída do pátio"))
                r["Tempo Percurso Para CD"] = calcular_tempo(r.get("Saída do pátio"), r.get("Entrada CD"))
                r["Tempo Espera Doca CD"] = calcular_tempo(r.get("Entrada CD"), r.get("Encostou na doca CD"))
                r["Tempo de Descarregamento CD"] = calcular_tempo(r.get("Início Descarregamento CD"), r.get("Fim Descarregamento CD"))
                r["Tempo Total CD"] = calcular_tempo(r.get("Entrada CD"), r.get("Saída CD"))

                try:
                    row_idx = r["df_index"] + 2
                    valores = [r.get(col, "") if r.get(col, "") != "" else None for col in COLUNAS_ESPERADAS]
                    worksheet.update(f"A{row_idx}", [valores], value_input_option='USER_ENTERED')
                    st.cache_data.clear()
                    st.session_state.notification = ("success", "Registro atualizado com sucesso!")
                    del st.session_state.registro_em_edicao
                    st.session_state.selectbox_edicao = "Selecione..."
                    st.session_state.rerun_needed = True
                except Exception as e:
                    st.session_state.notification = ("error", f"Falha ao salvar: {e}")

        indice_campo = {campo: i for i, campo in enumerate(campos_tempo)}

        for i, campo in enumerate(campos_tempo):
            valor_atual = reg.get(campo, "")
            if valor_atual and str(valor_atual).strip():
                st.success(f"✅ {campo}: {valor_atual}")
            else:
                if i == 0 or (reg.get(campos_tempo[i - 1], "").strip() != ""):
                    st.button(f"Registrar {campo}", key=f"btn_edit_{campo}", on_click=registrar_agora_edit, args=(campo,), use_container_width=True)
                else:
                    st.warning(f"Aguardando preenchimento de: {campos_tempo[i - 1]}")

        st.markdown("---")
        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True, type="primary", on_click=salvar_alteracoes):
            pass

    if st.session_state.get("notification"):
        msg_type, msg_text = st.session_state.notification
        if msg_type == "success": st.success(msg_text)
        else: st.error(msg_text)
        del st.session_state.notification

    if st.session_state.rerun_needed:
        st.session_state.rerun_needed = False
        st.rerun()
