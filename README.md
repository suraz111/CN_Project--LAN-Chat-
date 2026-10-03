# 📡 Simple LAN Chat

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Architecture-Hybrid%20P2P-orange?logo=diagramsdotnet&logoColor=white" alt="Hybrid P2P">
  <img src="https://img.shields.io/badge/Transport-TCP%20%7C%20UDP-green" alt="TCP / UDP">
  <img src="https://img.shields.io/badge/GUI-Tkinter%20(Catppuccin)-purple" alt="Tkinter GUI">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20External-success" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Tests-37%20Passed-brightgreen" alt="37 Tests Passed">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License MIT">
</p>

<p align="center">
  <a href="https://cn-project-lan-chat.onrender.com" target="_blank">
    <img src="https://img.shields.io/badge/🌐_Live_Demo-cn--project--lan--chat.onrender.com-00C7B7?style=for-the-badge&logo=render&logoColor=white" alt="Live Demo on Render">
  </a>
</p>

<p align="center">
  <strong>A lightweight, zero-configuration Peer-to-Peer (P2P) desktop chat and file-sharing application designed for Local Area Networks (LAN), featuring a 24/7 cloud gateway and mobile web client.</strong>
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

- 🔍 **Decentralized Auto-Discovery:** Discovers peers dynamically across the local subnet using periodic UDP broadcast heartbeats on port `50000` with zero server configuration.
- 💬 **Multi-Channel Communication:** Seamlessly switch between global **Group Broadcast Room** and private, isolated **1-on-1 Direct Messaging (DM)** channels with unread notification badges.
- 📱 **Zero-Install Mobile Web Client:** Any smartphone (iOS / Android), tablet, or secondary laptop on the same Wi-Fi can join instantly via browser at `http://<local_ip>:8080`.
- 📁 **High-Speed Binary File Transfer:** Chunked socket streaming with **SHA-256 checksum integrity verification**, transfer progress bars, and an in-app received files viewer.
- 🎨 **Modern Catppuccin Themes:** Sleek dark mode (Catppuccin Mocha) and crisp light mode with dynamic theme toggle and glassmorphism accents.
- ⌨️ **Live Typing Indicators:** Real-time, debounced typing presence across both desktop and mobile clients.
- ⚡ **Built-In Slash Commands & Quick Emojis:** Client-side commands (`/help`, `/nick`, `/mobile`, `/users`, `/open`, `/clear`, `/shrug`) and one-click emoji selector.
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

### Connecting Your Phone

1. Start the desktop application on your computer (`python main.py`).
2. Notice your local Web Gateway URL displayed in the header or click **`📱 Mobile Web`** (e.g., `http://192.168.1.100:8080`).
3. Open **Chrome**, **Safari**, or **Firefox** on your phone.
4. Type the exact address including `http://`:
   ```text
   http://<your_computer_ip>:8080
   ```
5. Enter your display name and tap **Join LAN Chat**. You can now exchange text messages, receive desktop alerts, and upload photos directly to the LAN network!

### 💡 Hostel & Campus Wi-Fi Tip (AP Isolation)

> [!TIP]
> **Can't reach the URL from your phone?**  
> On university and hostel Wi-Fi networks (e.g., eduroam, hostel routers), **AP Isolation (Client Isolation)** is frequently enabled, blocking devices on the Wi-Fi from communicating directly with each other.  
> **Easy Solution:** Turn on your phone's **Mobile Hotspot**, connect your computer to that hotspot, and use the updated IP displayed in the desktop app!

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
└── tests/                      # Automated test suite (37 tests)
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

The project includes a comprehensive automated test suite with **37 test conditions** covering unit, integration, and end-to-end scenarios.

Run all tests with a single command:
```bash
python -m unittest discover tests/
```

### Key Validated Test Conditions:
- ✅ **Length-Prefixed Framing:** Correct encoding and stream reassembly across multi-byte character boundaries.
- ✅ **Port Safety:** Proper rejection of invalid target ports (`0`, `-1`) to prevent OS socket errors.
- ✅ **Windows Port Exclusivity:** `SO_EXCLUSIVEADDRUSE` enforcement and automatic port incrementing (`8080` $\rightarrow$ `8081`).
- ✅ **HTTP Protocol Compliance:** Handling of `GET`, `HEAD`, and CORS `OPTIONS` pre-flight headers.
- ✅ **Mobile Lifecycle:** Complete mobile workflow from join $\rightarrow$ status touch $\rightarrow$ group message $\rightarrow$ private DM $\rightarrow$ polling.
- ✅ **Binary Stream Integrity:** Chunked file transfers verified with bit-level SHA-256 cryptographic hashes.

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
