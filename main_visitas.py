from datetime import datetime, timedelta
import os
import pandas as pd
import oracledb
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent
load_dotenv()

def obter_mes_para_consulta():
    data_atual = datetime.now()

    if data_atual.day == 1:
        mes_anterior = data_atual.replace(day=1) - timedelta(days=1)
        return mes_anterior.strftime("%Y-%m")
    else:
        return data_atual.strftime("%Y-%m-01")
    


mesAtual = obter_mes_para_consulta()

def connection_postgres(database: str):
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASS")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")

    return create_engine(
        f"postgresql://{user}:{password}@{host}:{port}/{database}"
    )

def conectar_oracle():
    uid = "guilhermeclaumann"
    pwd = "COMPANY_NAME"
    db = "10.1.1.20/pdb1"
    return oracledb.connect(uid + "/" + pwd + "@" + db)

def read_sql_file(path_sql: str, con, params=None):
    with open(path_sql, "r", encoding="utf-8") as f:
        query = f.read().strip()
    return pd.read_sql(query, con=con, params=params)

def padroniza_cd_cliente(df: pd.DataFrame, col="cd_cliente"):
    df[col] = (
        pd.to_numeric(df[col], errors="coerce")
          .round(0)
          .astype("Int64")
    )
    return df

def corta_ultimo_digito_cd_cliente(df: pd.DataFrame, col="cd_cliente"):
    df = padroniza_cd_cliente(df, col)
    df[col] = (df[col] // 10).astype("Int64")
    return df

def gerar_chave_execucao():
    # Obtém a data e hora atual no formato compactado
    chave = datetime.now().strftime("%Y%m%d%H%M%S")
    return chave

connection_oracle = conectar_oracle()

# Df visitas
try:
    df_visitas = read_sql_file(rf"{PROJECT_ROOT}//visitas.sql", connection_oracle)
finally:
    connection_oracle.close()

df_visitas.columns = df_visitas.columns.str.lower()
df_visitas = padroniza_cd_cliente(df_visitas)

# Faturamento
con_fat = connection_postgres("projeto_ia_tornis")
df_faturamento = read_sql_file(rf"{PROJECT_ROOT}//faturamento.sql", con_fat)
df_faturamento = corta_ultimo_digito_cd_cliente(df_faturamento)
df_faturamento = padroniza_cd_cliente(df_faturamento)

# Prazo médio
con_dw = connection_postgres("dw_fluxo_caixa")
params = {"mes_atual": mesAtual}
df_prazo_medio = read_sql_file(rf"{PROJECT_ROOT}//prazo_medio.sql", con_dw, params=params)
df_prazo_medio = corta_ultimo_digito_cd_cliente(df_prazo_medio)

# Inadimplencia
df_inadimplencia = read_sql_file(rf"{PROJECT_ROOT}//inadimplencia.sql", con_dw, params=params)
df_inadimplencia = padroniza_cd_cliente(df_inadimplencia)


df_final = (
    df_visitas
      .merge(df_faturamento,   on="cd_cliente", how="left", suffixes=("", "_fat"))
      .merge(df_prazo_medio,   on="cd_cliente", how="left", suffixes=("", "_prazo"))
      .merge(df_inadimplencia, on="cd_cliente", how="left", suffixes=("", "_inad"))
)

con_out = connection_postgres("projeto_ia_tornis")

df_final['chave_execucao'] = gerar_chave_execucao()

df_final['cd_cliente'] = df_final['cd_cliente'].astype(str) + df_final['digito'].astype(str)

try:
    print(f"Gravando no banco...")
    df_final.to_sql(
        "resumo_visitas",
        con=con_out,
        schema="public",
        if_exists="replace",
        index=False
    )
    print(f"Gravação concluída com sucesso!")
except Exception as e:
    print(f"Erro ao gravar no banco: {e}")