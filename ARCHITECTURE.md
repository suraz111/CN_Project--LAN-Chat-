# 🏛️ Simple LAN Chat — System Architecture Specification

> **Project Title:** Simple LAN Chat Application  
> **Subject:** Computer Networks (CN)  
> **Date:** 30 September 2026  
> **Version:** 1.0  
> **Architecture Pattern:** Decentralized Hybrid Peer-to-Peer (P2P)

---

## Table of Contents
1. [System Architectural Overview](#1-system-architectural-overview)
2. [OSI & TCP/IP Network Model Mapping](#2-osi--tcpip-network-model-mapping)
3. [High-Level Architecture Diagram](#3-high-level-architecture-diagram)
4. [Subsystem Breakdown](#4-subsystem-breakdown)
   - [4.1 Peer Discovery Subsystem (UDP)](#41-peer-discovery-subsystem-udp)
   - [4.2 Connection & Messaging Engine (TCP)](#42-connection--messaging-engine-tcp)
   - [4.3 File Transfer Subsystem](#43-file-transfer-subsystem)
   - [4.4 Peer Directory & State Management](#44-peer-directory--state-management)
   - [4.5 Presentation Layer (Tkinter GUI)](#45-presentation-layer-tkinter-gui)
5. [Threading & Concurrency Architecture](#5-threading--concurrency-architecture)
6. [Data & Sequence Flow Diagrams](#6-data--sequence-flow-diagrams)
7. [Protocol & Packet Framing Architecture](#7-protocol--packet-framing-architecture)
8. [Network Fault Tolerance & Edge Case Handling](#8-network-fault-tolerance--edge-case-handling)

---

## 1. System Architectural Overview

The **Simple LAN Chat** application employs a **Hybrid Peer-to-Peer (P2P) Architecture**. It operates entirely within a local subnet (`Layer 3 IPv4 Broadcast Subnet`), avoiding any reliance on external internet connections or centralized cloud servers.

### Key Architectural Principles:
1. **Decentralized Discovery:** Peer nodes dynamically announce presence via UDP broadcasts (`50000/UDP`).
2. **Direct Peer-to-Peer Connections:** Messaging and file transfers occur over dedicated point-to-point TCP sockets (`50001/TCP`).
3. **Layered Component Separation:** Strict division between Network I/O, Data Models, Business Logic, and UI View.
4. **Thread Isolation & Safe Queue Messaging:** Asynchronous non-blocking network socket threads communicate with the single-threaded Tkinter UI event loop using thread-safe queues.

---

## 2. OSI & TCP/IP Network Model Mapping

The application maps cleanly to the 7-Layer OSI Model and 4-Layer TCP/IP Model for Computer Networks educational demonstrations.

```
+-----------------------------------------------------------------------------------------+
| OSI 7-LAYER MODEL       | TCP/IP MODEL       | SIMPLE LAN CHAT MODULE IMPLEMENTATION    |
+-------------------------+--------------------+------------------------------------------+
| 7. Application Layer    |                    | JSON Protocol, Command Parsing, UI View  |
| 6. Presentation Layer   | Application Layer  | Custom Length-Prefix Framing, SHA-256    |
| 5. Session Layer        |                    | Peer Table State, Heartbeat Manager      |
+-------------------------+--------------------+------------------------------------------+
| 4. Transport Layer      | Transport Layer    | TCP (Reliable Data/Files), UDP (Discov.) |
+-------------------------+--------------------+------------------------------------------+
| 3. Network Layer        | Internet Layer     | IPv4 Subnet Masking (`ipaddress` module) |
+-------------------------+--------------------+------------------------------------------+
| 2. Data Link Layer      | Network Interface  | Ethernet / Wi-Fi MAC Layer Frames (OS)   |
| 1. Physical Layer       | Layer              | Physical Medium (Cat6, Wi-Fi 802.11)     |
+-----------------------------------------------------------------------------------------+
```

---

## 3. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------------+
|                                    GUI / UI LAYER                                       |
|                  (Tkinter Main Thread - Event-Driven Control Engine)                    |
+-------------------------------------------+---------------------------------------------+
                                            |  Queue Notifications
                                            v
+-----------------------------------------------------------------------------------------+
|                                CORE APP CONTROLLER                                      |
|                     (Peer Registry, State Manager, Configuration)                       |
+--------------------+-----------------------------------------------+--------------------+
                     |                                               |
        UDP Messages |                                  TCP Socket   |
                     v                                    Data       v
+--------------------+-------------------+   +-----------------------+--------------------+
|     DISCOVERY ENGINE (UDP BROADCAST)   |   |        MESSAGING & FILE ENGINE (TCP)       |
|  +-------------------+---------------+ |   |  +-------------------+-------------------+ |
|  |  Broadcast Sender | Receiver Thread| |   |  | TCP Server Listener| Active TCP Clients| |
|  +-------------------+---------------+ |   |  +-------------------+-------------------+ |
+--------------------+-------------------+   +-----------------------+--------------------+
                     |                                               |
                     v                                               v
+--------------------+-----------------------------------------------+--------------------+
|                                OPERATING SYSTEM KERNEL                                  |
|                               (BSD Socket API & NIC Driver)                             |
+-----------------------------------------------------------------------------------------+
```

---

## 4. Subsystem Breakdown

### 4.1 Peer Discovery Subsystem (UDP)
- **Role:** Automatic peer detection and live presence tracking without manual IP entry.
- **Components:**
  - **`HeartbeatSender` (Thread):** Emits a UDP broadcast packet every `3 seconds` containing Username, Device Name, TCP Port, and App Version.
  - **`DiscoveryListener` (Thread):** Binds to `50000/UDP`, parses incoming broadcast datagrams, and updates the local Peer Directory.

### 4.2 Connection & Messaging Engine (TCP)
- **Role:** Handles high-speed, reliable, ordered delivery of instant messages and chat notifications.
- **Components:**
  - **`TCPServer` (Thread):** Listens on `50001/TCP` for incoming peer connection requests.
  - **`TCPClientManager`:** Spawns and manages active persistent connection sockets to target peers.
  - **`MessagePacker / Unpacker`:** Handles 4-byte big-endian header length framing to prevent TCP stream concatenation/fragmentation issues.

### 4.3 File Transfer Subsystem
- **Role:** Zero-corruption high-speed file and image transmission across local peers.
- **Mechanism:**
  - **Handshake Protocol:** Sender sends `FILE_REQUEST` with filename, filesize, and SHA-256 hash. Receiver accepts (`FILE_ACCEPT`) or rejects (`FILE_REJECT`).
  - **Chunked Transfer Engine:** Streams file content in `64 KB` fixed binary blocks.
  - **Hash Verification:** Recipient computes SHA-256 digest on completed byte stream to verify file integrity before opening.

### 4.4 Peer Directory & State Management
- **Role:** In-memory registry tracking live network participants.
- **Peer Life Cycle:**
  ```
  [ DISCOVERED ] ---> ( Receives Heartbeats ) ---> [ ACTIVE ]
         |                                           |
  ( Misses 3 Heartbeats )                    ( Send Goodbye Msg )
         |                                           |
         v                                           v
    [ TIMEOUT ] --------------------------------> [ OFFLINE ]
  ```

### 4.5 Presentation Layer (Tkinter GUI)
- **Role:** User interface for user interactions, room views, peer lists, and file transfer progress bars.
- **Thread Safety:** All network threads push updates to a thread-safe `queue.Queue()`. The GUI reads queue items inside `root.after()` cycles.

---

## 5. Threading & Concurrency Architecture

The application runs a clean, multi-threaded worker model:

```
[ Application Process ]
  ├── Thread 1: Main Thread (Tkinter GUI & Event Loop)
  ├── Thread 2: UDP Discovery Listener (Port 50000)
  ├── Thread 3: UDP Heartbeat Broadcast Worker (Every 3s)
  ├── Thread 4: TCP Master Server Listener (Port 50001)
  └── Thread N...: Active TCP Worker Threads per active peer connection
```

---

## 6. Data & Sequence Flow Diagrams

### 6.1 Peer Discovery & Presence Flow

```
Peer A (192.168.1.10)                        Peer B (192.168.1.20)
   |                                            |
   |---- UDP Broadcast Heartbeat (Port 50000) ->| (Peer B receives heartbeat)
   |     {"user":"Alice", "tcp_port":50001}     |---> Updates Peer Table: Alice (Online)
   |                                            |
   |<--- UDP Broadcast Heartbeat (Port 50000)---| (Peer A receives heartbeat)
   |     {"user":"Bob", "tcp_port":50001}       |
   |---> Updates Peer Table: Bob (Online)       |
```

### 6.2 Direct Message & File Transfer Flow

```
Sender (Alice)                               Receiver (Bob)
   |                                            |
   |========== TCP Handshake (Port 50001) =====>| [TCP Connection Established]
   |                                            |
   |--- 4-Byte Length + JSON Msg Payload ------>| [Decodes & Displays Chat Msg]
   |                                            |
   |--- 4-Byte Length + FILE_REQUEST JSON ----->| [Prompts User: Accept File?]
   |<-- 4-Byte Length + FILE_ACCEPT JSON -------| [User Accepts]
   |                                            |
   |=== Binary Stream (64KB Chunks) ===========>| [Writes File & Updates Progress Bar]
   |--- 4-Byte Length + FILE_COMPLETE JSON ---->| [Verifies SHA-256 Hash Digest]
```

---

## 7. Protocol & Packet Framing Architecture

### 7.1 Text & Control Frame Standard

```text
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Payload Size (N Bytes)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         JSON Payload                          |
|                       (UTF-8 Encoded)                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

---

## 8. Network Fault Tolerance & Edge Case Handling

1. **Packet Concatenation & Partial Framing:** Solved via 4-byte explicit payload size prefixes.
2. **Subnet Isolation:** Automatically computes subnet broadcast address (e.g., `192.168.1.255`) if global broadcast `255.255.255.255` is blocked by OS routing tables.
3. **Unexpected Peer Disconnect:** TCP sockets set socket timeout (`5.0s`) and handle `ConnectionResetError` gracefully.
4. **Duplicate Heartbeats:** Deduplicated using unique Peer UUIDs to support IP changes on Wi-Fi reconnects.
