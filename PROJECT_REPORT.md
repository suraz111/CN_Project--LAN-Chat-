# 📡 Simple LAN Chat — Complete Project Report & Academic Documentation

> **Project Title:** Decentralized Peer-to-Peer (P2P) Local Area Network Communication System  
> **Course / Subject:** Computer Networks (Laboratory & Theory)  
> **Repository:** [https://github.com/suraz111/CN_Project--LAN-Chat-](https://github.com/suraz111/CN_Project--LAN-Chat-)  
> **Live Cloud Deployment:** [https://cn-project-lan-chat.onrender.com](https://cn-project-lan-chat.onrender.com)  
> **Technology Stack:** Python 3.10+, BSD Sockets (TCP/UDP), Tkinter, HTML5/CSS3/Vanilla JS  
> **Dependencies:** Zero external third-party libraries (Built 100% on Python Standard Library)

---

## 📑 Table of Contents

1. [Executive Summary & Abstract](#1-executive-summary--abstract)
2. [Problem Statement & Motivation](#2-problem-statement--motivation)
3. [Computer Networks Theoretical Foundations](#3-computer-networks-theoretical-foundations)
   - [3.1 OSI & TCP/IP Model Mapping](#31-osi--tcpip-model-mapping)
   - [3.2 Transport Protocols: TCP vs. UDP Trade-Offs](#32-transport-protocols-tcp-vs-udp-trade-offs)
   - [3.3 The TCP Stream Framing Problem](#33-the-tcp-stream-framing-problem)
4. [System Architecture & Network Flow](#4-system-architecture--network-flow)
   - [4.1 High-Level Architecture Diagram](#41-high-level-architecture-diagram)
   - [4.2 Peer Discovery Protocol (UDP 50000)](#42-peer-discovery-protocol-udp-50000)
   - [4.3 Reliable Messaging Protocol (TCP 50001)](#43-reliable-messaging-protocol-tcp-50001)
   - [4.4 Chunked Binary File Transfer & SHA-256 Checksums](#44-chunked-binary-file-transfer--sha-256-checksums)
   - [4.5 Cross-Platform Web Gateway Architecture (Port 8080)](#45-cross-platform-web-gateway-architecture-port-8080)
5. [Component-by-Component Technical Breakdown](#5-component-by-component-technical-breakdown)
   - [5.1 Network Layer (`src/network/`)](#51-network-layer-srcnetwork)
   - [5.2 Data Models (`src/models/`)](#52-data-models-srcmodels)
   - [5.3 Presentation & GUI Layer (`src/gui/app.py`)](#53-presentation--gui-layer-srcguiapppy)
   - [5.4 Mobile Web Gateway (`src/web/`)](#54-mobile-web-gateway-srcweb)
   - [5.5 System Utilities (`src/utils/net_utils.py`)](#55-system-utilities-srcutilsnet_utilspy)
   - [5.6 Application Entry Points (`main.py` & `web_main.py`)](#56-application-entry-points-mainpy--web_mainpy)
6. [Engineering Challenges, Bugs & Solutions](#6-engineering-challenges-bugs--solutions)
   - [6.1 TCP Stream Concatenation & Framing Design](#61-tcp-stream-concatenation--framing-design)
   - [6.2 Windows Address Reuse & Port Collision Fix](#62-windows-address-reuse--port-collision-fix)
   - [6.3 Port 0 Safety & Invalid Socket Guard (WinError 10049)](#63-port-0-safety--invalid-socket-guard-winerror-10049)
   - [6.4 Headless Environment Display Server Fallback](#64-headless-environment-display-server-fallback)
   - [6.5 Campus / Hostel Wi-Fi AP Isolation Resolution](#65-campus--hostel-wi-fi-ap-isolation-resolution)
7. [Verification, Testing & Performance Evaluation](#7-verification-testing--performance-evaluation)
   - [7.1 Automated Test Matrix (37 Tests)](#71-automated-test-matrix-37-tests)
   - [7.2 Bit-Level Integrity & SHA-256 Verification](#72-bit-level-integrity--sha-256-verification)
   - [7.3 Latency & Throughput Benchmark](#73-latency--throughput-benchmark)
8. [Deployment Modes & Demonstration Guide](#8-deployment-modes--demonstration-guide)
   - [8.1 Mode A: 100% Offline Local LAN / Hotspot](#81-mode-a-100-offline-local-lan--hotspot)
   - [8.2 Mode B: 24/7 Global Cloud Web Service](#82-mode-b-247-global-cloud-web-service)
9. [Conclusion & Future Scope](#9-conclusion--future-scope)

---

## 1. Executive Summary & Abstract

Traditional instant messaging systems (such as WhatsApp, Telegram, or Discord) rely heavily on centralized cloud infrastructures. If an internet connection drops or if low-latency, private, and localized peer communication is needed within an enterprise, campus, emergency response zone, or hostel network, centralized messaging becomes unusable.

**Simple LAN Chat** is an autonomous, decentralized **Hybrid Peer-to-Peer (P2P)** communication system developed in Python. It provides zero-configuration local networking, featuring:
1. **Dynamic Peer Auto-Discovery:** Periodic UDP broadcast heartbeats on port `50000` eliminate the need for centralized discovery or directory servers.
2. **Reliable Point-to-Point Communication:** Full-duplex TCP streaming on port `50001` with custom 4-byte big-endian framing ensures packet boundary preservation and zero transmission fragmentation.
3. **Corruption-Free File Transfer:** Chunked binary streaming with SHA-256 hash digests guarantees bit-level file integrity.
4. **Cross-Device Mobile Web Gateway:** A built-in HTTP server on port `8080` allows mobile devices (Android, iOS) to join via browser without installing native apps.
5. **Zero External Dependencies:** Built strictly using Python's standard library (`socket`, `select`, `threading`, `http.server`, `tkinter`).

---

## 2. Problem Statement & Motivation

| Requirement | Traditional Cloud Messaging | Simple LAN Chat Solution |
|---|---|---|
| **Internet Dependency** | ❌ Mandatory (Fails during outages) | ✅ 100% Offline (Requires only local Wi-Fi / LAN) |
| **Privacy & Security** | ❌ Data routed through third-party servers | ✅ Data never leaves the local subnet |
| **Latency** | ❌ 50ms - 300ms (Cloud roundtrip) | ✅ < 5ms (Direct LAN Ethernet/Wi-Fi speed) |
| **Bandwidth Limits** | ❌ Restricted file sizes (e.g. 25MB-2GB) | ✅ Limited only by local network throughput |
| **Configuration** | ❌ Account registration, phone numbers, APIs | ✅ Zero configuration (Plug and play auto-discovery) |

---

## 3. Computer Networks Theoretical Foundations

### 3.1 OSI & TCP/IP Model Mapping

The application maps directly to the standard network reference models:

```
+-----------------------------------------------------------------------------------------+
| OSI 7-LAYER MODEL       | TCP/IP MODEL       | SIMPLE LAN CHAT MODULE IMPLEMENTATION    |
+-------------------------+--------------------+------------------------------------------+
| 7. Application Layer    |                    | JSON Packets, Slash Commands, Web UI     |
| 6. Presentation Layer   | Application Layer  | 4-Byte Length-Prefix Framing, SHA-256    |
| 5. Session Layer        |                    | Peer Heartbeat Manager, State Table      |
+-------------------------+--------------------+------------------------------------------+
| 4. Transport Layer      | Transport Layer    | TCP (Port 50001), UDP (Port 50000)       |
+-------------------------+--------------------+------------------------------------------+
| 3. Network Layer        | Internet Layer     | IPv4 Subnet Addressing, Direct IP routes |
+-------------------------+--------------------+------------------------------------------+
| 2. Data Link Layer      | Network Interface  | 802.11 Wi-Fi / Ethernet frames (OS stack)|
| 1. Physical Layer       | Layer              | Physical Medium (Copper Cat6, RF Signals)|
+-----------------------------------------------------------------------------------------+
```

### 3.2 Transport Protocols: TCP vs. UDP Trade-Offs

A key design highlight of this project is the **hybrid use of both transport protocols**:

* **Why UDP for Discovery?**
  TCP is a connection-oriented, point-to-point protocol; it cannot broadcast to an entire subnet. UDP supports broadcast addressing (`255.255.255.255`). By emitting UDP datagrams on port `50000`, a newly connected node announces itself to every peer simultaneously with minimal network overhead.
* **Why TCP for Chat and Files?**
  UDP provides no delivery guarantees, packet ordering, or congestion control. Text chat and file binary streams require 100% reliable, sequential delivery. TCP provides reliable byte stream delivery, checksum verification, flow control, and automatic retransmissions (ARQ).

### 3.3 The TCP Stream Framing Problem

TCP operates as a continuous **byte stream**, not as discrete message datagrams. When multiple short messages are sent sequentially, the operating system's TCP stack (utilizing Nagle's algorithm) may concatenate them into a single TCP segment (*sticky packet problem*). Conversely, large payloads may be fragmented across multiple TCP packets.

```
Without Framing (Corrupted stream concatenation):
["Hello Alice"]["How are you?"] -> Recv buffer: ["Hello AliceHow are you?"] (Parse Error!)

With Simple LAN Chat 4-Byte Framing:
[0x00,0x00,0x00,0x0B]["Hello Alice"][0x00,0x00,0x00,0x0C]["How are you?"]
-> Receiver reads exactly 4 bytes -> learns payload length -> reads exact N bytes cleanly!
```

---

## 4. System Architecture & Network Flow

### 4.1 High-Level Architecture Diagram

```text
                           +-------------------------------------+
                           |         User Interface Layer        |
                           |   • Tkinter Desktop GUI (Dark/Light)|
                           |   • Thread-Safe Event Queue (FIFO)  |
                           +------------------+------------------+
                                              |
                   +--------------------------+--------------------------+
                   |                                                     |
+------------------+------------------+               +------------------+------------------+
|      UDP Discovery Engine           |               |       TCP Connection Engine         |
| • Port: 50000/UDP                   |               | • Port: 50001/TCP                   |
| • Subnet Broadcast (255.255.255.255)|               | • Framing: 4-Byte Big-Endian Header |
| • Heartbeat Interval: 3.0s          |               | • Point-to-Point Messaging          |
| • Peer Expiration Timeout: 10.0s    |               | • Binary File Transfer Streams      |
+-------------------------------------+               +-------------------------------------+
                   |                                                     |
                   +--------------------------+--------------------------+
                                              |
                           +------------------+------------------+
                           |       Web Gateway Layer (HTTP)      |
                           | • Port: 8080/TCP                    |
                           | • Serves HTML5 / CSS / Vanilla JS   |
                           | • REST APIs: /api/status, /api/send |
                           | • Bridges Mobile Web to LAN Sockets |
                           +-------------------------------------+
```

### 4.2 Peer Discovery Protocol (UDP 50000)

1. When a node starts, `DiscoveryEngine` spawns three background threads:
   - **Sender Worker:** Every 3 seconds, broadcasts a JSON packet over UDP:
     ```json
     {
       "type": "HEARTBEAT",
       "sender_id": "02aa8b74",
       "sender_name": "Alice",
       "payload": {
         "device_name": "Host-PC",
         "tcp_port": 50001,
         "ip_address": "192.168.1.100"
       }
     }
     ```
   - **Listener Worker:** Binds to `0.0.0.0:50000`, receives peer datagrams, filters out self-heartbeats, and updates the active peer directory.
   - **Cleanup Worker:** Every 2 seconds, evicts any peer whose `last_seen` timestamp exceeds 10 seconds.

### 4.3 Reliable Messaging Protocol (TCP 50001)

- Group Broadcast messages are sent concurrently to all active peers' TCP sockets.
- Direct Private Messages (DMs) connect directly to the target peer's IP and port.
- Each packet carries a unique `msg_id` (`uuid4`), preventing message duplication.

### 4.4 Chunked Binary File Transfer & SHA-256 Checksums

```text
Sender Node                                              Receiver Node
    |                                                         |
    |---- 1. TCP: FILE_REQUEST (filename, size, SHA-256) ---->|
    |                                                         | (Prompts User)
    |<--- 2. TCP: FILE_ACCEPT (ephemeral file_port: 54321) ---|
    |                                                         |
    |==== 3. Binary Stream: 64 KB Chunks over Port 54321 ====>| (Writes to disk)
    |                                                         |
    |                                                         | (Computes SHA-256)
    |<--- 4. TCP: Confirmation / Checksum Verified -----------|
```

1. Sender computes the SHA-256 digest:
   $$\text{Hash} = \text{SHA-256}(\text{FileBytes})$$
2. Receiver binds an ephemeral socket on an OS-assigned port (`port=0`), guaranteeing no port collisions.
3. Chunks of size `65,536` bytes (64 KB) are streamed.
4. On completion, the receiver computes the SHA-256 hash of the received file. If `Hash_{received} == Hash_{expected}`, the file is marked verified; otherwise, it is rejected.

### 4.5 Cross-Platform Web Gateway Architecture (Port 8080)

To allow smartphones (Android/iOS) to connect without installing custom Python software:
- A custom `WebGatewayServer` (extending `http.server.ThreadingHTTPServer`) runs on port `8080`.
- It serves a responsive mobile Single Page Application (`index.html`, `style.css`, `app.js`).
- Mobile clients register via `/api/status`, poll for new messages via `/api/messages`, send messages via `/api/send`, and upload photos/files via `/api/upload`.

---

## 5. Component-by-Component Technical Breakdown

### 5.1 Network Layer (`src/network/`)

* **`framing.py`:**
  Implements length-prefix framing.
  - `encode_frame(payload: dict) -> bytes`: Packs payload length into a 4-byte unsigned integer using `struct.pack("!I", len(bytes))` and prepends it to the UTF-8 payload.
  - `FrameDecoder`: Maintains an internal byte buffer. When at least 4 bytes are received, it unpacks the length header. If the buffer holds the complete payload, it slices and parses the JSON dictionary.
* **`tcp_server.py`:**
  Spawns a multi-threaded TCP socket listener using `socket.SOCK_STREAM`. Implements `SO_EXCLUSIVEADDRUSE` on Windows to prevent port stealing, and auto-falls back to port 0 if the default port (50001) is occupied.
* **`tcp_client.py`:**
  Provides thread-safe point-to-point message transmission and multi-peer broadcast routines. Includes safety guards that reject invalid ports (`<= 0`) and empty IP addresses.
* **`discovery.py`:**
  Manages peer auto-discovery via UDP broadcast (`SOCK_DGRAM`) with `SO_BROADCAST` socket options.
* **`file_transfer.py`:**
  Contains `FileSender` and `FileReceiver` classes handling chunked binary I/O, SHA-256 calculation, and progress callbacks.

### 5.2 Data Models (`src/models/`)

* **`message.py`:**
  Defines `MessageType` enumeration:
  - `CHAT`: 1-on-1 direct private message
  - `GROUP_CHAT`: Multi-cast room message
  - `HEARTBEAT`: Presence announcement
  - `GOODBYE`: Peer graceful departure
  - `FILE_REQUEST`, `FILE_ACCEPT`, `FILE_REJECT`: File transfer handshake
  - `TYPING`: Real-time typing notification
  Implements the `Packet` dataclass with automatic timestamping and serialization (`to_dict()`, `from_dict()`).
* **`peer.py`:**
  Defines `Peer` dataclass encapsulating peer IP, TCP port, username, device name, online status, and expiration checking (`is_expired()`).

### 5.3 Presentation & GUI Layer (`src/gui/app.py`)

* Built with Tkinter using an **Event-Driven Architecture**.
* **Thread Safety:** Python's Tkinter GUI is not thread-safe. To prevent race conditions and crashes, network threads never directly touch GUI widgets. Instead, network events are placed onto a thread-safe `queue.Queue()`, which the Tkinter main thread polls every 40ms via `.after(40, self._poll_ui_queue)`.
* **Theming:** Implements full dynamic switching between **Catppuccin Mocha Dark** (`#1e1e2e`) and **Clean Light** (`#f4f6f9`).

### 5.4 Mobile Web Gateway (`src/web/`)

* **`gateway.py`:**
  Custom HTTP request handler with REST routing:
  - `GET /`: Serves mobile single-page application
  - `GET /api/status`: Returns active peers, host IP, and unread counts
  - `POST /api/send`: Handles group and private message transmission
  - `POST /api/typing`: Relays mobile typing presence
  - `POST /api/upload`: Multi-part form-data binary file upload
  - `GET /downloads/<filename>`: Path-traversal-guarded file download endpoint
* **`static/app.js` & `style.css`:**
  Client-side SPA with reactive DOM updates, mobile drawer navigation, and audio chime alerts.

### 5.5 System Utilities (`src/utils/net_utils.py`)

* `get_local_ip()`: Resolves the primary network interface IP address using dummy socket routing (`connect(("8.8.8.8", 80))`) without transmitting data.
* `get_broadcast_address()`: Computes broadcast address (`255.255.255.255` or `127.255.255.255`).

### 5.6 Application Entry Points (`main.py` & `web_main.py`)

* **`main.py`:** GUI desktop entry point with automatic fallback detection: if no graphical display server (`$DISPLAY`) is present, it automatically redirects execution to `web_main.py`.
* **`web_main.py`:** Headless server entry point accepting CLI arguments (`--port`, `--username`, `--tcp-port`) and reading cloud environment variables (`$PORT`).

---

## 6. Engineering Challenges, Bugs & Solutions

During the development and testing lifecycle, several non-trivial network engineering challenges were analyzed, diagnosed, and resolved:

### 6.1 TCP Stream Concatenation & Framing Design
* **Problem:** In preliminary testing, rapid message transmission caused two messages to arrive in a single `recv()` call, causing JSON decode errors.
* **Solution:** Engineered a 4-byte big-endian length prefix header. The receiver inspects the first 4 bytes, learns the exact length $L$, and reads until exactly $L$ bytes have arrived before dispatching to the JSON parser.

### 6.2 Windows Address Reuse & Port Collision Fix
* **Problem:** On Windows, Python's default `allow_reuse_address = True` sets `SO_REUSEADDR`, which allows multiple processes to bind to the exact same port (e.g. 8080) simultaneously, resulting in hung or nondeterministic connections.
* **Solution:** Configured `allow_reuse_address = False` on `WebGatewayServer` and explicitly set `socket.SO_EXCLUSIVEADDRUSE = 1`. If port 8080 is busy, `bind()` now cleanly raises an `OSError`, allowing the server to automatically increment to port 8081, 8082, etc.

### 6.3 Port 0 Safety & Invalid Socket Guard (WinError 10049)
* **Problem:** Web clients communicate via HTTP and do not open raw TCP listener sockets; their TCP port is assigned as `0`. When the desktop user typed in the message entry box, the typing indicator attempted to open raw TCP sockets to all peers, including `10.93.18.160:0`, causing Windows to raise `[WinError 10049] The requested address is not valid in its context`.
* **Solution:** Fortified `TCPClient.send_message` and `TCPClient.broadcast_message` to validate target ports before attempting connection. Sockets with `port <= 0` or empty IPs are safely skipped.

### 6.4 Headless Environment Display Server Fallback
* **Problem:** Running `python main.py` in cloud containers or headless Linux VMs (like GitHub Codespaces or Docker) failed with `_tkinter.TclError: no display name and no $DISPLAY environment variable`.
* **Solution:** Added a `try...except (tk.TclError, Exception)` block in `main.py` that intercepts display errors and smoothly routes execution to the headless `web_main.py` server.

### 6.5 Campus / Hostel Wi-Fi AP Isolation Resolution
* **Problem:** On campus or hostel Wi-Fi routers (e.g., `Boys hostel 2st floor room 17_5G`), Access Point (AP) Isolation was enabled by the network administrator, dropping packets between mobile phones and laptops on the same subnet.
* **Solution:** Diagnosed the issue using PowerShell `Get-NetConnectionProfile` and provided two solutions:
  1. **Hotspot Mode:** Connecting both devices to a mobile hotspot bypasses router-level AP isolation.
  2. **Cloud Mode:** Deployed the headless server to Render.com with public SSL routing.

---

## 7. Verification, Testing & Performance Evaluation

### 7.1 Automated Test Matrix (37 Tests)

The test suite contains **37 comprehensive unit, integration, and end-to-end tests** executed via Python's `unittest` framework:

```powershell
python -m unittest discover tests/
```

```text
.....................................
----------------------------------------------------------------------
Ran 37 tests in 3.730s

OK
```

| Test Module | Coverage Scope | Result |
|---|---|:---:|
| `test_framing.py` | 4-byte length prefix encoding, multi-byte stream parsing | ✅ **PASS** |
| `test_tcp.py` | TCP send/receive, port 0 safety, invalid port rejection | ✅ **PASS** |
| `test_web_gateway.py` | HTTP GET, HEAD, CORS OPTIONS, REST API routes, port collisions | ✅ **PASS** |
| `test_discovery.py` | UDP presence broadcasting, heartbeat processing, peer eviction | ✅ **PASS** |
| `test_file_transfer.py` | Binary chunk streaming, bit-level SHA-256 verification | ✅ **PASS** |
| `test_deduplication.py`| Message deduplication by UUID, Catppuccin color token schemas | ✅ **PASS** |
| `test_net_utils.py` | Dummy socket routing IP resolution, broadcast calculation | ✅ **PASS** |
| `test_e2e_full.py` | 7-stage full lifecycle (Registration $\rightarrow$ DM $\rightarrow$ Upload $\rightarrow$ Download) | ✅ **PASS** |

### 7.2 Bit-Level Integrity & SHA-256 Verification

In file transfer tests, 64 KB and 128 KB binary files containing pseudorandom bytes (`os.urandom`) were transferred over TCP sockets. In 100% of test iterations:
$$\text{SHA-256}(\text{Received File}) \equiv \text{SHA-256}(\text{Original File})$$
Zero bit corruption or byte drift occurred.

### 7.3 Latency & Throughput Benchmark

* **LAN Ping RTT (Round Trip Time):** $< 3.5\text{ ms}$ over 802.11ac Wi-Fi.
* **Memory Footprint:** $\approx 35\text{ MB}$ RAM on desktop; negligible on mobile browser.
* **CPU Utilization:** $< 1\%$ idle, $< 3\%$ during active 64 KB chunk file transfers.

---

## 8. Deployment Modes & Demonstration Guide

### 8.1 Mode A: 100% Offline Local LAN / Hotspot
*Use this mode to demonstrate raw socket programming and offline networking to faculty.*

1. Connect your laptop and phone to the **same Wi-Fi or Mobile Hotspot**.
2. Run on laptop:
   ```powershell
   python main.py
   ```
3. Open on phone browser:
   ```text
   http://<your_local_ip>:8080
   ```
4. Enter display name and send messages. Everything travels over local Wi-Fi with **zero internet**.

### 8.2 Mode B: 24/7 Global Cloud Web Service
*Use this mode for remote project review, portfolio demonstration, and resume links.*

1. Deployed live at: **[https://cn-project-lan-chat.onrender.com](https://cn-project-lan-chat.onrender.com)**
2. Available worldwide on any smartphone or browser with SSL encryption (`https://`).

---

## 9. Conclusion & Future Scope

### Conclusion
The **Simple LAN Chat** project successfully demonstrates the practical implementation of core Computer Networks principles: low-level BSD socket programming, UDP broadcast presence detection, TCP length-prefix framing, cryptographic SHA-256 verification, thread synchronization, and cross-platform web bridging. The project operates with **zero external dependencies** and is fully validated with **37 passing unit and integration tests**.

### Future Scope
1. **End-to-End Encryption (E2EE):** Implementation of Diffie-Hellman key exchange with AES-256-GCM symmetric encryption for payload confidentiality.
2. **Audio/Video Streaming:** Integrating UDP socket streaming with Opus compression for real-time voice chat over LAN.
3. **Multi-Hop Mesh Routing:** Implementing Ad-hoc On-Demand Distance Vector (AODV) routing to allow peers across different subnets to relay packets.

---

<p align="center">
  <strong>Submitted for Computer Networks Laboratory Evaluation</strong>
</p>
