import cv2
import easyocr

# --- CONFIGURAÇÕES ---
NOME_IMAGEM = 'teste.png'
# Use a sua imagem de teste original

# Coordenadas (x, y, w, h) para o campo "Nome completo"
# X = Distância da borda esquerda
# Y = Distância do topo
# W = Largura do campo
# H = Altura do campo
# AJUSTE ESTES VALORES OLHANDO SUA IMAGEM EM UM EDITOR COMO O PAINT
X_NOME = 180
Y_NOME = 50
W_NOME = 770
# Largura (Width)
H_NOME = 45  # Altura (Height)

# --- CÓDIGO ---
print("Carregando o leitor de OCR...")
reader = easyocr.Reader(['pt'])
print("Leitor pronto.")

# Carrega a imagem original
img_original = cv2.imread(NOME_IMAGEM)

if img_original is None:
    print(f"ERRO: Não foi possível carregar a imagem '{NOME_IMAGEM}'")
else:
    # Recorta cirurgicamente a Região de Interesse (ROI) do nome completo
    roi_nome = img_original[Y_NOME:Y_NOME+H_NOME, X_NOME:X_NOME+W_NOME]

    print("\nProcessando apenas o recorte do nome...")
    
    # Executa o OCR apenas no recorte
    resultado = reader.readtext(roi_nome, detail=0)

    # Mostra o resultado
    print("\n" + "="*30)
    print("🔍 TEXTO EXTRAÍDO DO RECORTE:")
    print("="*30)
    if resultado:
        for texto in resultado:
            print(texto)
    else:
        print("Nenhum texto encontrado no recorte.")

    # Opcional: Mostra a imagem do recorte para verificação
    cv2.imshow("Recorte do Nome", roi_nome)
    cv2.waitKey(0)
    cv2.destroyAllWindows()