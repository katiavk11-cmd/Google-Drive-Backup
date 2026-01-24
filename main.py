import os
import sys
import requests
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ==============================================================================
# INFORMAÇÕES SENSÍVEIS - NÃO COMPARTILHE OS ARQUIVOS ABAIXO:
# 1. credentials.json: Contém a chave da sua aplicação no Google Cloud.
# 2. token.json: Contém sua sessão ativa (acesso direto aos seus arquivos).
# ==============================================================================

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# CAMINHO GENÉRICO: Alterado para D:\ para evitar expor nomes de usuário do Windows
CAMINHO_SSD_BASE = Path(r"D:\BACKUP_GOOGLE_DRIVE")

def obter_servico():
    """
    Realiza a autenticação OAuth2. 
    IMPORTANTE: Requer o arquivo 'credentials.json' na mesma pasta.
    """
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
                print("\n[ERRO CRÍTICO] Arquivo 'credentials.json' não encontrado!")
                print("Acesse o Google Cloud Console para baixar suas credenciais.")
                sys.exit()
            flow = InstalledAppFlow.from_client_secrets_file(str(caminho_creds), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(caminho_token, 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds), creds

def sincronizar_recursivo(service, creds, folder_id, caminho_local, stats):
    """
    Percorre a estrutura do Drive e sincroniza com o disco local.
    """
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
            # Sanitização de nome para compatibilidade com Windows
            nome_limpo = "".join([c for c in nome_original if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            sincronizar_recursivo(service, creds, item_id, caminho_local / nome_limpo, stats)
        else:
            # Tratamento de extensão para vídeos (.mp4)
            nome_final = nome_original if "." in nome_original else nome_original + ".mp4"
            destino = caminho_local / nome_final
            tamanho_drive = int(item.get('size', 0))

            # Verificação de sincronização (Idempotência)
            if destino.exists():
                if abs(destino.stat().st_size - tamanho_drive) < 1024 * 1024:
                    stats['pulados'] += 1
                    print(f"  [-] Já sincronizado: {nome_final}", end="\r")
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

def iniciar_backup():
    print("="*60)
    print("   Sincronizador Google Drive para SSD (Versão GitHub)")
    print("="*60)
    
    try:
        service, creds = obter_servico()
        
        # Solicita o ID da pasta ao usuário para não deixar hardcoded no código
        print("\nDica: O ID está no final da URL da pasta no navegador.")
        id_alvo = input("Digite o ID da pasta do Google Drive: ").strip()
        id_alvo = id_alvo.split('/')[-1] # Limpa caso o usuário cole a URL inteira
        
        info_pasta = service.files().get(fileId=id_alvo, fields="name").execute()
        nome_pasta_raiz = info_pasta.get('name')
        
        caminho_final = CAMINHO_SSD_BASE / nome_pasta_raiz
        stats = {'baixados': 0, 'pulados': 0, 'erros': []}
        
        sincronizar_recursivo(service, creds, id_alvo, caminho_final, stats)
        
        print(f"\nSincronização concluída em: {caminho_final}")
        print(f"Baixados: {stats['baixados']} | Pulados: {stats['pulados']}")
        os.startfile(caminho_final)
        
    except Exception as e:
        print(f"\n[ERRO]: {e}")

if __name__ == "__main__":
    iniciar_backup()
