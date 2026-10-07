# 📡 LAN Chat — Offline-First P2P Messenger

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Architecture-Hybrid%20P2P-orange?logo=diagramsdotnet&logoColor=white" alt="Hybrid P2P">
  <img src="https://img.shields.io/badge/Transport-TCP%20%7C%20UDP-green" alt="TCP / UDP">
  <img src="https://img.shields.io/badge/GUI-Tkinter%20(Catppuccin)-purple" alt="Tkinter GUI">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20External-success" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Tests-61%20Passed-brightgreen" alt="61 Tests Passed">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License MIT">
</p>

<p align="center">
  <a href="https://cn-project-lan-chat.onrender.com" target="_blank">
    <img src="https://img.shields.io/badge/🌐_Live_Demo-cn--project--lan--chat.onrender.com-00C7B7?style=for-the-badge&logo=render&logoColor=white" alt="Live Demo on Render">
  </a>
</p>

<p align="center">
  <strong>A lightweight, zero-configuration offline-first LAN chat platform. Works completely without the internet — just connect to the same Wi-Fi and start chatting via QR code or Network Code invite.</strong>
</p>

<p align="center">
  🚀 <strong>Live Web App:</strong> <a href="https://cn-project-lan-chat.onrender.com">https://cn-project-lan-chat.onrender.com</a>
</p>

---

## 📑 Table of Contents

- [🌐 Live Online Demo (24/7 Access)](#-live-online-demo-247-access)
- [🌟 Features Overview](#-features-overview)
- [🏗️ Network Architecture & Protocols](#️-network-architecture--protocols)
  - [OSI Layer Implementation](#osi-layer-implementation)
  - [Packet Framing Specification](#packet-framing-specification)
  - [Port Allocation Matrix](#port-allocation-matrix)
- [📱 Mobile & Cross-Device Access](#-mobile--cross-device-access)
  - [Connecting Your Phone](#connecting-your-phone)
  - [Hostel & Campus Wi-Fi Tip (AP Isolation)](#-hostel--campus-wi-fi-tip-ap-isolation)
- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation & Launch](#installation--launch)
- [💬 Slash Commands & Shortcuts](#-slash-commands--shortcuts)
- [📂 Project Structure](#-project-structure)
- [🧪 Automated Testing & Verification](#-automated-testing--verification)
- [🏛️ Detailed Documentation](#️-detailed-documentation)

---

## 🌐 Live Online Demo (24/7 Access)

You can try the live application right now without installing anything:

👉 **[https://cn-project-lan-chat.onrender.com](https://cn-project-lan-chat.onrender.com)**

- 📱 **Cross-Platform:** Works on any browser on **Android**, **iPhone**, **iPad**, **Windows**, **macOS**, and **Linux**.
- ⚡ **Zero Installation:** Open the link $\rightarrow$ enter your display name $\rightarrow$ start chatting!
- 💬 **Features Live Online:** Group broadcast room, 1-on-1 direct messaging, picture uploads, and light/dark Catppuccin themes.

---

## 🌟 Features Overview

- 🔍 **Decentralized Auto-Discovery:** Discovers peers automatically on the LAN using UDP broadcast heartbeats on port `50000` — zero server configuration required.
- 🔗 **QR Code & Network Code Invite System:** The host generates a scannable QR code and 6-character Network Code (e.g. `NET-A3F7C1`). Guests scan the QR code or paste the URL to join instantly.
- 💬 **Private Isolated Networks:** Each host creates an isolated network session. Only users who explicitly join a network (via QR / Network Code / direct URL) can see its rooms and messages.
- 🏠 **Dynamic Room Creation:** Users create named rooms (e.g. `#classroom`, `#study`) on demand. No preconfigured channels clutter the interface.
- 🖼️ **Image Lightbox & Shared Media Gallery:** Clickable image preview thumbnails with full-screen Lightbox zoom and in-app categorized Media Gallery.
- 📥 **Drag-and-Drop File Sharing:** Smooth drag-and-drop file upload overlay with animated percentage transfer progress bars and SHA-256 integrity verification.
- 📌 **Sticky Pinned Messages & Live Search:** Pin critical announcements to the top of any channel and filter conversations with real-time text matching.
- 🎙️ **Voice Notes Recording & Playback:** Native in-browser audio recording via Web Audio and MediaRecorder with inline responsive audio player.
- 👍 **Live Emoji Message Reactions:** Interactive reaction bar (👍, ❤️, 😂, 🔥) with toggleable participant badge pills.
- 🌐 **Multi-Interface IP Selection:** Enumerates all active local interfaces (Wi-Fi, Ethernet, Mobile Hotspot) to generate the correct LAN invite URL.
- 📱 **Zero-Install Mobile Web Client:** Any smartphone (iOS / Android), tablet, or secondary laptop on the same Wi-Fi can join instantly via browser — no app required.
- 📁 **High-Speed Binary File Transfer:** Chunked TCP socket streaming with SHA-256 checksum integrity verification.
- 🎨 **Glassmorphism Dark UI:** Premium dark mode interface with glassmorphism accents and smooth micro-animations.
- 🔒 **Zero External Dependencies:** Built strictly using the Python Standard Library (`socket`, `select`, `threading`, `http.server`, `tkinter`).

---

## 🏗️ Network Architecture & Protocols

The application is structured as a **Hybrid Peer-to-Peer (P2P) System** with layered component isolation:

```text
               +-------------------------------------------------------+
               |                  Desktop UI (Tkinter)                 |
               |                Thread-Safe Event Queue                |
               +---------------------------+---------------------------+
                                           |
                    +----------------------+----------------------+
                    |                                             |
   +----------------+----------------+           +----------------+----------------+
   |    Discovery Engine (UDP)       |           |   Connection Engine (TCP)       |
   | • Broadcast Heartbeats (50000)  |           | • P2P TCP Server (50001)        |
   | • Subnet Presence Table         |           | • 4-Byte Framing Client         |
   | • Peer Timeout Eviction         |           | • Binary File Transfer Streams  |
   +---------------------------------+           +---------------------------------+
                    |                                             |
                    +----------------------+----------------------+
                                           |
               +---------------------------+---------------------------+
               |             Web Gateway HTTP/REST (8080)              |
               | • Serves Mobile Web SPA (HTML/CSS/JS)                 |
               | • JSON REST API: /api/status, /api/send, /api/poll    |
               | • Binary File Uploads & Local Downloads Streaming     |
               +-------------------------------------------------------+
```

### OSI Layer Implementation

| OSI Layer | Protocol / Technology | Implementation in Simple LAN Chat |
|---|---|---|
| **7. Application Layer** | JSON / HTTP | P2P Chat Packets, REST Endpoints, Tkinter Presentation |
| **6. Presentation Layer** | Custom Framing / SHA-256 | 4-byte big-endian framing (`struct`), file checksum hashing |
| **5. Session Layer** | Heartbeat Engine | Peer lifecycle state table, keep-alive timers, client pruning |
| **4. Transport Layer** | TCP & UDP Sockets | TCP streaming (reliable chat/files), UDP broadcast (discovery) |
| **3. Network Layer** | IPv4 | Subnet mask resolution, local network routing |
| **2. Data Link Layer** | Ethernet / Wi-Fi (802.11) | Local network broadcast delivery handled by OS network stack |

### Packet Framing Specification

To prevent **TCP stream concatenation** and **packet fragmentation**, all direct P2P messages are transmitted with a strict 4-byte prefix:

```text
+----------------------------+------------------------------------------+
|  Length Header (4 Bytes)   |         JSON Encoded Payload Data        |
|     Big-Endian UInt32      |              (UTF-8 String)              |
+----------------------------+------------------------------------------+
  Example: [0x00, 0x00, 0x00, 0x2A] -> 42-byte JSON Payload
```

### Port Allocation Matrix

| Port | Transport | Purpose | Description |
|---|:---:|---|---|
| **50000** | UDP | Peer Discovery | Subnet broadcast heartbeats every 3.0s |
| **50001** | TCP | P2P Messaging & Files | Dedicated length-prefixed stream server (auto-fallback to OS dynamic port if occupied) |
| **8080** | TCP | Web & Mobile Gateway | Lightweight HTTP server serving Mobile Web UI and REST API (auto-increments on collision) |

---

## 📱 Mobile & Cross-Device Access

You can connect your **Android phone**, **iPhone**, **iPad**, or another laptop without installing anything:

> [!NOTE]
> **Global 24/7 Cloud Access:** You can instantly access the live cloud-hosted app from anywhere at **[https://cn-project-lan-chat.onrender.com](https://cn-project-lan-chat.onrender.com)**.  
> Follow the steps below if you want to run your own **private offline local Wi-Fi LAN** instance.

### Connecting Your Phone / Tablet

#### Method 1 — QR Code (Easiest)
1. Start the web gateway on your computer: `python web_main.py`.
2. Open the app in **your own browser** at `http://localhost:8080`, set your nickname and create your network.
3. Click the **🔗 Invite** button in the top navigation bar.
4. A QR code is generated pointing to the **local LAN IP** of your machine.
5. Scan the QR code with any phone camera — the phone's browser opens and auto-joins the network.

#### Method 2 — Network Code
1. Click **🔗 Invite** → note the **Network Code** badge (e.g., `NET-A3F7C1`).
2. Share the 6-character code verbally or via any messaging app.
3. Guests navigate to `http://<host_ip>:8080`, tap **Join Existing Network**, enter the code and their name.

#### Method 3 — Direct URL
1. Click **🔗 Invite** → Copy the **Direct Room URL** (displays the correct LAN IP, not a cloud domain).
2. Send this link over WhatsApp, Telegram, etc. to anyone on the same Wi-Fi.
3. Clicking the link opens the browser and auto-joins the network.

### 💡 Hostel & Campus Wi-Fi Tip (AP Isolation)

> [!TIP]
> **Can't reach the URL from your phone?**  
> On university and hostel Wi-Fi networks (e.g., eduroam, hostel routers), **AP Isolation (Client Isolation)** is frequently enabled, blocking devices on the Wi-Fi from communicating directly with each other.  
> **Easy Solution:** Turn on your phone's **Mobile Hotspot**, connect your computer to that hotspot, and use the updated IP displayed in the invite modal.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10** or higher.
- Standard Tkinter support (included by default in Python for Windows and macOS).

### Installation & Launch

1. **Clone the repository:**
   ```bash
   git clone https://github.com/suraz111/CN_Project--LAN-Chat-.git
   cd CN_Project--LAN-Chat-
   ```

2. **Run Desktop Application:**
   ```bash
   python main.py
   ```

3. **Or Run Standalone Headless Web Gateway (Server Mode):**
   ```bash
   python web_main.py
   ```

---

## 💬 Slash Commands & Shortcuts

Type slash commands directly into the desktop chat input box:

| Command | Description | Example |
|---|---|---|
| `/help` | Displays available slash commands and usage guide | `/help` |
| `/mobile` | Displays the current local Wi-Fi URL for mobile connection | `/mobile` |
| `/nick <name>` | Updates your chat display name across the network | `/nick Suraj_Laptop` |
| `/users` | Lists all online peers, device types, and IP:Port endpoints | `/users` |
| `/open` | Opens the local `Downloads/LANChat_Received` folder in explorer | `/open` |
| `/clear` | Clears local chat history in the current channel | `/clear` |
| `/shrug` | Quickly sends the classic `¯\_(ツ)_/¯` emoji | `/shrug` |

---

## 📂 Project Structure

```text
CN_project/
├── main.py                     # Primary GUI application entry point
├── web_main.py                 # Standalone headless web gateway entry point
├── config.py                   # Centralized network ports, timeouts & buffer limits
├── README.md                   # Project overview & documentation
├── ARCHITECTURE.md             # Detailed network architecture & protocol design
├── DESIGN.md                   # Software component models & wireframes
├── STACK.md                    # Technology stack & dependency breakdown
├── BRAINSTORMING.md            # Feature requirements & concept analysis
│
├── src/
│   ├── models/                 # Data structures
│   │   ├── message.py          # Packet model & MessageType enum
│   │   └── peer.py             # Peer entity state & expiration logic
│   │
│   ├── network/                # Socket communication layers
│   │   ├── discovery.py        # UDP heartbeat broadcast engine
│   │   ├── tcp_server.py       # Multi-threaded TCP listener
│   │   ├── tcp_client.py       # Framed TCP socket sender with port-0 safety
│   │   ├── framing.py          # 4-byte length prefix framing encoder/decoder
│   │   └── file_transfer.py    # Binary streaming with SHA-256 verification
│   │
│   ├── gui/                    # Presentation layer
│   │   └── app.py              # Tkinter application, theme engine & queue poller
│   │
│   ├── web/                    # Mobile web gateway
│   │   ├── gateway.py          # Threading HTTP server & REST endpoint router
│   │   └── static/             # Mobile Single-Page Application (SPA)
│   │       ├── index.html      # Responsive mobile UI layout & dialogs
│   │       ├── style.css       # Glassmorphism dark/light design system
│   │       └── app.js          # Client polling, DOM rendering & uploads
│   │
│   └── utils/                  # Helper utilities
│       └── net_utils.py        # Local IP resolution & subnet broadcast calculation
│
└── tests/                      # Automated test suite (61 tests)
    ├── test_new_features.py    # Reactions, pinning, rooms, audio upload, and interfaces
    ├── test_e2e_full.py        # Comprehensive 7-condition End-to-End test suite
    ├── test_tcp.py             # TCP framing, send/receive & port-0 safety tests
    ├── test_web_gateway.py     # HTTP methods, REST routes & port collision tests
    ├── test_discovery.py       # UDP heartbeats & peer lifecycle tests
    ├── test_file_transfer.py   # Binary file streaming & SHA-256 checksum tests
    ├── test_framing.py         # Packet fragmentation & length-prefix tests
    ├── test_deduplication_and_themes.py # Message deduplication & theme tokens
    └── test_net_utils.py       # IP address resolution & broadcast tests
```

---

## 🧪 Automated Testing & Verification

The project includes a comprehensive automated test suite with **61 test conditions** covering unit, integration, and end-to-end scenarios.

Run all tests with a single command:
```bash
python -m unittest discover tests/
```

### Key Validated Test Conditions:
- ✅ **Length-Prefixed Framing:** Correct encoding and stream reassembly across multi-byte character boundaries.
- ✅ **Port Safety:** Proper rejection of invalid target ports (`0`, `-1`) to prevent OS socket errors.
- ✅ **Windows Port Exclusivity:** `SO_EXCLUSIVEADDRUSE` enforcement and automatic port incrementing (`8080` → `8081`).
- ✅ **HTTP Protocol Compliance:** Handling of `GET`, `HEAD`, and CORS `OPTIONS` pre-flight headers.
- ✅ **Mobile Lifecycle:** Complete mobile workflow from join → status touch → group message → private DM → polling.
- ✅ **Binary Stream Integrity:** Chunked file transfers verified with bit-level SHA-256 cryptographic hashes.
- ✅ **Network Isolation:** Only members of a network can read its messages — cross-network visibility blocked.
- ✅ **QR / Invite URL:** Invite URL generation uses the correct LAN IP address, not a cloud domain.

---

## 🏛️ Detailed Documentations

For comprehensive academic and implementation details, refer to:

- 📄 [PROJECT_REPORT.md](PROJECT_REPORT.md) — **Complete Academic Project Report, Component Breakdown & Faculty Viva Q&A Guide**.
- 📋 [BRAINSTORMING.md](BRAINSTORMING.md) — Feature ideation, protocol selection & requirement analysis.
- 🏗️ [DESIGN.md](DESIGN.md) — Detailed class diagrams, state machines, packet schemas & wireframes.
- 🛠️ [STACK.md](STACK.md) — Technology stack specification, tooling choices & standard library rationale.
- 🏛️ [ARCHITECTURE.md](ARCHITECTURE.md) — OSI model mapping, sequence diagrams & concurrency thread models.

---

<p align="center">
  Developed for <strong>Computer Networks (CN)</strong> Laboratory Demonstration.<br>
  Built with ❤️ using pure Python standard library sockets.
</p>
