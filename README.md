"""# 🎥 OBS Studio Model Context Protocol (MCP) Bridge & Tray App

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![OBS Version](https://img.shields.io/badge/OBS%20Studio-28.0%2B-red.svg)](https://obsproject.com/)
[![Protocol](https://img.shields.io/badge/protocol-MCP-orange.svg)](https://modelcontextprotocol.io/)

Este projeto é uma **Ponte de Comunicação (Bridge) Avançada** baseada no padrão **Model Context Protocol (MCP)** da Anthropic. Ele permite que Modelos de Linguagem de Grande Porte (LLMs) e Assistentes de IA — como o **Claude Desktop**, **Cursor Editor**, **GitHub Copilot CLI** ou qualquer outro cliente compatível com MCP — controlem e interajam diretamente com o seu **OBS Studio** de forma nativa e inteligente.

Além do servidor de ferramentas de IA (`mcp_obs.py`), o projeto inclui um aplicativo gráfico utilitário que roda na **Bandeja do Sistema (System Tray)** (`obs_tray.py`), facilitando a configuração das credenciais do WebSocket, a realização de testes de comunicação em tempo real e a vinculação automatizada (injeção de configuração JSON) nas ferramentas de IA suportadas.

---

## 🚀 O que o Programa Faz?

O programa atua como um tradutor em tempo real. Ele expõe a API do OBS Studio na forma de dezenas de ferramentas padronizadas para a inteligência artificial. Quando você conversa com o assistente de IA, ele consegue executar ações físicas no seu fluxo de gravação ou transmissão.

### 🧠 Exemplos de Capacidades Mapeadas:
* **Controle de Cenas:** Listar todas as cenas disponíveis, alternar entre cenas, criar novas cenas ou remover cenas obsoletas.
* **Gerenciamento do Modo Estúdio:** Ativar/desativar o Modo Estúdio, gerenciar a cena de *Preview* (Pré-visualização) e realizar a transição para a cena de *Program* (Transmissão ativa).
* **Manipulação de Fontes e Itens de Cena:** Ocultar/mostrar fontes (como webcams, capturas de jogo ou imagens), reordenar camadas, além de ler e alterar propriedades de transformação (posição X/Y, escala, rotação e tamanho).
* **Fontes de Navegador Dinâmicas:** Criar e atualizar URLs de *Browser Sources* em tempo real.
* **Automação de Áudio Completa:** Alterar volumes em decibéis (dB), aplicar mute/unmute em canais de áudio e alterar o modo de monitoramento (Não monitorar, Monitorar e Enviar para a Saída).
* **Transmissão & Gravação:** Iniciar, parar ou pausar gravações, controlar o início e fim da transmissão ao vivo, e extrair estatísticas de performance do OBS (uso de CPU, FPS atual, bitrate e contagem de frames perdidos/dropados).
* **Gatilhos Avançados:** Acionar o Replay Buffer (para salvar os últimos segundos de gameplay) e ativar/desativar a Câmera Virtual do OBS.
* **Filtros e Configurações:** Listar filtros aplicados a qualquer fonte, ativar/desativar filtros específicos (como Chroma Key ou Correção de Cor) e atualizar seus parâmetros JSON dinamicamente.
* **Ação Coringa (`call_obs_api`):** Expõe o protocolo completo **obs-websocket 5.x** nativo para a IA. Se uma funcionalidade muito específica não estiver implementada em uma função Python dedicada, a IA pode construir o payload JSON do WebSocket e executar o comando nativo por conta própria.

---

## 🛠️ Requisitos e Dependências

Para rodar o projeto sem problemas, certifique-se de cumprir os seguintes pré-requisitos:

### 1. Requisitos do Sistema Operacional
* **Python 3.10 ou superior** instalado na máquina.
* **OBS Studio v28.0 ou superior** instalado. (O OBS v28+ é obrigatório pois ele traz o plugin `obs-websocket 5.x` integrado nativamente de fábrica).

### 2. Ativação do WebSocket no OBS Studio
Antes de iniciar o programa, você precisa ativar a comunicação externa no seu OBS:
1. Abra o **OBS Studio**.
2. Clique no menu superior em **Ferramentas (Tools)** ➔ **Configurações do WebSockets Server (WebSockets Server Settings)**.
3. Marque a caixa de seleção **Habilitar WebSocket Server (Enable WebSocket Server)**.
4. Veja o número da **Porta do Servidor (Server Port)** (o padrão do OBS é `4455`).
5. Marque a opção **Habilitar Autenticação (Enable Authentication)** e defina/copie a **Senha (Server Password)**.

### 3. Bibliotecas Python Necessárias
As seguintes dependências principais são utilizadas no código:
* `mcp` / `fastmcp` — Para a criação da infraestrutura de ferramentas do servidor de IA.
* `obsws-python` — SDK otimizada em Python para gerenciar a comunicação com o WebSocket do OBS Studio.
* `pystray` — Para desenhar o ícone persistente do aplicativo na bandeja do sistema do Windows/Mac/Linux.
* `pillow` (PIL) — Para carregar, processar e renderizar dinamicamente os ícones visuais do System Tray.

---

## 📦 Como Instalar e Configurar (Passo a Passo)

### Passo 1: Clonar o Repositório
Abra o seu terminal preferido e clone a pasta do projeto

```bash
git clone [https://github.com/SEU-USUARIO/NOME-DO-REPOSITORIO.git](https://github.com/SEU-USUARIO/NOME-DO-REPOSITORIO.git)
cd NOME-DO-REPOSITORIO

Passo 2: Instalar as Dependências
Instale todos os pacotes necessários através do pip:

Bash
pip install -r requirements.txt

Caso não possua o arquivo requirements.txt gerado, você pode instalar as bibliotecas principais manualmente executando:

Bash
pip install mcp obsws-python pystray pillow

Passo 3: Executar o Aplicativo de Configuração (System Tray)
Execute a interface gráfica utilitária para configurar o ambiente com facilidade:

Bash
python app/obs_tray.py

⚙️ Como Utilizar a Interface Gráfica
Ao rodar o obs_tray.py, um ícone redondo (inicialmente cinza, indicando desconectado) aparecerá na bandeja do sistema.

Abrir o Painel: Dê um duplo clique no ícone ou clique com o botão direito e selecione "⚙️ Painel Multicontrol".

Configurar Conexão: Insira o Host (localhost ou o IP da máquina do OBS), a Porta (4455) e a Senha que você definiu nas configurações do WebSocket do OBS.

Testar Comunicação: Clique no botão "🔌 Testar Conexão Física". Se as credenciais estiverem corretas, o aplicativo exibirá uma mensagem de sucesso e o ícone na bandeja mudará de cor (verde para conectado).

Vinculação com as IAs (Injeção de Configuração):

Clique em "⚡ Vincular ao Claude" ou "🚀 Vincular ao Cursor".

O utilitário localizará automaticamente o arquivo de configuração do seu assistente de IA (mesmo se você estiver utilizando a versão do Claude instalada via Windows Microsoft Store/Sandbox) e injetará as linhas necessárias para chamar o script mcp_obs.py.

Reiniciar os Assistentes: Feche completamente o Claude Desktop ou o Cursor Editor (certifique-se de fechar os processos em background) e abra-os novamente. Isso fará com que eles leiam o novo servidor MCP configurado.