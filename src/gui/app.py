"""
Tkinter Desktop Graphical User Interface (GUI) Application.
Features modern Catppuccin-inspired Dark & Light themes, multi-channel chat (Group + Direct DMs),
real-time typing indicators, quick emoji bar, slash commands, received file browser, and settings modal.
"""

import os
import queue
import socket
import threading
import time
import tkinter as tk
import urllib.parse
import uuid
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

import config
from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.network.discovery import DiscoveryEngine
from src.network.file_transfer import FileReceiver, FileSender
from src.network.tcp_client import TCPClient
from src.network.tcp_server import TCPServer
from src.utils.net_utils import get_local_ip
from src.web.gateway import WebGateway

# Color palettes for Dark (Catppuccin Mocha) and Light themes
THEMES = {
    "dark": {
        "bg_main": "#1e1e2e",
        "bg_sidebar": "#181825",
        "bg_card": "#26283b",
        "bg_input": "#313244",
        "bg_hover": "#45475a",
        "fg_main": "#cdd6f4",
        "fg_secondary": "#a6adc8",
        "fg_muted": "#6c7086",
        "accent": "#89b4fa",
        "accent_green": "#a6e3a1",
        "accent_pink": "#f5c2e7",
        "accent_yellow": "#f9e2af",
        "accent_red": "#f38ba8",
        "border": "#313244",
        "chat_bg": "#181825",
    },
    "light": {
        "bg_main": "#f4f6f9",
        "bg_sidebar": "#ffffff",
        "bg_card": "#e9ecef",
        "bg_input": "#ffffff",
        "bg_hover": "#dee2e6",
        "fg_main": "#212529",
        "fg_secondary": "#495057",
        "fg_muted": "#6c757d",
        "accent": "#0d6efd",
        "accent_green": "#198754",
        "accent_pink": "#d63384",
        "accent_yellow": "#b58105",
        "accent_red": "#dc3545",
        "border": "#dee2e6",
        "chat_bg": "#ffffff",
    },
}


class LANChatApp(tk.Tk):
    """
    Main Tkinter LAN Chat Desktop Application Window.
    """

    def __init__(self, peer_id: str, username: str, tcp_port: int = config.DEFAULT_TCP_PORT) -> None:
        super().__init__()

        self.peer_id = peer_id
        self.username = username
        self.tcp_port = tcp_port
        self.device_name = socket.gethostname()
        self.local_ip = get_local_ip()

        self.title(f"{config.APP_NAME} — {self.username} ({self.local_ip})")
        self.geometry("980x660")
        self.minsize(820, 520)

        # Thread-safe event queue for network-to-UI updates
        self.ui_queue: queue.Queue = queue.Queue()

        # Peer directory & channel routing
        self.peers: Dict[str, Peer] = {}
        self.selected_peer_id: Optional[str] = None  # None = Group Broadcast Room
        self.pending_outgoing_files: Dict[str, Path] = {}

        # Multi-channel message history: channel_id -> list of message dicts
        # channel_id = None for Group Chat; peer_id for direct DMs
        self.chat_histories: Dict[Optional[str], List[dict]] = {None: []}
        self.unread_counts: Dict[Optional[str], int] = {}
        self.custom_rooms: set = set()
        self.pinned_messages: Dict[Optional[str], Optional[dict]] = {}

        # Feature flags & state
        self.current_theme = "dark"
        self.sound_enabled = True
        self._last_typing_sent = 0.0
        self._typing_clear_job = None
        self.seen_message_ids: Set[str] = set()

        # Build UI layout & apply theme
        self._setup_ui()
        self._apply_theme(self.current_theme)

        # Initialize Network Engines
        self.tcp_server = TCPServer(
            port=self.tcp_port, on_message_received=self._on_tcp_message_received
        )
        self.actual_tcp_port = self.tcp_server.start()

        # Update window title and status header with actual bound TCP port
        self.title(f"{config.APP_NAME} — {self.username} ({self.local_ip}:{self.actual_tcp_port})")
        self.lbl_status.config(
            text=f"👤 {self.username} | 🌐 {self.local_ip}:{self.actual_tcp_port}"
        )

        self.discovery_engine = DiscoveryEngine(
            peer_id=self.peer_id,
            username=self.username,
            device_name=self.device_name,
            tcp_port=self.actual_tcp_port,
            on_peer_updated=self._on_peer_updated,
            on_peer_removed=self._on_peer_removed,
        )
        self.discovery_engine.start()

        # Initialize Web Gateway for Mobile Browser LAN Access
        self.web_gateway = WebGateway(app_context=self, host="0.0.0.0", port=8080)
        self.web_port = self.web_gateway.start()

        # Welcome announcement
        welcome_info = (
            f"Welcome to {config.APP_NAME}! Type a message or type '/help' for commands.\n"
            f"📱 Mobile Web Interface: http://{self.local_ip}:{self.web_port}"
        )
        self._append_message(None, "System", welcome_info, category="system")

        # Start UI event queue polling (every 40ms)
        self.after(40, self._poll_ui_queue)

        # Window closing handler
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self) -> None:
        """Constructs the Tkinter widget layout."""
        theme = THEMES[self.current_theme]

        # Top Header Bar
        self.header_frame = tk.Frame(self, bg=theme["bg_card"], padx=12, pady=8)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.lbl_logo = tk.Label(
            self.header_frame,
            text=f"📡 {config.APP_NAME}",
            font=("Segoe UI", 12, "bold"),
            bg=theme["bg_card"],
            fg=theme["accent"],
        )
        self.lbl_logo.pack(side=tk.LEFT)

        self.lbl_status_badge = tk.Label(
            self.header_frame,
            text="● Online",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_card"],
            fg=theme["accent_green"],
            padx=8,
        )
        self.lbl_status_badge.pack(side=tk.LEFT)

        # Action Buttons on Right Header
        self.btn_settings = tk.Button(
            self.header_frame,
            text="⚙️ Settings",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._open_settings_dialog,
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_p2p = tk.Button(
            self.header_frame,
            text="🔗 Direct P2P",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent_green"],
            fg="#11111b",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._open_p2p_connect_dialog,
        )
        self.btn_p2p.pack(side=tk.RIGHT, padx=4)

        self.btn_mobile_web = tk.Button(
            self.header_frame,
            text="📱 Mobile Web",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._open_mobile_web_dialog,
        )
        self.btn_mobile_web.pack(side=tk.RIGHT, padx=4)

        self.btn_downloads = tk.Button(
            self.header_frame,
            text="📁 Downloads",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._open_downloads_folder,
        )
        self.btn_downloads.pack(side=tk.RIGHT, padx=4)

        self.btn_theme = tk.Button(
            self.header_frame,
            text="🌙 Dark",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side=tk.RIGHT, padx=4)

        self.lbl_status = tk.Label(
            self.header_frame,
            text=f"👤 {self.username} | 🌐 {self.local_ip}:{self.tcp_port}",
            font=("Segoe UI", 9),
            bg=theme["bg_card"],
            fg=theme["fg_secondary"],
        )
        self.lbl_status.pack(side=tk.RIGHT, padx=8)

        # Separator Line
        self.header_sep = tk.Frame(self, height=1, bg=theme["border"])
        self.header_sep.pack(side=tk.TOP, fill=tk.X)

        # Main Paned Area (Left Sidebar + Right Chat)
        self.main_container = tk.Frame(self, bg=theme["bg_main"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Left Sidebar (Peers Directory)
        self.sidebar_frame = tk.Frame(self.main_container, bg=theme["bg_sidebar"], width=240, padx=8, pady=8)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.lbl_sidebar_title = tk.Label(
            self.sidebar_frame,
            text="👥 Active Peers (0)",
            font=("Segoe UI", 10, "bold"),
            bg=theme["bg_sidebar"],
            fg=theme["fg_main"],
        )
        self.lbl_sidebar_title.pack(anchor=tk.W, pady=(0, 6))

        # Styled ttk Treeview for Peers
        self.tree_style = ttk.Style(self)
        self.tree_style.theme_use("clam")

        self.peer_tree = ttk.Treeview(
            self.sidebar_frame, columns=("name", "ip"), show="tree", selectmode="browse"
        )
        self.peer_tree.pack(fill=tk.BOTH, expand=True)

        # Insert Group Chat item at top
        self.group_item_id = self.peer_tree.insert(
            "", tk.END, text="🌐 Group Broadcast Chat", open=True
        )
        self.peer_tree.selection_set(self.group_item_id)
        self.peer_tree.bind("<<TreeviewSelect>>", self._on_peer_selected)
        self.peer_tree.bind("<Double-1>", self._on_peer_double_click)
        self.peer_tree.bind("<Button-3>", self._show_peer_context_menu)

        # Sidebar Footer
        self.sidebar_footer = tk.Label(
            self.sidebar_frame,
            text=f"ID: {self.peer_id}",
            font=("Segoe UI", 8),
            bg=theme["bg_sidebar"],
            fg=theme["fg_muted"],
        )
        self.sidebar_footer.pack(side=tk.BOTTOM, anchor=tk.W, pady=(4, 0))

        # Divider between sidebar and chat
        self.v_sep = tk.Frame(self.main_container, width=1, bg=theme["border"])
        self.v_sep.pack(side=tk.LEFT, fill=tk.Y)

        # Right Chat Area
        self.chat_container = tk.Frame(self.main_container, bg=theme["bg_main"], padx=10, pady=8)
        self.chat_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Chat Header with P2P Action Buttons
        self.chat_header = tk.Frame(self.chat_container, bg=theme["bg_main"])
        self.chat_header.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

        self.header_left = tk.Frame(self.chat_header, bg=theme["bg_main"])
        self.header_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_chat_title = tk.Label(
            self.header_left,
            text="💬 Group Broadcast Chat",
            font=("Segoe UI", 11, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        )
        self.lbl_chat_title.pack(anchor=tk.W)

        self.lbl_chat_sub = tk.Label(
            self.header_left,
            text="🌐 Public Room — Messages broadcast to all online peers",
            font=("Segoe UI", 8),
            bg=theme["bg_main"],
            fg=theme["fg_muted"],
        )
        self.lbl_chat_sub.pack(anchor=tk.W)

        self.header_actions = tk.Frame(self.chat_header, bg=theme["bg_main"])
        self.header_actions.pack(side=tk.RIGHT)

        self.btn_header_file = tk.Button(
            self.header_actions,
            text="📁 Share File",
            font=("Segoe UI", 8, "bold"),
            bg=theme["accent"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._send_file_dialog,
        )
        self.btn_header_file.pack(side=tk.LEFT, padx=3)

        self.btn_header_info = tk.Button(
            self.header_actions,
            text="ℹ️ Peer Info",
            font=("Segoe UI", 8),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._show_selected_peer_info,
        )
        self.btn_header_info.pack(side=tk.LEFT, padx=3)

        self.btn_clear_chat = tk.Button(
            self.header_actions,
            text="🧹 Clear",
            font=("Segoe UI", 8),
            bg=theme["bg_input"],
            fg=theme["fg_secondary"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._clear_current_chat,
        )
        self.btn_clear_chat.pack(side=tk.LEFT, padx=3)

        # Chat Text Box with Scrollbar
        self.txt_frame = tk.Frame(
            self.chat_container,
            bg=theme["chat_bg"],
            bd=0,
            highlightbackground=theme["border"],
            highlightthickness=1,
        )
        self.txt_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_display = tk.Text(
            self.txt_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10),
            bg=theme["chat_bg"],
            fg=theme["fg_main"],
            bd=0,
            padx=10,
            pady=8,
            selectbackground=theme["accent"],
            selectforeground="#ffffff",
        )
        self.scroll = ttk.Scrollbar(self.txt_frame, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=self.scroll.set)

        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Setup Tag Styles for Rich Text Messages
        self._configure_text_tags(theme)

        # Typing Indicator Bar
        self.lbl_typing = tk.Label(
            self.chat_container,
            text="",
            font=("Segoe UI", 9, "italic"),
            bg=theme["bg_main"],
            fg=theme["fg_muted"],
            anchor=tk.W,
        )
        self.lbl_typing.pack(fill=tk.X, pady=(3, 1))

        # Quick Emoji Bar
        self.emoji_frame = tk.Frame(self.chat_container, bg=theme["bg_main"])
        self.emoji_frame.pack(fill=tk.X, pady=(2, 4))

        quick_emojis = ["😀", "😂", "❤️", "👍", "🔥", "🚀", "🎉", "👋", "👀", "📎"]
        for emoji in quick_emojis:
            btn_e = tk.Button(
                self.emoji_frame,
                text=emoji,
                font=("Segoe UI", 9),
                bg=theme["bg_card"],
                fg=theme["fg_main"],
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=1,
                cursor="hand2",
                command=lambda e=emoji: self._insert_emoji(e),
            )
            btn_e.pack(side=tk.LEFT, padx=(0, 3))

        # Message Input Area
        self.input_frame = tk.Frame(self.chat_container, bg=theme["bg_main"])
        self.input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_attach = tk.Button(
            self.input_frame,
            text="📎 Attach",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_input"],
            fg=theme["accent"],
            relief=tk.FLAT,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._send_file_dialog,
        )
        self.btn_attach.pack(side=tk.LEFT, padx=(0, 6))

        self.entry_msg = tk.Entry(
            self.input_frame,
            font=("Segoe UI", 10),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            insertbackground=theme["fg_main"],
            bd=1,
            relief=tk.SOLID,
        )
        self.entry_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), ipady=4)
        self.entry_msg.bind("<Return>", lambda e: self._send_message())
        self.entry_msg.bind("<KeyRelease>", self._on_keystroke)
        self.entry_msg.focus_set()

        self.btn_send = tk.Button(
            self.input_frame,
            text="Send ➔",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=5,
            cursor="hand2",
            command=self._send_message,
        )
        self.btn_send.pack(side=tk.RIGHT)

    def _configure_text_tags(self, theme: dict) -> None:
        """Sets up colored tags for the chat text widget."""
        self.chat_display.tag_config("timestamp", foreground=theme["fg_muted"], font=("Segoe UI", 8))
        self.chat_display.tag_config("self_label", foreground=theme["accent"], font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("peer_label", foreground=theme["accent_green"], font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("dm_label", foreground=theme["accent_pink"], font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("system_label", foreground=theme["accent_yellow"], font=("Segoe UI", 9, "bold"))
        self.chat_display.tag_config("error_label", foreground=theme["accent_red"], font=("Segoe UI", 9, "bold"))
        self.chat_display.tag_config("body", foreground=theme["fg_main"], font=("Segoe UI", 10))
        self.chat_display.tag_config("system_body", foreground=theme["accent_yellow"], font=("Segoe UI", 9, "italic"))

    def _apply_theme(self, theme_key: str) -> None:
        """Dynamically applies the chosen theme palette across all UI widgets."""
        self.current_theme = theme_key
        theme = THEMES[theme_key]

        self.configure(bg=theme["bg_main"])
        self.header_frame.configure(bg=theme["bg_card"])
        self.lbl_logo.configure(bg=theme["bg_card"], fg=theme["accent"])
        self.lbl_status_badge.configure(bg=theme["bg_card"], fg=theme["accent_green"])
        self.lbl_status.configure(bg=theme["bg_card"], fg=theme["fg_secondary"])
        self.btn_settings.configure(bg=theme["bg_input"], fg=theme["fg_main"])
        if hasattr(self, "btn_mobile_web"):
            self.btn_mobile_web.configure(bg=theme["accent"], fg="#ffffff")
        self.btn_downloads.configure(bg=theme["bg_input"], fg=theme["fg_main"])
        self.btn_theme.configure(
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            text="🌙 Dark" if theme_key == "dark" else "☀️ Light",
        )
        self.header_sep.configure(bg=theme["border"])

        self.main_container.configure(bg=theme["bg_main"])
        self.sidebar_frame.configure(bg=theme["bg_sidebar"])
        self.lbl_sidebar_title.configure(bg=theme["bg_sidebar"], fg=theme["fg_main"])
        self.sidebar_footer.configure(bg=theme["bg_sidebar"], fg=theme["fg_muted"])
        self.v_sep.configure(bg=theme["border"])

        # Style Treeview
        self.tree_style.configure(
            "Treeview",
            background=theme["bg_sidebar"],
            foreground=theme["fg_main"],
            fieldbackground=theme["bg_sidebar"],
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        self.tree_style.map(
            "Treeview",
            background=[("selected", theme["bg_input"])],
            foreground=[("selected", theme["accent"])],
        )

        self.chat_container.configure(bg=theme["bg_main"])
        self.chat_header.configure(bg=theme["bg_main"])
        self.header_left.configure(bg=theme["bg_main"])
        self.header_actions.configure(bg=theme["bg_main"])
        self.lbl_chat_title.configure(bg=theme["bg_main"], fg=theme["fg_main"])
        if hasattr(self, "lbl_chat_sub"):
            self.lbl_chat_sub.configure(bg=theme["bg_main"], fg=theme["fg_muted"])
        if hasattr(self, "txt_frame"):
            self.txt_frame.configure(
                bg=theme["chat_bg"],
                highlightbackground=theme["border"],
            )
        self.btn_clear_chat.configure(bg=theme["bg_input"], fg=theme["fg_secondary"])

        self.chat_display.configure(
            bg=theme["chat_bg"],
            fg=theme["fg_main"],
            selectbackground=theme["accent"],
        )
        self._configure_text_tags(theme)

        self.lbl_typing.configure(bg=theme["bg_main"], fg=theme["fg_muted"])
        self.emoji_frame.configure(bg=theme["bg_main"])
        for child in self.emoji_frame.winfo_children():
            if isinstance(child, tk.Button):
                child.configure(bg=theme["bg_card"], fg=theme["fg_main"])

        self.input_frame.configure(bg=theme["bg_main"])
        self.btn_attach.configure(bg=theme["bg_input"], fg=theme["accent"])
        self.entry_msg.configure(
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            insertbackground=theme["fg_main"],
        )
        self.btn_send.configure(bg=theme["accent"], fg="#ffffff")
        if hasattr(self, "btn_p2p"):
            self.btn_p2p.configure(bg=theme["accent_green"], fg="#11111b")
        if hasattr(self, "lbl_chat_sub"):
            self.lbl_chat_sub.configure(bg=theme["bg_main"], fg=theme["fg_muted"])
        if hasattr(self, "btn_header_file"):
            self.btn_header_file.configure(bg=theme["accent"], fg="#ffffff")
        if hasattr(self, "btn_header_info"):
            self.btn_header_info.configure(bg=theme["bg_input"], fg=theme["fg_main"])

        # Re-render active chat
        self._render_current_chat()

    def _toggle_theme(self) -> None:
        """Toggles between Dark and Light mode."""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_theme(new_theme)

    def _insert_emoji(self, emoji_char: str) -> None:
        """Inserts selected emoji at current cursor position in entry box."""
        self.entry_msg.insert(tk.INSERT, emoji_char)
        self.entry_msg.focus_set()

    def _open_downloads_folder(self) -> None:
        """Opens the received files folder in Windows Explorer."""
        dl_dir = config.DEFAULT_DOWNLOAD_DIR
        os.makedirs(dl_dir, exist_ok=True)
        try:
            os.startfile(dl_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Failed opening downloads directory: {e}")

    def _open_mobile_web_dialog(self) -> None:
        """Opens a modal showing the local web URL for mobile phones and laptops."""
        dialog = tk.Toplevel(self)
        dialog.title("📱 Connect Mobile Phone / Other Devices")
        dialog.geometry("520x400")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        theme = THEMES[self.current_theme]
        dialog.configure(bg=theme["bg_main"])

        frame = tk.Frame(dialog, bg=theme["bg_main"], padx=20, pady=18)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="📱 Mobile & Browser LAN Access",
            font=("Segoe UI", 13, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        ).pack(anchor=tk.W, pady=(0, 6))

        tk.Label(
            frame,
            text="Open this URL on any mobile phone, tablet, or laptop connected to your Wi-Fi network (no app install needed):",
            font=("Segoe UI", 9),
            bg=theme["bg_main"],
            fg=theme["fg_secondary"],
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 14))

        url_str = f"http://{self.local_ip}:{self.web_port}"

        url_card = tk.Frame(frame, bg=theme["bg_sidebar"], padx=14, pady=12, bd=1, relief=tk.SOLID)
        url_card.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            url_card,
            text="MOBILE WEB URL:",
            font=("Segoe UI", 8, "bold"),
            bg=theme["bg_sidebar"],
            fg=theme["fg_muted"],
        ).pack(anchor=tk.W)

        url_entry = tk.Entry(
            url_card,
            font=("Consolas", 12, "bold"),
            bg=theme["bg_sidebar"],
            fg=theme["accent"],
            bd=0,
            readonlybackground=theme["bg_sidebar"],
        )
        url_entry.insert(0, url_str)
        url_entry.configure(state="readonly")
        url_entry.pack(fill=tk.X, pady=(4, 0))

        # Instructions / Feature list
        tips = (
            "✅ 1. Connect your phone to the same Wi-Fi or Mobile Hotspot\n"
            "✅ 2. Open Chrome, Safari, or Firefox on your phone\n"
            "✅ 3. Type or paste the URL above into the address bar\n"
            "✅ 4. Join chat, send group/direct messages & upload photos/files"
        )
        tk.Label(
            frame,
            text=tips,
            font=("Segoe UI", 9),
            bg=theme["bg_main"],
            fg=theme["fg_secondary"],
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 16))

        btn_box = tk.Frame(frame, bg=theme["bg_main"])
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)

        def copy_url():
            self.clipboard_clear()
            self.clipboard_append(url_str)
            btn_copy.config(text="✅ Copied!", bg=theme["accent_green"])
            dialog.after(2000, lambda: btn_copy.config(text="📋 Copy URL", bg=theme["accent"]))

        btn_copy = tk.Button(
            btn_box,
            text="📋 Copy URL",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=copy_url,
        )
        btn_copy.pack(side=tk.LEFT, padx=(0, 8))

        btn_browse = tk.Button(
            btn_box,
            text="🌐 Open in Browser",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=lambda: webbrowser.open(url_str),
        )
        btn_browse.pack(side=tk.LEFT)

        tk.Button(
            btn_box,
            text="Close",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=dialog.destroy,
        ).pack(side=tk.RIGHT)

    def _on_peer_double_click(self, event: tk.Event) -> None:
        """Opens direct chat immediately on double click."""
        item = self.peer_tree.identify_row(event.y)
        if item:
            self.peer_tree.selection_set(item)
            self._on_peer_selected()
            self.entry_msg.focus_set()

    def _show_peer_context_menu(self, event: tk.Event) -> None:
        """Shows right-click options menu for selected peer in directory."""
        item_id = self.peer_tree.identify_row(event.y)
        if not item_id:
            return
        self.peer_tree.selection_set(item_id)
        self._on_peer_selected()

        menu = tk.Menu(self, tearoff=0)
        theme = THEMES[self.current_theme]
        menu.configure(
            bg=theme["bg_card"],
            fg=theme["fg_main"],
            activebackground=theme["accent"],
            activeforeground="#ffffff",
        )

        if item_id == self.group_item_id:
            menu.add_command(label="💬 Open Group Broadcast", command=self._on_peer_selected)
            menu.add_command(label="📁 Share File to Group", command=self._send_file_dialog)
            menu.add_separator()
            menu.add_command(label="🔗 Direct P2P Connect...", command=self._open_p2p_connect_dialog)
        else:
            peer = self.peers.get(item_id)
            peer_name = peer.username if peer else "Peer"
            menu.add_command(label=f"💬 Direct P2P Chat with {peer_name}", command=self._on_peer_selected)
            menu.add_command(label=f"📁 Send File P2P to {peer_name}...", command=self._send_file_dialog)
            menu.add_separator()
            menu.add_command(label=f"ℹ️ Peer Connection Details", command=lambda: self._show_selected_peer_info(item_id))
            menu.add_command(label=f"🔄 Test Connection (Ping)", command=lambda: self._ping_peer(item_id))
            menu.add_separator()
            menu.add_command(label="🧹 Clear Conversation", command=self._clear_current_chat)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_selected_peer_info(self, peer_id: Optional[str] = None) -> None:
        """Displays connection diagnostics and protocol metadata for selected peer."""
        target_id = peer_id or self.selected_peer_id
        if not target_id or target_id not in self.peers:
            messagebox.showinfo("Peer Info", "Select an active peer from the directory to view connection details.")
            return

        peer = self.peers[target_id]
        ptype = "Mobile Web / Gateway Client" if getattr(peer, "is_web", False) else "Raw TCP Direct Socket Peer"

        info_text = (
            f"👤 Username: {peer.username}\n"
            f"🆔 Peer ID: {peer.peer_id}\n"
            f"💻 Device: {peer.device_name}\n"
            f"🌐 IP Address: {peer.ip_address}\n"
            f"🔌 Port: {peer.tcp_port if peer.tcp_port else self.web_port} ({ptype})\n"
            f"🟢 Status: {peer.status}\n"
            f"📡 Connection Type: {'HTTP Web Stream' if getattr(peer, 'is_web', False) else 'P2P TCP Stream'}\n"
            f"📁 Direct File Sharing: Supported\n"
            f"🔒 Private Direct Messaging: Active"
        )
        messagebox.showinfo(f"Connection Details — {peer.username}", info_text)

    def _ping_peer(self, peer_id: str) -> None:
        """Pings a direct peer to measure round-trip connection health."""
        if peer_id not in self.peers:
            return
        peer = self.peers[peer_id]
        if getattr(peer, "is_web", False):
            self._append_message(peer_id, "System", f"Peer '{peer.username}' is connected via Web Gateway (Active).", category="system")
            return

        t0 = time.time()
        packet = Packet(
            type=MessageType.TYPING,
            sender_id=self.peer_id,
            sender_name=self.username,
            payload={"channel": self.selected_peer_id, "ping": True},
        )

        def worker():
            success = TCPClient.send_message(peer.ip_address, peer.tcp_port, packet.to_dict())
            rtt = int((time.time() - t0) * 1000)
            if success:
                self.ui_queue.put(("PING_RESULT", peer_id, f"Ping to '{peer.username}' ({peer.ip_address}): Success ({rtt}ms RTT). Direct P2P active."))
            else:
                self.ui_queue.put(("PING_RESULT", peer_id, f"Ping to '{peer.username}' ({peer.ip_address}) failed. Peer may be unreachable."))

        threading.Thread(target=worker, daemon=True).start()

    def _open_p2p_connect_dialog(self) -> None:
        """Opens Direct Peer-to-Peer Connection Hub dialog for manual connect and 1-click P2P."""
        dialog = tk.Toplevel(self)
        dialog.title("🔗 Direct Peer-to-Peer (P2P) Connection Hub")
        dialog.geometry("540x530")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        theme = THEMES[self.current_theme]
        dialog.configure(bg=theme["bg_main"])

        frame = tk.Frame(dialog, bg=theme["bg_main"], padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="🔗 Direct Peer-to-Peer (P2P) Connection Hub",
            font=("Segoe UI", 12, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        ).pack(anchor=tk.W, pady=(0, 4))

        tk.Label(
            frame,
            text="Connect directly to any peer on this LAN via raw TCP socket or Web Gateway.",
            font=("Segoe UI", 9),
            bg=theme["bg_main"],
            fg=theme["fg_secondary"],
        ).pack(anchor=tk.W, pady=(0, 10))

        # Section 1: Discovered Online Peers
        lbl_sec1 = tk.Label(
            frame,
            text=f"Active Discovered Peers ({len(self.peers)}):",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_main"],
            fg=theme["accent"],
        )
        lbl_sec1.pack(anchor=tk.W, pady=(4, 4))

        peers_frame = tk.Frame(frame, bg=theme["bg_sidebar"], bd=1, relief=tk.SOLID, height=150)
        peers_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        p_canvas = tk.Canvas(peers_frame, bg=theme["bg_sidebar"], bd=0, highlightthickness=0)
        p_scrollbar = ttk.Scrollbar(peers_frame, orient="vertical", command=p_canvas.yview)
        p_scrollable = tk.Frame(p_canvas, bg=theme["bg_sidebar"])

        p_scrollable.bind(
            "<Configure>",
            lambda e: p_canvas.configure(scrollregion=p_canvas.bbox("all")),
        )
        p_canvas.create_window((0, 0), window=p_scrollable, anchor="nw", width=480)
        p_canvas.configure(yscrollcommand=p_scrollbar.set)
        p_canvas.pack(side="left", fill="both", expand=True)
        p_scrollbar.pack(side="right", fill="y")

        if not self.peers:
            tk.Label(
                p_scrollable,
                text="No other peers discovered yet.\nUse Manual Connect below to link directly by IP:Port.",
                font=("Segoe UI", 9, "italic"),
                bg=theme["bg_sidebar"],
                fg=theme["fg_muted"],
                pady=16,
            ).pack()
        else:
            for pid, peer in self.peers.items():
                p_row = tk.Frame(p_scrollable, bg=theme["bg_card"], padx=8, pady=6)
                p_row.pack(fill=tk.X, padx=4, pady=3)

                icon = "📱" if getattr(peer, "is_web", False) else "🟢"
                ptype = "Mobile / Web" if getattr(peer, "is_web", False) else f"TCP {peer.tcp_port}"

                tk.Label(
                    p_row,
                    text=f"{icon} {peer.username}",
                    font=("Segoe UI", 9, "bold"),
                    bg=theme["bg_card"],
                    fg=theme["fg_main"],
                ).pack(side=tk.LEFT)

                tk.Label(
                    p_row,
                    text=f"({peer.ip_address} | {ptype})",
                    font=("Segoe UI", 8),
                    bg=theme["bg_card"],
                    fg=theme["fg_muted"],
                ).pack(side=tk.LEFT, padx=6)

                def make_chat_cb(p_id=pid):
                    def cb():
                        dialog.destroy()
                        self.selected_peer_id = p_id
                        self.peer_tree.selection_set(p_id)
                        self._on_peer_selected()
                        self.entry_msg.focus_set()
                    return cb

                def make_file_cb(p_id=pid):
                    def cb():
                        dialog.destroy()
                        self.selected_peer_id = p_id
                        self.peer_tree.selection_set(p_id)
                        self._on_peer_selected()
                        self._send_file_dialog()
                    return cb

                tk.Button(
                    p_row,
                    text="💬 Chat",
                    font=("Segoe UI", 8, "bold"),
                    bg=theme["accent"],
                    fg="#ffffff",
                    relief=tk.FLAT,
                    padx=6,
                    pady=1,
                    cursor="hand2",
                    command=make_chat_cb(),
                ).pack(side=tk.RIGHT, padx=2)

                tk.Button(
                    p_row,
                    text="📁 File",
                    font=("Segoe UI", 8),
                    bg=theme["bg_input"],
                    fg=theme["fg_main"],
                    relief=tk.FLAT,
                    padx=6,
                    pady=1,
                    cursor="hand2",
                    command=make_file_cb(),
                ).pack(side=tk.RIGHT, padx=2)

        # Section 2: Manual Direct P2P Connect
        tk.Label(
            frame,
            text="⚡ Manual Direct Connect (Bypass UDP / Connect by IP:Port):",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_main"],
            fg=theme["accent_green"],
        ).pack(anchor=tk.W, pady=(4, 2))

        manual_box = tk.Frame(frame, bg=theme["bg_main"])
        manual_box.pack(fill=tk.X, pady=(0, 10))

        entry_ip = tk.Entry(
            manual_box,
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            insertbackground=theme["fg_main"],
        )
        entry_ip.insert(0, f"127.0.0.1:{config.DEFAULT_TCP_PORT}")
        entry_ip.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)

        lbl_feedback = tk.Label(frame, text="", font=("Segoe UI", 8), bg=theme["bg_main"])
        lbl_feedback.pack(anchor=tk.W, pady=(0, 8))

        def do_manual_connect():
            target_str = entry_ip.get().strip()
            if not target_str:
                return
            btn_connect.config(state=tk.DISABLED, text="Connecting...")
            lbl_feedback.config(text=f"Connecting to {target_str}...", fg=theme["accent"])

            def worker():
                try:
                    if ":" in target_str:
                        ip, port_str = target_str.split(":", 1)
                        port = int(port_str.strip())
                    else:
                        ip = target_str.strip()
                        port = config.DEFAULT_TCP_PORT

                    if ip in (self.local_ip, "127.0.0.1", "localhost") and port == self.actual_tcp_port:
                        self.after(0, lambda: on_fail("Cannot connect to yourself (own IP and Port)."))
                        return

                    packet = Packet(
                        type=MessageType.HEARTBEAT,
                        sender_id=self.peer_id,
                        sender_name=self.username,
                        payload={
                            "device_name": self.device_name,
                            "tcp_port": self.actual_tcp_port,
                            "ip_address": self.local_ip,
                            "manual": True,
                        },
                    )
                    success = TCPClient.send_message(ip, port, packet.to_dict())
                    if success:
                        self.after(0, lambda: on_success(ip, port))
                    else:
                        self.after(0, lambda: on_fail(f"Could not reach TCP port at {ip}:{port}. Check IP/Port and firewall."))
                except Exception as ex:
                    self.after(0, lambda: on_fail(str(ex)))

            def on_success(ip, port):
                lbl_feedback.config(text=f"✅ Handshake sent to {ip}:{port}! Direct P2P active.", fg=theme["accent_green"])
                btn_connect.config(state=tk.NORMAL, text="⚡ Connect Directly")
                dialog.after(1500, dialog.destroy)

            def on_fail(err_msg):
                lbl_feedback.config(text=f"❌ {err_msg}", fg=theme["accent_red"])
                btn_connect.config(state=tk.NORMAL, text="⚡ Connect Directly")

            threading.Thread(target=worker, daemon=True).start()

        btn_connect = tk.Button(
            manual_box,
            text="⚡ Connect Directly",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent_green"],
            fg="#11111b",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=do_manual_connect,
        )
        btn_connect.pack(side=tk.RIGHT)

        btn_close = tk.Button(
            frame,
            text="Close",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
            command=dialog.destroy,
        )
        btn_close.pack(side=tk.BOTTOM, anchor=tk.E)

    def manual_connect_peer(self, target_str: str) -> bool:
        """Manually connects to a peer by IP:Port over TCP and exchanges presence."""
        if not target_str:
            return False
        try:
            if ":" in target_str:
                ip, port_str = target_str.split(":", 1)
                port = int(port_str.strip())
            else:
                ip = target_str.strip()
                port = config.DEFAULT_TCP_PORT

            # Prevent connecting to self
            if ip in (self.local_ip, "127.0.0.1", "localhost") and port == self.actual_tcp_port:
                return False

            packet = Packet(
                type=MessageType.HEARTBEAT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={
                    "device_name": self.device_name,
                    "tcp_port": self.actual_tcp_port,
                    "ip_address": self.local_ip,
                    "manual": True,
                },
            )
            return TCPClient.send_message(ip, port, packet.to_dict())
        except Exception:
            return False

    def _open_settings_dialog(self) -> None:
        """Opens settings modal to modify username and preferences."""
        dialog = tk.Toplevel(self)
        dialog.title("⚙️ Simple LAN Chat — Settings")
        dialog.geometry("440x360")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        theme = THEMES[self.current_theme]
        dialog.configure(bg=theme["bg_main"])

        frame = tk.Frame(dialog, bg=theme["bg_main"], padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="Settings & Preferences",
            font=("Segoe UI", 12, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        ).pack(anchor=tk.W, pady=(0, 12))

        # Username Change
        tk.Label(
            frame,
            text="Chat Display Name:",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        ).pack(anchor=tk.W)

        name_entry = tk.Entry(
            frame,
            font=("Segoe UI", 10),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            insertbackground=theme["fg_main"],
        )
        name_entry.insert(0, self.username)
        name_entry.pack(fill=tk.X, pady=(3, 10), ipady=3)

        # Sound Toggle
        sound_var = tk.BooleanVar(value=self.sound_enabled)
        chk_sound = tk.Checkbutton(
            frame,
            text="Enable Sound Alerts on Incoming Messages",
            variable=sound_var,
            font=("Segoe UI", 9),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
            activebackground=theme["bg_main"],
            activeforeground=theme["accent"],
            selectcolor=theme["bg_input"],
        )
        chk_sound.pack(anchor=tk.W, pady=(0, 12))

        # Network Info Display
        tk.Label(
            frame,
            text="Network Diagnostics:",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_main"],
            fg=theme["fg_main"],
        ).pack(anchor=tk.W)

        info_box = tk.Text(
            frame,
            height=5,
            font=("Consolas", 8),
            bg=theme["bg_sidebar"],
            fg=theme["fg_secondary"],
            bd=0,
            padx=6,
            pady=6,
        )
        info_box.insert(
            tk.END,
            f"Peer ID:       {self.peer_id}\n"
            f"Device Name:   {self.device_name}\n"
            f"Local IP:      {self.local_ip}\n"
            f"TCP Port:      {self.actual_tcp_port}\n"
            f"Mobile Web:    http://{self.local_ip}:{getattr(self, 'web_port', '8080')}\n"
            f"Active Peers:  {len(self.peers)}",
        )
        info_box.config(state=tk.DISABLED)
        info_box.pack(fill=tk.X, pady=(3, 16))

        def save_settings():
            new_name = name_entry.get().strip()
            if new_name and new_name != self.username:
                self.username = new_name
                self.discovery_engine.update_username(new_name)
                self.title(f"{config.APP_NAME} — {self.username} ({self.local_ip}:{self.actual_tcp_port})")
                self.lbl_status.config(
                    text=f"👤 {self.username} | 🌐 {self.local_ip}:{self.actual_tcp_port}"
                )
                self._append_message(
                    self.selected_peer_id,
                    "System",
                    f"Display name updated to '{self.username}'.",
                    category="system",
                )

            self.sound_enabled = sound_var.get()
            dialog.destroy()

        btn_box = tk.Frame(frame, bg=theme["bg_main"])
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_box,
            text="Save Changes",
            font=("Segoe UI", 9, "bold"),
            bg=theme["accent"],
            fg="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=save_settings,
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 9),
            bg=theme["bg_input"],
            fg=theme["fg_main"],
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=dialog.destroy,
        ).pack(side=tk.RIGHT)

    def _on_peer_selected(self, event: tk.Event) -> None:
        """Handles selection change in left treeview to switch active chat channel."""
        selected_items = self.peer_tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0]
        if item_id == self.group_item_id:
            self.selected_peer_id = None
            self.lbl_chat_title.config(text="💬 Group Broadcast Chat")
            if hasattr(self, "lbl_chat_sub"):
                self.lbl_chat_sub.config(text="🌐 Public Room — Messages broadcast to all online peers")
            if hasattr(self, "btn_header_file"):
                self.btn_header_file.config(text="📁 Share File")
            if hasattr(self, "btn_header_info"):
                self.btn_header_info.config(state=tk.DISABLED)
        else:
            self.selected_peer_id = item_id
            if hasattr(self, "btn_header_info"):
                self.btn_header_info.config(state=tk.NORMAL)
            if item_id in self.peers:
                peer = self.peers[item_id]
                icon = "📱 Mobile DM" if getattr(peer, "is_web", False) else "🔒 Direct P2P Chat"
                sub = (
                    f"📱 Mobile Web / Gateway Client ({peer.ip_address})"
                    if getattr(peer, "is_web", False)
                    else f"🟢 Direct TCP P2P ({peer.ip_address}:{peer.tcp_port}) — Direct Stream Channel"
                )
                self.lbl_chat_title.config(text=f"{icon}: {peer.username}")
                if hasattr(self, "lbl_chat_sub"):
                    self.lbl_chat_sub.config(text=sub)
                if hasattr(self, "btn_header_file"):
                    self.btn_header_file.config(text="📁 Send File P2P")

        # Clear unread counter for selected channel
        self.unread_counts[self.selected_peer_id] = 0
        self._refresh_tree_item_label(self.selected_peer_id)
        self._render_current_chat()

    def _refresh_tree_item_label(self, channel_id: Optional[str]) -> None:
        """Updates treeview text with online status and unread message badges."""
        if channel_id is None:
            unread = self.unread_counts.get(None, 0)
            badge = f" ({unread})" if unread > 0 else ""
            self.peer_tree.item(self.group_item_id, text=f"🌐 Group Broadcast Chat{badge}")
        else:
            if channel_id in self.peers and self.peer_tree.exists(channel_id):
                peer = self.peers[channel_id]
                unread = self.unread_counts.get(channel_id, 0)
                badge = f" 🔴 ({unread})" if unread > 0 else ""
                icon = "📱" if getattr(peer, "is_web", False) else "🟢"
                self.peer_tree.item(
                    channel_id, text=f"{icon} {peer.username} ({peer.device_name}){badge}"
                )

    def _render_current_chat(self) -> None:
        """Clears chat display and redraws message history for active channel."""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)

        history = self.chat_histories.get(self.selected_peer_id, [])
        for entry in history:
            self._write_entry_to_display(entry)

        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def _write_entry_to_display(self, entry: dict) -> None:
        """Helper to format and write a single message record into chat_display."""
        timestamp = entry.get("timestamp", time.strftime("%H:%M:%S"))
        sender = entry.get("sender", "Unknown")
        message = entry.get("message", "")
        category = entry.get("category", "peer")

        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")

        if category == "system":
            self.chat_display.insert(tk.END, "ℹ️ System: ", "system_label")
            self.chat_display.insert(tk.END, f"{message}\n", "system_body")
        elif category == "error":
            self.chat_display.insert(tk.END, "⚠️ Error: ", "error_label")
            self.chat_display.insert(tk.END, f"{message}\n", "body")
        elif category == "self":
            self.chat_display.insert(tk.END, f"{sender}: ", "self_label")
            self.chat_display.insert(tk.END, f"{message}\n", "body")
        elif category == "dm":
            self.chat_display.insert(tk.END, f"🔒 {sender}: ", "dm_label")
            self.chat_display.insert(tk.END, f"{message}\n", "body")
        else:
            self.chat_display.insert(tk.END, f"{sender}: ", "peer_label")
            self.chat_display.insert(tk.END, f"{message}\n", "body")

    def _append_message(
        self,
        channel_id: Optional[str],
        sender: str,
        message: str,
        category: str = "peer",
        sender_id: Optional[str] = None,
        msg_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Appends a message to channel history and updates UI with badge/sound if unread."""
        now = time.time()
        timestamp = time.strftime("%H:%M:%S", time.localtime(now))
        effective_sender_id = sender_id or (self.peer_id if (category in ("self", "file") and "You" in sender) else None)
        entry_id = msg_id or f"{now}_{uuid.uuid4().hex[:6]}"

        if channel_id not in self.chat_histories:
            self.chat_histories[channel_id] = []

        # Deduplication: ignore if this message entry ID is already present
        if any(e.get("id") == entry_id for e in self.chat_histories[channel_id]):
            return

        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "timestamp_epoch": now,
            "sender": sender,
            "sender_id": effective_sender_id,
            "message": message,
            "category": category,
            "channel": channel_id,
        }

        self.chat_histories[channel_id].append(entry)

        # Check if message is incoming from another peer
        is_incoming = category in ("peer", "dm", "file") and effective_sender_id != self.peer_id and "You" not in sender

        # If currently looking at this channel, render immediately
        if self.selected_peer_id == channel_id:
            self.chat_display.config(state=tk.NORMAL)
            self._write_entry_to_display(entry)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)

            if is_incoming:
                try:
                    is_unfocused = (self.focus_get() is None or self.state() == "iconic")
                except Exception:
                    is_unfocused = False

                if is_unfocused:
                    title = f"🔒 Private from {sender}" if channel_id is not None else f"💬 Group from {sender}"
                    self._notify_desktop_user(title, message, channel_id)
                elif self.sound_enabled:
                    self._play_notification_sound(is_dm=(channel_id is not None))
        else:
            # Unread message in background channel
            self.unread_counts[channel_id] = self.unread_counts.get(channel_id, 0) + 1
            self._refresh_tree_item_label(channel_id)
            if is_incoming:
                title = f"🔒 Private from {sender}" if channel_id is not None else f"💬 Group from {sender}"
                self._notify_desktop_user(title, message, channel_id)

    def _play_notification_sound(self, is_dm: bool = False) -> None:
        """Plays standard OS notification sound."""
        if not self.sound_enabled:
            return
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION if is_dm else winsound.MB_ICONASTERISK)
        except Exception:
            try:
                self.bell()
            except Exception:
                pass

    def _notify_desktop_user(self, title: str, message: str, channel_id: Optional[str] = None) -> None:
        """Alerts desktop user with sound, taskbar flash, and floating toast."""
        is_dm = channel_id is not None
        self._play_notification_sound(is_dm=is_dm)

        # Flash Windows taskbar button when window is inactive
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            ctypes.windll.user32.FlashWindow(hwnd, True)
        except Exception:
            try:
                self.bell()
            except Exception:
                pass

        # Floating non-intrusive notification toast
        self._show_inapp_toast(title, message, channel_id)

    def _show_inapp_toast(self, title: str, message: str, channel_id: Optional[str] = None) -> None:
        """Displays a modern floating toast card in the top-right corner."""
        theme = THEMES[self.current_theme]
        if hasattr(self, "_active_toast") and self._active_toast:
            try:
                self._active_toast.destroy()
            except Exception:
                pass

        # Modern floating non-intrusive notification toast
        toast = tk.Frame(
            self,
            bg=theme["bg_card"],
            bd=0,
            highlightbackground=theme["accent"],
            highlightthickness=1,
            padx=14,
            pady=10,
            cursor="hand2",
        )
        self._active_toast = toast

        def on_click(event=None):
            toast.destroy()
            self._active_toast = None
            if channel_id is None:
                self.peer_tree.selection_set("")
                self.selected_peer_id = None
                self._on_peer_selected(None)
            else:
                if self.peer_tree.exists(channel_id):
                    self.peer_tree.selection_set(channel_id)
                    self.selected_peer_id = channel_id
                    self._on_peer_selected(None)

        toast.bind("<Button-1>", on_click)

        lbl_t = tk.Label(
            toast,
            text=f"🔔 {title}",
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg_card"],
            fg=theme["accent"],
            anchor=tk.W,
        )
        lbl_t.pack(fill=tk.X)
        lbl_t.bind("<Button-1>", on_click)

        preview = (message[:50] + "...") if len(message) > 50 else message
        lbl_m = tk.Label(
            toast,
            text=preview,
            font=("Segoe UI", 8),
            bg=theme["bg_card"],
            fg=theme["fg_main"],
            anchor=tk.W,
        )
        lbl_m.pack(fill=tk.X, pady=(2, 0))
        lbl_m.bind("<Button-1>", on_click)

        # Place toast cleanly in bottom-right corner to never cover chat header controls
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)

        def auto_dismiss():
            try:
                if hasattr(self, "_active_toast") and self._active_toast == toast:
                    toast.destroy()
                    self._active_toast = None
            except Exception:
                pass

        self.after(5000, auto_dismiss)

    def _clear_current_chat(self) -> None:
        """Clears the message history of the currently viewed channel."""
        self.chat_histories[self.selected_peer_id] = []
        self._render_current_chat()
        self._append_message(self.selected_peer_id, "System", "Chat history cleared.", category="system")

    def _on_keystroke(self, event: tk.Event) -> None:
        """Detects keystrokes in entry box and sends debounced typing indicator."""
        if event.keysym in ("Return", "BackSpace", "Delete", "Escape", "Up", "Down", "Left", "Right"):
            return

        now = time.time()
        if now - self._last_typing_sent > 2.5:
            self._last_typing_sent = now
            packet = Packet(
                type=MessageType.TYPING,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"channel": self.selected_peer_id},
            )
            if self.selected_peer_id is None:
                peers_info = [
                    (p.ip_address, p.tcp_port)
                    for p in self.peers.values()
                    if not getattr(p, "is_web", False)
                    and p.tcp_port > 0
                    and p.peer_id != self.peer_id
                    and not (p.ip_address in (self.local_ip, "127.0.0.1", "localhost") and p.tcp_port == self.actual_tcp_port)
                ]
                if peers_info:
                    threading.Thread(
                        target=TCPClient.broadcast_message, args=(peers_info, packet.to_dict()), daemon=True
                    ).start()
            else:
                peer = self.peers.get(self.selected_peer_id)
                if peer and not getattr(peer, "is_web", False) and peer.tcp_port > 0:
                    threading.Thread(
                        target=TCPClient.send_message,
                        args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                        daemon=True,
                    ).start()

    def _send_message(self) -> None:
        """Sends chat message or processes slash commands from entry box."""
        text = self.entry_msg.get().strip()
        if not text:
            return

        self.entry_msg.delete(0, tk.END)

        # Handle Slash Commands
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        if self.selected_peer_id is None:
            # Group Broadcast
            packet = Packet(
                type=MessageType.GROUP_CHAT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"text": text},
            )
            # Track our own packet ID so we never duplicate
            self.seen_message_ids.add(packet.msg_id)

            peers_info = [
                (p.ip_address, p.tcp_port)
                for p in self.peers.values()
                if not getattr(p, "is_web", False)
                and p.peer_id != self.peer_id
                and not (p.ip_address in (self.local_ip, "127.0.0.1", "localhost") and p.tcp_port == self.actual_tcp_port)
            ]
            if peers_info:
                threading.Thread(
                    target=TCPClient.broadcast_message, args=(peers_info, packet.to_dict()), daemon=True
                ).start()

            self._append_message(None, f"You (Group)", text, category="self", msg_id=packet.msg_id)
        else:
            # Direct Peer Message
            peer = self.peers.get(self.selected_peer_id)
            if not peer:
                self._append_message(self.selected_peer_id, "Error", "Selected peer is no longer online.", category="error")
                return

            if getattr(peer, "is_web", False):
                # Web / Mobile peer: save to DM history where mobile client receives it via real-time polling
                self._append_message(self.selected_peer_id, f"You -> {peer.username}", text, category="self")
            else:
                # Regular LAN TCP desktop peer
                packet = Packet(
                    type=MessageType.CHAT,
                    sender_id=self.peer_id,
                    sender_name=self.username,
                    payload={"text": text},
                )
                threading.Thread(
                    target=TCPClient.send_message,
                    args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                    daemon=True,
                ).start()

                self._append_message(self.selected_peer_id, f"You -> {peer.username}", text, category="self")

    def _handle_slash_command(self, cmd_line: str) -> None:
        """Parses and executes client-side slash commands."""
        parts = cmd_line.split(" ", 1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            help_text = (
                "💡 Available Commands:\n"
                "  /mobile        - Show Mobile Web access URL\n"
                "  /nick <name>   - Change your chat display name\n"
                "  /users         - View all online peers and their IPs\n"
                "  /open          - Open received downloads folder\n"
                "  /clear         - Clear message history in current channel\n"
                "  /shrug         - Send ¯\\_(ツ)_/¯\n"
                "  /help          - Show this help message"
            )
            self._append_message(self.selected_peer_id, "System", help_text, category="system")

        elif command == "/mobile":
            self._append_message(
                self.selected_peer_id,
                "System",
                f"📱 Mobile Web URL: http://{self.local_ip}:{self.web_port}\nOpen in browser on your phone connected to this Wi-Fi network.",
                category="system",
            )

        elif command == "/nick":
            if not arg:
                self._append_message(self.selected_peer_id, "System", "Usage: /nick <new_name>", category="system")
                return
            old_name = self.username
            self.username = arg
            self.discovery_engine.update_username(arg)
            self.title(f"{config.APP_NAME} — {self.username} ({self.local_ip}:{self.actual_tcp_port})")
            self.lbl_status.config(text=f"👤 {self.username} | 🌐 {self.local_ip}:{self.actual_tcp_port}")
            self._append_message(self.selected_peer_id, "System", f"Changed display name from '{old_name}' to '{self.username}'.", category="system")

        elif command == "/users":
            if not self.peers:
                self._append_message(self.selected_peer_id, "System", "No other peers currently online.", category="system")
            else:
                user_list = [f"• {p.username} ({p.device_name}) — {p.ip_address}:{p.tcp_port}" for p in self.peers.values()]
                self._append_message(self.selected_peer_id, "System", f"Online Peers ({len(self.peers)}):\n" + "\n".join(user_list), category="system")

        elif command == "/clear":
            self._clear_current_chat()

        elif command == "/open":
            self._open_downloads_folder()

        elif command == "/shrug":
            self.entry_msg.insert(0, "¯\\_(ツ)_/¯")
            self._send_message()

        else:
            self._append_message(self.selected_peer_id, "System", f"Unknown command '{command}'. Type /help for available commands.", category="system")

    def _send_file_dialog(self) -> None:
        """Opens file picker dialog to initiate file transfer to desktop or mobile peers."""
        filepath_str = filedialog.askopenfilename(title="Select File to Send")
        if not filepath_str:
            return

        filepath = Path(filepath_str)
        filesize = filepath.stat().st_size
        filename = filepath.name

        # Case 1: Group Broadcast Chat -> Share via local LAN Web link to all devices
        if self.selected_peer_id is None:
            dest_dir = config.DEFAULT_DOWNLOAD_DIR
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = dest_dir / filename
            try:
                import shutil
                if filepath.resolve() != dest_path.resolve():
                    shutil.copy2(filepath, dest_path)
            except Exception:
                pass

            download_url = f"http://{self.local_ip}:{self.web_port}/downloads/{urllib.parse.quote(filename)}"
            notice = f"📎 Shared file: {filename} ({filesize} bytes)\nDownload / View: {download_url}"

            packet = Packet(
                type=MessageType.GROUP_CHAT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"text": notice},
            )
            self.seen_message_ids.add(packet.msg_id)

            peers_info = [
                (p.ip_address, p.tcp_port)
                for p in self.peers.values()
                if not getattr(p, "is_web", False)
                and p.peer_id != self.peer_id
                and not (p.ip_address in (self.local_ip, "127.0.0.1", "localhost") and p.tcp_port == self.actual_tcp_port)
            ]
            if peers_info:
                threading.Thread(
                    target=TCPClient.broadcast_message, args=(peers_info, packet.to_dict()), daemon=True
                ).start()

            self._append_message(None, f"You (Group)", notice, category="file", msg_id=packet.msg_id)
            return

        peer = self.peers.get(self.selected_peer_id)
        if not peer:
            return

        # Case 2: Direct peer is a Mobile / Web client -> Share via local LAN Web link privately
        if getattr(peer, "is_web", False):
            dest_dir = config.DEFAULT_DOWNLOAD_DIR
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = dest_dir / filename
            try:
                import shutil
                if filepath.resolve() != dest_path.resolve():
                    shutil.copy2(filepath, dest_path)
            except Exception:
                pass

            download_url = f"http://{self.local_ip}:{self.web_port}/downloads/{urllib.parse.quote(filename)}"
            notice = f"📎 Shared file: {filename} ({filesize} bytes)\nDownload / View: {download_url}"

            self._append_message(self.selected_peer_id, f"You -> {peer.username}", notice, category="file")
            return

        # Case 3: Regular LAN TCP desktop peer -> P2P Binary Stream
        checksum = FileSender.calculate_sha256(filepath)
        self.pending_outgoing_files[filepath.name] = filepath

        packet = Packet(
            type=MessageType.FILE_REQUEST,
            sender_id=self.peer_id,
            sender_name=self.username,
            payload={
                "filename": filepath.name,
                "filesize": filesize,
                "sha256": checksum,
                "tcp_port": self.actual_tcp_port,
            },
        )

        self._append_message(
            self.selected_peer_id,
            "System",
            f"Sending file request for '{filepath.name}' ({filesize} bytes)...",
            category="system",
        )

        threading.Thread(
            target=TCPClient.send_message,
            args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
            daemon=True,
        ).start()

    # Network Thread Event Callbacks
    def register_web_peer(self, client_id: str, username: str, ip_address: str) -> None:
        """Registers or updates an active mobile/web client into the peer directory."""
        peer = Peer(
            peer_id=client_id,
            username=username,
            device_name="Mobile / Web",
            ip_address=ip_address,
            tcp_port=0,
            status="Online",
            is_web=True,
        )
        self.ui_queue.put(("PEER_UPDATED", peer))

    def remove_web_peer(self, client_id: str) -> None:
        """Removes a disconnected mobile/web client."""
        self.ui_queue.put(("PEER_REMOVED", client_id))

    def _on_peer_updated(self, peer: Peer) -> None:
        if peer.peer_id == self.peer_id:
            return
        if peer.ip_address in (self.local_ip, "127.0.0.1") and peer.tcp_port == self.actual_tcp_port:
            return
        self.ui_queue.put(("PEER_UPDATED", peer))

    def _on_peer_removed(self, peer_id: str) -> None:
        self.ui_queue.put(("PEER_REMOVED", peer_id))

    def _on_tcp_message_received(self, payload: dict, client_ip: str) -> None:
        self.ui_queue.put(("TCP_MSG", payload, client_ip))

    def _poll_ui_queue(self) -> None:
        """Polls background network events and updates GUI widgets safely."""
        try:
            while True:
                item = self.ui_queue.get_nowait()
                event_type = item[0]

                if event_type == "PEER_UPDATED":
                    peer: Peer = item[1]
                    # Never add self into peer directory
                    if peer.peer_id == self.peer_id:
                        continue
                    if peer.ip_address in (self.local_ip, "127.0.0.1") and peer.tcp_port == self.actual_tcp_port:
                        continue

                    self.peers[peer.peer_id] = peer
                    self.lbl_sidebar_title.config(text=f"👥 Active Peers ({len(self.peers)})")

                    icon = "📱" if getattr(peer, "is_web", False) else "🟢"
                    if not self.peer_tree.exists(peer.peer_id):
                        self.peer_tree.insert(
                            "",
                            tk.END,
                            iid=peer.peer_id,
                            text=f"{icon} {peer.username} ({peer.device_name})",
                        )
                        self._append_message(
                            None,
                            "System",
                            f"Peer '{peer.username}' joined the local network.",
                            category="system",
                        )
                    else:
                        self._refresh_tree_item_label(peer.peer_id)

                elif event_type == "PEER_REMOVED":
                    peer_id: str = item[1]
                    if peer_id in self.peers:
                        removed_peer = self.peers.pop(peer_id)
                        self.lbl_sidebar_title.config(text=f"👥 Active Peers ({len(self.peers)})")
                        if self.peer_tree.exists(peer_id):
                            self.peer_tree.delete(peer_id)
                        self._append_message(
                            None,
                            "System",
                            f"Peer '{removed_peer.username}' went offline.",
                            category="system",
                        )

                elif event_type == "TCP_MSG":
                    payload, client_ip = item[1], item[2]
                    packet = Packet.from_dict(payload)

                    # 1. Ignore packets sent by ourselves (prevent echo / loopback)
                    if packet.sender_id == self.peer_id:
                        continue

                    # 2. Ignore packets already seen (deduplication)
                    if hasattr(packet, "msg_id") and packet.msg_id:
                        if packet.msg_id in self.seen_message_ids:
                            continue
                        self.seen_message_ids.add(packet.msg_id)

                    if packet.type in (MessageType.GROUP_CHAT, MessageType.ROOM_MESSAGE):
                        text = packet.payload.get("text", "")
                        room = packet.payload.get("room")
                        if room:
                            if not hasattr(self, "custom_rooms"):
                                self.custom_rooms = set()
                            self.custom_rooms.add(room)
                            self._append_message(
                                room,
                                f"{packet.sender_name} ({room})",
                                text,
                                category="peer",
                                sender_id=packet.sender_id,
                                msg_id=packet.msg_id,
                            )
                        else:
                            self._append_message(
                                None,
                                f"{packet.sender_name} (Group)",
                                text,
                                category="peer",
                                sender_id=packet.sender_id,
                                msg_id=packet.msg_id,
                            )

                    elif packet.type == MessageType.CHAT:
                        text = packet.payload.get("text", "")
                        # Direct DM routes to conversation thread with sender
                        self._append_message(
                            packet.sender_id,
                            packet.sender_name,
                            text,
                            category="dm",
                            sender_id=packet.sender_id,
                            msg_id=packet.msg_id,
                        )

                    elif packet.type == MessageType.HEARTBEAT:
                        # Direct TCP handshake received from peer (manual or mutual P2P connect)
                        tcp_port = packet.payload.get("tcp_port", config.DEFAULT_TCP_PORT)
                        if client_ip in (self.local_ip, "127.0.0.1") and tcp_port == self.actual_tcp_port:
                            continue
                        device_name = packet.payload.get("device_name", "Desktop Peer")
                        peer = Peer(
                            peer_id=packet.sender_id,
                            username=packet.sender_name,
                            device_name=device_name,
                            ip_address=client_ip,
                            tcp_port=tcp_port,
                            status="Online",
                        )
                        self.peers[peer.peer_id] = peer
                        if not self.peer_tree.exists(peer.peer_id):
                            self.peer_tree.insert(
                                "",
                                tk.END,
                                iid=peer.peer_id,
                                text=f"🟢 {peer.username} ({peer.device_name})",
                            )
                            self._append_message(
                                None,
                                "System",
                                f"Direct P2P connection established with '{peer.username}' ({client_ip}:{tcp_port}).",
                                category="system",
                            )
                        else:
                            self._refresh_tree_item_label(peer.peer_id)

                        if packet.payload.get("manual"):
                            reply_packet = Packet(
                                type=MessageType.HEARTBEAT,
                                sender_id=self.peer_id,
                                sender_name=self.username,
                                payload={
                                    "device_name": self.device_name,
                                    "tcp_port": self.actual_tcp_port,
                                    "ip_address": self.local_ip,
                                    "manual": False,
                                },
                            )
                            threading.Thread(
                                target=TCPClient.send_message,
                                args=(client_ip, tcp_port, reply_packet.to_dict()),
                                daemon=True,
                            ).start()

                    elif packet.type == MessageType.TYPING:
                        self._handle_incoming_typing(packet)

                    elif packet.type == MessageType.FILE_REQUEST:
                        self._handle_incoming_file_request(packet, client_ip)

                    elif packet.type == MessageType.FILE_ACCEPT:
                        self._handle_file_accepted_by_peer(packet, client_ip)

                    elif packet.type == MessageType.FILE_REJECT:
                        filename = packet.payload.get("filename", "unknown")
                        self._append_message(
                            packet.sender_id,
                            "System",
                            f"Peer '{packet.sender_name}' declined file '{filename}'.",
                            category="system",
                        )

                elif event_type == "PING_RESULT":
                    peer_id, msg = item[1], item[2]
                    self._append_message(peer_id, "System", msg, category="system")

        except queue.Empty:
            pass

        self.after(40, self._poll_ui_queue)

    def _handle_incoming_typing(self, packet: Packet) -> None:
        """Displays real-time typing notification with auto-expiring timer."""
        # Only show typing indicator if user is viewing relevant channel
        is_relevant = (packet.payload.get("channel") is None and self.selected_peer_id is None) or (
            self.selected_peer_id == packet.sender_id
        )
        if is_relevant:
            self.lbl_typing.config(text=f"💬 {packet.sender_name} is typing...")
            if self._typing_clear_job:
                self.after_cancel(self._typing_clear_job)
            self._typing_clear_job = self.after(3000, lambda: self.lbl_typing.config(text=""))

    def _handle_incoming_file_request(self, packet: Packet, sender_ip: str) -> None:
        """Handles incoming FILE_REQUEST prompt and receives file."""
        filename = packet.payload.get("filename", "unknown.bin")
        filesize = packet.payload.get("filesize", 0)
        checksum = packet.payload.get("sha256", "")
        sender_peer = self.peers.get(packet.sender_id)
        sender_tcp_port = packet.payload.get("tcp_port") or (
            sender_peer.tcp_port if sender_peer else config.DEFAULT_TCP_PORT
        )

        accept = messagebox.askyesno(
            "Incoming File Transfer",
            f"Peer '{packet.sender_name}' wants to send file:\n\n"
            f"Filename: {filename}\n"
            f"Size: {filesize} bytes\n\nAccept transfer?",
        )

        if accept:
            save_path = config.DEFAULT_DOWNLOAD_DIR / filename
            self._append_message(
                packet.sender_id,
                "System",
                f"Accepting file '{filename}'. Preparing receiver...",
                category="system",
            )

            try:
                server_sock, file_port = FileReceiver.create_listener()
            except Exception as e:
                self._append_message(
                    packet.sender_id,
                    "Error",
                    f"Failed starting file receiver: {e}",
                    category="error",
                )
                return

            # Transmit FILE_ACCEPT packet back to sender with bound ephemeral file_port
            accept_packet = Packet(
                type=MessageType.FILE_ACCEPT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"file_port": file_port, "filename": filename},
            )
            threading.Thread(
                target=TCPClient.send_message,
                args=(sender_ip, sender_tcp_port, accept_packet.to_dict()),
                daemon=True,
            ).start()

            def receive_worker():
                success = FileReceiver.receive_stream(
                    server_sock=server_sock,
                    save_path=save_path,
                    filesize=filesize,
                    expected_sha256=checksum,
                )

                if success:
                    self.ui_queue.put(
                        (
                            "TCP_MSG",
                            Packet(
                                type=MessageType.CHAT,
                                sender_id=packet.sender_id,
                                sender_name="System",
                                payload={"text": f"File '{filename}' downloaded successfully to {save_path}"},
                            ).to_dict(),
                            sender_ip,
                        )
                    )
                else:
                    self.ui_queue.put(
                        (
                            "TCP_MSG",
                            Packet(
                                type=MessageType.CHAT,
                                sender_id=packet.sender_id,
                                sender_name="System",
                                payload={"text": f"File transfer for '{filename}' failed or checksum mismatch!"},
                            ).to_dict(),
                            sender_ip,
                        )
                    )

            threading.Thread(target=receive_worker, daemon=True).start()
        else:
            # User declined file transfer
            reject_packet = Packet(
                type=MessageType.FILE_REJECT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"filename": filename},
            )
            threading.Thread(
                target=TCPClient.send_message,
                args=(sender_ip, sender_tcp_port, reject_packet.to_dict()),
                daemon=True,
            ).start()
            self._append_message(
                packet.sender_id,
                "System",
                f"Declined file '{filename}' from {packet.sender_name}.",
                category="system",
            )

    def _handle_file_accepted_by_peer(self, packet: Packet, recipient_ip: str) -> None:
        """Recipient accepted file request, start streaming file binary chunks."""
        file_port = packet.payload.get("file_port")
        filename = packet.payload.get("filename")

        filepath = self.pending_outgoing_files.pop(filename, None)
        if not filepath or not filepath.exists():
            self._append_message(
                packet.sender_id,
                "Error",
                f"Cannot send '{filename}': file not found on disk.",
                category="error",
            )
            return

        self._append_message(
            packet.sender_id,
            "System",
            f"Peer '{packet.sender_name}' accepted transfer. Streaming '{filename}'...",
            category="system",
        )

        def send_worker():
            success = FileSender.send_file(
                target_ip=recipient_ip,
                target_port=file_port,
                filepath=filepath,
            )
            if success:
                self.ui_queue.put(
                    (
                        "TCP_MSG",
                        Packet(
                            type=MessageType.CHAT,
                            sender_id=packet.sender_id,
                            sender_name="System",
                            payload={"text": f"File '{filename}' sent successfully to {packet.sender_name}!"},
                        ).to_dict(),
                        recipient_ip,
                    )
                )
            else:
                self.ui_queue.put(
                    (
                        "TCP_MSG",
                        Packet(
                            type=MessageType.CHAT,
                            sender_id=packet.sender_id,
                            sender_name="System",
                            payload={"text": f"Failed streaming file '{filename}' to {packet.sender_name}."},
                        ).to_dict(),
                        recipient_ip,
                    )
                )

        threading.Thread(target=send_worker, daemon=True).start()

    def _on_closing(self) -> None:
        """Stops network engines cleanly when window closes."""
        if hasattr(self, "web_gateway") and self.web_gateway:
            self.web_gateway.stop()
        self.discovery_engine.stop()
        self.tcp_server.stop()
        self.destroy()
