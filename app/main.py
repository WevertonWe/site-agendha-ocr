"""
Este módulo contém a lógica principal do aplicativo FastAPI "AguaqueAlimenta".
Gerencia uploads de múltiplos arquivos, processamento OCR paralelo, WebSockets,
histórico de usuários e prepara a integração com Selenium e Google Sheets.
"""

import os
import shutil
import uuid
import json
import datetime
import asyncio
import logging
import re
import sqlite3
from typing import List, Dict, Any

import pytesseract  # Importado aqui para configurar tesseract_cmd
from pdf2image import convert_from_path  # type: ignore
from PIL import Image
from pathlib import Path


# Imports para OpenCV
import cv2
import numpy as np

from fastapi import (
    FastAPI,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    Request,
    File,
)
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Configuração do FastAPI ---
app = FastAPI(
    title="Água que Alimenta API",
    description="API para processamento de documentos de beneficiários.",
    version="1.0.0"
)

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Constrói o caminho absoluto para a pasta 'app' onde este arquivo
# (main.py) está
BASE_DIR = Path(__file__).resolve().parent

# Monta os caminhos para as pastas 'static' e 'templates' usando o caminho base

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- Constantes e Configurações do Projeto ---
UPLOAD_FOLDER = "uploads"
PRINT_FOLDER = "prints_erros"
HISTORICO_PATH = "historico.json"


# ==============================================================================
#  IMPORTANTE: AJUSTE OS CAMINHOS DO POPPLER E TESSERACT ABAIXO
# ==============================================================================

POPPLER_PATH = (
    r"C:\Users\Weverton\Downloads\poppler-24.08.0\Library\bin"
)
pytesseract.pytesseract.tesseract_cmd = (
    r'C:\Program Files\Tesseract-OCR\tesseract.exe'
)
# ==============================================================================

FAVICON_PATH = os.path.join("static", "favicon.ico")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PRINT_FOLDER, exist_ok=True)

if not os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=4)

# ==============================================================================
# Informações sobre as Coordenadas das Páginas
# ==============================================================================
LARGURA_PADRAO = 1000

# Definições de ROI para a Página 1
# Estas coordenadas são baseadas na imagem após redimensionamento para
# LARGURA_PADRAO e, idealmente, após correção de perspectiva.
# As coordenadas x, y dos campos individuais são, por agora, relativas
# ao RETANGULO_PRINCIPAL (ou à imagem inteira corrigida se o retângulo
# principal for x=0, y=0, w=LARGURA_PADRAO, h=altura_dinamica).

# Coordenadas (X, Y, W, H) do retângulo principal de dados na Página 1.
# PROVISÓRIO: Ajustar APÓS a Etapa 2 (Correção de Perspectiva).
# Se (x=0, y=0, w=LARGURA_PADRAO, h=altura_dinamica_da_pagina),
# significa que usaremos a página inteira como área principal inicialmente.
# 'h' para RETANGULO_PRINCIPAL pode ser atualizado dinamicamente com base
# na altura da imagem redimensionada, ou você pode definir um valor fixo
# se o conteúdo principal tiver uma altura fixa e conhecida após correção.
RETANGULO_PRINCIPAL_PAG1_COORDS = {
    "x": 2, "y": 2, "w": 962, "h": 1017
}

ROI_DEFINICOES_PAGINA1 = {
    "nome_completo_l1": {
        "x": 190, "y": 52, "w": 760, "h": 39, "tipo": "texto"
    },
    "nome_completo_l2": {
        "x": 13, "y": 84, "w": 502, "h": 39, "tipo": "texto",
        "condicional": True
    },
    "sexo_cb_masc": {
        # Aguardando as novas coordenadas (x, y) do checkbox "Masc."
        "x": 0, "y": 0, "w": 22, "h": 22, "tipo": "checkbox",
        "campo_destino": "sexo", "valor_marcado": "Masculino"
    },
    "sexo_cb_fem": {
        # Aguardando as novas coordenadas (x, y) do checkbox "Fem."
        "x": 0, "y": 0, "w": 22, "h": 22, "tipo": "checkbox",
        "campo_destino": "sexo", "valor_marcado": "Feminino"
    }
    # Adicionaremos mais campos aqui conforme progredimos
}

# Estrutura para agrupar todas as definições de ROI por página
TODAS_ROIS_POR_PAGINA = {
    1: {  # Para a página 1
        "retangulo_principal": RETANGULO_PRINCIPAL_PAG1_COORDS,
        "campos": ROI_DEFINICOES_PAGINA1
    },
    # 2: { # Para a página 2, quando definirmos
    #     "retangulo_principal": RETANGULO_PRINCIPAL_PAG2_COORDS,
    #     "campos": ROI_DEFINICOES_PAGINA2
    # },
}
# --- Gerenciamento de Conexões WebSocket ---


class ConnectionManager:
    """Gerencia as conexões WebSocket ativas para comunicação em tempo real
    com os clientes."""

    def __init__(self):
        """Inicializa a lista de conexões ativas."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Aceita uma nova conexão WebSocket e a adiciona à lista de conexões
        ativas."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info("Nova conexão WebSocket estabelecida.")

    def disconnect(self, websocket: WebSocket):
        """Remove uma conexão WebSocket da lista de conexões ativas."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info("Conexão WebSocket fechada.")

    async def send_message(self, message: str, beneficiario_id: str = None):
        """Envia uma mensagem para todas as conexões WebSocket ativas,
        opcionalmente identificando o beneficiário."""
        log_msg_prefix = "WS Enviando"
        if beneficiario_id:
            message_to_send = f"[{beneficiario_id}] {message}"
            log_msg_prefix += f" para Beneficiário ID [{beneficiario_id}]"
        else:
            message_to_send = message

        logging.info("%s: %s", log_msg_prefix, message)

        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_to_send)
            except RuntimeError as e_runtime:
                logging.error(
                    "Erro de runtime ao enviar msg WS para %s: %s",
                    connection.client, e_runtime
                )
            except ConnectionError as e_conn:
                logging.error(
                    "Erro de conexão ao enviar msg WS para %s: %s",
                    connection.client, e_conn
                )
            except OSError as e_os:
                logging.error(
                    "Erro de sistema ao enviar msg WS para %s: %s",
                    connection.client, e_os
                )
            except Exception as e:  # pylint: disable=broad-except
                logging.error(
                    "Erro genérico inesperado ao enviar msg WS para %s: %s",
                    connection.client, e
                )


manager = ConnectionManager()

# --- Rotas HTML ---


# NOVA ROTA PRINCIPAL (/) PARA O DASHBOARD
@app.get("/", response_class=HTMLResponse, summary="Página do Dashboard Consolidado")
async def get_dashboard(request: Request):
    """Renderiza a página principal do dashboard (dashboard.html)."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


# NOVA ROTA (/dados-brutos) PARA A TABELA ANTIGA
@app.get("/dados-brutos", response_class=HTMLResponse, summary="Página da Tabela Completa")
async def get_tabela_completa(request: Request):
    """Renderiza a página da tabela completa de beneficiários (index.html)."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/mapa", response_class=HTMLResponse, summary="Página do Mapa")
async def get_mapa(request: Request):
    """Renderiza a página do mapa (mapa.html)."""
    return templates.TemplateResponse("mapa.html", {"request": request})


@app.get(
    "/processar",
    response_class=HTMLResponse,
    summary="Página de Processamento de Beneficiário"
)
async def get_processar_pagina(request: Request):
    """
    Renderiza a página de processamento de beneficiários (processar.html).
    """
    return templates.TemplateResponse("processar.html", {"request": request})

# --- Endpoint de API para os Dados ---


@app.get("/api/beneficiarios", response_class=JSONResponse)
def get_beneficiarios():
    """
    Busca todos os registros de beneficiários no banco de dados SQLite
    e os retorna como uma lista de dicionários (JSON).
    """
    db_path = "agendha.db"
    try:
        logging.info(
            "API: Conectando ao banco de dados para buscar beneficiários...")
        conexao = sqlite3.connect(db_path)
        # O Row_factory faz com que o resultado venha como dicionários,
        # o que é perfeito para converter para JSON.
        conexao.row_factory = sqlite3.Row
        cursor = conexao.cursor()

        # Executa a consulta para pegar todos os dados da tabela
        cursor.execute("SELECT * FROM beneficiarios")
        registros = cursor.fetchall()

        # Converte a lista de registros do banco em uma lista de dicionários
        # que pode ser enviada como JSON
        lista_beneficiarios = [dict(registro) for registro in registros]

        logging.info(
            "API: %d registros encontrados e enviados.", len(
                lista_beneficiarios)
        )
        return lista_beneficiarios

    except sqlite3.Error as e:
        logging.error(f"API: Erro ao acessar o banco de dados: {e}")
        # Retorna uma resposta de erro no formato JSON
        return JSONResponse(
            status_code=500,
            content={"error": "Erro interno ao buscar os dados."}
        )
    finally:
        if 'conexao' in locals() and conexao:
            conexao.close()
            logging.info(
                "API: %s registros encontrados e enviados.",
                len(lista_beneficiarios)
            )


@app.get("/api/consolidado/atividades", response_class=JSONResponse)
def get_consolidado_atividades():
    """
    Gera um resumo de atividades por município.
    Assume que os dados de município já estão padronizados no banco.
    """
    db_path = "agendha.db"
    conexao = None
    try:
        logging.info("API: Gerando dados consolidados (v3)...")
        conexao = sqlite3.connect(db_path)
        conexao.row_factory = sqlite3.Row
        cursor = conexao.cursor()

        # Consulta SQL agora muito mais simples!
        query = """
        SELECT
            municipio,
            COUNT(*) AS total_beneficiarios,
            SUM(CASE WHEN status = 'EM CADASTRO' THEN 1 ELSE 0 END) AS em_cadastro,
            SUM(CASE WHEN status = 'CADASTRADO' THEN 1 ELSE 0 END) AS cadastrado,
            SUM(CASE WHEN status = 'A CONSTRUIR' THEN 1 ELSE 0 END) AS a_construir,
            SUM(CASE WHEN status = 'CONSTRUÍDA' THEN 1 ELSE 0 END) AS construida,
            SUM(CASE WHEN status NOT IN (
                'EM CADASTRO', 'CADASTRADO', 'A CONSTRUIR', 'CONSTRUÍDA'
                ) OR status IS NULL THEN 1 ELSE 0 END) AS outros_status
        FROM
            beneficiarios
        WHERE
            municipio IS NOT NULL AND municipio != ''
        GROUP BY
            municipio
        ORDER BY
            municipio;
        """
        cursor.execute(query)
        registros = cursor.fetchall()
        dados_consolidados = [dict(registro) for registro in registros]

        logging.info("API: Dados consolidados (v3) gerados com sucesso.")
        return dados_consolidados
    except sqlite3.Error as e:
        logging.error(f"API: Erro ao gerar dados consolidados (v3): {e}")
        return JSONResponse(status_code=500, content={"error": "Erro interno."})
    finally:
        if conexao:
            conexao.close()
            logging.info("API: Conexão do consolidado (v3) fechada.")


# --- Endpoint para Favicon ---


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve o arquivo favicon.ico."""
    if os.path.exists(FAVICON_PATH):
        return FileResponse(
            FAVICON_PATH,
            media_type="image/vnd.microsoft.icon"
        )
    else:
        logging.warning("favicon.ico não encontrado em %s", FAVICON_PATH)
        return JSONResponse(
            content={"error": "Favicon not found"},
            status_code=404
        )

# FUNÇÕES

# -----------------------------------------------------------------------------
# ETAPA 1: FUNÇÕES AUXILIARES PARA CARREGAMENTO E PRÉ-PROCESSAMENTO BÁSICO
# -----------------------------------------------------------------------------

# Converte imagem PIL para OpenCV (BGR) e redimensiona à largura alvo.


def _converter_pil_para_cv_e_redimensionar(
    imagem_pil: Image.Image, largura_alvo: int
) -> np.ndarray:

    # Converter PIL Image para OpenCV array (RGB)
    img_cv_rgb = np.array(imagem_pil.convert('RGB'))
    # Converter RGB para BGR (formato padrão do OpenCV)
    img_cv_bgr = cv2.cvtColor(img_cv_rgb, cv2.COLOR_RGB2BGR)

    altura_original, largura_original = img_cv_bgr.shape[:2]
    if largura_original == 0:
        logging.error("Largura original da imagem é 0. Imagem inválida.")
        raise ValueError("Imagem com largura original zero.")

    proporcao = largura_alvo / float(largura_original)
    altura_alvo = int(altura_original * proporcao)

    img_redimensionada = cv2.resize(
        img_cv_bgr, (largura_alvo, altura_alvo),
        interpolation=cv2.INTER_AREA  # Bom para reduzir, ok para aumentar
    )
    logging.info(
        f"Imagem redimensionada de {largura_original}x{altura_original} "
        f"para {largura_alvo}x{altura_alvo}"
    )
    return img_redimensionada


# Endireita uma imagem de formulário que possa estar em perspectiva.
def _corrigir_perspectiva(imagem_cv_bgr: np.ndarray) -> np.ndarray:
    # Para o processamento, uma cópia da imagem é usada
    imagem_processo = imagem_cv_bgr.copy()

    # Converte para escala de cinza, aplica desfoque e detecta bordas
    cinza = cv2.cvtColor(imagem_processo, cv2.COLOR_BGR2GRAY)
    desfoque = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(desfoque, 75, 200)

    # Encontra os contornos na imagem
    contornos, _ = cv2.findContours(
        bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    # Ordena os contornos por área, do maior para o menor
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:5]

    contorno_tela = None

    # Itera sobre os maiores contornos para encontrar o formulário
    for c in contornos:
        # Aproxima o contorno para uma forma com menos vértices
        perimetro = cv2.arcLength(c, True)
        aprox = cv2.approxPolyDP(c, 0.02 * perimetro, True)

        # Se a forma aproximada tiver 4 vértices, assumimos que é o formulário
        if len(aprox) == 4:
            contorno_tela = aprox
            break

    # Se nenhum contorno de 4 pontos foi encontrado, retorna a imagem original
    if contorno_tela is None:
        logging.warning("Não foi possível encontrar contorno de 4 pontos. "
                        "A correção de perspectiva não será aplicada.")
        return imagem_cv_bgr

    # --- Ordena os 4 pontos do contorno para uma ordem consistente ---
    pontos = contorno_tela.reshape(4, 2)
    pontos_ret = np.zeros((4, 2), dtype="float32")

    soma = pontos.sum(axis=1)
    pontos_ret[0] = pontos[np.argmin(soma)]  # Canto superior esquerdo
    pontos_ret[2] = pontos[np.argmax(soma)]  # Canto inferior direito

    diff = np.diff(pontos, axis=1)
    pontos_ret[1] = pontos[np.argmin(diff)]  # Canto superior direito
    pontos_ret[3] = pontos[np.argmax(diff)]  # Canto inferior esquerdo
    # --- Fim da ordenação ---

    (sup_esq, sup_dir, inf_dir, inf_esq) = pontos_ret

    # Calcula a largura da nova imagem "plana"
    largura_a = np.sqrt(
        ((inf_dir[0] - inf_esq[0]) ** 2) + ((inf_dir[1] - inf_esq[1]) ** 2))
    largura_b = np.sqrt(
        ((sup_dir[0] - sup_esq[0]) ** 2) + ((sup_dir[1] - sup_esq[1]) ** 2))
    max_largura = max(int(largura_a), int(largura_b))

    # Calcula a altura da nova imagem "plana"
    altura_a = np.sqrt(
        ((sup_dir[0] - inf_dir[0]) ** 2) + ((sup_dir[1] - inf_dir[1]) ** 2))
    altura_b = np.sqrt(
        ((sup_esq[0] - inf_esq[0]) ** 2) + ((sup_esq[1] - inf_esq[1]) ** 2))
    max_altura = max(int(altura_a), int(altura_b))

    # Define os pontos de destino para a transformação
    dst = np.array([
        [0, 0],
        [max_largura - 1, 0],
        [max_largura - 1, max_altura - 1],
        [0, max_altura - 1]], dtype="float32")

    # Calcula a matriz de transformação de perspectiva e a aplica
    matriz_transformacao = cv2.getPerspectiveTransform(pontos_ret, dst)
    imagem_corrigida = cv2.warpPerspective(
        imagem_processo, matriz_transformacao, (max_largura, max_altura)
    )

    logging.info("Correção de perspectiva aplicada com sucesso.")
    return imagem_corrigida

# Aplica pré-processamento OpenCV (escala de cinza, binarização) em imagem
# OpenCV (BGR) já redimensionada.


async def _preprocessar_imagem_para_ocr(
    img_cv_redimensionada: np.ndarray,
    beneficiario_id: str,
    pagina_num: int = 0
) -> np.ndarray:

    try:
        logging.info(
            "[%s] Iniciando pré-processamento OpenCV para página/imagem "
            "(já redimensionada)...", beneficiario_id
        )

        img_cinza = cv2.cvtColor(img_cv_redimensionada, cv2.COLOR_BGR2GRAY)

        img_cinza_desfocada = cv2.GaussianBlur(img_cinza, (3, 3), 0)

        # Parâmetros de binarização que você está testando
        blockSize = 15
        C_val = 6

        logging.info(
            "[%s] Aplicando adaptiveThreshold: blockSize=%s, C=%s, "
            "ADAPTIVE_THRESH_MEAN_C", beneficiario_id, blockSize, C_val
        )

        img_binarizada = cv2.adaptiveThreshold(
            img_cinza_desfocada,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            blockSize,
            C_val
        )

        # Salvar imagem de depuração
        try:
            nome_base_debug = f"debug_opencv_b{blockSize}_C{C_val}_mean"
            if pagina_num > 0:
                nome_base_debug += f"_p{pagina_num}"

            debug_filename = (
                f"{nome_base_debug}_"
                f"{beneficiario_id}_"
                f"{uuid.uuid4().hex[:4]}.png"
            )
            debug_path = os.path.join(UPLOAD_FOLDER, debug_filename)
            cv2.imwrite(debug_path, img_binarizada)

            logging.info(
                "[%s] Imagem OpenCV pré-processada salva em: %s",
                beneficiario_id, debug_path
            )
            await manager.send_message(
                f"Imagem de depuração OpenCV salva: {debug_filename}",
                beneficiario_id
            )
        except Exception as e_save:  # pylint: disable=broad-except
            logging.error(
                "[%s] Erro ao salvar imagem OpenCV de depuração: %s",
                beneficiario_id, e_save
            )

        logging.info(
            "[%s] Pré-processamento OpenCV concluído.", beneficiario_id
        )
        return img_binarizada

    except Exception as e_cv:  # pylint: disable=broad-except
        logging.exception(
            "[%s] Erro crítico durante o pré-processamento com OpenCV: %s."
            " Retornando imagem original em escala de cinza (se possível).",
            beneficiario_id, e_cv
        )
        try:
            return cv2.cvtColor(img_cv_redimensionada, cv2.COLOR_BGR2GRAY)
        except Exception as e_fallback:
            logging.error(
                "[%s] Erro ao converter para cinza no fallback: %s",
                beneficiario_id, e_fallback
            )
            raise e_cv


# -----------------------------------------------------------------------------
# FUNÇÕES PRINCIPAIS DE ORQUESTRAÇÃO DO OCR E PROCESSAMENTO DE ARQUIVO
# (Esta função será modificada ao longo de várias etapas)
# -----------------------------------------------------------------------------

async def _executar_ocr_para_arquivo(
    file_path: str, original_filename: str, beneficiario_id: str
) -> Dict[str, Any]:
    """
    Prepara uma imagem para extração por ROI. O processo inclui
    redimensionamento, correção de perspectiva, recorte e pré-processamento.
    Esta função RETORNA A IMAGEM PROCESSADA, não o texto.
    """
    await manager.send_message(
        f"Preparando imagem do arquivo: {original_filename}...",
        beneficiario_id
    )
    logging.info(
        "[%s] Iniciando preparação de imagem para: %s",
        beneficiario_id, file_path
    )

    try:
        imagem_pil = None
        pagina_num = 1  # Assume página 1 para imagens e para o primeiro do PDF

        if file_path.lower().endswith('.pdf'):
            # Lógica para converter a primeira página do PDF em imagem PIL
            imagens_pil_pdf = await asyncio.to_thread(
                convert_from_path,
                file_path, poppler_path=POPPLER_PATH, dpi=300
            )
            if imagens_pil_pdf:
                imagem_pil = imagens_pil_pdf[0]
        elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Lógica para abrir um arquivo de imagem
            imagem_pil = await asyncio.to_thread(Image.open, file_path)

        if imagem_pil is None:
            logging.error(
                "Não foi possível carregar a imagem de %s", file_path)
            return {
                "error": "Não foi possível carregar a imagem do arquivo."
            }

        # --- Etapa 1: Redimensionamento ---
        img_redim = _converter_pil_para_cv_e_redimensionar(
            imagem_pil, LARGURA_PADRAO
        )
        # --- Etapa 2: Correção de Perspectiva ---
        img_corrigida = _corrigir_perspectiva(img_redim)

        # --- Etapa 3: Recorte para o Retângulo Principal de Dados ---
        imagem_base_para_processar = img_corrigida  # Valor padrão
        if pagina_num in TODAS_ROIS_POR_PAGINA:
            coords = TODAS_ROIS_POR_PAGINA[pagina_num]["retangulo_principal"]
            x, y, w, h = (coords["x"], coords["y"], coords["w"], coords["h"])

            if h == 0:
                h = img_corrigida.shape[0] - y
            if w == 0:
                w = img_corrigida.shape[1] - x

            imagem_base_para_processar = img_corrigida[y:y+h, x:x+w]
            logging.info(
                "Imagem da página %d recortada para a área de dados.",
                pagina_num
            )
        else:
            logging.warning(
                "ROI principal não definida para pág %d. Usando imagem "
                "inteira.",
                pagina_num
            )

        # Opcional: Salvar imagem de depuração do recorte
        try:
            path_debug = os.path.join(
                UPLOAD_FOLDER, f"debug_recorte_{beneficiario_id}.png")
            cv2.imwrite(path_debug, imagem_base_para_processar)
        except Exception as e:
            logging.error(
                "Erro ao salvar imagem de depuração do recorte: %s", e)

        # A função agora retorna um dicionário com a imagem pronta para a
        # extração por ROI
        logging.info("[%s] Preparação da imagem concluída.", beneficiario_id)
        return {"imagem_processada": imagem_base_para_processar}

    except Exception as e:
        error_msg = f"Erro crítico ao preparar imagem: {e!s}"
        logging.exception("[%s] %s", beneficiario_id, error_msg)
        await manager.send_message(error_msg, beneficiario_id)
        raise


def _limpar_valor_extraido(valor: str) -> str:
    """Remove espaços extras e quebras de linha de um valor extraído."""
    if valor:
        return ' '.join(valor.split()).strip()
    return ""


def _normalizar_data(data_str: str) -> str:
    """Tenta normalizar uma string de data para o formato DD/MM/YYYY."""
    if not data_str:
        return "Não encontrada"

    digitos_data = re.sub(r'\D', '', data_str)

    if len(digitos_data) == 8:  # DDMMYYYY
        return f"{digitos_data[0:2]}/{digitos_data[2:4]}/{digitos_data[4:8]}"
    return data_str

# -----------------------------------------------------------------------------
# ETAPA 4: FUNÇÕES AUXILIARES PARA EXTRAÇÃO BASEADA EM ROI
# -----------------------------------------------------------------------------

# Analisa a imagem de uma ROI de checkbox e retorna True se parecer marcada.


def _analisar_checkbox(roi_img_checkbox: np.ndarray) -> bool:
    """Analisa uma ROI de checkbox para determinar se está marcada.

    Converte a imagem para preto e branco e verifica a proporção de
    pixels não-brancos. Retorna True se a proporção exceder um limiar.
    """
    # Limiar experimental - percentual de pixels "escuros" para
    # considerar marcado
    LIMIAR_MARCACAO = 0.15  # 15%

    # Converte para escala de cinza e aplica limiar de Otsu
    # para criar uma imagem binária (preto e branco)
    cinza = cv2.cvtColor(roi_img_checkbox, cv2.COLOR_BGR2GRAY)
    _, binarizada = cv2.threshold(
        cinza, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # Conta os pixels brancos (que representam a marcação "X" ou preenchimento)
    pixels_marcados = cv2.countNonZero(binarizada)
    total_pixels = roi_img_checkbox.shape[0] * roi_img_checkbox.shape[1]

    if total_pixels == 0:
        return False

    proporcao_marcada = pixels_marcados / total_pixels

    return proporcao_marcada >= LIMIAR_MARCACAO


# Extrai dados de uma imagem processada usando um dicionário de ROIs.
async def _extrair_dados_roi(
    imagem_processada: np.ndarray,
    definicoes_rois: Dict[str, Any],
    beneficiario_id: str
) -> Dict[str, str]:

    dados_extraidos = {}

    # Processa campos de texto primeiro
    textos_nome = []
    for nome_campo, roi_info in definicoes_rois.items():
        if roi_info["tipo"] == "texto":
            x, y, w, h = (roi_info["x"], roi_info["y"],
                          roi_info["w"], roi_info["h"])

            # Recorta a ROI do campo de texto
            roi_texto_img = imagem_processada[y:y+h, x:x+w]

            # Pré-processamento específico para OCR na ROI
            # Usaremos as mesmas configurações do Teste 8B que foram boas
            img_para_ocr = await _preprocessar_imagem_para_ocr(
                roi_texto_img, beneficiario_id
            )

            # Executa OCR com configuração para linha única
            config_ocr = r'--oem 3 --psm 7'  # PSM 7: Tratar como linha única
            texto = await asyncio.to_thread(
                pytesseract.image_to_string,
                img_para_ocr,
                lang='por',
                config=config_ocr
            )

            # Tratamento específico para o nome completo
            if nome_campo.startswith("nome_completo"):
                textos_nome.append(texto.strip())

    # Consolida os campos que podem ter múltiplas partes
    dados_extraidos["nome_completo"] = " ".join(filter(None, textos_nome))

    # Processa checkboxes
    # Agrupa checkboxes pelo campo_destino para garantir que
    # apenas um seja escolhido
    checkboxes_por_campo = {}
    for nome_campo, roi_info in definicoes_rois.items():
        if roi_info["tipo"] == "checkbox":
            campo_destino = roi_info["campo_destino"]
            if campo_destino not in checkboxes_por_campo:
                checkboxes_por_campo[campo_destino] = []
            checkboxes_por_campo[campo_destino].append(roi_info)

    for campo_destino, cbs in checkboxes_por_campo.items():
        dados_extraidos[campo_destino] = "Não preenchido"  # Valor padrão
        for cb_info in cbs:
            x, y, w, h = (cb_info["x"], cb_info["y"],
                          cb_info["w"], cb_info["h"])
            roi_cb_img = imagem_processada[y:y+h, x:x+w]

            if _analisar_checkbox(roi_cb_img):
                dados_extraidos[campo_destino] = cb_info["valor_marcado"]
                # CORREÇÃO: Argumentos formatados corretamente dentro
                #  da chamada
                logging.info(
                    "[%s] Checkbox para '%s' detectado como marcado. "
                    "Valor: %s",
                    beneficiario_id,
                    campo_destino,
                    cb_info["valor_marcado"]
                )
                break
    return dados_extraidos


def _extrair_dados_do_texto(
        texto_combinado: str, beneficiario_id: str
) -> Dict[str, str]:
    """
    Extrai Nome, CPF, Data de Nascimento, NIS, etc., de um texto
    usando regex, baseado nos formulários.
    """
    logging.info(
        "[%s] Iniciando extração de dados do texto combinado.", beneficiario_id
    )

    dados_extraidos = {
        "nome_completo": "Desconhecido",
        "cpf": "000.000.000-00",
        "data_nascimento": "Não encontrada",
        "nis_titular": "Não encontrado",
        "nome_titular_nis": "Não preenchido ou igual ao beneficiário",
        "comunidade": "Não encontrada"
    }

    nome_pattern = (
        r'(?:1-\s*)?Nome\s*completo\s*[:\-]\s*([\s\S]+?)'
        r'(?=\n\s*(?:[2-9]|-|\b[A-ZÀ-ÖØ-öø-ÿ]{2,})|\Z)'
    )
    nome_match = re.search(
        nome_pattern, texto_combinado, re.IGNORECASE | re.MULTILINE
    )
    if nome_match:
        nome_bruto = nome_match.group(1).strip()
        dados_extraidos["nome_completo"] = _limpar_valor_extraido(
            nome_bruto
        ).upper()
        logging.info(
            "[%s] Nome completo: %s",
            beneficiario_id, dados_extraidos['nome_completo']
        )

    cpf_pattern = r'(?:4\s*-\s*)?CPF\s*[:\-]?\s*(\d{3}\.\d{3}\.\d{3}-\d{2})'
    cpf_match = re.search(cpf_pattern, texto_combinado, re.IGNORECASE)
    if cpf_match:
        dados_extraidos["cpf"] = cpf_match.group(1)
        logging.info("[%s] CPF: %s", beneficiario_id, dados_extraidos['cpf'])

    data_nasc_pattern = (
        r'(?:3\s*-\s*)?Data\s*de\s*Nascimento\s*[:\-]?\s*([\d\s/.-]{8,10})'
    )
    data_nasc_match = re.search(
        data_nasc_pattern, texto_combinado, re.IGNORECASE
    )
    if data_nasc_match:
        data_bruta = _limpar_valor_extraido(data_nasc_match.group(1))
        dados_extraidos["data_nascimento"] = _normalizar_data(data_bruta)
        logging.info(
            "[%s] Data Nasc.: %s (Bruta: %s)",
            beneficiario_id, dados_extraidos['data_nascimento'], data_bruta
        )

    nome_titular_pattern = (
        r'(?:21\.1\s*(?:-|\s*-\s*)?)?Nome\s*do\s*titular\s*'
        r'\(conforme\s*escrito\s*no\s*cart[ãa]o\)\s*[:\-]?\s*'
        r'([A-Za-zÀ-ÖØ-öø-ÿ\s´`\'.-]+)'
    )
    nome_titular_nis_match = re.search(
        nome_titular_pattern, texto_combinado, re.IGNORECASE | re.MULTILINE
    )
    if nome_titular_nis_match:
        nome_titular_bruto = nome_titular_nis_match.group(1).strip()
        dados_extraidos["nome_titular_nis"] = _limpar_valor_extraido(
            nome_titular_bruto
        ).upper()
        logging.info(
            "[%s] Nome Titular NIS: %s",
            beneficiario_id, dados_extraidos['nome_titular_nis']
        )

    nis_pattern = (
        r'(?:21\.2\s*(?:-|\s*-\s*)?)?N[úu]mero\s*do\s*cart[ãa]o\s*'
        r'\(NIS\s*(?:do\s*titular)?\)\s*[:\-]?\s*([\d\s.-]+)'
    )
    nis_match = re.search(nis_pattern, texto_combinado,
                          re.IGNORECASE | re.MULTILINE)
    if nis_match:
        nis_bruto = nis_match.group(1).strip()
        dados_extraidos["nis_titular"] = re.sub(r'\D', '', nis_bruto)
        logging.info(
            "[%s] NIS Titular: %s (Bruto: %s)",
            beneficiario_id, dados_extraidos['nis_titular'], nis_bruto
        )

    comunidade_pattern = (
        r'(?:6\s*-\s*)?Comunidade\s*[:\-]?\s*([A-Za-zÀ-ÖØ-öø-ÿ\s\d´`\'.-]+?)'
        r'(?=\n\s*(?:[7-9]|-|\b[A-ZÀ-ÖØ-öø-ÿ]{2,})|\Z)'
    )
    comunidade_match = re.search(
        comunidade_pattern, texto_combinado, re.IGNORECASE | re.MULTILINE
    )
    if comunidade_match:
        dados_extraidos["comunidade"] = _limpar_valor_extraido(
            comunidade_match.group(1)
        ).upper()
        logging.info(
            "[%s] Comunidade: %s",
            beneficiario_id, dados_extraidos['comunidade']
        )

    logging.info(
        "[%s] Dados finais extraídos: %s", beneficiario_id, dados_extraidos
    )
    return dados_extraidos


async def _verificar_cadastro_planilha(
        cpf: str, nome: str, beneficiario_id: str
) -> bool:
    """Verifica se beneficiário já está cadastrado em Google Sheets"""
    msg = f"Consultando planilha para CPF: {cpf} (Beneficiário: {nome})..."
    await manager.send_message(msg, beneficiario_id)
    logging.info(
        "[%s] Simulação: Verificando cadastro na planilha para CPF %s",
        beneficiario_id, cpf
    )
    await asyncio.sleep(1)
    return False


async def _executar_automacao_selenium(
        dados_beneficiario: Dict[str, Any], beneficiario_id: str
) -> str:
    """Executa automação Selenium para cadastrar beneficiário (simulação)."""
    nome_para_msg = dados_beneficiario.get('nome_completo')
    cpf_para_msg = dados_beneficiario.get('cpf')
    msg = (
        f"Iniciando automação Selenium para cadastro de {nome_para_msg} "
        f"(CPF: {cpf_para_msg})..."
    )
    await manager.send_message(msg, beneficiario_id)
    logging.info(
        "[%s] Simulação: Iniciando automação Selenium com dados: %s",
        beneficiario_id, dados_beneficiario
    )
    await asyncio.sleep(5)
    logging.info(
        "[%s] Simulação: Automação Selenium concluída.", beneficiario_id
    )
    return "Cadastrado com sucesso (simulado via Selenium)"


def salvar_historico(
    nome: str,
    cpf: str,
    status: str,
    beneficiario_id: str = None,
    detalhes_ocr: List[str] = None,
    dados_completos: Dict[str, Any] = None
):
    """Salva informações do processamento no arquivo de histórico JSON."""
    logging.info("Salvando histórico para CPF %s, Status: %s", cpf, status)
    try:
        with open(HISTORICO_PATH, 'r+', encoding='utf-8') as hist_file:
            try:
                historico_data = json.load(hist_file)
            except json.JSONDecodeError:
                logging.warning(
                    "Arquivo histórico %s vazio/corrompido. Iniciando com "
                    "lista vazia.", HISTORICO_PATH
                )
                historico_data = []

            novo_registro = {
                "id_lote": beneficiario_id or str(uuid.uuid4()),
                "nome_beneficiario": nome,
                "cpf_beneficiario": cpf,
                "status_processamento": status,
                "data_processamento": datetime.datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
                "arquivos_originais": detalhes_ocr if detalhes_ocr else [],
                "dados_extraidos_completos": (
                    dados_completos if dados_completos else {}
                )
            }

            historico_data.append(novo_registro)

            hist_file.seek(0)
            json.dump(historico_data, hist_file, indent=4, ensure_ascii=False)
            hist_file.truncate()
        logging.info("Histórico salvo com sucesso para CPF %s.", cpf)
    except IOError as e:
        logging.error("Erro de I/O ao salvar histórico: %s", e)
    except json.JSONDecodeError as e_json:
        logging.error(
            "Erro ao decodificar JSON ao salvar histórico: %s",
            e_json
        )

# Orquestra o processo completo para os documentos de um beneficiário.


async def processar_documentos_beneficiario(
    beneficiario_id: str, file_paths: List[str], original_filenames: List[str]
):
    """Orquestra o processo completo, agora usando a extração por ROI."""
    msg_inicial = (
        f"Iniciando processamento para lote ID: {beneficiario_id} "
        f"(Arquivos: {', '.join(original_filenames)})..."
    )
    await manager.send_message(msg_inicial, beneficiario_id)

    # --- Prepara a imagem do primeiro arquivo usando o novo pipeline ---
    # A função agora retorna um dicionário com a imagem ou um erro.
    # Usamos o primeiro arquivo da lista como exemplo.
    resultado_preparacao = await _executar_ocr_para_arquivo(
        file_paths[0], original_filenames[0], beneficiario_id
    )

    # Verifica se a preparação da imagem falhou
    if ("error" in resultado_preparacao or
            "imagem_processada" not in resultado_preparacao):
        msg_final_erro = (

            f"Processamento para {beneficiario_id} interrompido. "
            f"Falha na preparação da imagem: "
            f"{resultado_preparacao.get('error', 'Erro desconhecido')}"
        )
        await manager.send_message(msg_final_erro, beneficiario_id)
        salvar_historico(
            "Erro Preparação Imagem", "N/A", msg_final_erro, beneficiario_id,
            original_filenames
        )
        return

    # Se a preparação foi bem-sucedida, obtemos a imagem pronta
    imagem_pronta_para_extracao = resultado_preparacao["imagem_processada"]

    # --- ETAPA 4: Chamada para a nova extração por ROI ---
    # A chamada antiga para _extrair_dados_do_texto foi removida.
    await manager.send_message("Extraindo dados com ROIs...", beneficiario_id)

    # Assume que estamos processando a Página 1 e busca suas definições de ROI
    pagina_num = 1
    if pagina_num in TODAS_ROIS_POR_PAGINA:
        definicoes_da_pagina = TODAS_ROIS_POR_PAGINA[pagina_num]["campos"]
        dados_beneficiario = await _extrair_dados_roi(
            imagem_pronta_para_extracao,
            definicoes_da_pagina,
            beneficiario_id
        )
    else:
        logging.error("Não há definições de ROI para a página %d.", pagina_num)
        dados_beneficiario = {}  # Inicia vazio se não houver ROIs
    # --- Fim da Etapa 4 ---

    # Garante que os campos principais existam no dicionário para evitar erros
    dados_beneficiario.setdefault("nome_completo", "Não extraído")
    dados_beneficiario.setdefault("sexo", "Não extraído")
    # Será extraído quando mapearmos a ROI do CPF
    dados_beneficiario.setdefault("cpf", "000.000.000-00")

    msg_dados_extraidos = (
        f"Dados extraídos: Nome: {dados_beneficiario['nome_completo']}, "
        f"Sexo: {dados_beneficiario['sexo']}"
    )
    await manager.send_message(msg_dados_extraidos, beneficiario_id)

    # O restante do fluxo para verificar na planilha, simular selenium e
    # salvar no histórico continua, agora usando os dados extraídos por ROI.
    ja_cadastrado_planilha = await _verificar_cadastro_planilha(
        dados_beneficiario['cpf'], dados_beneficiario['nome_completo'],
        beneficiario_id
    )
    status_planilha = ('Já cadastrado' if ja_cadastrado_planilha
                       else 'Não cadastrado na planilha')
    await manager.send_message(
        f"Consulta à planilha concluída. Status: {status_planilha}",
        beneficiario_id
    )

    status_final_cadastro = ""
    if ja_cadastrado_planilha:
        status_final_cadastro = "Já cadastrado (conforme consulta à planilha)"
    else:
        nome_valido = dados_beneficiario['nome_completo'] not in [
            "Não extraído", ""]
        cpf_valido = dados_beneficiario['cpf'] != "000.000.000-00"

        if not nome_valido or not cpf_valido:
            status_final_cadastro = (
                "Falha na extração de Nome/CPF via ROI. "
                "Cadastro Selenium não iniciado."
            )
            await manager.send_message(status_final_cadastro, beneficiario_id)
        else:
            resultado_selenium = await _executar_automacao_selenium(
                dados_beneficiario, beneficiario_id
            )
            status_final_cadastro = resultado_selenium

    await manager.send_message(
        f"Status final para {beneficiario_id}: {status_final_cadastro}",
        beneficiario_id
    )

    salvar_historico(
        dados_beneficiario["nome_completo"],
        dados_beneficiario["cpf"],
        status_final_cadastro,
        beneficiario_id,
        original_filenames,
        dados_beneficiario
    )

    await manager.send_message(
        f"Processamento para beneficiário {beneficiario_id} concluído.",
        beneficiario_id
    )

# --- Endpoint de Upload de Arquivos ---


@app.post("/upload", summary="Upload de Documentos do Beneficiário")
async def upload_documentos_beneficiario(
    files: List[UploadFile] = File(
        ..., description="Lista de arquivos (PDFs/imagens) do beneficiário."
    )
):
    """
    Recebe arquivos, salva-os e inicia o processo de OCR e cadastro.
    """
    if not files:
        return JSONResponse(
            content={"error": "Nenhum arquivo enviado."}, status_code=400
        )

    saved_file_paths = []
    original_filenames = []
    beneficiario_id = str(uuid.uuid4())[:8]

    await manager.send_message(
        f"Recebendo {len(files)} arquivo(s) para o lote {beneficiario_id}...",
        beneficiario_id
    )

    for file_obj in files:
        if not file_obj.filename.lower().endswith(
            ('.pdf', '.jpg', '.jpeg', '.png')
        ):
            for p in saved_file_paths:
                if os.path.exists(p):
                    os.remove(p)
            error_msg = (
                f"Formato inválido para '{file_obj.filename}'. "
                "Apenas PDF, JPG, JPEG, PNG são permitidos."
            )
            await manager.send_message(
                f"Erro no upload: {error_msg}", beneficiario_id
            )
            return JSONResponse(content={"error": error_msg}, status_code=400)

        unique_filename = (
            f"{beneficiario_id}_{uuid.uuid4().hex[:8]}_{file_obj.filename}"
        )
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        original_filenames.append(file_obj.filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file_obj.file, buffer)
            saved_file_paths.append(file_path)
            logging.info(
                "Arquivo '%s' salvo como '%s' para o lote %s.",
                file_obj.filename, file_path, beneficiario_id
            )
        except IOError as e_io:
            logging.exception(
                "Erro de I/O ao salvar arquivo %s para lote %s",
                file_obj.filename, beneficiario_id
            )
            for p_clean in saved_file_paths:
                if os.path.exists(p_clean):
                    os.remove(p_clean)
            await manager.send_message(
                (
                    f"Erro crítico ao salvar {file_obj.filename}. "
                    "Upload cancelado."
                ),
                beneficiario_id
            )
            return JSONResponse(
                content={
                    "error": (
                        f"Erro ao salvar {file_obj.filename}: {e_io!s}"
                    )
                },
                status_code=500
            )
        finally:
            if hasattr(file_obj, 'close') and callable(file_obj.close):
                await file_obj.close()

    if len(saved_file_paths) == len(files):
        asyncio.create_task(processar_documentos_beneficiario(
            beneficiario_id, saved_file_paths, original_filenames
        ))
        msg_sucesso = (
            f"{len(saved_file_paths)} arquivo(s) para o lote "
            f"{beneficiario_id} recebido(s) e em processamento."
        )
        await manager.send_message(msg_sucesso, beneficiario_id)
        return JSONResponse(
            content={"message": msg_sucesso,
                     "beneficiario_id": beneficiario_id},
            status_code=202
        )

    await manager.send_message(
        "Erro interno ao lidar com arquivos. Upload falhou.",
        beneficiario_id
    )
    return JSONResponse(
        content={"error": "Erro interno ao lidar com os arquivos."},
        status_code=500
    )

# --- Endpoint de Histórico ---


@app.get("/historico", summary="Obter Histórico de Processamentos")
async def get_historico_endpoint():
    """Retorna o histórico de processamentos do arquivo JSON."""
    try:
        with open(HISTORICO_PATH, 'r', encoding='utf-8') as hist_file:
            historico_data = json.load(hist_file)
        return JSONResponse(content=historico_data)
    except FileNotFoundError:
        logging.warning("Arquivo histórico %s não encontrado.", HISTORICO_PATH)
        return JSONResponse(content=[], status_code=200)
    except json.JSONDecodeError:
        logging.error(
            "Erro ao decodificar JSON do histórico %s.", HISTORICO_PATH
        )
        return JSONResponse(
            content={"error": "Erro ao ler o histórico."}, status_code=500
        )
    except IOError as e_io:
        logging.exception("Erro de I/O ao buscar histórico: %s", e_io)
        return JSONResponse(
            content={"error": "Erro interno ao buscar histórico."},
            status_code=500
        )

# --- Endpoint WebSocket ---


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Gerencia a conexão WebSocket para comunicação em tempo real."""
    await manager.connect(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
            # logging.debug("WebSocket recebeu (e ignorou): %s", _)
    except WebSocketDisconnect:
        logging.info("Cliente %s desconectado do WebSocket.", websocket.client)
    except RuntimeError as e_runtime:
        logging.error(
            "Erro de Runtime na conexão WebSocket com %s: %s",
            websocket.client, e_runtime, exc_info=True
        )
    except Exception as e_ws:  # pylint: disable=broad-except
        logging.error(
            "Erro inesperado na conexão WebSocket com %s: %s",
            websocket.client, e_ws, exc_info=True
        )
    finally:
        manager.disconnect(websocket)

# --- Ponto de entrada para Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
