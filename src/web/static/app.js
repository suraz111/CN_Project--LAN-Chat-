/**
 * Simple LAN Chat — Mobile Web Single Page Application (SPA)
 * Handles reactive channel switching, real-time message polling,
 * private DMs & file sharing to/from Host and other devices.
 */

// Generate or retrieve persistent client ID for this browser session
function getOrCreateClientId() {
  let id = localStorage.getItem("lanchat_client_id");
  if (!id) {
    id = "mob_" + Math.random().toString(36).substring(2, 9) + Date.now().toString(36).substring(4);
    localStorage.setItem("lanchat_client_id", id);
  }
  return id;
}

// Application State
const state = {
  clientId: getOrCreateClientId(),
  username: localStorage.getItem("lanchat_username") || "",
  currentChannel: null, // null = Group Broadcast Room; or peer_id for Direct DMs
  peers: [],
  renderedMessageIds: new Set(),
  unreadCounts: { null: 0 },
  lastPollTime: 0,
  hostInfo: {},
  theme: localStorage.getItem("lanchat_theme") || "dark",
  soundEnabled: localStorage.getItem("lanchat_sound_enabled") !== "false",
  notifiedMessageIds: new Set(),
  lastTypingSent: 0,
  typingTimer: null,
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
  btnHeaderInfo: document.getElementById("btn-header-info"),
  fileUploader: document.getElementById("file-uploader"),
  p2pModal: document.getElementById("p2p-modal"),
  p2pHubCount: document.getElementById("p2p-hub-count"),
  p2pHubList: document.getElementById("p2p-hub-list"),
  inputManualIp: document.getElementById("input-manual-ip"),
  btnManualConnect: document.getElementById("btn-manual-connect"),
  manualConnectFeedback: document.getElementById("manual-connect-feedback"),
  peerInfoModal: document.getElementById("peer-info-modal"),
  peerInfoName: document.getElementById("peer-info-name"),
  peerInfoContent: document.getElementById("peer-info-content"),
  btnPingPeer: document.getElementById("btn-ping-peer"),
  toastContainer: document.getElementById("toast-container"),
};

// ========================================================
// Initialization
// ========================================================
window.addEventListener("DOMContentLoaded", () => {
  applyTheme(state.theme);
  updateNotifIcon();
  setupEventHandlers();

  // Request browser notification permission on first user gesture
  document.addEventListener("click", () => requestNotificationPermission(), { once: true });

  if (!state.username) {
    dom.loginModal.classList.remove("hidden");
    dom.inputUsername.focus();
  } else {
    dom.loginModal.classList.add("hidden");
    initUserSession();
  }

  // Initial fetch of host status and peers
  fetchStatus();

  // Periodic polling for peers (every 2.5 seconds)
  setInterval(fetchStatus, 2500);

  // Periodic polling for chat messages (every 800ms)
  setInterval(fetchMessages, 800);
});

function setupEventHandlers() {
  // Mobile drawer sidebar toggle
  dom.btnToggleSidebar.addEventListener("click", () => {
    dom.sidebarDrawer.classList.toggle("open");
    dom.drawerBackdrop.classList.toggle("active");
  });

  dom.drawerBackdrop.addEventListener("click", () => {
    dom.sidebarDrawer.classList.remove("open");
    dom.drawerBackdrop.classList.remove("active");
  });

  // Theme switcher
  dom.btnThemeToggle.addEventListener("click", toggleTheme);

  // Notification toggle
  if (dom.btnNotifToggle) {
    dom.btnNotifToggle.addEventListener("click", toggleNotificationSetting);
  }

  // Manual refresh button
  dom.btnRefresh.addEventListener("click", () => {
    fetchStatus();
    fetchMessages();
  });
}

function initUserSession() {
  dom.userDisplayName.textContent = state.username;
  dom.userAvatarText.textContent = (state.username || "M").slice(0, 1).toUpperCase();
  dom.loginModal.classList.add("hidden");
  fetchStatus();
  fetchMessages();
}

function handleLogin() {
  const entered = dom.inputUsername.value.trim();
  if (entered) {
    state.username = entered;
    localStorage.setItem("lanchat_username", entered);
    initUserSession();
  }
}

function changeName() {
  const newName = prompt("Enter new display name:", state.username);
  if (newName && newName.trim()) {
    state.username = newName.trim();
    localStorage.setItem("lanchat_username", state.username);
    initUserSession();
  }
}

// ========================================================
// Theming
// ========================================================
function applyTheme(themeName) {
  state.theme = themeName;
  localStorage.setItem("lanchat_theme", themeName);
  document.body.className = `theme-${themeName}`;
  dom.themeIcon.textContent = themeName === "dark" ? "🌙" : "☀️";
}

function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

// ========================================================
// API Communication
// ========================================================
async function fetchStatus() {
  try {
    const url = `/api/status?client_id=${encodeURIComponent(state.clientId)}&username=${encodeURIComponent(state.username || "Mobile User")}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    state.hostInfo = data;

    dom.hostIpPreview.textContent = `${data.host_ip}:${data.host_port}`;
    dom.userIpText.textContent = `${data.host_ip}:${data.host_port}`;

    // Process unread messages and alert user across channels
    if (data.unreads) {
      for (const [chId, count] of Object.entries(data.unreads)) {
        const normId = chId === "group" ? null : chId;
        state.unreadCounts[normId] = count;
      }
      const groupUnread = state.unreadCounts[null] || 0;
      dom.badgeGroup.textContent = groupUnread;
      dom.badgeGroup.classList.toggle("hidden", groupUnread <= 0 || state.currentChannel === null);
    }

    // Process server-pushed message notifications
    if (Array.isArray(data.notifications) && data.notifications.length > 0) {
      data.notifications.forEach((notif) => {
        const notifId = notif.id || `${notif.timestamp_epoch}_${notif.sender}_${notif.message}`;
        if (!state.notifiedMessageIds.has(notifId)) {
          state.notifiedMessageIds.add(notifId);
          // Only alert if we are not actively viewing this channel or tab is in background
          if (notif.channel !== state.currentChannel || document.hidden) {
            const isDM = Boolean(notif.is_dm);
            const title = isDM ? `🔒 Private from ${notif.sender}` : `💬 Group from ${notif.sender}`;
            sendDeviceNotification(title, notif.message, notif.channel);
          }
        }
      });
    }

    updatePeersList(data.active_peers || []);

    if (dom.p2pModal && !dom.p2pModal.classList.contains("hidden")) {
      renderP2PHubList();
    }
  } catch (err) {
    console.warn("Failed syncing status:", err);
  }
}

function updatePeersList(newPeers) {
  // Exclude our own mobile client from the peer directory
  const filtered = newPeers.filter((p) => p.peer_id !== state.clientId);
  state.peers = filtered;
  const count = filtered.length;
  dom.onlineCount.textContent = `${count} Online`;
  dom.peersCountLabel.textContent = count;

  if (count === 0) {
    dom.peersList.innerHTML = `<div class="empty-peers">Searching for LAN peers...<br><button type="button" class="btn-p2p-pill" onclick="openP2PModal()">⚡ Direct Connect IP:Port</button></div>`;
    return;
  }

  dom.peersList.innerHTML = "";
  filtered.forEach((peer) => {
    const isSelected = state.currentChannel === peer.peer_id;
    const unread = state.unreadCounts[peer.peer_id] || 0;

    const item = document.createElement("div");
    item.className = `peer-item ${isSelected ? "active" : ""}`;
    item.onclick = () => selectChannel(peer.peer_id);

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

async function fetchMessages() {
  const channelParam = state.currentChannel === null ? "group" : state.currentChannel;
  try {
    const url = `/api/messages?channel=${encodeURIComponent(channelParam)}&client_id=${encodeURIComponent(state.clientId)}&username=${encodeURIComponent(state.username || "Mobile User")}&since=${state.lastPollTime}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();

    if (data.server_time) {
      state.lastPollTime = data.server_time;
    }

    if (Array.isArray(data.messages) && data.messages.length > 0) {
      data.messages.forEach((msg) => {
        const msgId = msg.id || `${msg.timestamp_epoch || Date.now()}_${msg.sender}_${msg.message}`;
        if (!state.renderedMessageIds.has(msgId)) {
          state.renderedMessageIds.add(msgId);
          appendMessageRow(msg);

          // Alert for incoming message in currently open channel
          const isFromSelf = Boolean(msg.is_self) || msg.category === "self" || (msg.sender && (msg.sender.includes("(You)") || msg.sender.startsWith(state.username)));
          if (!isFromSelf && msg.category !== "system") {
            if (!state.notifiedMessageIds.has(msgId)) {
              state.notifiedMessageIds.add(msgId);
              if (document.hidden) {
                const isDM = state.currentChannel !== null;
                const title = isDM ? `🔒 Private from ${msg.sender}` : `💬 Group from ${msg.sender}`;
                sendDeviceNotification(title, msg.message, state.currentChannel);
              } else {
                playNotificationSound(state.currentChannel !== null);
              }
            }
          }
        }
      });
    }
  } catch (err) {
    // Quiet retry on network hiccup
  }
}

// ========================================================
// Channel & Chat Management
// ========================================================
function selectChannel(channelId) {
  state.currentChannel = channelId;

  // Close mobile drawer on item select
  dom.sidebarDrawer.classList.remove("open");
  dom.drawerBackdrop.classList.remove("active");

  // Highlight active channel in sidebar
  document.getElementById("channel-group").classList.toggle("active", channelId === null);
  document.querySelectorAll(".peer-item").forEach((el) => {
    el.classList.remove("active");
  });

  // Clear unread badge
  state.unreadCounts[channelId] = 0;
  if (channelId === null) {
    dom.badgeGroup.classList.add("hidden");
  }

  // Update Chat Header
  if (channelId === null) {
    dom.activeChannelTitle.textContent = "💬 Group Broadcast";
    dom.activeChannelSub.textContent = "Broadcast to all network peers";
    dom.btnHeaderInfo.title = "View LAN Network Details";
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

  // Reset poll timestamp to re-fetch full channel history
  state.lastPollTime = 0;
  state.renderedMessageIds.clear();
  dom.chatMessages.innerHTML = "";
  fetchMessages();
}

function appendMessageRow(msg) {
  const row = document.createElement("div");
  const isSelf = Boolean(msg.is_self) || msg.category === "self" || (msg.sender && (msg.sender.includes("(You)") || msg.sender.startsWith(state.username)));
  const role = msg.category === "system" ? "system" : (isSelf ? "self" : "peer");

  row.className = `message-row ${role}`;

  // Check for download links
  let formattedText = escapeHtml(msg.message || "");
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  if (formattedText.match(urlRegex)) {
    formattedText = formattedText.replace(urlRegex, (url) => {
      const filename = decodeURIComponent(url.split("/").pop());
      return `<div class="file-card"><span class="file-icon">📎</span> <a href="${url}" target="_blank" download class="file-link">Download ${filename}</a></div>`;
    });
  }

  if (role === "system") {
    row.innerHTML = `
      <div class="message-bubble system-bubble">
        ℹ️ ${formattedText}
      </div>
    `;
  } else {
    row.innerHTML = `
      <span class="sender-tag">${escapeHtml(msg.sender || "Peer")}</span>
      <div class="message-bubble">
        ${formattedText}
        <div class="bubble-meta">
          <span>${escapeHtml(msg.timestamp || "")}</span>
        </div>
      </div>
    `;
  }

  dom.chatMessages.appendChild(row);
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
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
// Message Transmission
// ========================================================
async function sendMessage() {
  const text = dom.messageInput.value.trim();
  if (!text) return;

  dom.messageInput.value = "";
  dom.messageInput.focus();

  // Handle client-side slash commands
  if (text.startsWith("/")) {
    handleSlashCommand(text);
    return;
  }

  const payload = {
    sender: state.username || "Mobile User",
    client_id: state.clientId,
    channel: state.currentChannel,
    text: text,
  };

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      // Immediate fetch renders the message cleanly
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
        sender: state.username || "Mobile User",
        client_id: state.clientId,
        channel: state.currentChannel,
      }),
    }).catch(() => {});
  }
}

function insertEmoji(char) {
  dom.messageInput.value += char;
  dom.messageInput.focus();
}

// ========================================================
// File & Photo Uploading
// ========================================================
async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  event.target.value = "";

  const formData = new FormData();
  formData.append("file", file);
  formData.append("sender", state.username || "Mobile User");
  formData.append("client_id", state.clientId);
  if (state.currentChannel) {
    formData.append("channel", state.currentChannel);
  }

  appendMessageRow({
    sender: "System",
    message: `Uploading '${file.name}' (${(file.size / 1024).toFixed(1)} KB)...`,
    category: "system",
  });

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    const result = await res.json();
    if (result.success) {
      await fetchMessages();
    } else {
      appendMessageRow({
        sender: "System",
        message: `Upload failed: ${result.error}`,
        category: "system",
      });
    }
  } catch (err) {
    appendMessageRow({
      sender: "System",
      message: `Upload failed: ${err.message}`,
      category: "system",
    });
  }
}

// ========================================================
// Slash Commands
// ========================================================
function handleSlashCommand(cmdLine) {
  const parts = cmdLine.split(" ");
  const cmd = parts[0].toLowerCase();

  if (cmd === "/help") {
    const helpMsg = `💡 Available Commands:\n• /nick <name> — Change your name\n• /clear — Clear chat screen\n• /shrug — Send ¯\\_(ツ)_/¯\n• /help — Show this help`;
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
// Utilities
// ========================================================
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ========================================================
// Direct Peer-to-Peer (P2P) Hub & Controls
// ========================================================
function triggerFileUpload() {
  if (dom.fileUploader) {
    dom.fileUploader.click();
  }
}

function startPeerFileUpload(peerId) {
  selectChannel(peerId);
  setTimeout(() => {
    if (dom.fileUploader) {
      dom.fileUploader.click();
    }
  }, 120);
}

function openP2PModal() {
  if (!dom.p2pModal) return;
  dom.p2pModal.classList.remove("hidden");
  renderP2PHubList();
  if (dom.inputManualIp && !dom.inputManualIp.value && state.hostInfo.host_ip) {
    dom.inputManualIp.value = `${state.hostInfo.host_ip}:${state.hostInfo.host_port || 9999}`;
  }
}

function closeP2PModal() {
  if (dom.p2pModal) {
    dom.p2pModal.classList.add("hidden");
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
        <small>Enter a device IP:Port below to establish a direct connection instantly.</small>
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
        <div class="p2p-info">
          <div class="p2p-name-row">
            <span class="p2p-name">${escapeHtml(peer.username)}</span>
            <span class="p2p-role-pill">${badgeText}</span>
          </div>
          <span class="p2p-ip">${escapeHtml(ipStr)}</span>
        </div>
      </div>
      <div class="p2p-card-actions">
        <button type="button" class="btn-action-primary-sm" onclick="closeP2PModal(); selectChannel('${peer.peer_id}')">
          💬 Chat
        </button>
        <button type="button" class="btn-action-secondary-sm" onclick="closeP2PModal(); startPeerFileUpload('${peer.peer_id}')">
          📎 File
        </button>
        <button type="button" class="btn-action-ghost-sm" onclick="showPeerInfo('${peer.peer_id}')">
          ℹ️ Info
        </button>
      </div>
    `;
    dom.p2pHubList.appendChild(card);
  });
}

async function handleManualP2PConnect() {
  const target = dom.inputManualIp.value.trim();
  if (!target) return;

  dom.btnManualConnect.disabled = true;
  dom.btnManualConnect.textContent = "Connecting...";
  dom.manualConnectFeedback.classList.remove("hidden", "error", "success");
  dom.manualConnectFeedback.textContent = `Establishing direct TCP handshake with ${target}...`;

  try {
    const res = await fetch("/api/connect_peer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: target }),
    });
    const data = await res.json();
    if (data.success) {
      dom.manualConnectFeedback.className = "feedback-text success";
      dom.manualConnectFeedback.textContent = `✅ Handshake sent to ${target}! Direct P2P active.`;
      setTimeout(() => {
        fetchStatus();
        closeP2PModal();
      }, 1200);
    } else {
      dom.manualConnectFeedback.className = "feedback-text error";
      dom.manualConnectFeedback.textContent = `❌ ${data.error || "Failed to reach target IP:Port"}`;
    }
  } catch (err) {
    dom.manualConnectFeedback.className = "feedback-text error";
    dom.manualConnectFeedback.textContent = `❌ Connection error: ${err.message}`;
  } finally {
    dom.btnManualConnect.disabled = false;
    dom.btnManualConnect.textContent = "⚡ Connect Directly";
  }
}

// ========================================================
// Peer Details & Latency Ping
// ========================================================
let activeInspectedPeerId = null;

function showPeerInfo(peerId) {
  activeInspectedPeerId = peerId;
  const peer = state.peers.find((p) => p.peer_id === peerId);
  if (!peer) return;

  dom.peerInfoName.textContent = `ℹ️ ${peer.username}`;
  const ptype = peer.is_host ? "Host Desktop" : (peer.is_web ? "Mobile Browser" : "LAN Desktop Peer");
  const protocol = peer.is_web ? "HTTP Gateway WebSocket / Polling" : "Raw TCP Socket (Framed JSON)";

  dom.peerInfoContent.innerHTML = `
    <div class="info-row">
      <span class="info-label">Peer Name:</span>
      <span class="info-value font-bold">${escapeHtml(peer.username)}</span>
    </div>
    <div class="info-row">
      <span class="info-label">IP Address:</span>
      <span class="info-value monospace">${escapeHtml(peer.ip_address)}</span>
    </div>
    <div class="info-row">
      <span class="info-label">TCP Port:</span>
      <span class="info-value monospace">${peer.tcp_port ? peer.tcp_port : "Web Client"}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Device Type:</span>
      <span class="info-value">${ptype}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Protocol:</span>
      <span class="info-value">${protocol}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Peer ID:</span>
      <span class="info-value monospace">${escapeHtml(peer.peer_id)}</span>
    </div>
    <div id="ping-status-row" class="info-row highlight-row">
      <span class="info-label">P2P Health:</span>
      <span id="ping-result" class="info-value">Ready to ping</span>
    </div>
  `;

  dom.peerInfoModal.classList.remove("hidden");
}

function showActivePeerInfo() {
  if (state.currentChannel) {
    showPeerInfo(state.currentChannel);
  } else {
    // Show Network Hub info
    activeInspectedPeerId = null;
    dom.peerInfoName.textContent = "ℹ️ LAN Network Status";
    dom.peerInfoContent.innerHTML = `
      <div class="info-row">
        <span class="info-label">Host Machine IP:</span>
        <span class="info-value monospace">${escapeHtml(state.hostInfo.host_ip || "127.0.0.1")}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Host TCP Port:</span>
        <span class="info-value monospace">${state.hostInfo.host_port || 9999}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Host User:</span>
        <span class="info-value font-bold">${escapeHtml(state.hostInfo.host_user || "Host")}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Your Client ID:</span>
        <span class="info-value monospace">${escapeHtml(state.clientId)}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Active Peers:</span>
        <span class="info-value font-bold">${state.peers.length} online</span>
      </div>
      <div id="ping-status-row" class="info-row highlight-row">
        <span class="info-label">Gateway Latency:</span>
        <span id="ping-result" class="info-value">Ready to test</span>
      </div>
    `;
    dom.peerInfoModal.classList.remove("hidden");
  }
}

function closePeerInfoModal() {
  if (dom.peerInfoModal) {
    dom.peerInfoModal.classList.add("hidden");
  }
}

async function pingActivePeer() {
  const resultEl = document.getElementById("ping-result");
  if (!resultEl) return;
  resultEl.textContent = "Pinging...";

  const targetParam = activeInspectedPeerId ? `peer_id=${encodeURIComponent(activeInspectedPeerId)}` : "";
  try {
    const res = await fetch(`/api/ping?${targetParam}`);
    const data = await res.json();
    if (data.success) {
      resultEl.textContent = `🟢 Active (${data.rtt_ms} ms RTT)`;
      resultEl.style.color = "var(--accent-green)";
    } else {
      resultEl.textContent = `🔴 Offline (${data.error || "unreachable"})`;
      resultEl.style.color = "var(--accent-red)";
    }
  } catch (err) {
    resultEl.textContent = `⚠️ Error: ${err.message}`;
    resultEl.style.color = "var(--accent-yellow)";
  }
}

// ========================================================
// Device Notifications: Sound, Vibration, Push & Toast
// ========================================================
function toggleNotificationSetting() {
  state.soundEnabled = !state.soundEnabled;
  localStorage.setItem("lanchat_sound_enabled", state.soundEnabled ? "true" : "false");
  updateNotifIcon();

  if (state.soundEnabled) {
    playNotificationSound(false);
    requestNotificationPermission();
    showToastNotification("🔔 Notifications Enabled", "Audio chimes and device alerts are active.", null);
  } else {
    showToastNotification("🔕 Notifications Muted", "Audio chimes and device alerts are paused.", null);
  }
}

function updateNotifIcon() {
  if (dom.notifIcon) {
    dom.notifIcon.textContent = state.soundEnabled ? "🔔" : "🔕";
    if (dom.btnNotifToggle) {
      dom.btnNotifToggle.title = state.soundEnabled ? "Notifications Active (Click to Mute)" : "Notifications Muted (Click to Enable)";
    }
  }
}

function requestNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
}

function playNotificationSound(isPrivate = false) {
  if (!state.soundEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    const now = ctx.currentTime;

    if (isPrivate) {
      // Pleasant double chime for private DMs: 587Hz (D5) -> 880Hz (A5)
      osc.frequency.setValueAtTime(587.33, now);
      osc.frequency.setValueAtTime(880.00, now + 0.12);
      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
      osc.start(now);
      osc.stop(now + 0.45);
    } else {
      // Warm bell chime for group broadcast: 523Hz (C5) -> 659Hz (E5)
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.setValueAtTime(659.25, now + 0.1);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    }
  } catch (e) {
    const audio = document.getElementById("audio-alert");
    if (audio) {
      audio.play().catch(() => {});
    }
  }
}

function sendDeviceNotification(title, body, channelId) {
  // 1. Play synthesized chime sound
  playNotificationSound(channelId !== null && channelId !== "group");

  // 2. Vibrate mobile device (if supported)
  if ("vibrate" in navigator) {
    try {
      navigator.vibrate([150, 75, 150]);
    } catch (_) {}
  }

  // 3. Native system push notification
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      const cleanBody = body ? (body.length > 75 ? body.substring(0, 75) + "..." : body) : "New message received";
      const notif = new Notification(title, {
        body: cleanBody,
        icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📡</text></svg>",
        tag: `lanchat_${channelId || "group"}`,
      });
      notif.onclick = () => {
        window.focus();
        selectChannel(channelId);
        notif.close();
      };
    } catch (e) {
      console.warn("Push notification error:", e);
    }
  }

  // 4. In-App Floating Toast
  showToastNotification(title, body, channelId);

  // 5. Document title flashing
  flashDocumentTitle(title);
}

let titleFlashTimer = null;
const originalDocTitle = document.title || "Simple LAN Chat — Mobile";

function flashDocumentTitle(alertText) {
  if (!document.hidden) return;
  if (titleFlashTimer) clearInterval(titleFlashTimer);

  let toggle = false;
  titleFlashTimer = setInterval(() => {
    if (!document.hidden) {
      clearInterval(titleFlashTimer);
      titleFlashTimer = null;
      document.title = originalDocTitle;
      return;
    }
    document.title = toggle ? `🔔 ${alertText}` : originalDocTitle;
    toggle = !toggle;
  }, 1000);
}

window.addEventListener("focus", () => {
  if (titleFlashTimer) {
    clearInterval(titleFlashTimer);
    titleFlashTimer = null;
  }
  document.title = originalDocTitle;
});

function showToastNotification(title, body, channelId) {
  if (!dom.toastContainer) return;

  const toast = document.createElement("div");
  toast.className = "toast-item";
  const displayBody = body ? (body.length > 55 ? body.substring(0, 55) + "..." : body) : "";

  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-title">${escapeHtml(title)}</span>
      <span class="toast-body">${escapeHtml(displayBody)}</span>
    </div>
    <button type="button" class="toast-btn">Open Chat</button>
  `;

  toast.querySelector(".toast-btn").onclick = () => {
    if (channelId !== undefined && channelId !== null) {
      selectChannel(channelId);
    } else if (channelId === null) {
      selectChannel(null);
    }
    toast.remove();
  };

  dom.toastContainer.appendChild(toast);

  // Auto dismiss after 6 seconds
  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 400);
  }, 6000);
}
