# 📁 Google Drive Backup 

Uma ferramenta em Python para clonar pastas do Google Drive para armazenamento local (SSD/HD) com inteligência de sincronização.

## 🛡️ Segurança e Privacidade (IMPORTANTE)
Este projeto utiliza a API do Google Drive. Por motivos de segurança, as credenciais de acesso **não estão incluídas** neste repositório. 

### Arquivos Ignorados:
Para sua proteção, o arquivo `.gitignore` deste projeto está configurado para nunca enviar:
* `credentials.json`: Suas chaves de API do Google Cloud.
* `token.json`: Sua sessão de login ativa.

**Nunca compartilhe esses arquivos com ninguém.**

---

## 🚀 Como Configurar

1. **Obtenha suas Credenciais:**
   * Vá ao [Google Cloud Console](https://console.cloud.google.com/).
   * Crie um novo projeto.
   * Ative a **Google Drive API**.
   * Em "Telas de Consentimento OAuth", configure um usuário de teste (seu próprio e-mail).
   * Em "Credenciais", crie um **ID do cliente OAuth** (tipo: Aplicativo de Desktop).
   * Baixe o JSON e renomeie para `credentials.json` na pasta raiz deste projeto.

2. **Instale as Dependências:**
   ```bash
   pip install google-api-python-client google-auth-oauthlib requests
