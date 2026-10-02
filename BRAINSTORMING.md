# 📋 Simple LAN Chat — Finalized Brainstorming Document

> **Project Title:** Simple LAN Chat Application  
> **Subject:** Computer Networks (CN)  
> **Date:** 30 September 2026  
> **Language:** Python 3.x  
> **Architecture:** Peer-to-Peer (Serverless) + Client-Server Hybrid

---

## 1. Problem Statement

Design and implement a real-time LAN-based chat application using **socket programming** that enables multiple users connected to the same local network to discover each other automatically and communicate — without requiring a central server. The project demonstrates core computer networking concepts including TCP/UDP communication, peer discovery via heartbeat broadcast, file/image transfer, and application-layer protocol design.

---

## 2. Architecture (Finalized)

### 2.1 Model: Hybrid P2P + Client-Server

We use a **Hybrid** approach:

```
┌──────────────────────────────────────────────────────────────┐
│                    LAN (192.168.x.x)                         │
│                                                              │
│   ┌──────────┐  UDP Heartbeat   ┌──────────┐                │
│   │  Peer A  │◄───────────────►│  Peer B  │                │
│   │ (Client) │  (255.255.255.255) │ (Client) │                │
│   └─────┬────┘                  └────┬─────┘                │
│         │                             │                      │
│         │ TCP (chat/files)            │ TCP (chat/files)     │
│         │                             │                      │
│         ▼                             ▼                      │
│   ┌──────────────────────────────────────┐                   │
│   │          Chat Server (Hub)           │                   │
│   │     TCP: 0.0.0.0:9999               │                   │
│   │     Relays messages between peers    │                   │
│   └──────────────────────────────────────┘                   │
│                                                              │
│   Discovery Layer (P2P):                                     │
│     • UDP broadcast on port 9998                             │
│     • Heartbeat every 5 seconds                              │
│     • Auto-detect online peers                               │
│     • Self-IP discovery                                      │
│                                                              │
│   Communication Layer (Client-Server):                       │
│     • TCP connection to server on port 9999                  │
│     • Reliable message delivery                              │
│     • File/image transfer                                    │
│     • Private messaging                                      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Why Hybrid?

| Layer | Protocol | Purpose | Why |
|---|---|---|---|
| **Discovery** | UDP (P2P) | Find peers, heartbeat, detect online/offline | Fast, connectionless, broadcast capable |
| **Communication** | TCP (Client-Server) | Chat messages, files, DMs | Reliable, ordered delivery |

### 2.3 How Heartbeat Works

```
Every 5 seconds:
    │
    ├── Each peer broadcasts a HEARTBEAT packet via UDP to 255.255.255.255:9998
    │     Packet: HEARTBEAT|<username>|<timestamp>
    │
    ├── Every peer listening on port 9998 receives it
    │     └── Adds/updates sender in their "online peers" list
    │
    ├── If no heartbeat received from a peer for 15 seconds:
    │     └── Mark peer as OFFLINE, remove from list
    │
    └── Self-discovery: If peer receives its own broadcast
          └── Extract own LAN IP from datagram.address
```

---

## 3. Application-Layer Protocol Specification

### 3.1 UDP Protocol (Discovery Layer)

All UDP messages are UTF-8 encoded, newline-delimited:

```
TYPE|SENDER|CONTENT\n
```

| Type | Direction | Purpose | Example |
|---|---|---|---|
| `HEARTBEAT` | Broadcast → All | Periodic presence announcement | `HEARTBEAT\|alice\|1696045200\n` |
| `DISCOVER` | Broadcast → All | Request server info | `DISCOVER\|\|\n` |
| `DISCOVER_ACK` | Server → Requester | Server responds with its IP | `DISCOVER_ACK\|server\|192.168.1.5:9999\n` |

### 3.2 TCP Protocol (Communication Layer)

| Type | Direction | Purpose | Example |
|---|---|---|---|
| `JOIN` | Client → Server | Register username | `JOIN\|alice\|\n` |
| `JOIN_ACK` | Server → Client | Confirm registration | `JOIN_ACK\|\|Welcome alice!\n` |
| `JOIN_REJECT` | Server → Client | Reject duplicate name | `JOIN_REJECT\|\|Username taken\n` |
| `MSG` | Client → Server | Broadcast message | `MSG\|alice\|Hello all!\n` |
| `BROADCAST` | Server → All Clients | Relayed broadcast message | `BROADCAST\|alice\|Hello all!\n` |
| `PRIVATE` | Client → Server | DM to specific user | `PRIVATE\|alice\|bob:Hey there!\n` |
| `DM` | Server → Target Client | Deliver private message | `DM\|alice\|Hey there!\n` |
| `USERLIST` | Server → Client | Active users list | `USERLIST\|\|alice,bob,charlie\n` |
| `SERVER` | Server → All Clients | System notification | `SERVER\|\|alice has joined\n` |
| `LEAVE` | Client → Server | Graceful disconnect | `LEAVE\|alice\|\n` |
| `ERROR` | Server → Client | Error notification | `ERROR\|\|User bob not found\n` |
| `HISTORY` | Server → Client | Chat history for new joiners | `HISTORY\|\|bob:Hi;alice:Hey\n` |
| `TYPING` | Client → Server | Typing indicator | `TYPING\|alice\|\n` |
| `TYPING_BROADCAST` | Server → All | Relay typing status | `TYPING_BROADCAST\|alice\|\n` |
| `FILE_START` | Client → Server | Begin file transfer | `FILE_START\|alice\|photo.jpg:45000\n` |
| `FILE_DATA` | Client → Server | File chunk data | `FILE_DATA\|alice\|<base64_chunk>\n` |
| `FILE_END` | Client → Server | File transfer complete | `FILE_END\|alice\|photo.jpg\n` |
| `FILE_NOTIFY` | Server → All | Notify about shared file | `FILE_NOTIFY\|alice\|photo.jpg:45000\n` |

### 3.3 Protocol Rules

1. Every message MUST end with `\n`.
2. Maximum text message size: **4096 bytes**.
3. File chunks: **32768 bytes (32 KB)** each, base64 encoded.
4. Username: **3–20 characters**, alphanumeric + underscores only.
5. The `|` (pipe) character is RESERVED as a delimiter.
6. Heartbeat interval: **5 seconds**. Timeout: **15 seconds**.

---

## 4. Finalized Feature List

### 4.1 Server Features

| # | Feature | Description |
|---|---|---|
| S1 | Multi-client TCP support | Accept and manage multiple simultaneous connections via threading |
| S2 | Username registration | Validate and register unique usernames on JOIN |
| S3 | Duplicate username rejection | Reject JOIN if username exists, send JOIN_REJECT |
| S4 | Broadcast relay | Relay MSG from any client to ALL connected clients |
| S5 | Private message routing | Route PRIVATE messages to the specified target user |
| S6 | User list management | Track online users; send USERLIST on change |
| S7 | Join/Leave notifications | Broadcast SERVER messages on connect/disconnect |
| S8 | Chat history buffer | Store last 50 messages; send HISTORY to new joiners |
| S9 | Graceful disconnect | Handle LEAVE, broken pipes, unexpected disconnections |
| S10 | UDP discovery responder | Listen on UDP 9998; respond to DISCOVER broadcasts |
| S11 | Typing indicator relay | Relay TYPING status to all connected clients |
| S12 | File transfer relay | Accept FILE_START/FILE_DATA/FILE_END, relay to recipients |
| S13 | Server console logging | Log all events with timestamps to terminal |
| S14 | Configurable settings | Port, max clients, history size via `config.py` |

### 4.2 Client Features

| # | Feature | Description |
|---|---|---|
| C1 | TCP connection | Connect to server via IP:Port |
| C2 | UDP auto-discovery | Broadcast DISCOVER to find server on LAN |
| C3 | Heartbeat system | Send periodic UDP heartbeats; detect peer online/offline status |
| C4 | Self-IP discovery | Detect own LAN IP from received broadcast datagram |
| C5 | Username setup | Ask user for username; retry if rejected |
| C6 | Send broadcast messages | Type and send messages to all users |
| C7 | Send private messages | `/dm <user> <message>` syntax for DMs |
| C8 | Receive in real-time | Dedicated listener thread for incoming messages |
| C9 | View online users | `/users` command to request user list |
| C10 | View chat history | Receive and display last 50 messages on join |
| C11 | Timestamps | Display timestamp with every message |
| C12 | Colored output | Color-code usernames, system, DMs, errors |
| C13 | File sharing | Send files via `/file <path>` command |
| C14 | Image sharing | Send images via `/image <path>` command |
| C15 | Typing indicator | Show "user is typing…" notification |
| C16 | Graceful exit | `/quit` to send LEAVE and disconnect |
| C17 | Connection error handling | Handle server unreachable, lost, timeout |

### 4.3 Client Commands

| Command | Action |
|---|---|
| `/dm <user> <msg>` | Send a private message to `<user>` |
| `/users` | Display list of online users |
| `/file <path>` | Share a file with all users |
| `/image <path>` | Share an image with all users |
| `/quit` | Disconnect and exit |
| `/help` | Show available commands |
| `/clear` | Clear terminal screen |
| `/nick <name>` | Change username |

### 4.4 GUI Client (Tkinter)

| # | Feature | Description |
|---|---|---|
| G1 | Chat window | Scrollable message area |
| G2 | Input field + Send button | Text entry with send action |
| G3 | Online users side panel | List of connected peers |
| G4 | Connection dialog | Enter server IP or auto-discover |
| G5 | Color-coded messages | Different colors for own, others, system, DMs |
| G6 | File/Image attachment button | Browse and send files/images |
| G7 | Settings page | Change username, port configuration |
| G8 | Typing indicator | "User is typing…" display |

---

## 5. Tech Stack (Finalized)

| Component | Technology | Justification |
|---|---|---|
| Language | **Python 3.10+** | Clean socket API, rapid prototyping |
| TCP Sockets | `socket` (stdlib) | Chat messages — `AF_INET`, `SOCK_STREAM` |
| UDP Sockets | `socket` (stdlib) | Discovery & heartbeats — `SOCK_DGRAM`, `SO_BROADCAST` |
| Concurrency | `threading` (stdlib) | One thread/client on server; send/recv/heartbeat threads on client |
| Terminal Colors | `colorama` (pip) | Cross-platform colored output |
| GUI | `tkinter` (stdlib) | Desktop GUI, no install needed |
| File Handling | `base64`, `os` (stdlib) | File chunking & encoding for transfer |
| Date/Time | `datetime` (stdlib) | Message timestamps |
| Settings Persistence | `json` (stdlib) | Save username/preferences locally |

### External Dependencies

```
colorama==0.4.6
```

---

## 6. Project File Structure

```
d:\CN_project\
│
├── BRAINSTORMING.md              # This document
├── README.md                     # Project overview, setup, usage
├── requirements.txt              # Python dependencies (colorama)
│
├── src/                          # Source code
│   ├── config.py                 # Shared constants & configuration
│   ├── protocol.py               # Message encoding, decoding, validation
│   ├── models/                   # Data models
│   │   ├── __init__.py
│   │   ├── message.py            # Message class (type, sender, content, timestamp)
│   │   ├── connection.py         # Peer/Connection class (IP, username, last_seen)
│   │   └── chat.py               # Chat state (messages list, connections list)
│   │
│   ├── networking/               # Core networking layer
│   │   ├── __init__.py
│   │   ├── tcp_server.py         # TCP chat server
│   │   ├── tcp_client.py         # TCP client connection handler
│   │   ├── udp_discovery.py      # UDP broadcast discovery + heartbeat
│   │   └── file_transfer.py      # File chunking, sending, reassembly
│   │
│   ├── server.py                 # Main server entry point
│   ├── client.py                 # Terminal-based client entry point
│   └── gui_client.py             # Tkinter GUI client
│
├── settings/                     # User settings
│   └── user_settings.json        # Persisted preferences
│
├── docs/                         # Documentation
│   ├── architecture.md
│   ├── protocol.md
│   ├── cn_concepts.md
│   └── screenshots/
│
└── tests/                        # Tests
    ├── test_protocol.py
    ├── test_discovery.py
    └── test_connection.py
```

---

## 7. CN Concepts Mapping

| CN Concept | Where in Project | Layer |
|---|---|---|
| **Socket Programming** | `socket.socket()` in TCP server/client & UDP discovery | Transport / Application |
| **TCP** | `SOCK_STREAM` — reliable chat delivery | Transport |
| **UDP** | `SOCK_DGRAM` — heartbeat discovery broadcast | Transport |
| **IP Addressing** | Server `0.0.0.0`, clients connect to LAN IP | Network |
| **Port Numbers** | TCP `9999`, UDP `9998` | Transport |
| **Broadcasting** | UDP `SO_BROADCAST` to `255.255.255.255` | Network |
| **Heartbeat Protocol** | Periodic keep-alive for peer detection | Application |
| **Client-Server Model** | Central server relays messages | Application |
| **P2P Discovery** | Peers find each other without central directory | Application |
| **Multithreading** | Thread-per-client, heartbeat thread | Application |
| **Application Protocol** | Custom `TYPE\|SENDER\|CONTENT\n` | Application |
| **File Transfer** | Chunked base64 over TCP | Application |
| **Data Serialization** | UTF-8 + base64 encoding | Presentation |
| **Connection State** | Track peers via Connection model | Application |
| **Self-Discovery** | Detect own IP from broadcast | Network |

---

## 8. Data Flow Diagrams

### 8.1 Peer Discovery (Heartbeat)

```
 Peer A                           LAN                         Peer B
   │                               │                            │
   ├──UDP HEARTBEAT|alice|ts──────►│◄──UDP HEARTBEAT|bob|ts────┤
   │   (to 255.255.255.255:9998)   │  (to 255.255.255.255:9998)│
   │                               │                            │
   ├──Receives bob's heartbeat ◄───┤───Receives alice's heartbeat─►│
   │   → Add bob to peer list      │   → Add alice to peer list │
   │                               │                            │
   ├──Receives OWN heartbeat ◄─────┤                            │
   │   → Extract own LAN IP        │                            │
   │     (self-discovery trick)     │                            │
   │                               │                            │
   │  [If no heartbeat from bob    │                            │
   │   for 15 seconds →            │                            │
   │   Mark bob as OFFLINE]        │                            │
```

### 8.2 Server Discovery & Connection

```
Client starts
    │
    ├── Start heartbeat thread (UDP broadcast every 5s)
    │     └── Discovers own IP + other peers
    │
    ├── Option A: Auto-discover server via UDP DISCOVER
    │       └── Broadcast "DISCOVER" to 255.255.255.255:9998
    │       └── Receive DISCOVER_ACK with server IP:port
    │
    ├── Option B: User manually enters server IP
    │
    ├── TCP connect to server_ip:9999
    │
    ├── Send JOIN|username|
    │
    ├── Receive JOIN_ACK or JOIN_REJECT
    │       └── If rejected → prompt again
    │
    ├── Receive HISTORY (last 50 messages)
    ├── Receive USERLIST (online users)
    │
    ├── Start receiver thread (TCP incoming messages)
    │
    └── Main thread: read user input → send messages/commands
```

### 8.3 Message Flow — Broadcast

```
Alice types "Hello!"
    │
    ├── Client encodes: MSG|alice|Hello!\n
    ├── Sends to server via TCP
    │
    ├── Server receives → stores in history buffer
    ├── Server encodes: BROADCAST|alice|Hello!\n
    │
    └── Server sends to ALL connected clients
            ├── Alice sees:   [10:30] alice: Hello!
            ├── Bob sees:     [10:30] alice: Hello!
            └── Charlie sees: [10:30] alice: Hello!
```

### 8.4 File Transfer Flow

```
Alice types "/file report.pdf"
    │
    ├── Client reads file → calculates size
    ├── Sends: FILE_START|alice|report.pdf:45000\n          (metadata)
    │
    ├── Chunks file into 32KB base64-encoded pieces
    │     ├── FILE_DATA|alice|<base64_chunk_1>\n             (chunk 1)
    │     ├── FILE_DATA|alice|<base64_chunk_2>\n             (chunk 2)
    │     └── ...                                            (chunk N)
    │
    ├── Sends: FILE_END|alice|report.pdf\n                   (done)
    │
    ├── Server reassembles file
    ├── Server sends: FILE_NOTIFY|alice|report.pdf:45000\n   (notify all)
    │
    └── Other clients can download the file
```



---

## 9. Configuration Defaults

```python
# config.py

# Network
SERVER_HOST       = "0.0.0.0"
SERVER_PORT       = 9999            # TCP port for chat
DISCOVERY_PORT    = 9998            # UDP port for discovery + heartbeat
BROADCAST_ADDR    = "255.255.255.255"
BUFFER_SIZE       = 4096            # Max bytes per recv()
FILE_CHUNK_SIZE   = 32768           # 32 KB file chunks

# Limits
MAX_CLIENTS       = 10
HISTORY_SIZE      = 50
USERNAME_MIN_LEN  = 3
USERNAME_MAX_LEN  = 20

# Heartbeat
HEARTBEAT_INTERVAL = 5              # Send heartbeat every 5 seconds
HEARTBEAT_TIMEOUT  = 15             # Mark peer offline after 15s silence

# Encoding
ENCODING          = "utf-8"
DELIMITER         = "\n"
SEPARATOR         = "|"

# Discovery
DISCOVER_MSG      = "DISCOVER"
DISCOVER_ACK_MSG  = "DISCOVER_ACK"
HEARTBEAT_MSG     = "HEARTBEAT"

# Settings file
SETTINGS_FILE     = "settings/user_settings.json"
```

---

## 10. Error Handling Matrix

| Scenario | Where | How It's Handled |
|---|---|---|
| Server not running | Client | "Connection refused" → retry or exit |
| Client disconnects unexpectedly | Server | `recv()` empty → remove client, notify others |
| Server crashes | Client | `recv()` exception → "Server lost" → exit |
| Duplicate username | Server | Send `JOIN_REJECT` → client re-prompts |
| DM to non-existent user | Server | Send `ERROR` to sender |
| Message too long (>4096) | Client | Truncate or reject before sending |
| Invalid protocol message | Server | Log warning, ignore malformed message |
| Port already in use | Server | Catch `OSError` → display error → exit |
| Firewall blocking | Both | Document: add exception for ports 9999/9998 |
| File too large | Client | Warn user, set max file size (10 MB) |
| Heartbeat timeout | Client | Remove peer from online list, show notification |
| UDP broadcast blocked | Client | Fall back to manual IP entry |

---

## 11. Color Scheme (Terminal)

| Element | Color | Colorama Code |
|---|---|---|
| Own messages | **Cyan** | `Fore.CYAN` |
| Others' messages | **White** | `Fore.WHITE` |
| System notifications | **Yellow** | `Fore.YELLOW` |
| Private messages (DM) | **Magenta** | `Fore.MAGENTA` |
| Error messages | **Red** | `Fore.RED` |
| Timestamps | **Green** | `Fore.GREEN` |
| Username prompt | **Blue** | `Fore.BLUE` |
| Typing indicators | **Dark Grey** | `Fore.LIGHTBLACK_EX` |
| File transfer status | **Cyan** | `Fore.CYAN` + `Style.DIM` |
| Heartbeat/discovery logs | **Dark Grey** | `Fore.LIGHTBLACK_EX` |

---

## 12. Implementation Plan

| Phase | Days | Tasks | Deliverables |
|---|---|---|---|
| **Phase 1: Foundation** | Day 1–2 | Create `config.py`, `models/` (message, connection, chat), basic TCP server (single client, echo), basic TCP client (connect, send, receive), test on `localhost` | Working echo server + client |
| **Phase 2: Discovery** | Day 2–3 | Implement `udp_discovery.py` — heartbeat broadcast, peer detection, self-IP discovery, server auto-discovery via DISCOVER/DISCOVER_ACK | Peers auto-detect each other on LAN |
| **Phase 3: Multi-Client** | Day 3–4 | Add threading to server, implement `protocol.py` (encode/decode), username registration + validation, broadcast relay, graceful disconnect | Multi-user chat on localhost |
| **Phase 4: Features** | Day 5–6 | Private messaging (`/dm`), user list + `/users`, chat history buffer, join/leave notifications, timestamps + colorama, typing indicator, client commands | Feature-complete terminal client |
| **Phase 5: File Transfer** | Day 6–7 | Implement `file_transfer.py` — chunking, base64 encoding, reassembly, `/file` and `/image` commands, FILE_START/DATA/END protocol | File & image sharing working |
| **Phase 6: GUI** | Day 7–8 | Tkinter GUI client — chat window, input field, online users panel, file attachment button, settings dialog | Desktop GUI client |
| **Phase 7: Polish** | Day 8–9 | Error handling, LAN testing (2+ machines), README.md + docs, screenshots, `/nick` command, settings persistence | Submission-ready project |

---

## 13. Testing Plan

### 13.1 Unit Tests

| Test | Module | What's Verified |
|---|---|---|
| Message encoding | `protocol.py` | `encode("MSG", "alice", "Hi")` → `MSG\|alice\|Hi\n` |
| Message decoding | `protocol.py` | `decode("MSG\|alice\|Hi\n")` → `("MSG", "alice", "Hi")` |
| Username validation | `protocol.py` | Rejects `""`, `"ab"`, `"a\|b"`, allows `"alice"` |
| Connection model | `models/connection.py` | Create, update last_seen, timeout check |
| File chunking | `file_transfer.py` | File → chunks → reassemble = identical file |

### 13.2 Integration Tests

| Test | How | Expected Result |
|---|---|---|
| Single client on localhost | Server + 1 client same machine | Messages echo back |
| 3 clients on localhost | Server + 3 clients same machine | Broadcast to all |
| LAN: 2 machines | Server on A, client on B (same Wi-Fi) | Cross-machine chat |
| Heartbeat detection | Start 2 peers, check /users | Both appear online |
| Heartbeat timeout | Start peer, then close it | Disappears after 15s |
| UDP auto-discovery | Client broadcasts DISCOVER | Client finds server |
| Self-IP detection | Client sends heartbeat | Correct LAN IP extracted |
| Private message | Alice `/dm bob hello` | Only Bob receives |
| File transfer | Alice `/file test.txt` | All peers receive file |
| Duplicate username | Two clients try "alice" | Second gets JOIN_REJECT |
| Server kill | Kill server mid-chat | Clients show "Server lost" |
| Client kill | Close one client terminal | Others see "user has left" |

---

## 14. Viva Preparation — Q&A Bank

### Networking Fundamentals

| # | Question | Answer |
|---|---|---|
| 1 | What transport protocols does your project use? | Both **TCP and UDP**. TCP (`SOCK_STREAM`) for reliable chat message delivery and file transfer. UDP (`SOCK_DGRAM`) for peer discovery, heartbeats, and server auto-detection. |
| 2 | Why use both TCP and UDP? | UDP is ideal for broadcast-based discovery — it's fast, connectionless, and supports broadcast to `255.255.255.255`. TCP is needed for chat messages because we need guaranteed, ordered delivery. |
| 3 | What is a heartbeat protocol? | A heartbeat is a periodic signal sent by each peer to announce "I'm still alive." We broadcast a UDP heartbeat every 5 seconds. If no heartbeat is received from a peer for 15 seconds, they're considered offline. |
| 4 | How does self-IP discovery work? | We broadcast a UDP packet to `255.255.255.255`. When we receive our own broadcast back, the datagram contains our LAN IP address. This avoids needing to query the OS for the network interface IP. |
| 5 | What is a socket? | An endpoint for two-way network communication. We create TCP sockets with `socket.socket(AF_INET, SOCK_STREAM)` and UDP sockets with `socket.socket(AF_INET, SOCK_DGRAM)`. |
| 6 | Explain the TCP 3-way handshake. | SYN → SYN-ACK → ACK. When our client calls `connect()`, Python handles this automatically to establish a reliable connection. |
| 7 | What does `bind(0.0.0.0, 9999)` mean? | `0.0.0.0` = listen on ALL network interfaces. `9999` = port number for application-level addressing. |
| 8 | What OSI layer does your app operate at? | Application Layer (L7). Our custom protocol sits on TCP (L4) and UDP (L4), which use IP (L3). |

### Project-Specific

| # | Question | Answer |
|---|---|---|
| 9 | What makes your project unique? | We use a **hybrid approach**: UDP for discovery/heartbeats, TCP for messages/files. This makes our chat reliable while keeping discovery fast. We support private messaging, chat history, typing indicators, file sharing, and both terminal + GUI clients. |
| 10 | How do you handle file transfer? | Files are chunked into 32 KB pieces, base64-encoded, and sent via TCP using FILE_START/FILE_DATA/FILE_END messages. TCP guarantees all chunks arrive in order, unlike unreliable UDP-based approaches. |
| 11 | How do you handle multiple clients? | The server spawns a new thread per client. Each thread runs a `client_handler()` that independently handles that client's communication. |
| 12 | What is the heartbeat timeout? | 5-second interval, 15-second timeout. If no heartbeat for 15 seconds, the peer is marked offline. |
| 13 | Can this work over the internet? | No. LAN IPs (192.168.x.x) are private and not routable. We'd need port forwarding or a public server. |
| 14 | How would you add encryption? | Wrap sockets with `ssl` module for TLS, or manually encrypt with AES from the `cryptography` library. |
| 15 | What happens if a file transfer fails mid-way? | The server tracks incomplete transfers. If no FILE_END arrives within a timeout, it discards the partial data and sends an ERROR to the sender. |

---

## 15. References

1. Python `socket` module — https://docs.python.org/3/library/socket.html
2. Python `threading` module — https://docs.python.org/3/library/threading.html
3. Beej's Guide to Network Programming — https://beej.us/guide/bgnet/
4. RFC 793 — Transmission Control Protocol (TCP)
5. RFC 768 — User Datagram Protocol (UDP)
6. Computer Networking: A Top-Down Approach — Kurose & Ross

---

## 16. Summary

| Aspect | Decision |
|---|---|
| Architecture | **Hybrid** — P2P discovery (UDP) + Client-Server messaging (TCP) |
| Transport | TCP (chat, files) + UDP (heartbeat, discovery) |
| Language | Python 3.10+ |
| Protocol | Custom text-based `TYPE\|SENDER\|CONTENT\n` — 17 message types |
| Peer Discovery | Heartbeat broadcast |
| Concurrency | `threading` — 1 thread/client on server + heartbeat thread |
| Features | 14 server + 17 client + 8 commands + GUI |
| File Transfer | TCP chunked (32 KB) |
| GUI | Tkinter (desktop) |
| Dependencies | `colorama` only |
| Timeline | 8–9 days |

---

> **Status: ✅ FINALIZED — Ready for Implementation**
