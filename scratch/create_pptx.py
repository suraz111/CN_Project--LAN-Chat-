"""
Generate a PowerPoint presentation for the LAN Chat project.
Run: python scratch/create_pptx.py
Requires: pip install python-pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import os

# ── Colour palette ──────────────────────────────────────────────
BG        = RGBColor(0x0D, 0x11, 0x17)   # near-black background
CARD      = RGBColor(0x16, 0x1B, 0x22)   # card / slide body
ACCENT    = RGBColor(0x58, 0xA6, 0xFF)   # bright blue accent
ACCENT2   = RGBColor(0x3F, 0xB9, 0x50)   # green tick accent
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT     = RGBColor(0xC9, 0xD1, 0xD9)
SUBTLE    = RGBColor(0x58, 0x66, 0x69)
YELLOW    = RGBColor(0xFF, 0xD7, 0x00)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]   # fully blank


def add_slide():
    return prs.slides.add_slide(BLANK)


def bg(slide, color=BG):
    """Fill slide background."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def box(slide, l, t, w, h, fill_color=None, border_color=None, border_pt=0):
    """Add a rectangle shape."""
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if border_color and border_pt:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(border_pt)
    else:
        shape.line.fill.background()
    return shape


def txt(slide, text, l, t, w, h, size=18, bold=False, color=WHITE,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    """Add a text box."""
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb


def accent_bar(slide, y=0.55, height=0.06):
    """Thin coloured accent line."""
    box(slide, 0, y, 13.33, height, fill_color=ACCENT)


# ────────────────────────────────────────────────────────────────
# SLIDE 1 — TITLE
# ────────────────────────────────────────────────────────────────
s1 = add_slide(); bg(s1)
box(s1, 0, 0, 13.33, 7.5, fill_color=BG)

# left glowing stripe
box(s1, 0, 0, 0.12, 7.5, fill_color=ACCENT)

txt(s1, "📡 LAN Chat", 0.4, 0.9, 12, 1.4, size=54, bold=True, color=ACCENT)
txt(s1, "Offline-First Peer-to-Peer Messenger", 0.4, 2.2, 12, 0.7,
    size=26, bold=False, color=WHITE)
txt(s1, "Zero Internet  •  Zero Installation  •  Instant LAN Sharing via QR Code",
    0.4, 3.0, 12, 0.6, size=18, color=LIGHT)

# divider
box(s1, 0.4, 3.75, 8, 0.04, fill_color=ACCENT)

txt(s1, "Computer Networks (CN) Lab  |  Group Presentation", 0.4, 3.95, 9, 0.5,
    size=14, color=SUBTLE)
txt(s1, "Technology Stack: Python • TCP • UDP • HTTP • JavaScript",
    0.4, 4.45, 9, 0.5, size=13, color=SUBTLE)

# badge chips
chips = [("🐍 Python 3.10+", 0.4), ("📡 TCP / UDP", 2.2), ("🔒 Zero Deps", 4.0),
         ("✅ 61 Tests", 5.8), ("📱 Mobile-First", 7.6), ("🔗 QR Invite", 9.4)]
for label, left in chips:
    box(s1, left, 5.6, 1.6, 0.42, fill_color=RGBColor(0x21, 0x26, 0x2D),
        border_color=ACCENT, border_pt=1)
    txt(s1, label, left + 0.05, 5.62, 1.5, 0.38, size=11, color=ACCENT,
        align=PP_ALIGN.CENTER)


# ────────────────────────────────────────────────────────────────
# SLIDE 2 — PROBLEM STATEMENT
# ────────────────────────────────────────────────────────────────
s2 = add_slide(); bg(s2)
txt(s2, "The Problem", 0.5, 0.25, 12, 0.7, size=38, bold=True, color=ACCENT)
accent_bar(s2, 1.05, 0.05)

problems = [
    ("☁️  Cloud Dependency",
     "WhatsApp, Telegram, Slack — all require active internet.\nDeadlines during internet outages? Impossible."),
    ("🔐  Privacy at Risk",
     "Messages route through foreign servers.\nConversations are logged and monetised."),
    ("📵  Campus / Hostel Wi-Fi",
     "University networks often block peer-to-peer and VoIP.\nYet devices ARE physically in the same room."),
    ("💻  No Universal Approach",
     "Existing LAN tools require software installation\nor IT administrator privileges."),
]

cols = [(0.4, 1.3), (6.9, 1.3), (0.4, 4.0), (6.9, 4.0)]
for (title, body), (cl, ct) in zip(problems, cols):
    box(s2, cl, ct, 6.0, 2.5, fill_color=RGBColor(0x16, 0x1B, 0x22),
        border_color=ACCENT, border_pt=1)
    txt(s2, title, cl + 0.2, ct + 0.2, 5.6, 0.5, size=17, bold=True, color=ACCENT)
    txt(s2, body, cl + 0.2, ct + 0.75, 5.6, 1.6, size=13, color=LIGHT)


# ────────────────────────────────────────────────────────────────
# SLIDE 3 — OUR SOLUTION
# ────────────────────────────────────────────────────────────────
s3 = add_slide(); bg(s3)
txt(s3, "Our Solution", 0.5, 0.25, 12, 0.7, size=38, bold=True, color=ACCENT2)
accent_bar(s3, 1.05, 0.05)

txt(s3,
    "LAN Chat turns any laptop into a private, offline chat server.\nAnyone on the same Wi-Fi joins by scanning a QR code — no app, no account, no internet needed.",
    0.5, 1.2, 12.3, 1.0, size=18, color=WHITE)

pillars = [
    ("🔗 Scan & Join", "Scan the QR code.\nBrowser opens. Done.\n< 10 seconds."),
    ("🏠 Private Networks", "Each host creates an\nisolated network session\nwith a unique code."),
    ("💬 Dynamic Rooms", "Create #classroom,\n#study rooms on demand.\nNo preconfigured channels."),
    ("📁 File Sharing", "Drag & drop files,\nvoice notes, images\nwith SHA-256 verification."),
]

left_positions = [0.4, 3.6, 6.8, 10.0]
for (title, body), lp in zip(pillars, left_positions):
    box(s3, lp, 2.4, 2.8, 3.8, fill_color=RGBColor(0x13, 0x1A, 0x20),
        border_color=ACCENT2, border_pt=1.5)
    txt(s3, title, lp + 0.15, 2.6, 2.5, 0.55, size=17, bold=True, color=ACCENT2)
    txt(s3, body, lp + 0.15, 3.2, 2.5, 2.8, size=13.5, color=LIGHT)


# ────────────────────────────────────────────────────────────────
# SLIDE 4 — NETWORK ARCHITECTURE
# ────────────────────────────────────────────────────────────────
s4 = add_slide(); bg(s4)
txt(s4, "Network Architecture", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s4, 0.95, 0.05)

arch_text = """\
┌────────────────────────────────────────────────────────────────────────────┐
│                  ┌───────────────────────────────────┐                     │
│   DISCOVERY      │  UDP Broadcast on Port 50000       │  Heartbeat every 3s │
│   ENGINE         │  Subnet presence table             │  Peer timeout evict │
│                  └───────────────────────────────────┘                     │
│                                    │                                        │
│                  ┌───────────────────────────────────┐                     │
│   TCP SERVER     │  Length-prefixed TCP on Port 50001 │  4-byte big-endian  │
│                  │  Binary file streaming             │  SHA-256 integrity  │
│                  └───────────────────────────────────┘                     │
│                                    │                                        │
│                  ┌───────────────────────────────────┐                     │
│   WEB GATEWAY    │  HTTP REST API on Port 8080        │  /api/send          │
│                  │  Serves Mobile SPA (HTML/CSS/JS)   │  /api/messages      │
│                  │  QR Code invite generation         │  /api/status        │
│                  └───────────────────────────────────┘                     │
└────────────────────────────────────────────────────────────────────────────┘"""

box(s4, 0.3, 1.05, 12.7, 6.2, fill_color=RGBColor(0x0A, 0x0D, 0x12),
    border_color=ACCENT, border_pt=0.8)
txt(s4, arch_text, 0.5, 1.1, 12.5, 6.0, size=11.5, color=ACCENT2,
    wrap=False)

# OSI column
osi = [
    ("L7 Application",  "JSON / HTTP REST  •  Custom Chat Packets"),
    ("L6 Presentation", "4-byte framing  •  SHA-256 hash"),
    ("L5 Session",      "Heartbeat lifecycle  •  Peer pruning"),
    ("L4 Transport",    "TCP (reliable)  •  UDP (broadcast)"),
    ("L3 Network",      "IPv4  •  Subnet masking"),
    ("L2 Data Link",    "Wi-Fi 802.11  •  Ethernet"),
]

# Show OSI as right column overlay
for i, (layer, desc) in enumerate(osi):
    yt = 1.15 + i * 0.87
    txt(s4, layer, 8.6, yt, 2.1, 0.4, size=10, bold=True, color=YELLOW)
    txt(s4, desc,  8.6, yt + 0.35, 4.5, 0.45, size=9.5, color=LIGHT)


# ────────────────────────────────────────────────────────────────
# SLIDE 5 — HOW IT WORKS (Join Flow)
# ────────────────────────────────────────────────────────────────
s5 = add_slide(); bg(s5)
txt(s5, "How It Works — Join Flow", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s5, 0.95, 0.05)

steps = [
    ("1", "Host starts\nweb_main.py", "Python boots UDP discovery,\nTCP server & HTTP gateway."),
    ("2", "Host opens\nbrowser", "Navigates to http://localhost:8080,\nenters nickname."),
    ("3", "Creates Network", "A unique Network ID (NET-XXXXXX)\nis generated and stored."),
    ("4", "Clicks Invite 🔗", "QR code + Direct URL generated\nusing the real LAN IP."),
    ("5", "Guest scans QR", "Phone camera opens the URL;\nbrowser auto-joins the network."),
    ("6", "Guest chats", "Messages polled via /api/messages.\nRooms created on demand."),
]

for i, (num, title, body) in enumerate(steps):
    lp = 0.3 + i * 2.16
    # number circle bg
    box(s5, lp, 1.2, 0.56, 0.56, fill_color=ACCENT)
    txt(s5, num, lp, 1.2, 0.56, 0.56, size=20, bold=True, color=BG, align=PP_ALIGN.CENTER)
    txt(s5, title, lp, 1.85, 2.0, 0.6, size=13.5, bold=True, color=WHITE)
    txt(s5, body, lp, 2.5, 2.0, 1.3, size=11.5, color=LIGHT)
    # arrow (except last)
    if i < 5:
        txt(s5, "→", lp + 1.82, 1.28, 0.4, 0.45, size=26, color=ACCENT,
            align=PP_ALIGN.CENTER)

# QR caption box
box(s5, 0.3, 4.05, 12.5, 3.2, fill_color=RGBColor(0x0D, 0x17, 0x1B),
    border_color=ACCENT, border_pt=0.8)
txt(s5, "🔗  Three ways to invite:  "
    "① Scan QR Code (fastest)   "
    "② Share Network Code  e.g. NET-A3F7C1   "
    "③ Copy & send Direct URL   http://192.168.x.x:8080/join?net=NET-A3F7C1",
    0.5, 4.2, 12.2, 0.8, size=13.5, color=ACCENT)

notes = [
    "✔  Works on any Wi-Fi — home, college, mobile hotspot",
    "✔  Guest needs no account, no installation, just a browser",
    "✔  URL auto-detects correct LAN IP, never uses cloud domain",
    "✔  Auto-join: opening the link sets name & network automatically",
]
for i, n in enumerate(notes):
    txt(s5, n, 0.5, 5.1 + i * 0.47, 12.2, 0.45, size=13, color=ACCENT2)


# ────────────────────────────────────────────────────────────────
# SLIDE 6 — KEY FEATURES
# ────────────────────────────────────────────────────────────────
s6 = add_slide(); bg(s6)
txt(s6, "Key Features", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s6, 0.95, 0.05)

features = [
    ("🔍 UDP Auto-Discovery",     "Broadcasts heartbeats every 3 s on the local subnet.\nPeers appear instantly — no manual IP entry."),
    ("🔗 QR / Network Code Invite","Generates ISO-compliant QR code pointing to the real LAN IP.\nNetwork Code (NET-XXXXXX) for verbal sharing."),
    ("🏠 Isolated Private Networks","Each session has a unique network ID.\nOnly joined members see rooms & messages."),
    ("💬 Dynamic Rooms",           "Create #classroom, #study, #team rooms on demand.\nNo static pre-configured channels."),
    ("📁 File Transfer + SHA-256", "Drag-and-drop file sharing over TCP.\nEvery transfer integrity-verified with SHA-256 hash."),
    ("🎙️ Voice Notes",             "Record audio in-browser via MediaRecorder API.\nPlayback inline without leaving the chat."),
    ("👍 Emoji Reactions",         "Live reaction bar with participant badges.\nReal-time sync across all connected devices."),
    ("📌 Pin & Search",            "Pin important messages to channel top.\nInstant text search filters any conversation."),
]

cols_f = [(0.3, 1.1), (6.7, 1.1), (0.3, 2.85), (6.7, 2.85),
          (0.3, 4.6), (6.7, 4.6), (0.3, 6.15), (6.7, 6.15)]
for (title, body), (cl, ct) in zip(features, cols_f):
    box(s6, cl, ct, 5.9, 1.55, fill_color=RGBColor(0x13, 0x1A, 0x20),
        border_color=ACCENT, border_pt=0.7)
    txt(s6, title, cl + 0.15, ct + 0.12, 5.6, 0.45, size=14, bold=True, color=ACCENT)
    txt(s6, body,  cl + 0.15, ct + 0.6,  5.6, 0.88, size=11.5, color=LIGHT)


# ────────────────────────────────────────────────────────────────
# SLIDE 7 — TECHNOLOGY STACK
# ────────────────────────────────────────────────────────────────
s7 = add_slide(); bg(s7)
txt(s7, "Technology Stack", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s7, 0.95, 0.05)

rows = [
    ("Category",       "Technology",                   "Why / How Used"),
    ("Language",       "Python 3.10+ (stdlib only)",   "No pip install needed; `socket`, `threading`, `http.server`"),
    ("Discovery",      "UDP Broadcast (port 50000)",    "Periodic heartbeat; peer table with timeout eviction"),
    ("Messaging",      "TCP + 4-byte framing",          "`struct.pack('>I', len)` prefix prevents fragmentation"),
    ("File Transfer",  "TCP streaming + hashlib",       "Chunked binary stream; SHA-256 end-to-end verification"),
    ("Web Gateway",    "Python http.server (port 8080)","Serves SPA + JSON REST API; zero framework dependency"),
    ("Frontend",       "Vanilla HTML / CSS / JS",       "Glassmorphism dark UI; polling via `fetch`; QR generator"),
    ("QR Code",        "Custom JS (ISO 18004)",         "Reed-Solomon EC, version 1-10; generates correct LAN URL"),
    ("Testing",        "unittest (stdlib)",             "61 tests: unit + integration + E2E; runs in CI with no deps"),
]

col_widths = [2.2, 3.4, 6.5]
col_lefts  = [0.3, 2.6, 6.1]
row_h      = 0.62
t_start    = 1.08

for ri, row in enumerate(rows):
    fill = RGBColor(0x1C, 0x28, 0x33) if ri % 2 == 0 else RGBColor(0x13, 0x1A, 0x22)
    is_hdr = ri == 0
    for ci, (cell, cw, cl) in enumerate(zip(row, col_widths, col_lefts)):
        box(s7, cl, t_start + ri * row_h, cw, row_h,
            fill_color=(RGBColor(0x0D, 0x3A, 0x5C) if is_hdr else fill),
            border_color=ACCENT, border_pt=0.5)
        txt(s7, cell, cl + 0.08, t_start + ri * row_h + 0.12,
            cw - 0.12, row_h - 0.12,
            size=(12 if is_hdr else 11),
            bold=is_hdr,
            color=(ACCENT if is_hdr else (WHITE if ci == 0 else LIGHT)))


# ────────────────────────────────────────────────────────────────
# SLIDE 8 — TESTING
# ────────────────────────────────────────────────────────────────
s8 = add_slide(); bg(s8)
txt(s8, "Testing & Verification", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s8, 0.95, 0.05)

txt(s8, "61 tests  •  100% pass rate  •  Runs in < 10 seconds  •  Zero external dependencies",
    0.5, 1.1, 12.3, 0.55, size=16, color=ACCENT2, bold=True)

test_modules = [
    ("test_tcp.py",          "TCP framing, send/receive & port-0 safety"),
    ("test_discovery.py",    "UDP heartbeats & peer lifecycle management"),
    ("test_file_transfer.py","Binary streaming & SHA-256 checksum integrity"),
    ("test_web_gateway.py",  "HTTP methods, CORS & port collision recovery"),
    ("test_e2e_full.py",     "7-condition full end-to-end workflow test"),
    ("test_new_features.py", "Reactions, pinning, rooms, audio upload"),
    ("test_framing.py",      "4-byte length-prefix encoding/decoding"),
    ("test_net_utils.py",    "LAN IP resolution & broadcast calculation"),
]

for i, (mod, desc) in enumerate(test_modules):
    lp = 0.35 if i % 2 == 0 else 6.75
    tp = 1.85 + (i // 2) * 1.32
    box(s8, lp, tp, 5.95, 1.15, fill_color=RGBColor(0x10, 0x18, 0x20),
        border_color=ACCENT2, border_pt=0.8)
    txt(s8, f"✅ {mod}", lp + 0.15, tp + 0.1, 5.6, 0.45, size=13, bold=True, color=ACCENT2)
    txt(s8, desc,       lp + 0.15, tp + 0.55, 5.6, 0.55, size=11.5, color=LIGHT)

txt(s8, "Run all tests:  python -m unittest discover tests/",
    0.35, 7.1, 12.5, 0.35, size=13, color=SUBTLE, italic=True)


# ────────────────────────────────────────────────────────────────
# SLIDE 9 — LIVE DEMO
# ────────────────────────────────────────────────────────────────
s9 = add_slide(); bg(s9)
txt(s9, "Live Demo", 0.5, 0.2, 12, 0.7, size=36, bold=True, color=ACCENT)
accent_bar(s9, 0.95, 0.05)

demo_steps = [
    ("Step 1", "Start the Server",
     "python web_main.py\n\nTerminal prints the local LAN IP and port"),
    ("Step 2", "Open in Browser",
     "Navigate to http://localhost:8080\n\nEnter your nickname → Create Network"),
    ("Step 3", "Invite a Guest",
     "Click 🔗 Invite\n\nShow QR code / Network Code / Direct URL"),
    ("Step 4", "Guest Scans QR",
     "Phone camera scans → auto-opens URL\n\nAuto-joins the network instantly"),
    ("Step 5", "Create a Room",
     "Click + New Room → type 'classroom'\n\nEveryone in the network can join"),
    ("Step 6", "Chat + Share Files",
     "Send messages, images, voice notes\n\nDrag & drop files with progress bar"),
]

for i, (step, title, body) in enumerate(demo_steps):
    lp = 0.3 + (i % 3) * 4.35
    tp = 1.1 + (i // 3) * 3.15
    box(s9, lp, tp, 4.0, 2.85, fill_color=RGBColor(0x0D, 0x17, 0x22),
        border_color=ACCENT, border_pt=1.2)
    txt(s9, step, lp + 0.15, tp + 0.1, 3.7, 0.4, size=11, color=SUBTLE)
    txt(s9, title, lp + 0.15, tp + 0.45, 3.7, 0.55, size=16, bold=True, color=WHITE)
    txt(s9, body,  lp + 0.15, tp + 1.05, 3.7, 1.65, size=12.5, color=LIGHT)

txt(s9, "🌐 Cloud Demo (always-on):  https://cn-project-lan-chat.onrender.com",
    0.3, 7.1, 12.5, 0.38, size=14, color=ACCENT2, bold=True)


# ────────────────────────────────────────────────────────────────
# SLIDE 10 — CONCLUSION
# ────────────────────────────────────────────────────────────────
s10 = add_slide(); bg(s10)
# Full-width accent stripe at top
box(s10, 0, 0, 13.33, 0.18, fill_color=ACCENT)

txt(s10, "Conclusion", 0.5, 0.3, 12, 0.75, size=40, bold=True, color=ACCENT)
txt(s10,
    "LAN Chat proves that sophisticated real-time communication\ndoes not require cloud infrastructure or external libraries.",
    0.5, 1.15, 12.3, 0.9, size=20, color=WHITE)

points = [
    ("✅", "Works completely offline — ideal for classrooms, workshops, and restricted networks"),
    ("✅", "Instant device onboarding via QR Code or 6-character Network Code"),
    ("✅", "Isolated private networks — no cross-session message leakage"),
    ("✅", "Full binary file transfer with SHA-256 integrity verification"),
    ("✅", "61 automated tests — unit, integration, and end-to-end coverage"),
    ("✅", "Zero external dependencies — pure Python 3.10 standard library"),
]

for i, (icon, point) in enumerate(points):
    tp = 2.25 + i * 0.7
    txt(s10, icon,  0.5, tp, 0.6, 0.62, size=18, color=ACCENT2, bold=True)
    txt(s10, point, 1.2, tp, 11.5, 0.62, size=16, color=LIGHT)

txt(s10, "GitHub →  github.com/suraz111/CN_Project--LAN-Chat-",
    0.5, 6.65, 12, 0.55, size=14, color=ACCENT, italic=True)
txt(s10, "Cloud Demo →  cn-project-lan-chat.onrender.com",
    0.5, 7.1,  12, 0.38, size=13, color=SUBTLE, italic=True)


# ────────────────────────────────────────────────────────────────
# SAVE
# ────────────────────────────────────────────────────────────────
out_path = os.path.join(os.path.dirname(__file__), "..", "LAN_Chat_Presentation.pptx")
prs.save(out_path)
print(f"Saved: {os.path.abspath(out_path)}")
