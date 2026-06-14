from datetime import datetime, timedelta
from pathlib import Path
import os
import pandas as pd
from sqlalchemy import create_engine
import oracledb
from dotenv import load_dotenv

BASE_DIR = Path(r'\\10.1.1.202\c\rpa\Python\sql_visitas_ai_agent')
load_dotenv(BASE_DIR / '.env')  

def obter_mes_para_consulta():
    # Obter a data atual
    data_atual = datetime.now()
    
    # Verificar se hoje é o primeiro dia do mês
    if data_atual.day == 1:
        # Se for o primeiro dia, retorna o mês anterior
        mes_anterior = data_atual.replace(day=1) - timedelta(days=1)
        return mes_anterior.strftime('%Y-%m')
    else:
        # Caso contrário, retorna o mês atual
        return data_atual.strftime('%Y-%m-01')
def connection_postgres(database):
    # Lê variáveis de ambiente
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASS")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    # Cria e retorna o engine
    return create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
def conectar_oracle():
    uid = "guilhermeclaumann"
    pwd = "COMPANY_NAME"
    db  = "10.1.1.20/pdb1"
    connection = oracledb.connect(uid + "/" + pwd + "@" + db)
    return connection

mesAtual = obter_mes_para_consulta()
connection_oracle = conectar_oracle()
with open(r'C:\rpa\Python\sql_visitas_ai_agent\visitas.sql', "r", encoding="utf-8") as f:
    query_visita = f.read().strip()
    df_visitas = pd.read_sql(query_visita, con=connection_oracle)
    df_visitas.columns = df_visitas.columns.str.lower()
    df_visitas['cd_cliente'] = df_visitas['cd_cliente'].astype('str')
    connection_oracle.close()


# Faturamento
conexao_postgres = connection_postgres('projeto_ia_tornis')
with open(r'C:\rpa\Python\sql_visitas_ai_agent\faturamento.sql', "r", encoding="utf-8") as f:
    params = {"mes_atual": mesAtual}     
    query_faturamento = f.read().strip()
    df_faturamento = pd.read_sql(query_faturamento, con=conexao_postgres, params=params)
    df_faturamento['cd_cliente'] = df_faturamento['cd_cliente'].astype('str')

# Prazo
conexao_postgres = connection_postgres('dw_fluxo_caixa')
with open(r'C:\rpa\Python\sql_visitas_ai_agent\prazo_medio.sql', "r", encoding="utf-8") as f:
    params = {"mes_atual": mesAtual}             
    query_prazo = f.read().strip()  
    df_prazo_medio = pd.read_sql(query_prazo, con=conexao_postgres, params=params)
    df_prazo_medio['cd_cliente'] = df_prazo_medio['cd_cliente'].astype('str')

# Inadimplencia
with open(r'C:\rpa\Python\sql_visitas_ai_agent\inadimplencia.sql', "r", encoding="utf-8") as f:
    query_inadimplencia = f.read().strip()
    params = {"mes_atual": mesAtual}   
    df_inadimplencia = pd.read_sql(query_inadimplencia, con=conexao_postgres ,params=params)
    df_inadimplencia['cd_cliente'] = df_inadimplencia['cd_cliente'].astype('str')

# Merge dos DataFrames
df_final = (
    df_visitas
    .merge(df_faturamento,   on="cd_cliente", how="left", suffixes=("", "_fat"))
    .merge(df_prazo_medio,   on="cd_cliente", how="left", suffixes=("", "_prazo"))
    .merge(df_inadimplencia, on="cd_cliente", how="left", suffixes=("", "_inad"))
)


engine_postgres = connection_postgres('projeto_ia_tornis')
# Especifica o esquema ao inserir os dados
df_final.to_sql('resumo_visitas', con=engine_postgres, schema='public', if_exists='replace', index=False)