import sqlite3
import os

# --- CONFIGURAÇÕES ---
NOME_BANCO_DE_DADOS = "agendha.db"

# --- LÓGICA DO SCRIPT ---

# 1. Conectar ao banco de dados (ele será criado se não existir)
# Usamos um bloco 'try...finally' para garantir
#  que a conexão seja sempre fechada.
try:
    print(f"Conectando ao banco de dados '{NOME_BANCO_DE_DADOS}'...")
    
    # Deleta o banco de dados antigo, se existir, 
    # para garantir um começo limpo.
    # CUIDADO: Isso apaga todos os dados existentes no arquivo .db!
    # É seguro para nós agora, pois estamos na fase de criação.
    if os.path.exists(NOME_BANCO_DE_DADOS):
        os.remove(NOME_BANCO_DE_DADOS)
        print("Banco de dados antigo removido.")

    conexao = sqlite3.connect(NOME_BANCO_DE_DADOS)
    cursor = conexao.cursor()
    print("Conexão bem-sucedida.")

    # 2. Definir o comando SQL para criar a tabela
    # Usamos """ para criar uma string de múltiplas
    #  linhas e facilitar a leitura.
    sql_criar_tabela = """
    CREATE TABLE IF NOT EXISTS beneficiarios (
        codigo INTEGER PRIMARY KEY,
        nome_tecnico TEXT,
        cpf_tecnico TEXT,
        municipio TEXT,
        comunidade TEXT,
        latitude REAL,
        longitude REAL,
        data_atividade TEXT,
        nome_familiar TEXT,
        cpf_familiar TEXT,
        nis TEXT,
        renda_media REAL,
        status TEXT,
        tecnico_agua_que_alimenta TEXT,
        doc_status TEXT,
        grh TEXT,
        verificado_bsf TEXT
    );
    """

    # 3. Executar o comando SQL
    print("Criando a tabela 'beneficiarios'...")
    cursor.execute(sql_criar_tabela)
    print("Tabela 'beneficiarios' criada com sucesso!")

    # 4. Salvar (commit) as alterações
    conexao.commit()

except sqlite3.Error as e:
    print(f"Ocorreu um erro ao interagir com o banco de dados: {e}")

finally:
    # 5. Fechar a conexão com o banco de dados
    if 'conexao' in locals() and conexao:
        conexao.close()
        print("Conexão com o banco de dados fechada.")