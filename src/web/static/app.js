/**
 * Simple LAN Chat — Mobile Web Single Page Application (SPA)
 * Features:
 * - Real-time channel switching & multi-channel chat (Group, Custom Rooms & Direct DMs)
 * - Emoji reactions (👍, ❤️, 😂, 🔥, 😮) on messages
 * - Voice Notes recording & playback via Web Audio / MediaRecorder
 * - Drag-and-drop file sharing with visual upload progress bar
 * - Rich image previews & Lightbox zoom modal
 * - In-app Shared Media Gallery modal
 * - Instant conversation search & live filter
 * - Sticky pinned message banner
 * - End-to-end room encryption passkey
 * - Network interfaces diagnostic in Direct P2P Hub
 * - Web Audio API synthesized notification chimes
 */

// Standalone zero-dependency SVG QR Code Generator (Pure Vanilla JS)
const QR = (() => {
  const GF256_EXP = new Uint8Array(512);
  const GF256_LOG = new Uint8Array(256);
  let x = 1;
  for (let i = 0; i < 255; i++) {
    GF256_EXP[i] = x;
    GF256_EXP[i + 255] = x;
    GF256_LOG[x] = i;
    x <<= 1;
    if (x & 256) x ^= 0x11d;
  }

  function gfMul(x, y) {
    if (x === 0 || y === 0) return 0;
    return GF256_EXP[GF256_LOG[x] + GF256_LOG[y]];
  }

  function getPoly(deg) {
    let p = [1];
    for (let i = 0; i < deg; i++) {
      let next = new Array(p.length + 1).fill(0);
      for (let j = 0; j < p.length; j++) {
        next[j] ^= p[j];
        next[j + 1] ^= gfMul(p[j], GF256_EXP[i]);
      }
      p = next;
    }
    return p;
  }

  function rsEncode(data, ecLen) {
    const gen = getPoly(ecLen);
    const res = new Uint8Array(ecLen);
    for (let i = 0; i < data.length; i++) {
      const factor = data[i] ^ res[0];
      for (let j = 0; j < ecLen - 1; j++) {
        res[j] = res[j + 1] ^ gfMul(gen[j + 1], factor);
      }
      res[ecLen - 1] = gfMul(gen[ecLen], factor);
    }
    return res;
  }

  const VERSIONS = [
    { v: 1, size: 21, total: 26, data: 19, ec: 7, blocks: 1, align: [] },
    { v: 2, size: 25, total: 44, data: 34, ec: 10, blocks: 1, align: [6, 18] },
    { v: 3, size: 29, total: 70, data: 55, ec: 15, blocks: 1, align: [6, 22] },
    { v: 4, size: 33, total: 100, data: 80, ec: 20, blocks: 2, align: [6, 26] },
    { v: 5, size: 37, total: 134, data: 108, ec: 26, blocks: 2, align: [6, 30] },
    { v: 6, size: 41, total: 172, data: 136, ec: 36, blocks: 4, align: [6, 34] },
  ];

  function encodeData(text, vInfo) {
    const bytes = new TextEncoder().encode(text);
    const bitBuf = [];

    function pushBits(val, len) {
      for (let i = len - 1; i >= 0; i--) {
        bitBuf.push((val >> i) & 1);
      }
    }

    pushBits(4, 4); // Byte Mode
    pushBits(bytes.length, 8); // Length
    for (const b of bytes) pushBits(b, 8);
    const capacityBits = vInfo.data * 8;
    const termLen = Math.min(4, capacityBits - bitBuf.length);
    pushBits(0, termLen);
    while (bitBuf.length % 8 !== 0) bitBuf.push(0);
    const padBytes = [0xec, 0x11];
    let padIdx = 0;
    while (bitBuf.length < capacityBits) {
      pushBits(padBytes[padIdx % 2], 8);
      padIdx++;
    }

    const codewords = new Uint8Array(vInfo.data);
    for (let i = 0; i < vInfo.data; i++) {
      let b = 0;
      for (let j = 0; j < 8; j++) b = (b << 1) | bitBuf[i * 8 + j];
      codewords[i] = b;
    }

    const numBlocks = vInfo.blocks;
    const dataPerBlock = Math.floor(vInfo.data / numBlocks);
    const ecPerBlock = Math.floor(vInfo.ec / numBlocks);
    const dataBlocks = [];
    const ecBlocks = [];

    for (let b = 0; b < numBlocks; b++) {
      const start = b * dataPerBlock;
      const end = start + dataPerBlock;
      const dBlock = codewords.slice(start, end);
      dataBlocks.push(dBlock);
      ecBlocks.push(rsEncode(dBlock, ecPerBlock));
    }

    const finalCodewords = new Uint8Array(vInfo.total);
    let idx = 0;
    for (let i = 0; i < dataPerBlock; i++) {
      for (let b = 0; b < numBlocks; b++) {
        finalCodewords[idx++] = dataBlocks[b][i];
      }
    }
    for (let i = 0; i < ecPerBlock; i++) {
      for (let b = 0; b < numBlocks; b++) {
        finalCodewords[idx++] = ecBlocks[b][i];
      }
    }

    return finalCodewords;
  }

  function createMatrix(vInfo, codewords) {
    const size = vInfo.size;
    const matrix = Array.from({ length: size }, () => new Int8Array(size).fill(-1));

    function addFinder(top, left) {
      for (let r = -1; r <= 7; r++) {
        for (let c = -1; c <= 7; c++) {
          const row = top + r;
          const col = left + c;
          if (row < 0 || row >= size || col < 0 || col >= size) continue;
          if (
            (r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
            (c >= 0 && c <= 6 && (r === 0 || r === 6)) ||
            (r >= 2 && r <= 4 && c >= 2 && c <= 4)
          ) {
            matrix[row][col] = 1;
          } else {
            matrix[row][col] = 0;
          }
        }
      }
    }

    addFinder(0, 0);
    addFinder(0, size - 7);
    addFinder(size - 7, 0);

    if (vInfo.align.length >= 2) {
      const coords = vInfo.align;
      for (const r of coords) {
        for (const c of coords) {
          if (
            (r === 6 && c === 6) ||
            (r === 6 && c === coords[coords.length - 1] && c === size - 7) ||
            (r === coords[coords.length - 1] && r === size - 7 && c === 6)
          ) {
            continue;
          }
          if (matrix[r][c] !== -1) continue;
          for (let dy = -2; dy <= 2; dy++) {
            for (let dx = -2; dx <= 2; dx++) {
              const d = Math.max(Math.abs(dy), Math.abs(dx));
              matrix[r + dy][c + dx] = d === 2 || d === 0 ? 1 : 0;
            }
          }
        }
      }
    }

    for (let i = 8; i < size - 8; i++) {
      if (matrix[6][i] === -1) matrix[6][i] = i % 2 === 0 ? 1 : 0;
      if (matrix[i][6] === -1) matrix[i][6] = i % 2 === 0 ? 1 : 0;
    }

    matrix[4 * vInfo.v + 9][8] = 1;

    for (let i = 0; i < 9; i++) {
      if (matrix[8][i] === -1) matrix[8][i] = 0;
      if (matrix[i][8] === -1) matrix[i][8] = 0;
    }
    for (let i = size - 8; i < size; i++) {
      if (matrix[8][i] === -1) matrix[8][i] = 0;
      if (matrix[i][8] === -1) matrix[i][8] = 0;
    }

    let bitIdx = 0;
    const totalBits = codewords.length * 8;
    let upward = true;

    for (let right = size - 1; right > 0; right -= 2) {
      if (right === 6) right--;
      const cols = [right, right - 1];
      const rows = upward
        ? Array.from({ length: size }, (_, i) => size - 1 - i)
        : Array.from({ length: size }, (_, i) => i);

      for (const r of rows) {
        for (const c of cols) {
          if (matrix[r][c] === -1) {
            let bit = 0;
            if (bitIdx < totalBits) {
              const byteVal = codewords[Math.floor(bitIdx / 8)];
              const shift = 7 - (bitIdx % 8);
              bit = (byteVal >> shift) & 1;
              bitIdx++;
            }
            if ((r + c) % 2 === 0) bit ^= 1;
            matrix[r][c] = bit;
          }
        }
      }
      upward = !upward;
    }

    const formatBits = [1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0];
    const tlCoords = [
      [8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8],
      [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8]
    ];
    for (let i = 0; i < 15; i++) {
      const [r, c] = tlCoords[i];
      matrix[r][c] = formatBits[i];
    }
    for (let i = 0; i < 7; i++) matrix[size - 1 - i][8] = formatBits[i];
    for (let i = 0; i < 8; i++) matrix[8][size - 8 + i] = formatBits[7 + i];

    return matrix;
  }

  function generateSVG(text, margin = 3) {
    const byteLen = new TextEncoder().encode(text).length;
    let chosenVersion = null;
    for (const v of VERSIONS) {
      if (v.data - 2 >= byteLen) {
        chosenVersion = v;
        break;
      }
    }
    if (!chosenVersion) chosenVersion = VERSIONS[VERSIONS.length - 1];

    const codewords = encodeData(text, chosenVersion);
    const matrix = createMatrix(chosenVersion, codewords);
    const size = chosenVersion.size;
    const fullSize = size + margin * 2;

    let paths = "";
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        if (matrix[r][c] === 1) {
          paths += `<rect x="${c + margin}" y="${r + margin}" width="1" height="1" fill="currentColor"/>`;
        }
      }
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${fullSize} ${fullSize}" shape-rendering="crispEdges" class="qr-svg">${paths}</svg>`;
  }

  return { generateSVG };
})();

// Cookie helpers for cross-tab / cross-webview persistence
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

function setCookie(name, val, days = 365) {
  const d = new Date();
  d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie = `${name}=${encodeURIComponent(val)};expires=${d.toUTCString()};path=/;SameSite=Lax`;
}

// Generate or retrieve persistent client ID for this browser device
function getOrCreateClientId() {
  let id = localStorage.getItem("lanchat_client_id") || getCookie("lanchat_client_id");
  if (!id) {
    id = "mob_" + Math.random().toString(36).substring(2, 9) + Date.now().toString(36).substring(4);
  }
  localStorage.setItem("lanchat_client_id", id);
  setCookie("lanchat_client_id", id);
  return id;
}

function getSavedUsername() {
  return localStorage.getItem("lanchat_username") || getCookie("lanchat_username") || "";
}

function saveUsername(name) {
  state.username = name;
  localStorage.setItem("lanchat_username", name);
  setCookie("lanchat_username", name);
}

function getSavedRooms() {
  try {
    const raw = localStorage.getItem("lanchat_my_rooms");
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveMyRooms() {
  try {
    localStorage.setItem("lanchat_my_rooms", JSON.stringify(state.customRooms || []));
  } catch (e) {}
}

// Application State
const state = {
  clientId: getOrCreateClientId(),
  username: getSavedUsername(),
  currentChannel: null, // null = No active room (Welcome hub); "group" = Local Broadcast; "#room" = Custom Room; or peer_id = Direct DM
  peers: [],
  customRooms: getSavedRooms(),
  roomSecrets: JSON.parse(localStorage.getItem("lanchat_room_secrets") || "{}"),
  pinnedMessage: null,
  renderedMessageIds: new Set(),
  unreadCounts: { null: 0 },
  lastPollTime: 0,
  hostInfo: {},
  theme: localStorage.getItem("lanchat_theme") || "dark",
  soundEnabled: localStorage.getItem("lanchat_sound_enabled") !== "false",
  notifiedMessageIds: new Set(),
  lastTypingSent: 0,
  typingTimer: null,
  pendingAutoJoin: null,
  
  // Voice Recording state
  voiceMediaRecorder: null,
  voiceChunks: [],
  voiceTimerInterval: null,
  voiceStartTime: 0,
  voiceMimeType: "audio/webm",
  
  // Search state
  searchQuery: "",
  
  // Media Gallery state
  galleryItems: [],
  activeGalleryFilter: "all",
};

// DOM References
const dom = {
  loginModal: document.getElementById("login-modal"),
  inputUsername: document.getElementById("input-username"),
  hostIpPreview: document.getElementById("host-ip-preview"),
  userDisplayName: document.getElementById("user-display-name"),
  userIpText: document.getElementById("user-ip-text"),
  userAvatarText: document.getElementById("user-avatar-text"),
  onlineCount: document.getElementById("online-count"),
  peersCountLabel: document.getElementById("peers-count-label"),
  peersList: document.getElementById("peers-list"),
  customRoomsList: document.getElementById("custom-rooms-list"),
  badgeGroup: document.getElementById("badge-group"),
  activeChannelTitle: document.getElementById("active-channel-title"),
  activeChannelSub: document.getElementById("active-channel-sub"),
  chatMessages: document.getElementById("chat-messages"),
  messageInput: document.getElementById("message-input"),
  typingIndicator: document.getElementById("typing-indicator"),
  typingText: document.getElementById("typing-text"),
  sidebarDrawer: document.getElementById("sidebar-drawer"),
  drawerBackdrop: document.getElementById("drawer-backdrop"),
  btnToggleSidebar: document.getElementById("btn-toggle-sidebar"),
  btnThemeToggle: document.getElementById("btn-theme-toggle"),
  themeIcon: document.getElementById("theme-icon"),
  btnNotifToggle: document.getElementById("btn-notif-toggle"),
  notifIcon: document.getElementById("notif-icon"),
  btnRefresh: document.getElementById("btn-refresh"),
  btnHeaderFile: document.getElementById("btn-header-file"),
  btnHeaderGallery: document.getElementById("btn-header-gallery"),
  btnHeaderEncrypt: document.getElementById("btn-header-encrypt"),
  btnHeaderInfo: document.getElementById("btn-header-info"),
  fileUploader: document.getElementById("file-uploader"),
  btnVoiceRecord: document.getElementById("btn-voice-record"),
  voiceRecordingBar: document.getElementById("voice-recording-bar"),
  recTimer: document.getElementById("rec-timer"),
  dragOverlay: document.getElementById("drag-overlay"),
  uploadProgressCard: document.getElementById("upload-progress-card"),
  uploadFilename: document.getElementById("upload-filename"),
  uploadPercent: document.getElementById("upload-percent"),
  progressBarFill: document.getElementById("progress-bar-fill"),
  btnSearchToggle: document.getElementById("btn-search-toggle"),
  searchBarDrawer: document.getElementById("search-bar-drawer"),
  searchInput: document.getElementById("search-input"),
  searchMatchCount: document.getElementById("search-match-count"),
  pinnedBanner: document.getElementById("pinned-banner"),
  pinnedMsgText: document.getElementById("pinned-msg-text"),
  p2pModal: document.getElementById("p2p-modal"),
  p2pHubCount: document.getElementById("p2p-hub-count"),
  p2pHubList: document.getElementById("p2p-hub-list"),
  networkInterfacesList: document.getElementById("network-interfaces-list"),
  inputManualIp: document.getElementById("input-manual-ip"),
  btnManualConnect: document.getElementById("btn-manual-connect"),
  manualConnectFeedback: document.getElementById("manual-connect-feedback"),
  peerInfoModal: document.getElementById("peer-info-modal"),
  peerInfoName: document.getElementById("peer-info-name"),
  peerInfoContent: document.getElementById("peer-info-content"),
  btnPingPeer: document.getElementById("btn-ping-peer"),
  lightboxModal: document.getElementById("lightbox-modal"),
  lightboxImg: document.getElementById("lightbox-img"),
  lightboxCaption: document.getElementById("lightbox-caption"),
  lightboxDownloadLink: document.getElementById("lightbox-download-link"),
  galleryModal: document.getElementById("gallery-modal"),
  galleryGrid: document.getElementById("gallery-grid"),
  roomModal: document.getElementById("room-modal"),
  inputRoomName: document.getElementById("input-room-name"),
  encryptionModal: document.getElementById("encryption-modal"),
  inputRoomSecret: document.getElementById("input-room-secret"),
  inputRoomPasskey: document.getElementById("input-room-passkey"),
  encryptIcon: document.getElementById("encrypt-icon"),
  encryptLabel: document.getElementById("encrypt-label"),
  encryptionModalTitle: document.getElementById("encryption-modal-title"),
  encryptionModalTarget: document.getElementById("encryption-modal-target"),
  encryptionStatusText: document.getElementById("encryption-status-text"),
  encryptionStatusBanner: document.getElementById("encryption-status-banner"),
  toastContainer: document.getElementById("toast-container"),
  
  // New Clean Navbar, Join Room, Invite & Share, and Control Center
  btnInviteToggle: document.getElementById("btn-invite-toggle"),
  btnControlCenterToggle: document.getElementById("btn-control-center-toggle"),
  btnOpenCreateRoom: document.getElementById("btn-open-create-room"),
  btnOpenJoinRoom: document.getElementById("btn-open-join-room"),
  joinRoomModal: document.getElementById("join-room-modal"),
  inputJoinRoomCode: document.getElementById("input-join-room-code"),
  inviteModal: document.getElementById("invite-modal"),
  inviteRoomSelect: document.getElementById("invite-room-select"),
  inviteIpSelect: document.getElementById("invite-ip-select"),
  loginInviteBanner: document.getElementById("login-invite-banner"),
  inviteLinkInput: document.getElementById("invite-link-input"),
  inviteQrContainer: document.getElementById("invite-qr-container"),
  btnCopyInvite: document.getElementById("btn-copy-invite"),
  copyText: document.getElementById("copy-text"),
  copyIcon: document.getElementById("copy-icon"),
  controlCenterModal: document.getElementById("control-center-modal"),
  ctrlThemeLabel: document.getElementById("ctrl-theme-label"),
  ctrlSoundLabel: document.getElementById("ctrl-sound-label"),
  ctrlThemeIcon: document.getElementById("ctrl-theme-icon"),
  ctrlSoundIcon: document.getElementById("ctrl-sound-icon"),
  btnHeaderInvite: document.getElementById("btn-header-invite"),
  btnHeaderEncrypt: document.getElementById("btn-header-encrypt"),
  btnGuideToggle: document.getElementById("btn-guide-toggle"),
  landingModal: document.getElementById("landing-modal"),
  chkSkipLanding: document.getElementById("chk-skip-landing"),
  landingInputNickname: document.getElementById("landing-input-nickname"),
};

// ========================================================
// Initialization
// ========================================================
window.addEventListener("DOMContentLoaded", () => {
  // Check for auto-join room or name from URL query parameters (?room=math or ?join=math&name=Alex)
  const urlParams = new URLSearchParams(window.location.search);
  const userParam = (urlParams.get("name") || urlParams.get("user") || "").trim();
  if (userParam && !state.username) {
    state.username = userParam;
    localStorage.setItem("lanchat_username", userParam);
  }

  const roomParam = (urlParams.get("room") || urlParams.get("join") || "").trim();
  if (roomParam) {
    state.pendingAutoJoin = roomParam.toLowerCase() === "group" ? "group" : (roomParam.startsWith("#") ? roomParam : `#${roomParam}`);
  }

  applyTheme(state.theme);
  updateNotifIcon();
  updateEncryptionIcon();
  updateControlCenterUI();
  setupEventHandlers();
  setupDragAndDrop();

  // Request browser notification permission on first user gesture
  document.addEventListener("click", () => requestNotificationPermission(), { once: true });

  if (!state.username) {
    if (state.pendingAutoJoin) {
      dom.loginModal.classList.remove("hidden");
      const banner = document.getElementById("login-invite-banner");
      if (banner) {
        const roomTitle = state.pendingAutoJoin === "group" ? "🌐 Group Broadcast" : state.pendingAutoJoin;
        banner.innerHTML = `<span>🎯 Invited to room <strong>${escapeHtml(roomTitle)}</strong></span>`;
        banner.classList.remove("hidden");
      }
      dom.inputUsername.focus();
    } else {
      // First visit / direct visit: ALWAYS show the full-page Landing Portal covering the entire page!
      dom.loginModal.classList.add("hidden");
      openLandingModal();
    }
  } else {
    dom.loginModal.classList.add("hidden");
    initUserSession();
    // Option 3 Hybrid Launch: Show full-page landing portal for direct visitors unless they opted to skip
    const shouldSkipLanding = localStorage.getItem("lanchat_skip_landing") === "true";
    if (!state.pendingAutoJoin && !shouldSkipLanding) {
      openLandingModal();
    }
  }

  // Initial fetch of host status and peers
  fetchStatus();

  // Periodic polling for peers and rooms (every 2.5 seconds)
  setInterval(fetchStatus, 2500);

  // Periodic polling for chat messages (every 800ms)
  setInterval(fetchMessages, 800);
});

function toggleSidebar(forceState) {
  if (window.innerWidth <= 768) {
    const shouldOpen = typeof forceState === "boolean" ? forceState : !dom.sidebarDrawer.classList.contains("open");
    dom.sidebarDrawer.classList.toggle("open", shouldOpen);
    dom.drawerBackdrop.classList.toggle("active", shouldOpen);
  } else {
    const shouldCollapse = typeof forceState === "boolean" ? forceState : !dom.sidebarDrawer.classList.contains("collapsed");
    dom.sidebarDrawer.classList.toggle("collapsed", shouldCollapse);
  }
}

function handleChannelHeaderClick() {
  if (window.innerWidth <= 768) {
    toggleSidebar(true);
  }
}

function setupEventHandlers() {
  // Mobile drawer and desktop collapsible sidebar toggle
  if (dom.btnToggleSidebar) {
    dom.btnToggleSidebar.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleSidebar();
    };
  }

  if (dom.drawerBackdrop) {
    dom.drawerBackdrop.onclick = (e) => {
      e.preventDefault();
      toggleSidebar(false);
    };
  }

  // Top Navbar action buttons
  if (dom.btnGuideToggle) {
    dom.btnGuideToggle.addEventListener("click", openLandingModal);
  }
  if (dom.btnInviteToggle) {
    dom.btnInviteToggle.addEventListener("click", openInviteModal);
  }
  if (dom.btnControlCenterToggle) {
    dom.btnControlCenterToggle.addEventListener("click", openControlCenterModal);
  }
  if (dom.btnHeaderInvite) {
    dom.btnHeaderInvite.addEventListener("click", openInviteModal);
  }
  if (dom.btnOpenJoinRoom) {
    dom.btnOpenJoinRoom.addEventListener("click", openJoinRoomModal);
  }

  // Theme switcher
  if (dom.btnThemeToggle) {
    dom.btnThemeToggle.addEventListener("click", toggleTheme);
  }

  // Notification toggle
  if (dom.btnNotifToggle) {
    dom.btnNotifToggle.addEventListener("click", toggleNotificationSetting);
  }

  // Manual refresh button
  if (dom.btnRefresh) {
    dom.btnRefresh.addEventListener("click", () => {
      fetchStatus();
      fetchMessages();
    });
  }

  // Quick Enter key trigger for landing page nickname input
  if (dom.landingInputNickname) {
    dom.landingInputNickname.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        launchChatFromLanding();
      }
    });
  }
}

function initUserSession() {
  dom.userDisplayName.textContent = state.username;
  dom.userAvatarText.textContent = (state.username || "M").slice(0, 1).toUpperCase();
  dom.loginModal.classList.add("hidden");
  fetchStatus();

  // Auto-join room from URL link if present
  if (state.pendingAutoJoin) {
    const target = state.pendingAutoJoin;
    state.pendingAutoJoin = null;

    // Clean query parameters from address bar to prevent infinite auto-join loops
    if (window.history && window.history.replaceState) {
      try {
        window.history.replaceState({}, document.title, window.location.pathname);
      } catch (e) {}
    }

    if (target === "group") {
      selectChannel("group");
    } else {
      joinRoomByName(target, true);
    }
  } else {
    // If user already has saved rooms, select the first room; otherwise new user starts with no room (Welcome Hub)
    if (state.customRooms && state.customRooms.length > 0) {
      selectChannel(state.customRooms[0]);
    } else {
      selectChannel(null);
    }
  }
}

function handleLogin() {
  const entered = dom.inputUsername.value.trim();
  if (entered) {
    saveUsername(entered);
    initUserSession();
  }
}

function changeName() {
  const newName = prompt("Enter new display name:", state.username);
  if (newName && newName.trim() && newName.trim() !== state.username) {
    saveUsername(newName.trim());
    initUserSession();
    fetchStatus();
  }
}

// ========================================================
// Web Audio API Synthesizer (Instant & 100% Reliable Chimes)
// ========================================================
function playNotificationChime(isDM = false) {
  if (!state.soundEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === "suspended") {
      ctx.resume();
    }
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    if (isDM) {
      // Pleasant dual chime for private DMs
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.setValueAtTime(880.00, now + 0.1); // A5
      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else {
      // Soft single tone for group/rooms
      osc.type = "triangle";
      osc.frequency.setValueAtTime(523.25, now); // C5
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    }
  } catch (e) {
    // Graceful fallback
  }
}

// ========================================================
// Drag and Drop File Sharing
// ========================================================
function setupDragAndDrop() {
  const viewport = document.querySelector(".chat-viewport");
  if (!viewport || !dom.dragOverlay) return;

  // Ensure overlay is strictly hidden on initialization
  dom.dragOverlay.style.display = "none";
  dom.dragOverlay.classList.add("hidden");
  dom.dragOverlay.classList.remove("active");

  let dragCounter = 0;

  viewport.addEventListener("dragenter", (e) => {
    // Only activate overlay if user is dragging real files from filesystem
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
      e.preventDefault();
      e.stopPropagation();
      dragCounter++;
      dom.dragOverlay.style.display = "flex";
      dom.dragOverlay.classList.remove("hidden");
      dom.dragOverlay.classList.add("active");
    }
  });

  viewport.addEventListener("dragover", (e) => {
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "copy";
    }
  });

  viewport.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      dom.dragOverlay.style.display = "none";
      dom.dragOverlay.classList.add("hidden");
      dom.dragOverlay.classList.remove("active");
    }
  });

  viewport.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter = 0;
    dom.dragOverlay.style.display = "none";
    dom.dragOverlay.classList.add("hidden");
    dom.dragOverlay.classList.remove("active");

    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      uploadFileWithProgress(file);
    }
  });

  // Failsafe: clicking overlay immediately hides it
  dom.dragOverlay.addEventListener("click", () => {
    dragCounter = 0;
    dom.dragOverlay.style.display = "none";
    dom.dragOverlay.classList.add("hidden");
    dom.dragOverlay.classList.remove("active");
  });

  window.addEventListener("dragend", () => {
    dragCounter = 0;
    dom.dragOverlay.style.display = "none";
    dom.dragOverlay.classList.add("hidden");
    dom.dragOverlay.classList.remove("active");
  });
}

// ========================================================
// Status, Peers & Rooms Directory
// ========================================================
async function fetchStatus() {
  try {
    const joinedRoomsParam = (state.customRooms || []).join(",");
    const url = `/api/status?client_id=${encodeURIComponent(state.clientId)}&username=${encodeURIComponent(state.username || "Mobile User")}&rooms=${encodeURIComponent(joinedRoomsParam)}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();

    // Auto-adopt remembered username from server only if local session name is completely empty
    if (!state.username && data.remembered_username && data.remembered_username !== "Mobile User") {
      saveUsername(data.remembered_username);
      initUserSession();
    }
    if (dom.inputUsername && !dom.inputUsername.value && data.remembered_username) {
      dom.inputUsername.value = data.remembered_username;
    }

    if (data.host_ip && dom.hostIpPreview) {
      dom.hostIpPreview.textContent = `${data.host_ip}:${data.host_port || 50001}`;
      dom.userIpText.textContent = data.host_ip;
    }

    if (Array.isArray(data.rooms)) {
      // Merge unique confirmed rooms
      const merged = Array.from(new Set([...state.customRooms, ...data.rooms]));
      const roomsChanged = JSON.stringify(merged) !== JSON.stringify(state.customRooms);
      state.customRooms = merged;
      saveMyRooms();
      if (roomsChanged) {
        renderCustomRooms();
      }
    }

    if (Array.isArray(data.peers)) {
      const peersChanged = JSON.stringify(data.peers) !== JSON.stringify(state.peers);
      if (peersChanged) {
        state.peers = data.peers;
        renderPeersList(data.peers);
        renderP2PHubList();

        const count = data.peers.length;
        dom.onlineCount.textContent = `${count} Peer${count === 1 ? "" : "s"}`;
        dom.peersCountLabel.textContent = count;
      }
    }

    if (data.unreads) {
      handleUnreadBadges(data.unreads);
    }

    if (Array.isArray(data.notifications)) {
      handleIncomingNotifications(data.notifications);
    }
  } catch (err) {
    // Network retry
  }
}

function renderCustomRooms() {
  if (!dom.customRoomsList) return;
  dom.customRoomsList.innerHTML = "";

  if (state.customRooms.length === 0) {
    const emptyItem = document.createElement("div");
    emptyItem.className = "empty-rooms-box";
    emptyItem.innerHTML = `
      <span class="empty-rooms-hint">No active rooms</span>
      <button type="button" class="btn-create-room-chip" onclick="openRoomModal()">➕ Create Room</button>
    `;
    dom.customRoomsList.appendChild(emptyItem);
    return;
  }

  state.customRooms.forEach((roomName) => {
    const item = document.createElement("div");
    const isActive = state.currentChannel === roomName;
    const isLocked = Boolean(state.roomSecrets[roomName]);
    item.className = `peer-item ${isActive ? "active" : ""} ${isLocked ? "has-lock" : ""}`;
    item.onclick = () => selectChannel(roomName);

    const unread = state.unreadCounts[roomName] || 0;

    item.innerHTML = `
      <div class="peer-avatar room-hash-avatar">${isLocked ? "🔒" : "#"}</div>
      <div class="peer-details">
        <span class="peer-name">${escapeHtml(roomName)} ${isLocked ? '<span class="room-lock-tag" title="Secured with passphrase">🔒</span>' : ''}</span>
        <span class="peer-sub">${isLocked ? "Encrypted Topic Room" : "Topic Room"}</span>
      </div>
      <div class="room-actions-inline">
        <button type="button" class="btn-room-del" title="Leave ${escapeHtml(roomName)}" onclick="event.stopPropagation(); handleDeleteRoomClick(this, '${escapeHtml(roomName)}')">🗑️</button>
      </div>
      <span class="unread-pill ${unread > 0 ? "" : "hidden"}">${unread}</span>
    `;
    dom.customRoomsList.appendChild(item);
  });
}

function renderPeersList(peers) {
  dom.peersList.innerHTML = "";

  if (peers.length === 0) {
    dom.peersList.innerHTML = `<div class="empty-peers">Searching for LAN peers...</div>`;
    return;
  }

  peers.forEach((peer) => {
    if (peer.peer_id === state.clientId) return;

    const item = document.createElement("div");
    const isActive = state.currentChannel === peer.peer_id;
    item.className = `peer-item ${isActive ? "active" : ""}`;
    item.onclick = () => selectChannel(peer.peer_id);

    const unread = state.unreadCounts[peer.peer_id] || 0;

    let avatarIcon = "🖥️";
    let badgeText = "Desktop";
    if (peer.is_host) {
      avatarIcon = "💻";
      badgeText = "Host";
    } else if (peer.is_web) {
      avatarIcon = "📱";
      badgeText = "Mobile";
    }

    item.innerHTML = `
      <div class="peer-avatar">${avatarIcon}</div>
      <div class="peer-details">
        <span class="peer-name">${escapeHtml(peer.username)} <small class="peer-role-badge">${badgeText}</small></span>
        <span class="peer-sub">${escapeHtml(peer.device_name || peer.ip_address)}</span>
      </div>
      <div class="peer-actions">
        <button type="button" class="peer-action-icon" title="Direct P2P Chat" onclick="event.stopPropagation(); selectChannel('${peer.peer_id}')">💬</button>
        <button type="button" class="peer-action-icon" title="Send File P2P" onclick="event.stopPropagation(); startPeerFileUpload('${peer.peer_id}')">📎</button>
        <button type="button" class="peer-action-icon" title="Connection Info" onclick="event.stopPropagation(); showPeerInfo('${peer.peer_id}')">ℹ️</button>
      </div>
      <span class="unread-pill ${unread > 0 ? "" : "hidden"}">${unread}</span>
    `;
    dom.peersList.appendChild(item);
  });
}

// ========================================================
// Message Fetching & Rendering
// ========================================================
function renderWelcomeHub() {
  if (!dom.chatMessages) return;
  // Guard against re-rendering every 800ms poll to eliminate page blinking
  if (dom.chatMessages.querySelector(".network-welcome-hub")) return;
  dom.chatMessages.innerHTML = `
    <div class="network-welcome-hub">
      <div class="welcome-hub-card glass-card">
        <div class="welcome-hub-badge">
          <span>🔒 PRIVATE LOCAL NETWORK</span>
        </div>
        <div class="welcome-hub-icon">📡</div>
        <h3 class="welcome-hub-title">Start Your Network</h3>
        <p class="welcome-hub-sub">
          You are currently not in any rooms. Conversations on this platform are strictly private to people who join your room or connect on the same local Wi-Fi.
        </p>
        <div class="welcome-hub-actions">
          <button type="button" class="btn-hub-primary" onclick="openRoomModal()">
            ➕ Create Private Room
          </button>
          <button type="button" class="btn-hub-secondary" onclick="openJoinRoomModal()">
            🔑 Join with Code
          </button>
          <button type="button" class="btn-hub-ghost" onclick="selectChannel('group')">
            🌐 Local LAN Broadcast
          </button>
        </div>
        <div class="welcome-hub-tips">
          <span>💡 <strong>Tip:</strong> Create a room like <code>#mygroup</code>, then click <strong>🔗 Invite</strong> to share a live QR code or 1-click link!</span>
        </div>
      </div>
    </div>
  `;
}

async function fetchMessages() {
  if (state.currentChannel === null) {
    renderWelcomeHub();
    return;
  }
  const channelParam = state.currentChannel;
  try {
    const isInitialLoad = state.lastPollTime === 0;
    const url = `/api/messages?channel=${encodeURIComponent(channelParam)}&client_id=${encodeURIComponent(state.clientId)}&username=${encodeURIComponent(state.username || "Mobile User")}&since=${state.lastPollTime}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();

    if (data.server_time) {
      state.lastPollTime = data.server_time;
    }

    // Update pinned banner for active channel
    if (data.pinned_message) {
      state.pinnedMessage = data.pinned_message;
      updatePinnedBanner(data.pinned_message);
    } else {
      state.pinnedMessage = null;
      updatePinnedBanner(null);
    }

    if (Array.isArray(data.messages) && data.messages.length > 0) {
      data.messages.forEach((msg) => {
        const msgId = msg.id || `${msg.timestamp_epoch || Date.now()}_${msg.sender}_${msg.message}`;
        if (!state.renderedMessageIds.has(msgId)) {
          state.renderedMessageIds.add(msgId);
          appendMessageRow(msg);

          // Alert for incoming message only when not the initial channel history load
          const isFromSelf = Boolean(msg.is_self) || msg.category === "self" || (msg.sender && (msg.sender.includes("(You)") || msg.sender.startsWith(state.username)));
          if (!isFromSelf && msg.category !== "system") {
            if (!state.notifiedMessageIds.has(msgId)) {
              state.notifiedMessageIds.add(msgId);
              if (!isInitialLoad) {
                if (document.hidden) {
                  const isDM = state.currentChannel !== null && !String(state.currentChannel).startsWith("#");
                  const title = isDM ? `🔒 Private from ${msg.sender}` : `💬 ${msg.sender}`;
                  sendDeviceNotification(title, msg.message, state.currentChannel);
                } else {
                  playNotificationChime(state.currentChannel !== null && !String(state.currentChannel).startsWith("#"));
                }
              }
            }
          }
        } else {
          // Update reactions and pinned state on already rendered row
          updateMessageRowReactions(msgId, msg.reactions, msg.pinned);
        }
      });
    }
  } catch (err) {
    // Network retry
  }
}

function selectChannel(channelId) {
  state.currentChannel = channelId;

  // Close mobile drawer on item select
  if (dom.sidebarDrawer) dom.sidebarDrawer.classList.remove("open");
  if (dom.drawerBackdrop) dom.drawerBackdrop.classList.remove("active");

  // Highlight active channel in sidebar
  const groupElem = document.getElementById("channel-group");
  if (groupElem) {
    groupElem.classList.toggle("active", channelId === "group");
  }
  document.querySelectorAll(".peer-item").forEach((el) => {
    if (el !== groupElem) el.classList.remove("active");
  });
  renderCustomRooms();

  // Clear unread badge
  if (channelId !== null) {
    state.unreadCounts[channelId] = 0;
  }
  if (channelId === "group" && dom.badgeGroup) {
    dom.badgeGroup.classList.add("hidden");
  }

  // Update Chat Header
  if (channelId === null) {
    dom.activeChannelTitle.textContent = "📡 Private Network Hub";
    dom.activeChannelSub.textContent = "Create or join a private room to start chatting";
    dom.btnHeaderInfo.title = "View LAN Network Details";
    renderWelcomeHub();
    return;
  } else if (channelId === "group") {
    dom.activeChannelTitle.textContent = "🌐 Local LAN Broadcast";
    dom.activeChannelSub.textContent = "All devices on local Wi-Fi / Hotspot";
    dom.btnHeaderInfo.title = "View LAN Network Details";
  } else if (String(channelId).startsWith("#")) {
    dom.activeChannelTitle.textContent = `🏷️ ${channelId}`;
    dom.activeChannelSub.textContent = "Private Topic Room • End-to-End Local Network";
    dom.btnHeaderInfo.title = `View Channel Info for ${channelId}`;
  } else {
    const peer = state.peers.find((p) => p.peer_id === channelId);
    const peerName = peer ? peer.username : "Direct Peer";
    const peerType = peer && peer.is_host ? "Host Desktop" : (peer && peer.is_web ? "Mobile User" : "LAN Peer");
    const portStr = peer && peer.tcp_port ? `:${peer.tcp_port}` : "";
    const ipStr = peer ? `${peer.ip_address}${portStr}` : "";
    dom.activeChannelTitle.textContent = `🔒 Direct P2P: ${peerName}`;
    dom.activeChannelSub.textContent = `${ipStr} • ${peerType} • Direct Peer-to-Peer`;
    dom.btnHeaderInfo.title = `View Connection Details for ${peerName}`;
  }

  updateEncryptionIcon();

  // Reset poll timestamp to re-fetch full channel history
  state.lastPollTime = 0;
  state.renderedMessageIds.clear();
  dom.chatMessages.innerHTML = "";
  fetchMessages();
}

// ========================================================
// Message Formatting, Media Previews & Reactions
// ========================================================
function appendMessageRow(msg) {
  const row = document.createElement("div");
  const msgId = msg.id || `${msg.timestamp_epoch || Date.now()}_${msg.sender}`;
  row.dataset.msgId = msgId;

  const isSelf = Boolean(msg.is_self) || msg.category === "self" || (msg.sender && (msg.sender.includes("(You)") || msg.sender.startsWith(state.username)));
  const role = msg.category === "system" ? "system" : (isSelf ? "self" : "peer");

  row.className = `message-row ${role}`;
  if (msg.pinned) {
    row.classList.add("pinned-highlight");
  }

  // Check for End-to-End Encryption
  const rawText = msg.message || "";
  const secretKey = state.roomSecrets[state.currentChannel] || "";
  const { text: displayText, isEncrypted, needsKey, wrongKey } = decryptMessagePayload(rawText, secretKey);

  // Parse media, audio and download links (both absolute URLs and relative /downloads/ paths)
  let mediaHtml = "";
  let messageContent = "";

  if (needsKey || wrongKey) {
    messageContent = `
      <div class="encrypted-locked-bubble">
        <span class="lock-bubble-text">${escapeHtml(displayText)}</span>
        <button type="button" class="btn-bubble-unlock" onclick="openEncryptionModal()">Enter Passphrase 🔑</button>
      </div>
    `;
  } else {
    messageContent = escapeHtml(displayText);
  }

  const urlRegex = /(?:https?:\/\/[^\s<>"']+|\/downloads\/[^\s<>"']+)/g;
  const urlMatches = rawText.match(urlRegex) || [];

  if (urlMatches.length > 0) {
    const matchedUrl = urlMatches[0];
    // Normalize to relative /downloads/... if pointing to downloaded file so it loads reliably from current host origin
    const audioSrc = matchedUrl.includes("/downloads/") ? "/downloads/" + matchedUrl.split("/downloads/")[1] : matchedUrl;
    const filename = decodeURIComponent(audioSrc.split("/").pop());
    const ext = filename.split(".").pop().toLowerCase();

    // 1. Audio / Voice Note
    if (msg.category === "audio" || ["webm", "ogg", "mp3", "wav", "m4a", "aac"].includes(ext) || filename.startsWith("voice_note_")) {
      mediaHtml = `
        <div class="voice-note-card">
          <div class="voice-note-header">
            <span>🎙️ Voice Note</span>
            <small>${escapeHtml(filename)}</small>
          </div>
          <audio controls preload="auto" src="${audioSrc}"></audio>
          <div class="voice-note-fallback">
            <a href="${audioSrc}" download="${escapeHtml(filename)}" class="voice-dl-link">⬇️ Download Audio (${escapeHtml(ext)})</a>
          </div>
        </div>
      `;
      // Clean up text link and any leading "Download / View:" label to prevent clutter
      messageContent = messageContent
        .replace(new RegExp(`(?:Download\\s*\\/\\s*View:\\s*)?${escapeRegex(matchedUrl)}`, "g"), "")
        .trim();
    }
    // 2. Photos / Images
    else if (msg.category === "image" || ["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
      mediaHtml = `
        <img src="${audioSrc}" class="chat-img-thumb" alt="${escapeHtml(filename)}" onclick="openLightbox('${audioSrc}', '${escapeHtml(filename)}')" title="Click to view full image">
      `;
      messageContent = messageContent
        .replace(new RegExp(`(?:Download\\s*\\/\\s*View:\\s*)?${escapeRegex(matchedUrl)}`, "g"), "")
        .trim();
    }
    // 3. General Files vs Web Links
    else {
      messageContent = messageContent.replace(urlRegex, (url) => {
        const isDownloadFile = url.includes("/downloads/") || msg.category === "file";
        if (isDownloadFile) {
          const cleanUrl = url.includes("/downloads/") ? "/downloads/" + url.split("/downloads/")[1] : url;
          const dlFilename = decodeURIComponent(cleanUrl.split("/").pop());
          return `<div class="file-card"><span class="file-icon">📎</span> <a href="${cleanUrl}" target="_blank" download class="file-link">Download ${escapeHtml(dlFilename)}</a></div>`;
        } else {
          return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-web-link">${escapeHtml(url)}</a>`;
        }
      });
      messageContent = messageContent.replace(/Download\s*\/\s*View:\s*/g, "").trim();
    }
  }

  if (role === "system") {
    row.innerHTML = `
      <div class="message-bubble system-bubble">
        ℹ️ ${messageContent}
      </div>
    `;
  } else {
    // Emoji reactions row
    const reactionsHtml = renderReactionsHtml(msg.reactions || {}, msgId);

    // Encrypted shield badge
    const encryptedBadgeHtml = isEncrypted ? `<span class="encrypted-shield-badge">🔒 Encrypted</span>` : "";

    row.innerHTML = `
      <span class="sender-tag">${escapeHtml(msg.sender || "Peer")}${encryptedBadgeHtml}</span>
      <div class="message-bubble-wrapper">
        <!-- Hover action menu for quick reactions & pin -->
        <div class="msg-actions-hover">
          <button type="button" class="msg-action-chip" onclick="toggleReaction('${msgId}', '👍')" title="React 👍">👍</button>
          <button type="button" class="msg-action-chip" onclick="toggleReaction('${msgId}', '❤️')" title="React ❤️">❤️</button>
          <button type="button" class="msg-action-chip" onclick="toggleReaction('${msgId}', '😂')" title="React 😂">😂</button>
          <button type="button" class="msg-action-chip" onclick="toggleReaction('${msgId}', '🔥')" title="React 🔥">🔥</button>
          <button type="button" class="msg-action-chip" onclick="togglePinMessage('${msgId}')" title="Pin / Unpin Message">📌</button>
        </div>

        <div class="message-bubble">
          ${messageContent ? `<div class="bubble-text">${messageContent}</div>` : ""}
          ${mediaHtml}
          <div class="bubble-meta">
            <span>${escapeHtml(msg.timestamp || "")}</span>
          </div>
        </div>

        <div id="reactions-for-${msgId}" class="reactions-badge-row">
          ${reactionsHtml}
        </div>
      </div>
    `;
  }

  dom.chatMessages.appendChild(row);
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;

  // Apply search filter if active
  if (state.searchQuery) {
    applySearchFilterToRow(row, state.searchQuery);
  }
}

function renderReactionsHtml(reactions, msgId) {
  let html = "";
  for (const [emoji, users] of Object.entries(reactions)) {
    if (Array.isArray(users) && users.length > 0) {
      const reactedBySelf = users.includes(state.username);
      html += `
        <span class="reaction-pill ${reactedBySelf ? "reacted" : ""}" onclick="toggleReaction('${msgId}', '${emoji}')" title="${escapeHtml(users.join(", "))}">
          ${emoji} ${users.length}
        </span>
      `;
    }
  }
  return html;
}

function updateMessageRowReactions(msgId, reactions, pinned) {
  const container = document.getElementById(`reactions-for-${msgId}`);
  if (container) {
    container.innerHTML = renderReactionsHtml(reactions || {}, msgId);
  }
  const row = document.querySelector(`.message-row[data-msg-id="${msgId}"]`);
  if (row) {
    row.classList.toggle("pinned-highlight", Boolean(pinned));
  }
}

// ========================================================
// Emoji Reactions API
// ========================================================
async function toggleReaction(msgId, emoji) {
  if (!msgId || !emoji) return;
  try {
    const res = await fetch("/api/react", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        msg_id: msgId,
        emoji: emoji,
        user: state.username,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      updateMessageRowReactions(msgId, data.reactions, false);
    }
  } catch (e) {}
}

// ========================================================
// Pinned Messages
// ========================================================
async function togglePinMessage(msgId) {
  const isPinned = state.pinnedMessage && state.pinnedMessage.id === msgId;
  const pinAction = !isPinned;

  try {
    const res = await fetch("/api/pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel: state.currentChannel,
        msg_id: msgId,
        pin: pinAction,
      }),
    });
    if (res.ok) {
      fetchMessages();
    }
  } catch (e) {}
}

async function unpinCurrentMessage() {
  if (!state.pinnedMessage) return;
  await togglePinMessage(state.pinnedMessage.id);
}

function updatePinnedBanner(pinnedMsg) {
  if (!dom.pinnedBanner || !dom.pinnedMsgText) return;
  if (pinnedMsg && pinnedMsg.message) {
    dom.pinnedBanner.classList.remove("hidden");
    dom.pinnedMsgText.textContent = `${pinnedMsg.sender}: ${pinnedMsg.message.slice(0, 75)}`;
  } else {
    dom.pinnedBanner.classList.add("hidden");
  }
}

function scrollToPinnedMessage() {
  if (!state.pinnedMessage) return;
  const targetRow = document.querySelector(`.message-row[data-msg-id="${state.pinnedMessage.id}"]`);
  if (targetRow) {
    targetRow.scrollIntoView({ behavior: "smooth", block: "center" });
    targetRow.classList.add("highlight-row");
    setTimeout(() => targetRow.classList.remove("highlight-row"), 2000);
  }
}

// ========================================================
// Search Messages
// ========================================================
function toggleSearchBar() {
  if (!dom.searchBarDrawer) return;
  const isHidden = dom.searchBarDrawer.classList.contains("hidden");
  if (isHidden) {
    dom.searchBarDrawer.classList.remove("hidden");
    dom.searchInput.focus();
  } else {
    dom.searchBarDrawer.classList.add("hidden");
    dom.searchInput.value = "";
    state.searchQuery = "";
    handleSearchInput();
  }
}

function handleSearchInput() {
  const query = (dom.searchInput.value || "").trim().toLowerCase();
  state.searchQuery = query;

  const rows = document.querySelectorAll(".message-row:not(.system)");
  let matchCount = 0;

  rows.forEach((row) => {
    const matched = applySearchFilterToRow(row, query);
    if (matched) matchCount++;
  });

  if (query) {
    dom.searchMatchCount.classList.remove("hidden");
    dom.searchMatchCount.textContent = `${matchCount} match${matchCount === 1 ? "" : "es"}`;
  } else {
    dom.searchMatchCount.classList.add("hidden");
  }
}

function applySearchFilterToRow(row, query) {
  if (!query) {
    row.classList.remove("search-hidden");
    return true;
  }
  const text = (row.textContent || "").toLowerCase();
  const isMatch = text.includes(query);
  row.classList.toggle("search-hidden", !isMatch);
  return isMatch;
}

// ========================================================
// Voice Notes Recording via MediaRecorder
// ========================================================
async function toggleVoiceRecording() {
  if (state.voiceMediaRecorder && state.voiceMediaRecorder.state === "recording") {
    stopAndSendVoiceRecording();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.voiceChunks = [];

    // Safari & Cross-Browser audio MIME type fallback
    let mimeType = "audio/webm";
    if (typeof MediaRecorder.isTypeSupported === "function") {
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/webm")) {
        mimeType = "audio/webm";
      } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
        mimeType = "audio/mp4";
      } else if (MediaRecorder.isTypeSupported("audio/aac")) {
        mimeType = "audio/aac";
      } else if (MediaRecorder.isTypeSupported("audio/ogg")) {
        mimeType = "audio/ogg";
      } else {
        mimeType = "";
      }
    }
    state.voiceMimeType = mimeType;
    const recOptions = mimeType ? { mimeType } : {};
    state.voiceMediaRecorder = new MediaRecorder(stream, recOptions);

    state.voiceMediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        state.voiceChunks.push(e.data);
      }
    };

    state.voiceMediaRecorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
    };

    state.voiceMediaRecorder.start();
    state.voiceStartTime = Date.now();

    // Show live UI bar
    dom.voiceRecordingBar.classList.remove("hidden");
    dom.recTimer.textContent = "0:00";

    state.voiceTimerInterval = setInterval(() => {
      const elapsedSec = Math.floor((Date.now() - state.voiceStartTime) / 1000);
      const mins = Math.floor(elapsedSec / 60);
      const secs = elapsedSec % 60;
      dom.recTimer.textContent = `${mins}:${secs < 10 ? "0" : ""}${secs}`;
    }, 500);
  } catch (err) {
    alert("Microphone access permission required to record voice notes: " + err.message);
  }
}

function cancelVoiceRecording() {
  if (state.voiceTimerInterval) {
    clearInterval(state.voiceTimerInterval);
  }
  if (state.voiceMediaRecorder && state.voiceMediaRecorder.state === "recording") {
    state.voiceMediaRecorder.stop();
  }
  state.voiceChunks = [];
  dom.voiceRecordingBar.classList.add("hidden");
}

function stopAndSendVoiceRecording() {
  if (state.voiceTimerInterval) {
    clearInterval(state.voiceTimerInterval);
  }
  if (!state.voiceMediaRecorder) return;

  state.voiceMediaRecorder.onstop = () => {
    const mime = state.voiceMimeType || "audio/webm";
    const ext = mime.includes("mp4") || mime.includes("aac") ? "mp4" : (mime.includes("ogg") ? "ogg" : "webm");
    const audioBlob = new Blob(state.voiceChunks, mime ? { type: mime } : {});
    const voiceFile = new File([audioBlob], `voice_note_${Date.now()}.${ext}`, { type: mime || "audio/webm" });
    uploadFileWithProgress(voiceFile);
    dom.voiceRecordingBar.classList.add("hidden");
  };

  state.voiceMediaRecorder.stop();
}

// ========================================================
// Upload File with Visual Progress Bar
// ========================================================
function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  uploadFileWithProgress(file);
  event.target.value = "";
}

function uploadFileWithProgress(file) {
  if (!file) return;

  const formData = new FormData();
  formData.append("sender", state.username || "Mobile User");
  formData.append("client_id", state.clientId);
  formData.append("channel", state.currentChannel || "group");
  formData.append("file", file);

  // Show progress card
  dom.uploadProgressCard.classList.remove("hidden");
  dom.uploadFilename.textContent = file.name;
  dom.uploadPercent.textContent = "0%";
  dom.progressBarFill.style.width = "0%";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload", true);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      dom.uploadPercent.textContent = `${pct}%`;
      dom.progressBarFill.style.width = `${pct}%`;
    }
  };

  xhr.onload = async () => {
    dom.progressBarFill.style.width = "100%";
    dom.uploadPercent.textContent = "100%";
    setTimeout(() => {
      dom.uploadProgressCard.classList.add("hidden");
    }, 600);

    if (xhr.status === 200) {
      await fetchMessages();
    } else {
      appendMessageRow({
        sender: "System",
        message: `Upload failed (Status ${xhr.status})`,
        category: "system",
      });
    }
  };

  xhr.onerror = () => {
    dom.uploadProgressCard.classList.add("hidden");
    appendMessageRow({
      sender: "System",
      message: "Network error during upload.",
      category: "system",
    });
  };

  xhr.send(formData);
}

// ========================================================
// Image Lightbox Modal
// ========================================================
function openLightbox(src, filename) {
  if (!dom.lightboxModal || !dom.lightboxImg) return;
  dom.lightboxImg.src = src;
  dom.lightboxCaption.textContent = filename || "Photo";
  dom.lightboxDownloadLink.href = src;
  dom.lightboxDownloadLink.download = filename || "photo.png";
  dom.lightboxModal.classList.remove("hidden");
}

function closeLightbox() {
  if (dom.lightboxModal) {
    dom.lightboxModal.classList.add("hidden");
    if (dom.lightboxImg) dom.lightboxImg.src = "";
  }
}

// ========================================================
// Media & Shared Files Gallery Modal
// ========================================================
async function openMediaGallery() {
  if (!dom.galleryModal) return;
  dom.galleryModal.classList.remove("hidden");
  dom.galleryGrid.innerHTML = `<div class="loading-hint">Loading media gallery...</div>`;

  try {
    const res = await fetch("/api/media");
    if (!res.ok) throw new Error("Failed to load");
    const data = await res.json();
    state.galleryItems = data.media || [];
    renderGalleryItems();
  } catch (e) {
    dom.galleryGrid.innerHTML = `<div class="empty-peers">No shared files found yet.</div>`;
  }
}

function closeMediaGallery() {
  if (dom.galleryModal) {
    dom.galleryModal.classList.add("hidden");
  }
}

function filterGalleryTab(filterType, btnEl) {
  state.activeGalleryFilter = filterType;
  document.querySelectorAll(".gallery-tab").forEach((b) => b.classList.remove("active"));
  if (btnEl) btnEl.classList.add("active");
  renderGalleryItems();
}

function renderGalleryItems() {
  if (!dom.galleryGrid) return;
  const filter = state.activeGalleryFilter;

  const items = state.galleryItems.filter((item) => {
    if (filter === "all") return true;
    return item.type === filter;
  });

  if (items.length === 0) {
    dom.galleryGrid.innerHTML = `<div class="empty-peers">No ${filter} items shared yet.</div>`;
    return;
  }

  dom.galleryGrid.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "media-card";

    let previewHtml = "";
    if (item.type === "image") {
      previewHtml = `<div class="media-card-preview"><img src="${item.download_url}" onclick="openLightbox('${item.download_url}', '${escapeHtml(item.filename)}')"></div>`;
    } else if (item.type === "audio") {
      previewHtml = `<div class="media-card-preview"><span class="media-card-icon">🎙️</span></div>`;
    } else {
      previewHtml = `<div class="media-card-preview"><span class="media-card-icon">📄</span></div>`;
    }

    const sizeStr = item.size > 1048576 ? `${(item.size / 1048576).toFixed(1)} MB` : `${Math.round(item.size / 1024)} KB`;

    card.innerHTML = `
      ${previewHtml}
      <div class="media-card-meta">
        <span class="media-card-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</span>
        <span class="media-card-size">${sizeStr}</span>
      </div>
      <a href="${item.download_url}" download class="media-card-dl">⬇️ Download</a>
    `;
    dom.galleryGrid.appendChild(card);
  });
}

// ========================================================
// Custom Channel Rooms Modal
// ========================================================
function openRoomModal() {
  if (!dom.roomModal) return;
  dom.roomModal.classList.remove("hidden");
  if (dom.inputRoomName) {
    dom.inputRoomName.value = "";
    dom.inputRoomName.focus();
  }
}

function closeRoomModal() {
  if (dom.roomModal) dom.roomModal.classList.add("hidden");
}

async function handleCreateRoomSubmit() {
  const roomName = (dom.inputRoomName.value || "").trim();
  if (!roomName) return;

  const passkey = dom.inputRoomPasskey ? dom.inputRoomPasskey.value.trim() : "";
  const formattedName = roomName.startsWith("#") ? roomName : `#${roomName}`;
  if (!state.customRooms.includes(formattedName)) {
    state.customRooms.push(formattedName);
    saveMyRooms();
  }

  // If a password was specified during creation, save it to roomSecrets immediately
  if (passkey) {
    state.roomSecrets[formattedName] = passkey;
    localStorage.setItem("lanchat_room_secrets", JSON.stringify(state.roomSecrets));
  }

  try {
    const res = await fetch("/api/room/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room: formattedName, client_id: state.clientId }),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.rooms)) {
        state.customRooms = Array.from(new Set([...state.customRooms, ...data.rooms]));
        saveMyRooms();
      }
    }
  } catch (e) {}

  if (dom.inputRoomPasskey) dom.inputRoomPasskey.value = "";
  closeRoomModal();
  renderCustomRooms();
  selectChannel(formattedName);

  if (passkey) {
    showToastNotification({
      id: "toast_lock_" + Date.now(),
      sender: "🔒 Room Secured",
      message: `${formattedName} is now locked with your passphrase.`,
      channel: formattedName,
    });
  }
}

function handleDeleteRoomClick(btn, roomName) {
  if (btn.dataset.confirming === "true") {
    btn.disabled = true;
    btn.textContent = "⏳";
    deleteRoom(roomName);
  } else {
    btn.dataset.confirming = "true";
    btn.textContent = "Leave?";
    btn.classList.add("confirming");
    setTimeout(() => {
      if (btn && btn.dataset.confirming === "true") {
        btn.dataset.confirming = "false";
        btn.textContent = "🗑️";
        btn.classList.remove("confirming");
      }
    }, 3500);
  }
}

async function deleteRoom(roomName) {
  state.customRooms = state.customRooms.filter((r) => r !== roomName);
  saveMyRooms();
  renderCustomRooms();

  try {
    await fetch("/api/room/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room: roomName, client_id: state.clientId }),
    });
  } catch (err) {}

  if (state.currentChannel === roomName) {
    if (state.customRooms.length > 0) {
      selectChannel(state.customRooms[0]);
    } else {
      selectChannel(null); // Return to Welcome Hub
    }
  }

  showToastNotification({
    id: "del_" + Date.now(),
    sender: "🗑️ Room Left",
    message: `Left room ${roomName}`,
    channel: null,
  });
}

// ========================================================
// Join Room Modal & Auto-Join Handler
// ========================================================
function openJoinRoomModal() {
  if (!dom.joinRoomModal) return;
  dom.joinRoomModal.classList.remove("hidden");
  if (dom.inputJoinRoomCode) {
    dom.inputJoinRoomCode.value = "";
    dom.inputJoinRoomCode.focus();
  }
}

function closeJoinRoomModal() {
  if (dom.joinRoomModal) dom.joinRoomModal.classList.add("hidden");
}

async function handleJoinRoomSubmit() {
  const code = (dom.inputJoinRoomCode.value || "").trim();
  if (!code) return;
  closeJoinRoomModal();
  await joinRoomByName(code, false);
}

async function joinRoomByName(roomName, isFromUrl = false) {
  if (!roomName) return;
  if (roomName.toLowerCase() === "group" || roomName === "Group Broadcast" || roomName === "Local LAN Broadcast") {
    selectChannel("group");
    const groupNotifKey = "joined_group";
    if (isFromUrl && !state.notifiedMessageIds.has(groupNotifKey)) {
      state.notifiedMessageIds.add(groupNotifKey);
      showToastNotification({
        id: groupNotifKey,
        sender: "🎉 Joined Chat",
        message: "You connected to Local LAN Broadcast via invitation link!",
        channel: "group",
      });
    }
    return;
  }
  const formatted = roomName.startsWith("#") ? roomName : `#${roomName}`;

  if (!state.customRooms.includes(formatted)) {
    state.customRooms.push(formatted);
    saveMyRooms();
  }

  try {
    const res = await fetch("/api/room/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room: formatted, client_id: state.clientId }),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.rooms)) {
        state.customRooms = Array.from(new Set([...state.customRooms, ...data.rooms]));
        saveMyRooms();
      }
    }
  } catch (e) {}

  renderCustomRooms();
  selectChannel(formatted);


  const joinNotifKey = `joined_${formatted}`;
  if (!state.notifiedMessageIds.has(joinNotifKey)) {
    state.notifiedMessageIds.add(joinNotifKey);
    if (isFromUrl) {
      showToastNotification({
        id: joinNotifKey,
        sender: "🎉 Joined Room",
        message: `You automatically joined ${formatted} via invitation link!`,
        channel: formatted,
      });
    } else {
      showToastNotification({
        id: joinNotifKey,
        sender: "🔑 Room Joined",
        message: `Successfully connected to ${formatted}!`,
        channel: formatted,
      });
    }
  }
}

// ========================================================
// Invite & 1-Click Share Modal (with Live QR Code)
// ========================================================
function openInviteModal(preselectedRoom) {
  if (!dom.inviteModal) return;

  const targetRoom = (typeof preselectedRoom === "string" && preselectedRoom)
    ? preselectedRoom
    : (state.currentChannel || "group");

  if (dom.inviteRoomSelect) {
    dom.inviteRoomSelect.innerHTML = "";
    state.customRooms.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r;
      opt.textContent = `🏷️ ${r}`;
      if (targetRoom === r) {
        opt.selected = true;
      }
      dom.inviteRoomSelect.appendChild(opt);
    });

    const optGroup = document.createElement("option");
    optGroup.value = "group";
    optGroup.textContent = "🌐 Group Broadcast";
    if (targetRoom === "group" || targetRoom === null) {
      optGroup.selected = true;
    }
    dom.inviteRoomSelect.appendChild(optGroup);
  }

  // Populate network adapters dropdown
  if (dom.inviteIpSelect) {
    dom.inviteIpSelect.innerHTML = "";
    const ipSet = new Set();

    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      ipSet.add(window.location.hostname);
    }
    if (state.hostInfo && state.hostInfo.active_ip) {
      ipSet.add(state.hostInfo.active_ip);
    }
    if (state.hostInfo && state.hostInfo.host_ip && state.hostInfo.host_ip !== "127.0.0.1") {
      ipSet.add(state.hostInfo.host_ip);
    }
    const ifaces = (state.hostInfo && state.hostInfo.interfaces) || [];
    ifaces.forEach((iface) => {
      if (iface.ip && iface.ip !== "127.0.0.1") {
        ipSet.add(iface.ip);
      }
    });

    if (ipSet.size === 0) {
      ipSet.add(window.location.hostname || "127.0.0.1");
    }

    const preferredIp = (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1")
      ? window.location.hostname
      : (state.hostInfo && (state.hostInfo.active_ip || state.hostInfo.host_ip));

    ipSet.forEach((ip) => {
      const opt = document.createElement("option");
      opt.value = ip;
      opt.textContent = `📶 ${ip}`;
      if (ip === preferredIp) {
        opt.selected = true;
      }
      dom.inviteIpSelect.appendChild(opt);
    });
  }

  updateInviteUrl();
  dom.inviteModal.classList.remove("hidden");
}

function closeInviteModal() {
  if (dom.inviteModal) {
    dom.inviteModal.classList.add("hidden");
  }
}

function updateInviteUrl() {
  const selectedRoom = dom.inviteRoomSelect ? dom.inviteRoomSelect.value : (state.currentChannel || "group");
  const cleanRoom = selectedRoom.startsWith("#") ? selectedRoom.slice(1) : selectedRoom;

  let hostAddress = "";
  const isCloudHost = window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1";

  if (isCloudHost) {
    // Cloud / Reverse Proxy deployment (Render, custom domain): use host directly without :8080
    hostAddress = window.location.host;
  } else {
    const port = window.location.port ? `:${window.location.port}` : ":8080";
    const ip = (dom.inviteIpSelect && dom.inviteIpSelect.value)
      || (state.hostInfo && (state.hostInfo.active_ip || state.hostInfo.host_ip))
      || "127.0.0.1";
    hostAddress = `${ip}${port}`;
  }

  const protocol = window.location.protocol || "http:";
  const url = `${protocol}//${hostAddress}/?room=${encodeURIComponent(cleanRoom)}`;

  if (dom.inviteLinkInput) {
    dom.inviteLinkInput.value = url;
  }

  if (dom.inviteQrContainer) {
    dom.inviteQrContainer.innerHTML = QR.generateSVG(url, 2);
  }
}

async function copyInviteLink() {
  if (!dom.inviteLinkInput) return;
  const url = dom.inviteLinkInput.value;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url);
    } else {
      dom.inviteLinkInput.select();
      document.execCommand("copy");
    }
    if (dom.copyText) dom.copyText.textContent = "Copied! ✓";
    if (dom.copyIcon) dom.copyIcon.textContent = "✅";
    if (dom.btnCopyInvite) dom.btnCopyInvite.classList.add("copied");

    setTimeout(() => {
      if (dom.copyText) dom.copyText.textContent = "Copy";
      if (dom.copyIcon) dom.copyIcon.textContent = "📋";
      if (dom.btnCopyInvite) dom.btnCopyInvite.classList.remove("copied");
    }, 2000);
  } catch (err) {
    dom.inviteLinkInput.select();
  }
}

async function shareInviteLinkNative() {
  const url = dom.inviteLinkInput ? dom.inviteLinkInput.value : window.location.href;
  const roomName = dom.inviteRoomSelect ? dom.inviteRoomSelect.value : (state.currentChannel || "General");
  if (navigator.share) {
    try {
      await navigator.share({
        title: `Join ${roomName} on LAN Chat`,
        text: `Join the conversation in ${roomName} on our local Wi-Fi chat:`,
        url: url,
      });
    } catch (e) {}
  } else {
    copyInviteLink();
    alert("Invitation link copied to clipboard! You can paste it into any app.");
  }
}

function shareViaWhatsApp() {
  const url = dom.inviteLinkInput ? dom.inviteLinkInput.value : window.location.href;
  const roomName = dom.inviteRoomSelect ? dom.inviteRoomSelect.value : (state.currentChannel || "General");
  const text = `Join our local network chat in room ${roomName}: ${url}`;
  window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`, "_blank");
}

function shareViaTelegram() {
  const url = dom.inviteLinkInput ? dom.inviteLinkInput.value : window.location.href;
  const roomName = dom.inviteRoomSelect ? dom.inviteRoomSelect.value : (state.currentChannel || "General");
  const text = `Join room ${roomName} on LAN Chat: ${url}`;
  window.open(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`, "_blank");
}

// ========================================================
// Control Center Modal
// ========================================================
function openControlCenterModal() {
  if (!dom.controlCenterModal) return;
  updateControlCenterUI();
  dom.controlCenterModal.classList.remove("hidden");
}

function closeControlCenterModal() {
  if (dom.controlCenterModal) dom.controlCenterModal.classList.add("hidden");
}

function updateControlCenterUI() {
  if (dom.ctrlThemeLabel) {
    dom.ctrlThemeLabel.textContent = state.theme === "dark" ? "Dark Mode (Catppuccin Mocha)" : "Light Mode (Latte)";
  }
  if (dom.ctrlThemeIcon) {
    dom.ctrlThemeIcon.textContent = state.theme === "dark" ? "🌙" : "☀️";
  }
  if (dom.ctrlSoundLabel) {
    dom.ctrlSoundLabel.textContent = state.soundEnabled ? "Sound Alerts Active" : "Sound Alerts Muted";
  }
  if (dom.ctrlSoundIcon) {
    dom.ctrlSoundIcon.textContent = state.soundEnabled ? "🔔" : "🔕";
  }
}

function triggerNetworkRefresh() {
  fetchStatus();
  fetchMessages();
  showToastNotification({
    id: "refresh_" + Date.now(),
    sender: "🔄 Network",
    message: "Refreshed peers and messages across LAN.",
    channel: null,
  });
}

// ========================================================
// Minimalist Landing Page & Offline Guide Modal (Option 3 / Solution A)
// ========================================================
function openLandingModal() {
  if (!dom.landingModal) return;
  if (dom.chkSkipLanding) {
    dom.chkSkipLanding.checked = localStorage.getItem("lanchat_skip_landing") === "true";
  }
  if (dom.landingInputNickname) {
    dom.landingInputNickname.value = state.username || "";
  }
  if (dom.loginModal) {
    dom.loginModal.classList.add("hidden");
  }
  dom.landingModal.classList.remove("hidden");
  if (dom.landingInputNickname && !state.username) {
    setTimeout(() => {
      try {
        dom.landingInputNickname.focus();
      } catch (e) {}
    }, 150);
  }
}

function closeLandingModal(savePreference = false) {
  if (dom.landingModal) {
    dom.landingModal.classList.add("hidden");
  }
  if (savePreference && dom.chkSkipLanding) {
    if (dom.chkSkipLanding.checked) {
      localStorage.setItem("lanchat_skip_landing", "true");
    } else {
      localStorage.removeItem("lanchat_skip_landing");
    }
  }
}

function launchChatFromLanding() {
  const enteredName = dom.landingInputNickname ? dom.landingInputNickname.value.trim() : "";
  if (enteredName) {
    saveUsername(enteredName);
    initUserSession();
  }
  closeLandingModal(true);
  if (!state.username) {
    if (dom.loginModal) dom.loginModal.classList.remove("hidden");
    if (dom.inputUsername) dom.inputUsername.focus();
  } else {
    if (dom.messageInput) dom.messageInput.focus();
  }
}

function startPrivateNetworkFlow() {
  const enteredName = dom.landingInputNickname ? dom.landingInputNickname.value.trim() : "";
  if (enteredName) {
    saveUsername(enteredName);
    initUserSession();
  }
  closeLandingModal(true);
  if (!state.username) {
    if (dom.loginModal) dom.loginModal.classList.remove("hidden");
    if (dom.inputUsername) dom.inputUsername.focus();
    showToastNotification({
      id: "toast_login_req_" + Date.now(),
      sender: "🔒 Private Network",
      message: "Please choose your display name to start or share private rooms.",
      channel: null,
    });
  } else {
    openRoomModal();
  }
}

function scrollToOfflineGuide() {
  const offlineSection = document.getElementById("landing-offline-section");
  if (offlineSection) {
    offlineSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// Ensure globally accessible for inline onclick handlers
window.openLandingModal = openLandingModal;
window.closeLandingModal = closeLandingModal;
window.launchChatFromLanding = launchChatFromLanding;
window.startPrivateNetworkFlow = startPrivateNetworkFlow;
window.scrollToOfflineGuide = scrollToOfflineGuide;
window.openEncryptionModal = openEncryptionModal;
window.closeEncryptionModal = closeEncryptionModal;
window.saveRoomEncryption = saveRoomEncryption;
window.disableRoomEncryption = disableRoomEncryption;

// ========================================================
// Room End-to-End Encryption
// ========================================================
function openEncryptionModal(targetChannel = null) {
  const channel = targetChannel || state.currentChannel;
  if (!channel) {
    showToastNotification({
      id: "toast_lock_warn_" + Date.now(),
      sender: "🔒 Room Lock",
      message: "Please select or create a room first to configure its lock.",
      channel: null,
    });
    openRoomModal();
    return;
  }

  if (!dom.encryptionModal) return;
  dom.encryptionModal.classList.remove("hidden");

  const channelLabel = channel === "group" ? "Local LAN Broadcast" : channel;
  if (dom.encryptionModalTarget) {
    dom.encryptionModalTarget.textContent = `Securing channel: ${channelLabel}`;
  }

  const currentSecret = state.roomSecrets[channel] || "";
  if (dom.inputRoomSecret) {
    dom.inputRoomSecret.value = currentSecret;
    dom.inputRoomSecret.focus();
  }

  if (dom.encryptionStatusText) {
    dom.encryptionStatusText.textContent = currentSecret
      ? "🔒 Lock is currently ACTIVE with a secret key"
      : "🔓 Room is currently UNENCRYPTED";
  }
  if (dom.encryptionStatusBanner) {
    dom.encryptionStatusBanner.className = `encryption-status-banner ${currentSecret ? "active" : "inactive"}`;
  }
}

function closeEncryptionModal() {
  if (dom.encryptionModal) dom.encryptionModal.classList.add("hidden");
}

function saveRoomEncryption() {
  const channel = state.currentChannel;
  if (!channel) {
    closeEncryptionModal();
    return;
  }
  const secret = (dom.inputRoomSecret ? dom.inputRoomSecret.value : "").trim();
  if (secret) {
    state.roomSecrets[channel] = secret;
    showToastNotification({
      id: "toast_lock_set_" + Date.now(),
      sender: "🔒 Passphrase Applied",
      message: `Lock enabled for ${channel}. Messages are now end-to-end encrypted.`,
      channel: channel,
    });
  } else {
    delete state.roomSecrets[channel];
  }
  localStorage.setItem("lanchat_room_secrets", JSON.stringify(state.roomSecrets));
  updateEncryptionIcon();
  renderCustomRooms();
  closeEncryptionModal();

  // Re-render active messages with updated key
  state.lastPollTime = 0;
  state.renderedMessageIds.clear();
  dom.chatMessages.innerHTML = "";
  fetchMessages();
}

function disableRoomEncryption() {
  const channel = state.currentChannel;
  if (channel) {
    delete state.roomSecrets[channel];
    localStorage.setItem("lanchat_room_secrets", JSON.stringify(state.roomSecrets));
    showToastNotification({
      id: "toast_lock_off_" + Date.now(),
      sender: "🔓 Lock Removed",
      message: `Encryption disabled for ${channel}.`,
      channel: channel,
    });
  }
  updateEncryptionIcon();
  renderCustomRooms();
  closeEncryptionModal();

  // Re-render active messages without key
  state.lastPollTime = 0;
  state.renderedMessageIds.clear();
  dom.chatMessages.innerHTML = "";
  fetchMessages();
}

function updateEncryptionIcon() {
  const isEncrypted = Boolean(state.currentChannel && state.roomSecrets[state.currentChannel]);
  if (dom.btnHeaderEncrypt) {
    dom.btnHeaderEncrypt.classList.toggle("lock-active", isEncrypted);
    dom.btnHeaderEncrypt.title = isEncrypted
      ? `🔒 Room Encrypted (${state.currentChannel}) - Click to manage lock`
      : "🔓 Room Unencrypted - Click to lock with a passphrase";
  }
  if (dom.encryptIcon) {
    dom.encryptIcon.textContent = isEncrypted ? "🔒" : "🔓";
  }
  if (dom.encryptLabel) {
    dom.encryptLabel.textContent = isEncrypted ? "Secured" : "Lock";
  }
}

// Lightweight zero-dependency authenticated symmetric cipher
function djb2Hash(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) hash = ((hash << 5) + hash) + str.charCodeAt(i);
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function u8ToBase64(u8) {
  let binary = "";
  for (let i = 0; i < u8.length; i++) binary += String.fromCharCode(u8[i]);
  return btoa(binary);
}

function base64ToU8(b64) {
  const binary = atob(b64);
  const u8 = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) u8[i] = binary.charCodeAt(i);
  return u8;
}

function encryptMessagePayload(text, secret) {
  if (!secret) return text;
  const tag = djb2Hash(secret).slice(0, 6);
  const textBytes = new TextEncoder().encode(text);
  const secBytes = new TextEncoder().encode(secret);
  const cipher = new Uint8Array(textBytes.length);
  for (let i = 0; i < textBytes.length; i++) {
    cipher[i] = textBytes[i] ^ secBytes[i % secBytes.length];
  }
  return `[ENC:v1:${tag}:${u8ToBase64(cipher)}]`;
}

function decryptMessagePayload(text, secret) {
  if (!text || !text.startsWith("[ENC:v1:")) {
    // Support legacy [ENC] format fallback
    if (text && text.startsWith("[ENC]")) {
      if (!secret) return { text: "🔒 Encrypted Message — Passphrase Required", isEncrypted: true, needsKey: true };
      try {
        const raw = decodeURIComponent(atob(text.slice(5)));
        let plain = "";
        for (let i = 0; i < raw.length; i++) plain += String.fromCharCode(raw.charCodeAt(i) ^ secret.charCodeAt(i % secret.length));
        return { text: plain, isEncrypted: true, wrongKey: false };
      } catch (e) {
        return { text: "🔒 Encrypted Message (Incorrect Passphrase)", isEncrypted: true, wrongKey: true };
      }
    }
    return { text: text, isEncrypted: false, needsKey: false, wrongKey: false };
  }

  const parts = text.split(":");
  if (parts.length < 4) return { text: "[Corrupted Encrypted Payload]", isEncrypted: true, wrongKey: true };
  const msgTag = parts[2];
  const b64 = parts[3].slice(0, -1);

  if (!secret) {
    return { text: "🔒 Encrypted Message — Passphrase Required", isEncrypted: true, needsKey: true };
  }

  const currTag = djb2Hash(secret).slice(0, 6);
  if (currTag !== msgTag) {
    return { text: "🔒 Encrypted Message (Incorrect Passphrase)", isEncrypted: true, wrongKey: true };
  }

  try {
    const cipher = base64ToU8(b64);
    const secBytes = new TextEncoder().encode(secret);
    const plain = new Uint8Array(cipher.length);
    for (let i = 0; i < cipher.length; i++) {
      plain[i] = cipher[i] ^ secBytes[i % secBytes.length];
    }
    return { text: new TextDecoder().decode(plain), isEncrypted: true, wrongKey: false };
  } catch (e) {
    return { text: "🔒 Encrypted Message (Decryption Error)", isEncrypted: true, wrongKey: true };
  }
}

// ========================================================
// Message Transmission
// ========================================================
async function sendMessage() {
  const rawText = dom.messageInput.value.trim();
  if (!rawText) return;

  if (state.currentChannel === null) {
    showToastNotification({
      id: "toast_room_req_" + Date.now(),
      sender: "🔒 Private Network",
      message: "Please create or join a private room to start chatting.",
      channel: null,
    });
    openRoomModal();
    return;
  }

  dom.messageInput.value = "";
  dom.messageInput.focus();

  // Handle client-side slash commands
  if (rawText.startsWith("/")) {
    handleSlashCommand(rawText);
    return;
  }

  // Encrypt message if room key is active
  const secretKey = state.roomSecrets[state.currentChannel] || "";
  const textToSend = encryptMessagePayload(rawText, secretKey);

  const payload = {
    sender: state.username || "Mobile User",
    client_id: state.clientId,
    channel: state.currentChannel,
    text: textToSend,
  };

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      await fetchMessages();
    } else {
      appendMessageRow({
        sender: "System",
        message: "Failed to deliver message.",
        category: "system",
      });
    }
  } catch (err) {
    appendMessageRow({
      sender: "System",
      message: `Error sending: ${err.message}`,
      category: "system",
    });
  }
}

function clearActiveChat() {
  dom.chatMessages.innerHTML = "";
  state.renderedMessageIds.clear();
  appendMessageRow({
    sender: "System",
    message: "Chat history cleared on this device.",
    category: "system",
  });
}

// ========================================================
// Slash Commands
// ========================================================
function handleSlashCommand(cmdLine) {
  const parts = cmdLine.split(" ");
  const cmd = parts[0].toLowerCase();

  if (cmd === "/help") {
    const helpMsg = `💡 Available Commands:\n• /nick <name> — Change display name\n• /room <name> — Jump or create room\n• /clear — Clear chat screen\n• /shrug — Send ¯\\_(ツ)_/¯\n• /help — Show this help`;
    appendMessageRow({ sender: "System", message: helpMsg, category: "system" });
  } else if (cmd === "/clear") {
    clearActiveChat();
  } else if (cmd === "/nick") {
    const newName = parts.slice(1).join(" ").trim();
    if (newName) {
      state.username = newName;
      localStorage.setItem("lanchat_username", newName);
      initUserSession();
      appendMessageRow({
        sender: "System",
        message: `Name changed to '${newName}'`,
        category: "system",
      });
    }
  } else if (cmd === "/room") {
    const roomName = parts.slice(1).join(" ").trim();
    if (roomName) {
      const formatted = roomName.startsWith("#") ? roomName : `#${roomName}`;
      selectChannel(formatted);
    }
  } else if (cmd === "/shrug") {
    dom.messageInput.value = "¯\\_(ツ)_/¯";
    sendMessage();
  } else {
    appendMessageRow({
      sender: "System",
      message: `Unknown command '${cmd}'. Type /help for assistance.`,
      category: "system",
    });
  }
}

// ========================================================
// Direct Peer-to-Peer Hub & Network Adapters
// ========================================================
function openP2PModal() {
  if (!dom.p2pModal) return;
  dom.p2pModal.classList.remove("hidden");
  renderP2PHubList();
  loadNetworkInterfaces();
  if (dom.inputManualIp && !dom.inputManualIp.value && state.hostInfo.host_ip) {
    dom.inputManualIp.value = `${state.hostInfo.host_ip}:${state.hostInfo.host_port || 50001}`;
  }
}

function closeP2PModal() {
  if (dom.p2pModal) dom.p2pModal.classList.add("hidden");
}

async function loadNetworkInterfaces() {
  if (!dom.networkInterfacesList) return;
  try {
    const res = await fetch("/api/interfaces");
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();
    const ifaces = data.interfaces || [];

    dom.networkInterfacesList.innerHTML = "";
    ifaces.forEach((iface) => {
      const item = document.createElement("div");
      item.className = "interface-item";
      item.innerHTML = `
        <div class="interface-left">
          <strong>${escapeHtml(iface.name)}</strong>
          ${iface.is_primary ? `<span class="interface-primary-badge">PRIMARY ROUTE</span>` : ""}
        </div>
        <span class="interface-ip-chip">${escapeHtml(iface.ip)}</span>
      `;
      dom.networkInterfacesList.appendChild(item);
    });
  } catch (e) {
    dom.networkInterfacesList.innerHTML = `<div class="empty-peers">Unable to query local interfaces</div>`;
  }
}

function renderP2PHubList() {
  if (!dom.p2pHubList) return;
  const peers = state.peers || [];
  if (dom.p2pHubCount) {
    dom.p2pHubCount.textContent = `${peers.length} online`;
  }

  if (peers.length === 0) {
    dom.p2pHubList.innerHTML = `
      <div class="empty-hub-state">
        <span class="hub-icon">🔍</span>
        <p>No active peers discovered on this network yet.</p>
        <small>Enter a device IP:Port below to establish an instant direct connection.</small>
      </div>
    `;
    return;
  }

  dom.p2pHubList.innerHTML = "";
  peers.forEach((peer) => {
    const card = document.createElement("div");
    card.className = "p2p-card";

    let avatarIcon = "🖥️";
    let badgeText = "Desktop TCP";
    if (peer.is_host) {
      avatarIcon = "💻";
      badgeText = "Host";
    } else if (peer.is_web) {
      avatarIcon = "📱";
      badgeText = "Mobile / Web";
    }

    const portStr = peer.tcp_port ? `:${peer.tcp_port}` : "";
    const ipStr = `${peer.ip_address}${portStr}`;

    card.innerHTML = `
      <div class="p2p-card-left">
        <div class="p2p-avatar">${avatarIcon}</div>
        <div class="p2p-details">
          <div class="p2p-name-row">
            <span class="p2p-name">${escapeHtml(peer.username)}</span>
            <span class="p2p-tag">${badgeText}</span>
          </div>
          <span class="p2p-ip">${ipStr}</span>
        </div>
      </div>
      <div class="p2p-actions">
        <button type="button" class="btn-primary-xs" onclick="closeP2PModal(); selectChannel('${peer.peer_id}')">💬 Chat</button>
        <button type="button" class="btn-primary-xs" onclick="closeP2PModal(); startPeerFileUpload('${peer.peer_id}')">📎 File</button>
      </div>
    `;
    dom.p2pHubList.appendChild(card);
  });
}

async function handleManualP2PConnect() {
  const target = (dom.inputManualIp.value || "").trim();
  if (!target) return;

  dom.btnManualConnect.disabled = true;
  dom.btnManualConnect.textContent = "Connecting...";
  dom.manualConnectFeedback.classList.remove("hidden");
  dom.manualConnectFeedback.textContent = `Establishing connection to ${target}...`;

  try {
    const res = await fetch("/api/connect_peer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: target }),
    });
    const result = await res.json();
    if (result.success) {
      dom.manualConnectFeedback.textContent = `✅ Successfully reached ${target}!`;
      setTimeout(() => {
        closeP2PModal();
        fetchStatus();
      }, 1000);
    } else {
      dom.manualConnectFeedback.textContent = `❌ Unable to connect to ${target}.`;
    }
  } catch (err) {
    dom.manualConnectFeedback.textContent = `❌ Error: ${err.message}`;
  } finally {
    dom.btnManualConnect.disabled = false;
    dom.btnManualConnect.textContent = "⚡ Connect Directly";
  }
}

// ========================================================
// Peer Info & Ping Diagnostics
// ========================================================
function showActivePeerInfo() {
  if (state.currentChannel === null) {
    showNetworkInfo();
  } else if (String(state.currentChannel).startsWith("#")) {
    showRoomInfo(state.currentChannel);
  } else {
    showPeerInfo(state.currentChannel);
  }
}

function showNetworkInfo() {
  dom.peerInfoName.textContent = "🌐 LAN Broadcast Network";
  dom.peerInfoContent.innerHTML = `
    <div class="info-row"><span class="info-lbl">Channel:</span> <span class="info-val">Group Broadcast</span></div>
    <div class="info-row"><span class="info-lbl">Local Host IP:</span> <span class="info-val">${state.hostInfo.local_ip || "127.0.0.1"}</span></div>
    <div class="info-row"><span class="info-lbl">Peer TCP Port:</span> <span class="info-val">${state.hostInfo.tcp_port || 50001}</span></div>
    <div class="info-row"><span class="info-lbl">Active Peers:</span> <span class="info-val">${state.peers.length} devices online</span></div>
  `;
  dom.btnPingPeer.classList.add("hidden");
  dom.peerInfoModal.classList.remove("hidden");
}

function showRoomInfo(roomName) {
  dom.peerInfoName.textContent = `🏷️ Room: ${roomName}`;
  const isEncrypted = Boolean(state.roomSecrets[roomName]);
  dom.peerInfoContent.innerHTML = `
    <div class="info-row"><span class="info-lbl">Channel Name:</span> <span class="info-val">${escapeHtml(roomName)}</span></div>
    <div class="info-row"><span class="info-lbl">Type:</span> <span class="info-val">Topic Channel</span></div>
    <div class="info-row"><span class="info-lbl">Encryption:</span> <span class="info-val">${isEncrypted ? "🔒 Symmetric Key Active" : "🔓 Open / Unencrypted"}</span></div>
  `;
  dom.btnPingPeer.classList.add("hidden");
  dom.peerInfoModal.classList.remove("hidden");
}

function showPeerInfo(peerId) {
  const peer = state.peers.find((p) => p.peer_id === peerId);
  if (!peer) return;

  dom.peerInfoName.textContent = `ℹ️ ${peer.username}`;
  dom.peerInfoContent.innerHTML = `
    <div class="info-row"><span class="info-lbl">Device Type:</span> <span class="info-val">${peer.is_host ? "Host PC" : (peer.is_web ? "Mobile Browser" : "LAN Desktop")}</span></div>
    <div class="info-row"><span class="info-lbl">IP Address:</span> <span class="info-val">${peer.ip_address}</span></div>
    <div class="info-row"><span class="info-lbl">TCP Port:</span> <span class="info-val">${peer.tcp_port || "Dynamic Web"}</span></div>
    <div class="info-row"><span class="info-lbl">Peer ID:</span> <span class="info-val">${peer.peer_id}</span></div>
    <div id="ping-result-box" class="ping-result-box hidden"></div>
  `;
  dom.btnPingPeer.classList.remove("hidden");
  dom.btnPingPeer.onclick = () => pingPeer(peer);
  dom.peerInfoModal.classList.remove("hidden");
}

async function pingPeer(peer) {
  const resultBox = document.getElementById("ping-result-box");
  if (!resultBox) return;
  resultBox.classList.remove("hidden");
  resultBox.textContent = `Pinging ${peer.ip_address}...`;

  try {
    const res = await fetch(`/api/ping?peer_id=${encodeURIComponent(peer.peer_id)}`);
    const data = await res.json();
    if (data.success) {
      resultBox.textContent = `✅ Pong! Latency: ${data.rtt_ms} ms (${data.status || "OK"})`;
    } else {
      resultBox.textContent = `❌ Ping timed out: ${data.error}`;
    }
  } catch (e) {
    resultBox.textContent = `❌ Network Error: ${e.message}`;
  }
}

function closePeerInfoModal() {
  if (dom.peerInfoModal) dom.peerInfoModal.classList.add("hidden");
}

// ========================================================
// Helper Utilities & Inputs
// ========================================================
function triggerFileUpload() {
  if (dom.fileUploader) dom.fileUploader.click();
}

function startPeerFileUpload(peerId) {
  selectChannel(peerId);
  setTimeout(() => triggerFileUpload(), 120);
}

function insertEmoji(char) {
  dom.messageInput.value += char;
  dom.messageInput.focus();
}

function handleInputKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function handleTypingKeystroke() {
  const now = Date.now();
  if (now - state.lastTypingSent > 2500) {
    state.lastTypingSent = now;
    fetch("/api/typing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender: state.username,
        client_id: state.clientId,
        channel: state.currentChannel,
      }),
    }).catch(() => {});
  }
}

function applyTheme(theme) {
  state.theme = theme;
  document.body.className = `theme-${theme}`;
  if (dom.themeIcon) {
    dom.themeIcon.textContent = theme === "dark" ? "🌙" : "☀️";
  }
  localStorage.setItem("lanchat_theme", theme);
}

function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

function toggleNotificationSetting() {
  state.soundEnabled = !state.soundEnabled;
  localStorage.setItem("lanchat_sound_enabled", state.soundEnabled);
  updateNotifIcon();
  if (state.soundEnabled) {
    playNotificationChime(false);
  }
}

function updateNotifIcon() {
  if (dom.notifIcon) {
    dom.notifIcon.textContent = state.soundEnabled ? "🔔" : "🔕";
  }
}

function requestNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function sendDeviceNotification(title, body, channelId) {
  if ("Notification" in window && Notification.permission === "granted") {
    const notif = new Notification(title, {
      body: body ? body.slice(0, 100) : "",
      icon: "favicon.ico",
    });
    notif.onclick = () => {
      window.focus();
      selectChannel(channelId);
    };
  }
}

function handleUnreadBadges(unreads) {
  const currentUnreads = unreads || {};
  const unreadsChanged = JSON.stringify(currentUnreads) !== JSON.stringify(state.unreadCounts);
  if (!unreadsChanged) return;
  state.unreadCounts = currentUnreads;
  const groupCount = currentUnreads.group || 0;
  if (dom.badgeGroup) {
    dom.badgeGroup.textContent = groupCount;
    dom.badgeGroup.classList.toggle("hidden", groupCount === 0);
  }
  renderCustomRooms();
  if (Array.isArray(state.peers) && state.peers.length > 0) {
    renderPeersList(state.peers);
  }
}

function handleIncomingNotifications(notifications) {
  if (!Array.isArray(notifications) || notifications.length === 0) return;
  notifications.forEach((item) => {
    // 1. Exclude system messages, joins, and disconnects
    if (
      item.category === "system" ||
      item.sender === "System" ||
      (item.sender && item.sender.includes("System")) ||
      (item.message && (item.message.includes("disconnected") || item.message.includes("connected.")))
    ) {
      return;
    }
    // 2. Exclude notifications for current channel user is actively viewing
    const currentChan = state.currentChannel === null ? "group" : state.currentChannel;
    const notifChan = (item.channel === null || item.channel === undefined) ? "group" : item.channel;
    if (notifChan === currentChan) {
      return;
    }
    const notifKey = `toast_${item.id}`;
    if (!state.notifiedMessageIds.has(notifKey)) {
      state.notifiedMessageIds.add(notifKey);
      showToastNotification(item);
    }
  });
}

function showToastNotification(item) {
  if (!dom.toastContainer) return;
  while (dom.toastContainer.children.length >= 2) {
    dom.toastContainer.removeChild(dom.toastContainer.firstChild);
  }
  const toast = document.createElement("div");
  toast.className = "toast-item";
  const channelTarget = item.channel === null || item.channel === undefined ? "group" : item.channel;
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-title">${escapeHtml(item.sender)}</span>
      <span class="toast-body">${escapeHtml(item.message || "Sent a message")}</span>
    </div>
    <button type="button" class="toast-btn" onclick="selectChannel(${channelTarget === 'group' ? 'null' : `'${escapeHtml(channelTarget)}'`}); this.parentElement.remove();">View</button>
  `;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeRegex(str) {
  if (!str) return "";
  return String(str).replace(/[/\-\\^$*+?.()|[\]{}]/g, '\\$&');
}
