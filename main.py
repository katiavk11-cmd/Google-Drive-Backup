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
# Caminho base no seu SSD (D:):
CAMINHO_SSD_BASE = Path(r"D:\BACKUP_GOOGLE_DRIVE")
# ============================================================

def obter_servico():
    """Gerencia a autenticação e conexão com a API."""
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
    """Percorre as pastas do Drive e baixa os arquivos para o SSD."""
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
            # Remove caracteres inválidos para pastas no Windows
            nome_limpo = "".join([c for c in nome_original if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            sincronizar_recursivo(service, creds, item_id, caminho_local / nome_limpo, stats)
        
        else:
            # Garante a extensão .mp4 se o arquivo vir sem extensão do Drive
            nome_final = nome_original if "." in nome_original else nome_original + ".mp4"
            destino = caminho_local / nome_final
            tamanho_drive = int(item.get('size', 0))

            if destino.exists():
                # Pula se o arquivo já existir com tamanho similar (evita re-download)
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
    """Interface principal que solicita o ID ao usuário."""
    print("\n" + "="*60)
    print("   GOOGLE DRIVE SYNC - MODO INTERATIVO")
    print("="*60)

    # SOLICITAÇÃO DO ID AO USUÁRIO
    entrada = input("\nCole aqui o ID da pasta (ou a URL do navegador): ").strip()
    
    # Lógica para extrair o ID caso o usuário cole a URL inteira
    id_pasta_alvo = entrada.split('/')[-1]

    try:
        service, creds = obter_servico()
        
        # Obtém o nome da pasta para criar a estrutura no SSD
        info_pasta = service.files().get(fileId=id_pasta_alvo, fields="name").execute()
        nome_pasta_raiz = info_pasta.get('name')
        
        caminho_destino_final = CAMINHO_SSD_BASE / nome_pasta_raiz
        
        print(f"\n-> Pasta identificada: {nome_pasta_raiz}")
        print(f"-> Local de destino: {caminho_destino_final}")
        print("-" * 60)

        stats = {'baixados': 0, 'pulados': 0, 'erros': []}
        sincronizar_recursivo(service, creds, id_pasta_alvo, caminho_destino_final, stats)
        
        print("\n" + "="*60)
        print(f"CONCLUÍDO: {stats['baixados']} baixados | {stats['pulados']} ignorados")
        if stats['erros']:
            print(f"FALHAS ({len(stats['erros'])}): Verifique a conexão ou permissões.")
        print("="*60)
        
        # Abre a pasta no Windows Explorer automaticamente
        os.startfile(caminho_destino_final)

    except Exception as e:
        print(f"\n[ERRO]: Não foi possível acessar a pasta. Verifique se o ID está correto.")
        print(f"Detalhes: {e}")

if __name__ == "__main__":
    iniciar_backup_por_lote()
