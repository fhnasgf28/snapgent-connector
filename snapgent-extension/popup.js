// SPDX-License-Identifier: GPL-3.0-or-later
const SUPPORTED_HOSTS = [
  "chat.deepseek.com", "deepseek.com", "chatgpt.com", "chat.openai.com", "claude.ai",
  "gemini.google.com", "www.kimi.ai", "kimi.ai",
  "chat.z.ai", "chat.qwen.ai", "arena.ai", "www.meta.ai", "meta.ai", "ptero.pro", "grok.com",
];
const DEFAULT_AI_URL = "https://chatgpt.com/";

function render(s) {
  const state = document.getElementById("state");
  const tools = document.getElementById("tools");
  const servers = document.getElementById("servers");
  const list = s.servers || [];
  const up = list.filter((x) => x.alive).length;
  const mcpOk = s.connected && (s.mcpAlive || up > 0 || s.tools > 0);
  const dot = document.getElementById("dot");

  dot.className = "dot " + (!s.connected ? "bad" : mcpOk ? "ok" : "warn");
  state.textContent = s.connected
    ? (mcpOk ? "Bridge Connected" : "MCP Standby")
    : "Bridge Offline";
  tools.textContent = s.connected ? `${s.tools || 0} tools active` : "Offline";
  servers.textContent = s.connected
    ? list.map((x) => `${x.alive ? "●" : "○"} ${x.id} (${x.alive ? x.tools + " tools" : "down"})`).join("\n")
    : "";
}

function refresh() {
  chrome.runtime.sendMessage({ type: "status" }, (s) => s && render(s));
}

function openOrFocusHost(hostUrl) {
  const hostDomain = new URL(hostUrl).hostname;
  chrome.tabs.query({}, (tabs) => {
    const existing = tabs.find((t) => t.url && t.url.includes(hostDomain));
    if (existing) {
      chrome.tabs.update(existing.id, { active: true });
      if (existing.windowId) {
        chrome.windows.update(existing.windowId, { focused: true });
      }
    } else {
      chrome.tabs.create({ url: hostUrl });
    }
  });
}

document.getElementById("reconnect").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "reconnect" }, () => setTimeout(refresh, 600));
});

document.getElementById("restart").addEventListener("click", (e) => {
  const orig = e.target.textContent;
  e.target.textContent = "Restarting…";
  chrome.runtime.sendMessage({ type: "restart_mcp" }, () => {
    e.target.textContent = orig;
    setTimeout(refresh, 600);
  });
});

document.getElementById("settings").addEventListener("click", () => {
  chrome.tabs.query({}, (tabs) => {
    const active = tabs.find((t) => t.active && t.url && SUPPORTED_HOSTS.some((h) => t.url.includes(h)));
    const anySupported = active || tabs.find((t) => t.url && SUPPORTED_HOSTS.some((h) => t.url.includes(h)));
    if (anySupported) {
      chrome.tabs.sendMessage(anySupported.id, { type: "zs-open-menu" });
      chrome.tabs.update(anySupported.id, { active: true });
    } else {
      chrome.tabs.create({ url: DEFAULT_AI_URL });
    }
  });
});

// Quick AI jump listeners
const aiLinks = [
  { id: "ai-deepseek", url: "https://chat.deepseek.com/" },
  { id: "ai-claude",   url: "https://claude.ai/" },
  { id: "ai-chatgpt",  url: "https://chatgpt.com/" },
  { id: "ai-gemini",   url: "https://gemini.google.com/" }
];

aiLinks.forEach(({ id, url }) => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      openOrFocusHost(url);
    });
  }
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "zs-status") render(msg);
});

refresh();
setInterval(refresh, 2000);