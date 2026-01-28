import os
import sys
import io
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Escopo de acesso
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Caminho base no seu SSD
CAMINHO_SSD_BASE = Path(r"D:\BACKUP_GOOGLE_DRIVE")

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
                print("\n[ERRO] 'credentials.json' não encontrado!")
                sys.exit()
            flow = InstalledAppFlow.from_client_secrets_file(str(caminho_creds), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(caminho_token, 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def sincronizar_recursivo(service, folder_id, caminho_local, stats):
    if not caminho_local.exists():
        caminho_local.mkdir(parents=True, exist_ok=True)

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false", 
        fields="nextPageToken, files(id, name, mimeType, size)",
        pageSize=1000
    ).execute()
    itens = results.get('files', [])

    for item in itens:
        item_id = item['id']
        nome_original = item['name']
        mime_type = item.get('mimeType', '')
        
        if mime_type == 'application/vnd.google-apps.folder':
            nome_limpo = "".join([c for c in nome_original if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            sincronizar_recursivo(service, item_id, caminho_local / nome_limpo, stats)
        
        else:
            # Identificação de extensão segura
            ext = ""
            if "." not in nome_original:
                if "video" in mime_type: ext = ".mp4"
                elif "image" in mime_type: ext = ".jpg"
                elif "pdf" in mime_type: ext = ".pdf"
            
            nome_final = nome_original + ext
            destino = caminho_local / nome_final
            tamanho_drive = int(item.get('size', 0))

            # Verifica se já existe e está íntegro
            if destino.exists() and abs(destino.stat().st_size - tamanho_drive) < 1024:
                stats['pulados'] += 1
                continue

            try:
                print(f"  [↓] Baixando: {nome_final}...", end=" ", flush=True)
                
                # MÉTODO OFICIAL DE DOWNLOAD (Evita corrupção)
                request = service.files().get_media(fileId=item_id)
                fh = io.FileIO(destino, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                stats['baixados'] += 1
                print("OK")
            except Exception as e:
                stats['erros'].append(f"{nome_final}: {e}")
                if destino.exists(): os.remove(destino) # Remove arquivo quebrado

def iniciar_programa():
    print("="*60)
    print("   SINCERIZADOR PROFISSIONAL - MODO BINÁRIO SEGURO")
    print("="*60)
    
    service = obter_servico()
    entrada = input("\nCole o ID da pasta do Drive: ").strip()
    id_alvo = entrada.split('/')[-1]

    try:
        info = service.files().get(fileId=id_alvo, fields="name").execute()
        destino_final = CAMINHO_SSD_BASE / info['name']
        
        stats = {'baixados': 0, 'pulados': 0, 'erros': []}
        sincronizar_recursivo(service, id_alvo, destino_final, stats)
        
        print(f"\nConcluído! {stats['baixados']} baixados.")
        os.startfile(destino_final)
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    iniciar_programa()
