"""
Simple LAN Chat Application Entry Point.
"""

import getpass
import os
import sys
import uuid
import tkinter as tk
from tkinter import simpledialog

# Ensure project root directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import config
from src.gui.app import LANChatApp


def main() -> None:
    """Initializes and runs the Simple LAN Chat Application."""
    default_user = getpass.getuser()

    # Create temporary root to ask for username prompt if needed
    root = tk.Tk()
    root.withdraw()

    username = simpledialog.askstring(
        "Simple LAN Chat — Login",
        f"Enter your chat display name:",
        initialvalue=default_user,
    )

    root.destroy()

    if not username:
        username = default_user

    peer_id = str(uuid.uuid4())[:8]

    print(f"==================================================")
    print(f" Starting {config.APP_NAME} v{config.APP_VERSION}")
    print(f" User: {username} | Peer ID: {peer_id}")
    print(f"==================================================")

    app = LANChatApp(peer_id=peer_id, username=username)
    app.mainloop()


if __name__ == "__main__":
    main()
