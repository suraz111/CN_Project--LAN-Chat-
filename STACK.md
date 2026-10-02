# 🛠️ Simple LAN Chat — Technology Stack Specification

> **Project Title:** Simple LAN Chat Application  
> **Subject:** Computer Networks (CN)  
> **Date:** 30 September 2026  
> **Version:** 1.0  
> **Target OS:** Cross-Platform (Windows 10/11, macOS, Linux)

---

## 1. Executive Summary & Core Stack Overview

The **Simple LAN Chat** application is engineered as a lightweight, zero-configuration peer-to-peer (P2P) desktop application designed for local area networks. The technical stack prioritizes minimal external dependencies, platform independence, direct low-level socket manipulation, and high educational value for Computer Networks concepts.

| Component Category | Technology Selected | Rationale / Purpose |
| :--- | :--- | :--- |
| **Language & Runtime** | **Python 3.10+** | High abstraction with native low-level socket support & cross-platform portability. |
| **Networking APIs** | `socket`, `select`, `ipaddress` | Direct BSD Socket API access for TCP/IP and UDP broadcast. |
| **Concurrency Model** | `threading`, `queue` | Multi-threaded I/O multiplexing without heavy async runtime overhead. |
| **UI Framework** | **Tkinter / `tkinter.ttk`** | Native GUI framework included in Python standard library; zero extra dependencies. |
| **Serialization** | `json`, `struct` | JSON for structured control signals; C-struct binary header framing for file transfer. |
| **Security & Crypto** | `cryptography` / `hashlib` | SHA-256 for file checksums; optional AES-256-GCM / RSA-2048 for E2E encryption. |
| **Packaging & Distribution**| `PyInstaller` | Single-file executable generation for Windows/Linux/macOS deployment. |

---

## 2. Core Language & Runtime

### Python 3.10+
- **Version Requirement:** `>= 3.10`
- **Features Utilized:**
  - **Structural Pattern Matching (`match / case`):** Efficient dispatching of incoming network packet types.
  - **Type Hinting (`typing`):** Strict static type safety with `mypy` support (`Optional`, `Dict`, `Tuple`, `Callable`).
  - **Thread-safe `queue.Queue`:** Secure inter-thread communication between network listener threads and Tkinter main loop.

---

## 3. Networking Subsystem & Socket APIs

The application directly interfaces with the operating system kernel network stack via standard socket interfaces.

```
+-------------------------------------------------------------------+
|                        Application Layer                          |
|         (Custom JSON Custom Framing & Binary Chunking)            |
+-----------------------------------+-------------------------------+
|         Transport Layer           |        Transport Layer        |
|             (TCP)                 |             (UDP)             |
|   - Peer-to-Peer Messaging        |   - Peer Discovery Broadcast  |
|   - File Transfer Streaming       |   - Heartbeat Keep-Alive      |
|   - Connection Handshake          |   - Presence Notification     |
+-----------------------------------+-------------------------------+
|                        Network Layer (IP)                         |
|           - IPv4 Subnet Masking (`ipaddress` module)              |
|           - Dynamic Interface Detection (`socket.getaddrinfo`)    |
+-------------------------------------------------------------------+
```

### 3.1 UDP Discovery Module (`socket.SOCK_DGRAM`)
- **Protocol:** UDP IPv4 Broadcast (`255.255.255.255`) or Subnet Broadcast (e.g., `192.168.1.255`).
- **Socket Options:**
  - `SOL_SOCKET, SO_BROADCAST`: Enables transmission of broadcast datagrams across local subnet.
  - `SOL_SOCKET, SO_REUSEADDR`: Allows multiple instances on the same host to bind to the discovery port for testing.
- **Port:** Configurable default `50000/UDP`.

### 3.2 TCP Messaging & Data Module (`socket.SOCK_STREAM`)
- **Protocol:** TCP IPv4 reliable byte-stream.
- **Socket Options:**
  - `SO_KEEPALIVE`: Operating system level TCP connection health monitoring.
  - `TCP_NODELAY`: Disables Nagle's algorithm for low-latency chat transmission.
- **Port:** Dynamic/Configurable default `50001/TCP`.

---

## 4. Graphical User Interface (GUI) Stack

### Tkinter (`tkinter` & `tkinter.ttk`)
- **Design Paradigm:** Event-driven architecture with native desktop widgets.
- **Threading Model Synchronization:**
  - Tkinter GUI runs exclusively on the **Main Thread**.
  - Background sockets send events to GUI via thread-safe `queue.Queue`.
  - GUI consumes events periodically using `root.after(50, poll_queue)`.

```
[ Network Worker Thread ]  ---( puts Message Event )---> [ Thread-Safe Queue ]
                                                                |
                                                          ( polls queue )
                                                                v
[ Tkinter Main Thread ]    <---( updates UI components )--- [ poll_queue() ]
```

---

## 5. Data Format & Serialization Stack

### 5.1 Control & Text Message Framing (JSON + Header)
- Format: `[4-Byte Length Prefix (Big-Endian Integer)] + [JSON Payload String]`
- Python Modules: `struct`, `json`

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Payload Length (Big-Endian 32-bit)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       JSON Payload Data                       |
|                             ...                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### 5.2 Binary File Transfer Framing
- Chunk Size: `64 KB` (`65,536 bytes`) optimal for socket buffers.
- Verification: SHA-256 Digest calculated on stream creation and completion.

---

## 6. Development, Testing & Verification Tooling

| Category | Tool / Library | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Static Analysis** | `mypy` | `^1.8.0` | Enforces static type checking across network models. |
| **Code Formatting** | `black` | `^24.1.0` | Standardized Python formatting code style. |
| **Unit Testing** | `pytest` | `^8.0.0` | Test suite for socket framing, JSON parsers, & peer table logic. |
| **Network Mocking** | `unittest.mock` | Standard | Mocking network sockets and packet drop scenarios. |
| **Packaging** | `pyinstaller` | `^6.3.0` | Packaging single binary executable for deployment. |

---

## 7. Tech Stack Selection Rationale

1. **Why Python Standard Library (Sockets & Tkinter)?**
   - Eliminates complex installation setups (`pip install` issues on lab machines).
   - Provides direct control over OS network primitives (ideal for Computer Networks course context).
2. **Why Hybrid UDP Broadcast + TCP P2P?**
   - Avoids single-point-of-failure server requirements.
   - UDP enables zero-configuration automatic discovery on local subnets.
   - TCP provides reliable delivery, ordered messages, and corruption-free file transfer.
3. **Why Custom Packet Framing instead of WebSockets/HTTP?**
   - Teaches fundamental network protocol design (message boundaries, framing, endianness).
   - Lightweight overhead with no HTTP web-server dependency.

---

## 8. Dependency Inventory

### Core (Zero External Installation Required for Base App)
- `socket` (Stdlib)
- `threading` (Stdlib)
- `queue` (Stdlib)
- `json` (Stdlib)
- `struct` (Stdlib)
- `tkinter` (Stdlib)
- `hashlib` (Stdlib)
- `ipaddress` (Stdlib)

### Optional Development Dependencies (`requirements-dev.txt`)
```text
pytest>=8.0.0
mypy>=1.8.0
black>=24.1.0
cryptography>=42.0.0
pyinstaller>=6.3.0
```
