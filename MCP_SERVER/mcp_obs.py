"""
OBS Studio MCP Bridge
=====================
Conecta IAs (Claude, Cursor, Copilot, etc.) ao OBS Studio via Model Context Protocol.
Usa obs-websocket 5.x (embutido no OBS 28+).

Arquitetura:
    IA → Python MCP Server → WebSocket → OBS Studio

Autor: gerado com base no padrão cheatengine-mcp-bridge
Requisitos: Python 3.10+, obs-websocket-py, mcp
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# ── Monkey-patch: força LF no stdout do Windows (evita quebra do JSON-RPC) ──
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, newline="\n")

# ── Dependências ──────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERRO: instale as dependências com:  pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import obsws_python as obs
except ImportError:
    print(
        "ERRO: instale as dependências com:  pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Configuração ──────────────────────────────────────────────────────────────
OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")  # senha do obs-websocket
LOG_LEVEL = os.getenv("OBS_MCP_LOG", "WARNING")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL), format="[OBS-MCP] %(levelname)s %(message)s"
)
log = logging.getLogger("obs_mcp")

# ── MCP Server ────────────────────────────────────────────────────────────────
mcp = FastMCP("obs-studio")

# ── Conexão (singleton lazy) ──────────────────────────────────────────────────
_client: obs.ReqClient | None = None


def get_client() -> obs.ReqClient:
    """Retorna cliente OBS, reconectando se necessário."""
    global _client
    try:
        if _client is None:
            raise ConnectionError("sem cliente")
        _client.get_version()  # teste de vida
    except Exception:
        log.info("Conectando ao OBS em %s:%s …", OBS_HOST, OBS_PORT)
        _client = obs.ReqClient(
            host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD, timeout=5
        )
        log.info("Conectado ao OBS com sucesso.")
    return _client


def safe_call(fn, *args, **kwargs) -> dict:
    """Chama uma função OBS e devolve dict padronizado."""
    try:
        result = fn(*args, **kwargs)
        if result is None:
            return {"success": True}
        # obsws_python retorna objetos com atributo attrs
        if hasattr(result, "attrs"):
            return {"success": True, **result.attrs()}
        return {"success": True, "raw": str(result)}
    except Exception as exc:
        log.error("Erro na chamada OBS: %s", exc)
        return {"success": False, "error": str(exc)}


# ════════════════════════════════════════════════════════════════════════════
# 1. UTILITÁRIOS / DIAGNÓSTICO
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def ping() -> dict:
    """Verifica conexão com o OBS e retorna versão do obs-websocket e do OBS."""
    return safe_call(get_client().get_version)


@mcp.tool()
def get_stats() -> dict:
    """Retorna estatísticas do OBS: CPU, RAM, FPS renderizado, frames perdidos, bitrate."""
    return safe_call(get_client().get_stats)


@mcp.tool()
def get_hotkey_list() -> dict:
    """Lista todos os hotkeys registrados no OBS."""
    return safe_call(get_client().get_hot_key_list)


# ════════════════════════════════════════════════════════════════════════════
# 2. CENAS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_scenes() -> dict:
    """Lista todas as cenas do OBS com seus índices."""
    return safe_call(get_client().get_scene_list)


@mcp.tool()
def get_current_scene() -> dict:
    """Retorna o nome da cena ativa no momento."""
    return safe_call(get_client().get_current_program_scene)


@mcp.tool()
def switch_scene(scene_name: str) -> dict:
    """
    Troca a cena ativa (Program).

    Args:
        scene_name: Nome exato da cena (case-sensitive).
    """
    return safe_call(get_client().set_current_program_scene, scene_name)


@mcp.tool()
def set_preview_scene(scene_name: str) -> dict:
    """
    Define a cena no Preview (Studio Mode deve estar ativo).

    Args:
        scene_name: Nome exato da cena.
    """
    return safe_call(get_client().set_current_preview_scene, scene_name)


@mcp.tool()
def trigger_studio_mode_transition() -> dict:
    """No Studio Mode, aplica a transição do Preview → Program."""
    return safe_call(get_client().trigger_studio_mode_transition)


@mcp.tool()
def create_scene(scene_name: str) -> dict:
    """
    Cria uma nova cena vazia.

    Args:
        scene_name: Nome da nova cena.
    """
    return safe_call(get_client().create_scene, scene_name)


@mcp.tool()
def remove_scene(scene_name: str) -> dict:
    """
    Remove uma cena existente.

    Args:
        scene_name: Nome da cena a remover.
    """
    return safe_call(get_client().remove_scene, scene_name)


@mcp.tool()
def get_studio_mode_enabled() -> dict:
    """Verifica se o Studio Mode está ativo."""
    return safe_call(get_client().get_studio_mode_enabled)


@mcp.tool()
def set_studio_mode_enabled(enabled: bool) -> dict:
    """
    Ativa ou desativa o Studio Mode.

    Args:
        enabled: True para ativar, False para desativar.
    """
    return safe_call(get_client().set_studio_mode_enabled, enabled)


# ════════════════════════════════════════════════════════════════════════════
# 3. FONTES (SOURCES / ITEMS)
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_scene_items(scene_name: str) -> dict:
    """
    Lista todas as fontes (itens) de uma cena.

    Args:
        scene_name: Nome da cena.
    """
    return safe_call(get_client().get_scene_item_list, scene_name)


@mcp.tool()
def set_source_visibility(scene_name: str, item_id: int, visible: bool) -> dict:
    """
    Mostra ou oculta uma fonte em uma cena.

    Args:
        scene_name: Nome da cena que contém a fonte.
        item_id:    ID numérico do item (use list_scene_items para descobrir).
        visible:    True para mostrar, False para ocultar.
    """
    return safe_call(get_client().set_scene_item_enabled, scene_name, item_id, visible)


@mcp.tool()
def get_source_visibility(scene_name: str, item_id: int) -> dict:
    """
    Verifica se uma fonte está visível.

    Args:
        scene_name: Nome da cena.
        item_id:    ID numérico do item.
    """
    return safe_call(get_client().get_scene_item_enabled, scene_name, item_id)


@mcp.tool()
def set_source_transform(scene_name: str, item_id: int, transform: dict) -> dict:
    """
    Reposiciona / redimensiona / rotaciona uma fonte.

    Args:
        scene_name: Nome da cena.
        item_id:    ID numérico do item.
        transform:  Dicionário com campos opcionais:
                    positionX, positionY, rotation,
                    scaleX, scaleY, width, height,
                    cropTop, cropBottom, cropLeft, cropRight
    Exemplo:
        set_source_transform("Gameplay", 3, {"positionX": 0, "positionY": 0, "scaleX": 1.0})
    """
    return safe_call(
        get_client().set_scene_item_transform, scene_name, item_id, transform
    )


@mcp.tool()
def get_source_transform(scene_name: str, item_id: int) -> dict:
    """
    Retorna posição, tamanho e rotação de uma fonte.

    Args:
        scene_name: Nome da cena.
        item_id:    ID numérico do item.
    """
    return safe_call(get_client().get_scene_item_transform, scene_name, item_id)


@mcp.tool()
def duplicate_scene_item(
    scene_name: str, item_id: int, destination_scene: str = ""
) -> dict:
    """
    Duplica um item de cena, opcionalmente para outra cena.

    Args:
        scene_name:         Cena de origem.
        item_id:            ID do item a duplicar.
        destination_scene:  Cena de destino (vazio = mesma cena).
    """
    kwargs: dict[str, Any] = {"scene_name": scene_name, "item_id": item_id}
    if destination_scene:
        kwargs["destination_scene_name"] = destination_scene
    return safe_call(get_client().duplicate_scene_item, **kwargs)


@mcp.tool()
def remove_scene_item(scene_name: str, item_id: int) -> dict:
    """
    Remove um item de uma cena.

    Args:
        scene_name: Nome da cena.
        item_id:    ID do item a remover.
    """
    return safe_call(get_client().remove_scene_item, scene_name, item_id)


@mcp.tool()
def get_input_settings(input_name: str) -> dict:
    """
    Retorna as configurações de uma fonte de entrada (câmera, captura de tela, etc.).

    Args:
        input_name: Nome da fonte.
    """
    return safe_call(get_client().get_input_settings, input_name)


@mcp.tool()
def list_inputs(input_kind: str = "") -> dict:
    """
    Lista todas as entradas (fontes) do OBS.

    Args:
        input_kind: Filtra por tipo, ex: 'dshow_input', 'browser_source', 'image_source'.
                    Deixe vazio para listar todas.
    """
    kwargs = {}
    if input_kind:
        kwargs["input_kind"] = input_kind
    return safe_call(get_client().get_input_list, **kwargs)


# ════════════════════════════════════════════════════════════════════════════
# 4. ÁUDIO
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_volume(input_name: str) -> dict:
    """
    Retorna o volume (mul e dB) de uma fonte de áudio.

    Args:
        input_name: Nome da fonte de áudio.
    """
    return safe_call(get_client().get_input_volume, input_name)


@mcp.tool()
def set_volume(input_name: str, volume_db: float) -> dict:
    """
    Define o volume de uma fonte em dB (-100 a 26).

    Args:
        input_name: Nome da fonte de áudio.
        volume_db:  Volume em dB. Use -100 para mudo efetivo.
    """
    return safe_call(get_client().set_input_volume, input_name, vol_db=volume_db)


@mcp.tool()
def set_mute(input_name: str, muted: bool) -> dict:
    """
    Muta ou desmuta uma fonte de áudio.

    Args:
        input_name: Nome da fonte de áudio.
        muted:      True para mutar, False para desmutar.
    """
    return safe_call(get_client().set_input_mute, input_name, muted)


@mcp.tool()
def toggle_mute(input_name: str) -> dict:
    """
    Alterna o estado de mute de uma fonte de áudio.

    Args:
        input_name: Nome da fonte de áudio.
    """
    return safe_call(get_client().toggle_input_mute, input_name)


@mcp.tool()
def get_mute(input_name: str) -> dict:
    """
    Verifica se uma fonte de áudio está mutada.

    Args:
        input_name: Nome da fonte de áudio.
    """
    return safe_call(get_client().get_input_mute, input_name)


@mcp.tool()
def get_audio_monitor_type(input_name: str) -> dict:
    """
    Retorna o tipo de monitor de áudio de uma fonte.

    Args:
        input_name: Nome da fonte de áudio.
    """
    return safe_call(get_client().get_input_audio_monitor_type, input_name)


@mcp.tool()
def set_audio_monitor_type(input_name: str, monitor_type: str) -> dict:
    """
    Define o tipo de monitor de áudio.

    Args:
        input_name:   Nome da fonte.
        monitor_type: 'OBS_MONITORING_TYPE_NONE' | 'OBS_MONITORING_TYPE_MONITOR_ONLY' |
                      'OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT'
    """
    return safe_call(
        get_client().set_input_audio_monitor_type, input_name, monitor_type
    )


# ════════════════════════════════════════════════════════════════════════════
# 5. GRAVAÇÃO
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_record_status() -> dict:
    """Retorna status atual da gravação (ativo, pausado, tempo decorrido, bytes gravados)."""
    return safe_call(get_client().get_record_status)


@mcp.tool()
def start_recording() -> dict:
    """Inicia a gravação."""
    return safe_call(get_client().start_record)


@mcp.tool()
def stop_recording() -> dict:
    """Para a gravação e retorna o caminho do arquivo salvo."""
    return safe_call(get_client().stop_record)


@mcp.tool()
def pause_recording() -> dict:
    """Pausa a gravação em andamento."""
    return safe_call(get_client().pause_record)


@mcp.tool()
def resume_recording() -> dict:
    """Retoma uma gravação pausada."""
    return safe_call(get_client().resume_record)


@mcp.tool()
def toggle_recording() -> dict:
    """Alterna gravação (inicia se parada, para se em andamento)."""
    return safe_call(get_client().toggle_record)


# ════════════════════════════════════════════════════════════════════════════
# 6. STREAMING
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_stream_status() -> dict:
    """Retorna status do stream (ativo, congestionamento, bitrate, tempo decorrido)."""
    return safe_call(get_client().get_stream_status)


@mcp.tool()
def start_streaming() -> dict:
    """Inicia o stream com as configurações atuais."""
    return safe_call(get_client().start_stream)


@mcp.tool()
def stop_streaming() -> dict:
    """Para o stream."""
    return safe_call(get_client().stop_stream)


@mcp.tool()
def toggle_streaming() -> dict:
    """Alterna streaming (inicia se parado, para se ativo)."""
    return safe_call(get_client().toggle_stream)


@mcp.tool()
def send_stream_caption(caption_text: str) -> dict:
    """
    Envia uma legenda para o stream (requer suporte do serviço).

    Args:
        caption_text: Texto da legenda.
    """
    return safe_call(get_client().send_stream_caption, caption_text)


# ════════════════════════════════════════════════════════════════════════════
# 7. VIRTUAL CAMERA
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_virtual_cam_status() -> dict:
    """Verifica se a câmera virtual está ativa."""
    return safe_call(get_client().get_virtual_cam_status)


@mcp.tool()
def start_virtual_cam() -> dict:
    """Ativa a câmera virtual do OBS."""
    return safe_call(get_client().start_virtual_cam)


@mcp.tool()
def stop_virtual_cam() -> dict:
    """Desativa a câmera virtual do OBS."""
    return safe_call(get_client().stop_virtual_cam)


@mcp.tool()
def toggle_virtual_cam() -> dict:
    """Alterna câmera virtual."""
    return safe_call(get_client().toggle_virtual_cam)


# ════════════════════════════════════════════════════════════════════════════
# 8. TRANSIÇÕES
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_transitions() -> dict:
    """Lista todas as transições disponíveis."""
    return safe_call(get_client().get_transition_kind_list)


@mcp.tool()
def get_current_transition() -> dict:
    """Retorna a transição atual e sua duração."""
    return safe_call(get_client().get_current_scene_transition)


@mcp.tool()
def set_transition(transition_name: str) -> dict:
    """
    Define a transição de cena ativa.

    Args:
        transition_name: Nome da transição (ex: 'Fade', 'Cut', 'Slide').
    """
    return safe_call(get_client().set_current_scene_transition, transition_name)


@mcp.tool()
def set_transition_duration(duration_ms: int) -> dict:
    """
    Define a duração da transição atual em milissegundos.

    Args:
        duration_ms: Duração em ms (ex: 500 = meio segundo).
    """
    return safe_call(get_client().set_current_scene_transition_duration, duration_ms)


# ════════════════════════════════════════════════════════════════════════════
# 9. FILTROS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_source_filters(source_name: str) -> dict:
    """
    Lista todos os filtros de uma fonte.

    Args:
        source_name: Nome da fonte.
    """
    return safe_call(get_client().get_source_filter_list, source_name)


@mcp.tool()
def set_filter_enabled(source_name: str, filter_name: str, enabled: bool) -> dict:
    """
    Ativa ou desativa um filtro de uma fonte.

    Args:
        source_name: Nome da fonte.
        filter_name: Nome do filtro.
        enabled:     True para ativar, False para desativar.
    """
    return safe_call(
        get_client().set_source_filter_enabled, source_name, filter_name, enabled
    )


@mcp.tool()
def get_filter_settings(source_name: str, filter_name: str) -> dict:
    """
    Retorna as configurações de um filtro.

    Args:
        source_name: Nome da fonte.
        filter_name: Nome do filtro.
    """
    return safe_call(get_client().get_source_filter, source_name, filter_name)


@mcp.tool()
def set_filter_settings(source_name: str, filter_name: str, settings: dict) -> dict:
    """
    Atualiza as configurações de um filtro.

    Args:
        source_name: Nome da fonte.
        filter_name: Nome do filtro.
        settings:    Dicionário com as configurações a atualizar.
    Exemplo:
        set_filter_settings("Webcam", "Color Correction", {"brightness": 0.2, "contrast": 0.1})
    """
    return safe_call(
        get_client().set_source_filter_settings, source_name, filter_name, settings
    )


@mcp.tool()
def remove_filter(source_name: str, filter_name: str) -> dict:
    """
    Remove um filtro de uma fonte.

    Args:
        source_name: Nome da fonte.
        filter_name: Nome do filtro a remover.
    """
    return safe_call(get_client().remove_source_filter, source_name, filter_name)


# ════════════════════════════════════════════════════════════════════════════
# 10. REPLAY BUFFER
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_replay_buffer_status() -> dict:
    """Verifica se o Replay Buffer está ativo."""
    return safe_call(get_client().get_replay_buffer_status)


@mcp.tool()
def start_replay_buffer() -> dict:
    """Inicia o Replay Buffer."""
    return safe_call(get_client().start_replay_buffer)


@mcp.tool()
def stop_replay_buffer() -> dict:
    """Para o Replay Buffer."""
    return safe_call(get_client().stop_replay_buffer)


@mcp.tool()
def save_replay_buffer() -> dict:
    """Salva o Replay Buffer atual para arquivo."""
    return safe_call(get_client().save_replay_buffer)


@mcp.tool()
def toggle_replay_buffer() -> dict:
    """Alterna o Replay Buffer."""
    return safe_call(get_client().toggle_replay_buffer)


# ════════════════════════════════════════════════════════════════════════════
# 11. PERFIS E COLEÇÕES DE CENAS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_profiles() -> dict:
    """Lista todos os perfis de configuração do OBS."""
    return safe_call(get_client().get_profile_list)


@mcp.tool()
def get_current_profile() -> dict:
    """Retorna o perfil ativo."""
    return safe_call(
        get_client().get_profile_list
    )  # currentProfileName está no retorno


@mcp.tool()
def set_profile(profile_name: str) -> dict:
    """
    Troca o perfil de configuração ativo.

    Args:
        profile_name: Nome do perfil.
    """
    return safe_call(get_client().set_current_profile, profile_name)


@mcp.tool()
def list_scene_collections() -> dict:
    """Lista todas as coleções de cenas."""
    return safe_call(get_client().get_scene_collection_list)


@mcp.tool()
def set_scene_collection(collection_name: str) -> dict:
    """
    Troca a coleção de cenas ativa.

    Args:
        collection_name: Nome da coleção.
    """
    return safe_call(get_client().set_current_scene_collection, collection_name)


# ════════════════════════════════════════════════════════════════════════════
# 12. SCREENSHOT / OUTPUT
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def take_screenshot(
    source_name: str, file_path: str, width: int = 1920, height: int = 1080
) -> dict:
    """
    Tira um screenshot de uma fonte e salva em arquivo.

    Args:
        source_name: Nome da fonte (ou deixe vazio para capturar a cena ativa).
        file_path:   Caminho completo para salvar (ex: C:/obs_shots/shot.png).
        width:       Largura da imagem (padrão 1920).
        height:      Altura da imagem (padrão 1080).
    """
    return safe_call(
        get_client().save_source_screenshot,
        source_name,
        "png",
        file_path,
        width,
        height,
    )


@mcp.tool()
def list_outputs() -> dict:
    """Lista todos os outputs configurados no OBS."""
    return safe_call(get_client().get_output_list)


@mcp.tool()
def get_output_settings(output_name: str) -> dict:
    """
    Retorna as configurações de um output específico.

    Args:
        output_name: Nome do output.
    """
    return safe_call(get_client().get_output_settings, output_name)

    # ════════════════════════════════════════════════════════════════════════════


# 14. AUTOMAÇÃO DE OVERLAYS E FONTES AVANÇADAS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def create_browser_source(
    scene_name: str,
    source_name: str,
    url_or_path: str,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    """
    Cria uma fonte de navegador (Browser Source) em uma cena específica.
    Se for um arquivo local, converte automaticamente para o formato file:///.

    Args:
        scene_name: Nome da cena onde a fonte será adicionada.
        source_name: Nome que a nova fonte receberá no OBS.
        url_or_path: URL da web ou caminho absoluto do arquivo HTML local.
        width: Largura da fonte (padrão 1920).
        height: Altura da fonte (padrão 1080).
    """
    client = get_client()

    # Se for um caminho de arquivo local, normaliza para o padrão que o OBS aceita
    if ":" in url_or_path or url_or_path.startswith("/") or url_or_path.startswith("."):
        path_obj = Path(url_or_path).resolve()
        url_to_use = path_obj.as_uri()
    else:
        url_to_use = url_or_path

    # Configurações iniciais do Browser Source no OBS 5.x
    input_settings = {
        "url": url_to_use,
        "width": width,
        "height": height,
        "is_local_file": False,  # 'False' porque passamos como URI file:/// estável
        "restart_when_active": True,
    }

    try:
        # 1. Cria a entrada global no OBS (Input)
        client.create_input(
            sceneName=scene_name,
            inputName=source_name,
            inputKind="browser_source",
            inputSettings=input_settings,
            sceneItemEnabled=True,
        )
        return {
            "success": True,
            "message": f"Browser Source '{source_name}' criada com sucesso na cena '{scene_name}'.",
        }
    except Exception as exc:
        log.error("Erro ao criar Browser Source: %s", exc)
        return {"success": False, "error": str(exc)}


@mcp.tool()
def setup_streaming_package(base_dir: str, overlays: dict) -> dict:
    """
    Automatiza o deploy completo de um pacote de overlays criando as cenas e fontes de uma só vez.

    Args:
        base_dir: Diretório absoluto na máquina local onde os HTMLs foram salvos.
        overlays: Dicionário mapeando { "Nome da Cena": {"source_name": "Nome da Fonte", "file": "nome.html"} }
    """
    client = get_client()
    results = []

    # Garante a lista de cenas atuais para não duplicar erros
    try:
        existing_scenes = [
            s["sceneName"] for s in client.get_scene_list().attrs()["scenes"]
        ]
    except Exception:
        existing_scenes = []

    for scene_name, config in overlays.items():
        # Se a cena não existe, cria
        if scene_name not in existing_scenes:
            safe_call(client.create_scene, scene_name)
            results.append(f"Cena '{scene_name}' criada.")

        full_path = str(Path(base_dir) / config["file"])

        # Chama a função interna para criar a fonte
        res = create_browser_source(
            scene_name=scene_name,
            source_name=config["source_name"],
            url_or_path=full_path,
        )

        if res["success"]:
            results.append(
                f"Fonte '{config['source_name']}' injetada na cena '{scene_name}'."
            )
        else:
            results.append(f"Falha na fonte '{config['source_name']}': {res['error']}")

    return {"success": True, "log": results}


@mcp.tool()
def call_obs_api(request_type: str, request_data: dict = None) -> dict:
    """
    Ferramenta CORINGA: Executa QUALQUER comando do protocolo oficial do OBS-WebSocket 5.x.
    Útil para comandos avançados que ainda não têm uma função própria criada no mcp_obs.py.

    Args:
        request_type: O nome exato do comando no protocolo do OBS (ex: 'GetMediaInputStatus', 'SetSourceFilterIndex').
        request_data: Dicionário opcional com os parâmetros exigidos pelo comando.
    """
    try:
        # O método .send do obsws_python permite enviar requisições puras e diretas ao WebSocket
        client = get_client()
        # Se request_data for None, passa um dicionário vazio
        data = request_data or {}

        # Executa a chamada genérica usando a estrutura nativa da biblioteca
        response = client.send(obs.requests.GenericRequest(request_type, data))

        if hasattr(response, "attrs"):
            return {"success": True, **response.attrs()}
        return {"success": True, "raw": str(response)}
    except Exception as exc:
        log.error(f"Erro na chamada da API genérica do OBS ({request_type}): {exc}")
        return {"success": False, "error": str(exc)}


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("[OBS-MCP] Servidor iniciando…", file=sys.stderr)
    print(f"[OBS-MCP] Conectará em: ws://{OBS_HOST}:{OBS_PORT}", file=sys.stderr)
    print("[OBS-MCP] Configure OBS_PASSWORD se necessário.", file=sys.stderr)
    mcp.run(transport="stdio")


# ════════════════════════════════════════════════════════════════════════════
# 13. CONTEXTO — informa o Claude sobre o estado do OBS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_obs_context() -> dict:
    """
    Retorna contexto atual do OBS MCP Bridge.
    Use esta ferramenta logo ao iniciar para saber se o OBS está conectado
    e qual versão está rodando.
    """
    context_file = Path(__file__).parent / "obs_context.json"
    base = {"bridge": "OBS MCP Bridge v1.1", "tools_available": 51}

    if context_file.exists():
        try:
            ctx = json.loads(context_file.read_text(encoding="utf-8"))
            return {**base, **ctx}
        except Exception:
            pass

    # Tenta conexão ao vivo
    try:
        result = safe_call(get_client().get_version)
        if result.get("success"):
            return {
                **base,
                "status": "connected",
                "obs_version": result.get("obs_version", "?"),
                "message": "OBS Studio conectado e pronto para uso.",
            }
    except Exception:
        pass

    return {
        **base,
        "status": "disconnected",
        "message": "OBS não está conectado. Abra o OBS e verifique o WebSocket.",
    }
