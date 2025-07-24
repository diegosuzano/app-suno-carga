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
    cor_fundo = "#1
