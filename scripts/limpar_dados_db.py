# scripts/limpar_dados_db.py
import sqlite3
from unidecode import unidecode

NOME_BANCO_DE_DADOS = "agendha.db"
NOME_TABELA = "beneficiarios"
COLUNA_ALVO = "municipio"


def padronizar_texto(texto):
    """Converte texto para maiúsculas, remove espaços e acentos."""
    if not isinstance(texto, str):
        return texto
    texto_sem_acento = unidecode(texto)
    return texto_sem_acento.upper().strip()


def limpar_coluna_municipio():
    """Padroniza todos os valores na coluna de municípios."""
    conexao = None
    try:
        conexao = sqlite3.connect(NOME_BANCO_DE_DADOS)
        cursor = conexao.cursor()

        print("Buscando nomes de municípios únicos para limpar...")
        cursor.execute(f"SELECT DISTINCT {COLUNA_ALVO} FROM {NOME_TABELA}")
        municipios_unicos = [row[0] for row in cursor.fetchall()]

        print("Iniciando a limpeza dos dados. Alterações:")
        alteracoes_feitas = 0
        for original in municipios_unicos:
            if not original:
                continue

            limpo = padronizar_texto(original)

            if original != limpo:
                print(f"- De '{original}' para '{limpo}'")
                cursor.execute(
                    f"UPDATE {NOME_TABELA} SET {COLUNA_ALVO} = ? WHERE {COLUNA_ALVO} = ?",
                    (limpo, original)
                )
                alteracoes_feitas += 1

        conexao.commit()
        print(
            f"\n✅ Limpeza de dados concluída! {alteracoes_feitas} registros"
            " de municípios foram padronizados."
        )

    except sqlite3.Error as e:
        print(f"❌ ERRO ao limpar o banco de dados: {e}")
    finally:
        if conexao:
            conexao.close()
            print("Conexão com o banco de dados fechada.")


if __name__ == "__main__":
    # CORREÇÃO: Chamando a função com o nome correto
    limpar_coluna_municipio()
