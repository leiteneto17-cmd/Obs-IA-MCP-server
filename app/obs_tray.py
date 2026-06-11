"""
OBS MCP Bridge — App de Bandeja v2.0
======================================
Atualizações v2.0:
  • CORREÇÃO PRINCIPAL: Substituído python.exe por pythonw.exe na injeção do config.
    python.exe cria janela de console visível + ícone extra na barra de tarefas ao ser
    chamado pelo Claude/Cursor. pythonw.exe roda em background 100% invisível.
  • Função _get_pythonw() localiza pythonw.exe automaticamente (instalação padrão e venv).

Atualizações v1.9:
  • CORREÇÃO DE DUPLICAÇÃO CLAUDE STORE: Rota automática para diretório Packages da Windows Store.
  • Tk roda na thread principal (mainloop real) e pystray em thread separada.
  • Cliente OBS singleton sem loop de reconexão.
  • Injeção de JSON blindada contra corrupção de arquivos.
  • Suporte MULTI-IA: Vínculo direto com Claude Desktop e Cursor.
"""

import ctypes
import json
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
from datetime import datetime
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont

    TRAY_OK = True
except ImportError:
    TRAY_OK = False

try:
    import obsws_python as obs

    OBS_AVAILABLE = True
except ImportError:
    OBS_AVAILABLE = False

# ── Caminhos ──────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent.resolve()
SERVER_PY = APP_DIR / "mcp_obs.py"
CONTEXT_JSON = APP_DIR / "obs_context.json"


def get_claude_config_path() -> Path:
    s = platform.system()
    if s == "Windows":
        user_profile = Path(os.environ["USERPROFILE"])
        # Rota dedicada para a Sandbox da Microsoft Store
        store_json = (
            user_profile
            / "AppData"
            / "Local"
            / "Packages"
            / "Claude_pzs8sxrjxfjjc"
            / "LocalCache"
            / "Roaming"
            / "Claude"
            / "claude_desktop_config.json"
        )

        if store_json.parent.exists():
            return store_json
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    elif s == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_cursor_config_path() -> Path:
    return Path.home() / ".cursor" / "mcp.json"


CONFIG_CLAUDE = get_claude_config_path()
CONFIG_CURSOR = get_cursor_config_path()

_obs_client = None
_obs_lock = threading.Lock()
_obs_info = {"connected": False, "version": ""}


def get_obs_client(host="localhost", port=4455, password=""):
    global _obs_client
    with _obs_lock:
        if _obs_client is not None:
            try:
                _obs_client.get_version()
                return _obs_client
            except Exception:
                _obs_client = None
        try:
            _obs_client = obs.ReqClient(
                host=host, port=port, password=password, timeout=3
            )
            return _obs_client
        except Exception:
            _obs_client = None
            return None


def disconnect_obs():
    global _obs_client
    with _obs_lock:
        _obs_client = None


def read_json_config(path: Path) -> dict:
    if path.exists():
        try:
            conteudo = path.read_text(encoding="utf-8").strip()
            if not conteudo:
                return {}
            return json.loads(conteudo)
        except Exception as e:
            print(f"Erro ao ler JSON em {path.name}: {e}")
            return {}
    return {}


def write_json_config(path: Path, data: dict):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        json_limpo = json.dumps(data, indent=2, ensure_ascii=False).strip()
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_limpo)
    except Exception as e:
        print(f"Erro ao escrever JSON em {path.name}: {e}")


def is_mcp_installed(path: Path) -> bool:
    return "obs-studio" in read_json_config(path).get("mcpServers", {})


def _get_pythonw() -> str:
    """
    Retorna pythonw.exe (sem janela de console) para que o Claude/Cursor
    não abra uma segunda janela visível na barra de tarefas ao iniciar o MCP.
    Cai em python.exe se não encontrar.
    """
    exe = Path(sys.executable)
    for candidate in [
        exe.parent / "pythonw.exe",  # instalação padrão
        exe.parent.parent / "pythonw.exe",  # dentro de venv
    ]:
        if candidate.exists():
            return str(candidate)
    return str(exe)  # fallback


def install_mcp_generic(path: Path, host, port, password) -> bool:
    try:
        cfg = read_json_config(path)
        cfg.setdefault("mcpServers", {})

        # Modo .exe compilado (PyInstaller): usa --server para stdio puro
        if sys.executable.endswith(".exe") and (
            "obs_tray" in sys.executable.lower() or "obs_mcp" in sys.executable.lower()
        ):
            cfg["mcpServers"]["obs-studio"] = {
                "command": sys.executable,
                "args": ["--server"],
                "env": {"OBS_HOST": host, "OBS_PORT": port, "OBS_PASSWORD": password},
            }
        else:
            # CORREÇÃO v2.0: usa pythonw.exe (sem console) em vez de python.exe
            # Isso impede que o Claude/Cursor abra uma janela visível + ícone extra
            # na barra de tarefas cada vez que inicia o servidor MCP.
            cfg["mcpServers"]["obs-studio"] = {
                "command": _get_pythonw(),
                "args": [str(SERVER_PY)],
                "env": {"OBS_HOST": host, "OBS_PORT": port, "OBS_PASSWORD": password},
            }

        write_json_config(path, cfg)
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível injetar as configurações:\n{e}")
        return False


def uninstall_mcp_generic(path: Path) -> bool:
    try:
        cfg = read_json_config(path)
        cfg.get("mcpServers", {}).pop("obs-studio", None)
        write_json_config(path, cfg)
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao desinstalar:\n{e}")
        return False


def get_saved_env() -> dict:
    try:
        return read_json_config(get_claude_config_path())["mcpServers"][
            "obs-studio"
        ].get("env", {})
    except Exception:
        try:
            return read_json_config(CONFIG_CURSOR)["mcpServers"]["obs-studio"].get(
                "env", {}
            )
        except Exception:
            return {}


def test_obs_connection(host, port, password) -> tuple[bool, str]:
    if not OBS_AVAILABLE:
        return False, "obsws-python não instalado"
    try:
        global _obs_client
        client = obs.ReqClient(host=host, port=port, password=password, timeout=3)
        v = client.get_version()
        obs_ver = getattr(v, "obs_version", "?")
        ws_ver = getattr(v, "obs_web_socket_version", "?")
        with _obs_lock:
            _obs_client = client
        _obs_info["connected"] = True
        _obs_info["version"] = f"OBS {obs_ver}  •  WebSocket {ws_ver}"
        notify_claude_obs_connected(obs_ver, host, port)
        return True, _obs_info["version"]
    except Exception as e:
        _obs_info["connected"] = False
        msg = str(e)
        if "Authentication" in msg:
            return False, "Senha incorreta"
        if "refused" in msg.lower() or "timed out" in msg.lower():
            return False, "OBS fechado ou WebSocket inativo"
        return False, msg


def notify_claude_obs_connected(obs_version, host, port):
    try:
        ctx = {
            "status": "connected",
            "obs_version": obs_version,
            "host": host,
            "port": port,
            "message": f"OBS Studio {obs_version} conectado em {host}:{port}. MCP Bridge ativo.",
            "last_handshake": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        CONTEXT_JSON.write_text(
            json.dumps(ctx, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def make_tray_icon(status="idle"):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg = {"idle": "#3a3a3a", "connected": "#1a7a3a", "error": "#8a1a1a"}.get(
        status, "#3a3a3a"
    )
    draw.ellipse([2, 2, size - 2, size - 2], fill=bg)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "O", fill="white", font=font, anchor="mm")
    dot = {"idle": "#aaaaaa", "connected": "#44ff88", "error": "#ff4444"}.get(
        status, "#aaaaaa"
    )
    draw.ellipse([size - 18, size - 18, size - 4, size - 4], fill=dot)
    return img


class ConfigWindow:
    def __init__(self, root: tk.Tk, on_status_change=None):
        self.root = root
        self.on_status_change = on_status_change
        self.win = None
        self._build()
        self._start_context_watcher()

    def _build(self):
        BG = "#1e1e2e"
        CARD = "#2a2a3e"
        ACCENT = "#7c3aed"
        FG = "#e2e8f0"
        SUBTLE = "#94a3b8"
        SUC = "#22c55e"

        win = tk.Toplevel(self.root)
        win.title("OBS MCP Bridge — Configuração Profissional")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", self.hide)

        w, h = 440, 750
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        hdr = tk.Frame(win, bg=ACCENT, height=56)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="🎥  OBS MCP Bridge",
            font=("Segoe UI", 14, "bold"),
            bg=ACCENT,
            fg="white",
        ).pack(side="left", padx=16, pady=12)
        tk.Label(hdr, text="v2.0", font=("Segoe UI", 9), bg=ACCENT, fg="#c4b5fd").pack(
            side="right", padx=16
        )

        sf = tk.Frame(win, bg=CARD, pady=8)
        sf.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(
            sf,
            text="Status do OBS Studio",
            font=("Segoe UI", 9, "bold"),
            bg=CARD,
            fg=SUBTLE,
        ).pack(anchor="w", padx=12)
        row = tk.Frame(sf, bg=CARD)
        row.pack(fill="x", padx=12, pady=(2, 4))
        self._dot = tk.Label(row, text="●", font=("Segoe UI", 11), bg=CARD, fg=SUBTLE)
        self._dot.pack(side="left")
        self._status_lbl = tk.Label(
            row, text="Não verificado", font=("Segoe UI", 10), bg=CARD, fg=SUBTLE
        )
        self._status_lbl.pack(side="left", padx=6)

        if _obs_info["connected"]:
            self._dot.config(fg=SUC)
            self._status_lbl.config(text=_obs_info["version"], fg=SUC)

        form = tk.Frame(win, bg=BG)
        form.pack(fill="x", padx=16, pady=4)
        saved = get_saved_env()

        def field(lbl, default, show=""):
            tk.Label(
                form, text=lbl, font=("Segoe UI", 9, "bold"), bg=BG, fg=SUBTLE
            ).pack(anchor="w", pady=(6, 1))
            var = tk.StringVar(value=default)
            tk.Entry(
                form,
                textvariable=var,
                font=("Segoe UI", 10),
                bg=CARD,
                fg=FG,
                insertbackground=FG,
                relief="flat",
                bd=0,
                show=show,
            ).pack(fill="x", ipady=6, padx=2)
            tk.Frame(form, bg=ACCENT, height=1).pack(fill="x", padx=2)
            return var

        self._host = field("Host do OBS", saved.get("OBS_HOST", "localhost"))
        self._port = field("Porta WebSocket", saved.get("OBS_PORT", "4455"))
        self._pwd = field(
            "Senha de Autenticação", saved.get("OBS_PASSWORD", ""), show="●"
        )

        tk.Button(
            form,
            text="🔌  Testar Conexão Física",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg=FG,
            relief="flat",
            cursor="hand2",
            bd=0,
            command=self._test,
            pady=6,
        ).pack(fill="x", pady=(12, 0), ipady=2)

        log_frame = tk.Frame(win, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(10, 4))
        tk.Label(
            log_frame,
            text="📜  Histórico de Atividades IA (Live)",
            font=("Segoe UI", 9, "bold"),
            bg=BG,
            fg=SUBTLE,
        ).pack(anchor="w", pady=(0, 2))

        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg="#0f111a",
            fg="#4af626",
            relief="flat",
            bd=0,
            height=6,
        )
        self.log_area.pack(fill="both", expand=True)
        self.log_area.insert(
            tk.END,
            f"[{datetime.now().strftime('%H:%M:%S')}] Motor Multi-IA ativo. Pronto para conexões.\n",
        )
        self.log_area.configure(state="disabled")

        ia_frame = tk.Frame(win, bg=BG)
        ia_frame.pack(fill="x", padx=16, pady=4)
        self._status_claude_lbl = tk.Label(
            ia_frame,
            text="• Claude Desktop: Verificando...",
            font=("Segoe UI", 9),
            bg=BG,
            fg=SUBTLE,
        )
        self._status_claude_lbl.pack(anchor="w")
        self._status_cursor_lbl = tk.Label(
            ia_frame,
            text="• Cursor Editor: Verificando...",
            font=("Segoe UI", 9),
            bg=BG,
            fg=SUBTLE,
        )
        self._status_cursor_lbl.pack(anchor="w")

        btn_box1 = tk.Frame(win, bg=BG)
        btn_box1.pack(fill="x", padx=16, pady=4)
        tk.Button(
            btn_box1,
            text="⚡  Vincular ao Claude",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT,
            fg="white",
            relief="flat",
            cursor="hand2",
            command=lambda: self._install_ia("claude"),
            pady=8,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            btn_box1,
            text="🚀  Vincular ao Cursor",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=lambda: self._install_ia("cursor"),
            pady=8,
        ).pack(side="right", fill="x", expand=True, padx=(4, 0))

        btn_box2 = tk.Frame(win, bg=BG)
        btn_box2.pack(fill="x", padx=16, pady=(4, 6))
        self._uninst_claude_btn = tk.Button(
            btn_box2,
            text="🗑  Remover Claude",
            font=("Segoe UI", 9),
            bg="#334155",
            fg=FG,
            relief="flat",
            cursor="hand2",
            command=lambda: self._uninstall_ia("claude"),
            pady=5,
        )
        self._uninst_claude_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self._uninst_cursor_btn = tk.Button(
            btn_box2,
            text="🗑  Remover Cursor",
            font=("Segoe UI", 9),
            bg="#334155",
            fg=FG,
            relief="flat",
            cursor="hand2",
            command=lambda: self._uninstall_ia("cursor"),
            pady=5,
        )
        self._uninst_cursor_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        tk.Label(
            win,
            text="💡 Se os limites do Claude esgotarem, vincule o Cursor e mude de IA instantaneamente!",
            font=("Segoe UI", 8, "italic"),
            bg=BG,
            fg="#64748b",
            wraplength=400,
        ).pack(pady=(2, 6))

        self.win = win
        self.hide()

    def add_log_message(self, message: str):
        self.log_area.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")

    def _start_context_watcher(self):
        def _watch():
            last_mtime = 0
            while True:
                try:
                    if CONTEXT_JSON.exists():
                        mtime = os.environ.get("NOT_USED") or os.path.getmtime(
                            CONTEXT_JSON
                        )
                        if mtime > last_mtime:
                            last_mtime = mtime
                            data = json.loads(CONTEXT_JSON.read_text(encoding="utf-8"))
                            if "last_action" in data:
                                msg = f"Ação recebida: {data['last_action']}"
                                self.root.after(
                                    0, lambda m=msg: self.add_log_message(m)
                                )
                except Exception:
                    pass
                import time

                time.sleep(1.2)

        threading.Thread(target=_watch, daemon=True).start()

    def show(self):
        self.root.after(0, self._do_show)

    def hide(self):
        self.root.after(0, self._do_hide)

    def _do_show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.refresh_ui_status()
        self.add_log_message("Painel de controle aberto em primeiro plano.")

    def _do_hide(self):
        self.win.withdraw()

    def refresh_ui_status(self):
        global CONFIG_CLAUDE
        CONFIG_CLAUDE = get_claude_config_path()
        c_inst = is_mcp_installed(CONFIG_CLAUDE)
        cur_inst = is_mcp_installed(CONFIG_CURSOR)

        self._status_claude_lbl.config(
            text=f"• Claude Desktop: {'Ativado ✅' if c_inst else 'Não conectado ⚠️'}",
            fg="#22c55e" if c_inst else "#f59e0b",
        )
        self._status_cursor_lbl.config(
            text=f"• Cursor Editor: {'Ativado ✅' if cur_inst else 'Não conectado ⚠️'}",
            fg="#0284c7" if cur_inst else "#f59e0b",
        )
        self._uninst_claude_btn.config(state="normal" if c_inst else "disabled")
        self._uninst_cursor_btn.config(state="normal" if cur_inst else "disabled")

    def _test(self):
        self._dot.config(fg="#f59e0b")
        self._status_lbl.config(text="Testando barramento físico…", fg="#f59e0b")
        self.win.update()
        host = self._host.get().strip()
        port = int(self._port.get().strip() or "4455")
        pwd = self._pwd.get()

        def _bg():
            ok, msg = test_obs_connection(host, port, pwd)
            color = "#22c55e" if ok else "#ef4444"
            self.root.after(0, lambda: self._dot.config(fg=color))
            self.root.after(0, lambda: self._status_lbl.config(text=msg, fg=color))
            self.root.after(
                0, lambda: self.add_log_message(f"Teste Conexão OBS: {msg}")
            )
            if self.on_status_change:
                self.root.after(
                    0, lambda: self.on_status_change("connected" if ok else "error")
                )

        threading.Thread(target=_bg, daemon=True).start()

    def _install_ia(self, target):
        host = self._host.get().strip() or "localhost"
        port = self._port.get().strip() or "4455"
        pwd = self._pwd.get()
        path = get_claude_config_path() if target == "claude" else CONFIG_CURSOR

        if install_mcp_generic(path, host, port, pwd):
            self.refresh_ui_status()
            if target == "claude":
                interp = _get_pythonw()
                self.add_log_message(
                    f"Ponte MCP vinculada com sucesso. Intérprete: {Path(interp).name}"
                )
                messagebox.showinfo(
                    "Vínculo Estabelecido!",
                    "Configuração injetada no Claude Desktop com sucesso.\n\n➡️  IMPORTANTE: Feche totalmente o Claude e abra novamente.",
                )
            else:
                self.add_log_message(
                    "Ponte MCP vinculada com sucesso ao Cursor Editor."
                )
                messagebox.showinfo(
                    "Vínculo Estabelecido com o Cursor!",
                    "Configuração injetada com sucesso!\n\nFeche e reabra o Cursor para ativar!",
                )

    def _uninstall_ia(self, target):
        path = get_claude_config_path() if target == "claude" else CONFIG_CURSOR
        name = "Claude Desktop" if target == "claude" else "Cursor"
        if not messagebox.askyesno(
            "Remover Vínculo", f"Deseja remover com segurança a ponte do OBS do {name}?"
        ):
            return
        if uninstall_mcp_generic(path):
            self.refresh_ui_status()
            self.add_log_message(f"Ponte removida das configurações do {name}.")
            messagebox.showinfo("Removido", f"Ponte removida do {name} com sucesso.")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("OBS MCP Bridge")
        self.config_win = ConfigWindow(self.root, on_status_change=self._update_icon)
        self._icon = None

    def _update_icon(self, status: str):
        if self._icon:
            self._icon.icon = make_tray_icon(status)

    def _tray_open(self, icon=None, item=None):
        self.root.after(0, self.config_win._do_show)

    def _tray_clean_all(self, icon=None, item=None):
        def _action():
            uninstall_mcp_generic(get_claude_config_path())
            uninstall_mcp_generic(CONFIG_CURSOR)
            self.root.after(0, self.config_win.refresh_ui_status)
            self.root.after(0, lambda: self._update_icon("idle"))
            self.root.after(
                0,
                lambda: self.config_win.add_log_message(
                    "Remoção total de IAs executada."
                ),
            )

        threading.Thread(target=_action, daemon=True).start()

    def _tray_check(self, icon=None, item=None):
        def _bg():
            env = get_saved_env()
            ok, msg = test_obs_connection(
                env.get("OBS_HOST", "localhost"),
                int(env.get("OBS_PORT", "4455")),
                env.get("OBS_PASSWORD", ""),
            )
            self.root.after(
                0, lambda: self._update_icon("connected" if ok else "error")
            )

        threading.Thread(target=_bg, daemon=True).start()

    def _tray_quit(self, icon, item):
        disconnect_obs()
        icon.stop()
        self.root.after(0, self.root.destroy)

    def _start_tray(self):
        if not TRAY_OK:
            return
        menu = pystray.Menu(
            pystray.MenuItem("⚙️  Painel Multicontrol", self._tray_open, default=True),
            pystray.MenuItem("🔄  Testar Canal OBS", self._tray_check),
            pystray.MenuItem("🗑️  Desvincular Todas as IAs", self._tray_clean_all),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌  Encerrar Aplicativo", self._tray_quit),
        )
        self._icon = pystray.Icon(
            "obs-mcp-bridge",
            icon=make_tray_icon("idle"),
            title="OBS MCP Bridge",
            menu=menu,
        )
        self._icon.run()

    def run(self):
        if TRAY_OK:
            threading.Thread(target=self._start_tray, daemon=True).start()
            self.root.after(
                1500,
                lambda: threading.Thread(target=self._tray_check, daemon=True).start(),
            )
            if not is_mcp_installed(get_claude_config_path()) and not is_mcp_installed(
                CONFIG_CURSOR
            ):
                self.root.after(800, self.config_win._do_show)
        else:
            self.config_win._do_show()
        self.root.mainloop()


if __name__ == "__main__":
    # COGNIÇÃO DE FLUXO (v1.9): Execução direta do motor via injeção interna stdio pura
    if "--server" in sys.argv:
        if SERVER_PY.exists():
            # Executa nativamente o código fonte sem criar processos paralelos que acionem a sandbox da Microsoft Store
            try:
                import sys
                import os

                os.environ["OBS_MCP_LOG"] = "WARNING"

                with open(SERVER_PY, "r", encoding="utf-8") as f:
                    code = f.read()

                # Execução direta e limpa no terminal stdio nativo aberto pelo próprio Claude/Cursor
                global_scope = {"__name__": "__main__", "__file__": str(SERVER_PY)}
                exec(code, global_scope)
            except Exception as e:
                sys.exit(1)
        sys.exit(0)
    else:
        if platform.system() == "Windows":
            try:
                ctypes.windll.user32.ShowWindow(
                    ctypes.windll.kernel32.GetConsoleWindow(), 0
                )
            except Exception:
                pass
        App().run()
