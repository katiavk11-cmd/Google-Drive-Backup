import os
import sys
import requests
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopo de acesso
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# ======================= CONFIGURAÇÃO =======================
# 1. Cole aqui o ID da pasta que você quer clonar agora:
ID_DA_PASTA_ALVO = "1UNiS5OZGdfmmoWW5JxK_fN6DIqjN6QTr" 

# 2. Caminho no seu SSD (D:):
CAMINHO_SSD_BASE = Path(r"D:\BACKUP_GOOGLE_DRIVE")
# ============================================================

def obter_servico():
    creds = None
    diretorio_script = Path(__file__).parent.absolute()
    caminho_token = diretorio_script / "token.json"
    caminho_creds = diretorio_script / "credentials.json"

    if caminho_token.exists():
        creds = Credentials.from_authorized_user_file(str(caminho_token), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not caminho_creds.exists():
                print(f"\n[ERRO] Arquivo 'credentials.json' não encontrado!")
                sys.exit()
            flow = InstalledAppFlow.from_client_secrets_file(str(caminho_creds), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(caminho_token, 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds), creds

def sincronizar_recursivo(service, creds, folder_id, caminho_local, stats):
    if not caminho_local.exists():
        caminho_local.mkdir(parents=True, exist_ok=True)

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false", 
        fields="nextPageToken, files(id, name, mimeType, webContentLink, size)",
        pageSize=1000
    ).execute()
    itens = results.get('files', [])

    for item in itens:
        item_id = item['id']
        nome_original = item['name']
        mime_type = item['mimeType']
        
        if mime_type == 'application/vnd.google-apps.folder':
            # Remove caracteres que o Windows não aceita em nomes de pastas
            nome_limpo = "".join([c for c in nome_original if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            sincronizar_recursivo(service, creds, item_id, caminho_local / nome_limpo, stats)
        
        else:
            nome_final = nome_original if "." in nome_original else nome_original + ".mp4"
            destino = caminho_local / nome_final
            tamanho_drive = int(item.get('size', 0))

            if destino.exists():
                if abs(destino.stat().st_size - tamanho_drive) < 1024 * 1024:
                    stats['pulados'] += 1
                    print(f"  [-] Já existe: {nome_final}", end="\r")
                    continue

            url = item.get('webContentLink')
            if url:
                try:
                    print(f"  [↓] Baixando: {nome_final}...", end=" ", flush=True)
                    headers = {'Authorization': f'Bearer {creds.token}'}
                    response = requests.get(url, headers=headers, stream=True)
                    
                    if response.status_code == 200:
                        with open(destino, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=1024*1024):
                                if chunk: f.write(chunk)
                        stats['baixados'] += 1
                        print("OK")
                    else:
                        stats['erros'].append(f"{nome_final} (HTTP {response.status_code})")
                except Exception as e:
                    stats['erros'].append(f"{nome_final} ({e})")

def iniciar_backup_por_lote():
    service, creds = obter_servico()
    
    # Obtém o nome da pasta alvo para organizar no SSD
    info_pasta = service.files().get(fileId=ID_DA_PASTA_ALVO, fields="name").execute()
    nome_pasta_raiz = info_pasta.get('name')
    
    caminho_destino_final = CAMINHO_SSD_BASE / nome_pasta_raiz
    
    print("="*50)
    print(f"Iniciando clone da pasta: {nome_pasta_raiz}")
    print(f"Destino: {caminho_destino_final}")
    print("="*50)

    stats = {'baixados': 0, 'pulados': 0, 'erros': []}
    sincronizar_recursivo(service, creds, ID_DA_PASTA_ALVO, caminho_destino_final, stats)
    
    print("\n" + "="*50)
    print(f"Lote concluído: {stats['baixados']} novos | {stats['pulados']} pulados")
    if stats['erros']:
        print(f"Atenção: {len(stats['erros'])} arquivos falharam.")
    print("="*50)
    os.startfile(caminho_destino_final)

if __name__ == "__main__":
    iniciar_backup_por_lote()