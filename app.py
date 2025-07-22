import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# -------------------- CONFIGURAÇÃO --------------------
FUSO = pytz.timezone("America/Sao_Paulo")
PLANILHA = "Controle de Carga Suzano"

# Conexão Google Sheets
def conectar_planilha():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credenciais = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=escopos)
    cliente = gspread.authorize(credenciais)
    return cliente.open(PLANILHA).sheet1

worksheet = conectar_planilha()

# -------------------- CAMPOS --------------------
campos = [
    "Placa", "Conferente", "Entrada no pátio", "Encostou na doca Fábrica",
    "Início carregamento", "Fim carregamento", "Faturado", "Amarração carga", 
    "Saída do pátio", "Entrada CD", "Início Descarregamento CD", "Fim Descarregamento CD", "Saída CD"
]

# -------------------- FUNÇÕES --------------------
def carregar_dados():
    dados = worksheet.get_all_records()
    return dados

def salvar_novo_dado(dado):
    linha = [dado.get(campo, "") for campo in campos]
    worksheet.append_row(linha, value_input_option="USER_ENTERED")

def atualizar_linha(placa, campo, valor):
    linha = worksheet.find(placa).row
    header = worksheet.row_values(1)
    if campo in header:
        col = header.index(campo) + 1
        worksheet.update_cell(linha, col, valor)

def registrar_agora():
    return datetime.now(FUSO).strftime("%Y-%m-%d %H:%M:%S")

# -------------------- INTERFACE --------------------
st.set_page_config("Controle de Carga", layout="wide")
menu = st.sidebar.selectbox("Navegação", ["Início", "Novo Lançamento", "Editar Lançamentos"])

# -------------------- INÍCIO --------------------
if menu == "Início":
    st.title("📦 Controle de Carga - Suzano")
    dados = carregar_dados()
    df = pd.DataFrame(dados)
    st.subheader("Registros em Aberto")
    if df.empty or "Saída CD" not in df.columns:
        st.info("Nenhum registro disponível.")
    else:
        em_andamento = df[df["Saída CD"] == ""]
        st.dataframe(em_andamento)

# -------------------- NOVO REGISTRO --------------------
elif menu == "Novo Lançamento":
    st.title("🆕 Novo Lançamento de Carga")
    novo = {}
    novo["Placa"] = st.text_input("🚛 Placa do Caminhão")
    novo["Conferente"] = st.text_input("👤 Nome do Conferente")

    etapas = campos[2:-1]  # Ignora Placa/Conferente e 'Saída CD'
    st.subheader("Etapas do Processo:")

    for i, campo in enumerate(etapas):
        if novo.get(campo):
            st.success(f"✅ {campo}: {novo[campo]}")
        else:
            pode_exibir = True
            if i > 0:
                anterior = etapas[i - 1]
                if not novo.get(anterior):
                    pode_exibir = False

            if pode_exibir:
                if st.button(f"Registrar {campo}"):
                    novo[campo] = registrar_agora()
                    st.experimental_rerun()
            else:
                st.warning(f"Aguardando preenchimento de: {etapas[i - 1]}")

    if novo.get("Placa") and novo.get("Conferente"):
        if st.button("💾 Salvar Registro"):
            salvar_novo_dado(novo)
            st.success("Registro salvo com sucesso!")
            st.experimental_rerun()
    else:
        st.warning("Preencha a placa e o conferente para salvar.")

# -------------------- EDITAR REGISTROS --------------------
elif menu == "Editar Lançamentos":
    st.title("✏️ Editar Lançamentos")

    dados = carregar_dados()
    registros = [r for r in dados if not r.get("Saída CD")]

    if not registros:
        st.info("Nenhum registro em andamento.")
    else:
        placas = [r["Placa"] for r in registros if r.get("Placa")]
        placa = st.selectbox("Escolha uma placa:", placas)

        reg = next((r for r in registros if r["Placa"] == placa), None)

        if reg:
            st.subheader(f"Editando Placa: {placa}")
            etapas = campos[2:-1]

            for i, campo in enumerate(etapas):
                valor = reg.get(campo, "")

                if valor:
                    st.success(f"✅ {campo}: {valor}")
                else:
                    pode_exibir = True
                    if i > 0:
                        anterior = etapas[i - 1]
                        if not reg.get(anterior):
                            pode_exibir = False

                    if pode_exibir:
                        if st.button(f"Registrar {campo}", key=f"edit_{campo}"):
                            novo_valor = registrar_agora()
                            atualizar_linha(placa, campo, novo_valor)
                            st.success(f"{campo} atualizado.")
                            st.experimental_rerun()
                    else:
                        st.warning(f"Aguardando preenchimento de: {etapas[i - 1]}")
