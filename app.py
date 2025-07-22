import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# CONFIGURAÇÃO
FUSO = pytz.timezone("America/Sao_Paulo")
PLANILHA = "Controle de Carga Suzano"

# Autenticação Google Sheets
def conectar_planilha():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credenciais = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=escopos)
    cliente = gspread.authorize(credenciais)
    return cliente.open(PLANILHA).sheet1

worksheet = conectar_planilha()

# CAMPOS DA PLANILHA
campos = [
    "Placa", "Conferente", "Entrada no pátio", "Encostou na doca Fábrica",
    "Início carregamento", "Fim carregamento", "Faturado", "Amarração carga",
    "Saída do pátio", "Entrada CD", "Início Descarregamento CD", "Fim Descarregamento CD", "Saída CD"
]

# FUNÇÕES DE MANIPULAÇÃO
def registrar_agora():
    return datetime.now(FUSO).strftime("%Y-%m-%d %H:%M:%S")

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

# INTERFACE
st.set_page_config("Controle de Carga", layout="wide")
menu = st.sidebar.selectbox("Navegação", ["Início", "Novo Lançamento", "Editar Lançamentos", "Dashboard"])

# INÍCIO
if menu == "Início":
    st.title("📦 Controle de Carga - Início")
    dados = carregar_dados()
    df = pd.DataFrame(dados)
    st.subheader("Últimos registros")
    st.dataframe(df.tail(10))

# NOVO LANÇAMENTO
elif menu == "Novo Lançamento":
    st.title("🆕 Novo Lançamento de Carga")
    novo = {}
    novo["Placa"] = st.text_input("🚛 Placa do Caminhão")
    novo["Conferente"] = st.text_input("👤 Nome do Conferente")

    etapas = campos[2:-1]
    st.subheader("Etapas do Processo:")

    for i, campo in enumerate(etapas):
        if novo.get(campo):
            st.success(f"✅ {campo}: {novo[campo]}")
        else:
            pode_exibir = True
            if i > 0 and not novo.get(etapas[i - 1]):
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

# EDITAR LANÇAMENTOS
elif menu == "Editar Lançamentos":
    st.title("✏️ Editar Lançamentos em Andamento")
    dados = carregar_dados()
    registros = [r for r in dados if "Placa" in r and not r.get("Saída CD")]

    if not registros:
        st.info("Nenhum registro em andamento.")
    else:
        placas = [r["Placa"] for r in registros]
        placa = st.selectbox("Escolha uma placa:", placas)
        reg = next((r for r in registros if r.get("Placa") == placa), None)

        if reg:
            st.subheader(f"Etapas da Placa: {placa}")
            etapas = [
                "Entrada no pátio", "Encostou na doca Fábrica", "Início carregamento",
                "Fim carregamento", "Faturado", "Amarração carga", "Saída do pátio",
                "Entrada CD", "Início Descarregamento CD", "Fim Descarregamento CD"
            ]

            for i, campo in enumerate(etapas):
                valor = reg.get(campo, "")

                if valor:
                    st.success(f"✅ {campo}: {valor}")
                else:
                    pode_mostrar = True
                    if i > 0 and not reg.get(etapas[i - 1]):
                        pode_mostrar = False

                    if pode_mostrar:
                        if st.button(f"Registrar {campo}", key=f"edit_{campo}"):
                            novo_valor = registrar_agora()
                            atualizar_linha(placa, campo, novo_valor)
                            st.success(f"{campo} registrado.")
                            st.experimental_rerun()
                    else:
                        st.warning(f"Aguardando preenchimento de: {etapas[i - 1]}")

# DASHBOARD (mantenha sua lógica antiga aqui)
elif menu == "Dashboard":
    st.title("📊 Dashboard de Operações")
    dados = carregar_dados()
    df = pd.DataFrame(dados)

    if df.empty:
        st.warning("Sem dados para exibir.")
    else:
        st.dataframe(df)
        st.metric("Total de Cargas", len(df))
        em_andamento = df[df["Saída CD"] == ""]
        st.metric("Em Operação", len(em_andamento))
