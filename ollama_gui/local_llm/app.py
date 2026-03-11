from flask import Flask, request, Response, jsonify
import requests
import json
import os
import uuid
from datetime import datetime

app = Flask(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
SESSIONS_FILE = "./sessions.json"


# ── Session persistence ──

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        print(f"⚠ Could not save sessions: {e}")

sessions = load_sessions()


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ollama Chat</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0d0f12; --surface: #13161b; --surface2: #181c23;
      --border: #1f242c; --border2: #2a3040;
      --text: #c8d0dc; --muted: #4a5568; --accent: #4ade80; --accent2: #22d3ee;
      --user-bg: #161c28; --ai-bg: #111418; --error: #f87171;
      --glow: rgba(74,222,128,0.15); --code-bg: #1a1d23;
      --sidebar-w: 240px;
    }
    html, body { height: 100%; }
    body {
      font-family: 'IBM Plex Mono', monospace;
      background: var(--bg); color: var(--text);
      display: flex; height: 100vh; overflow: hidden;
    }
    body::before {
      content: ''; position: fixed; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);
      pointer-events: none; z-index: 9999;
    }

    /* ── Sidebar ── */
    #sidebar {
      width: var(--sidebar-w); flex-shrink: 0;
      background: var(--surface); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden;
    }
    .sidebar-header { padding: 16px 16px 12px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
    .logo { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .logo-icon {
      width: 24px; height: 24px; border: 1.5px solid var(--accent); border-radius: 4px;
      display: flex; align-items: center; justify-content: center; box-shadow: 0 0 8px var(--glow);
    }
    .logo-icon svg { width: 13px; height: 13px; fill: var(--accent); }
    .logo-text { font-size: 12px; font-weight: 600; letter-spacing: 0.15em; color: var(--accent); text-transform: uppercase; }
    #new-session-btn {
      width: 100%; background: rgba(74,222,128,0.08); border: 1px solid rgba(74,222,128,0.25);
      color: var(--accent); font-family: 'IBM Plex Mono', monospace; font-size: 10px;
      font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
      padding: 7px 10px; border-radius: 4px; cursor: pointer;
      transition: background 0.2s, border-color 0.2s; display: flex; align-items: center; gap: 6px;
    }
    #new-session-btn:hover { background: rgba(74,222,128,0.15); border-color: rgba(74,222,128,0.5); }
    #new-session-btn::before { content: '+'; font-size: 14px; line-height: 1; }

    #session-list { flex: 1; overflow-y: auto; padding: 8px; }
    #session-list::-webkit-scrollbar { width: 3px; }
    #session-list::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

    .session-item {
      padding: 8px 10px; border-radius: 4px; cursor: pointer;
      border: 1px solid transparent; margin-bottom: 2px;
      transition: background 0.15s, border-color 0.15s;
      display: flex; align-items: center; gap: 8px;
      animation: fadeIn 0.2s ease;
    }
    .session-item:hover { background: var(--surface2); border-color: var(--border); }
    .session-item.active { background: rgba(74,222,128,0.07); border-color: rgba(74,222,128,0.25); }
    .session-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--muted); }
    .session-item.active .session-dot { background: var(--accent); box-shadow: 0 0 5px var(--accent); }
    .session-info { flex: 1; min-width: 0; }
    .session-name { font-size: 11px; font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: 0.03em; }
    .session-item.active .session-name { color: var(--accent); }
    .session-meta { font-size: 9px; color: var(--muted); letter-spacing: 0.05em; margin-top: 2px; }
    .session-del {
      background: none; border: none; color: var(--muted); cursor: pointer;
      font-size: 12px; padding: 2px 4px; border-radius: 3px;
      opacity: 0; transition: opacity 0.15s, color 0.15s; flex-shrink: 0;
    }
    .session-item:hover .session-del { opacity: 1; }
    .session-del:hover { color: var(--error); }

    .sidebar-footer { padding: 10px 16px; border-top: 1px solid var(--border); flex-shrink: 0; }
    .model-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .model-label { font-size: 9px; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; }
    .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); transition: background 0.3s; flex-shrink: 0; }
    .status-dot.online { background: var(--accent); box-shadow: 0 0 5px var(--accent); animation: pulse 2s infinite; }
    .status-dot.error  { background: var(--error); }
    @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
    #model-select {
      width: 100%; background: var(--bg); border: 1px solid var(--border2); color: var(--text);
      font-family: 'IBM Plex Mono', monospace; font-size: 11px; padding: 5px 8px;
      border-radius: 4px; cursor: pointer; outline: none; margin-top: 6px; transition: border-color 0.2s;
    }
    #model-select:focus { border-color: var(--accent); }
    #model-select option { background: var(--surface); }

    /* ── Main area ── */
    #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

    /* Top bar */
    #topbar {
      display: flex; align-items: center; gap: 10px;
      padding: 12px 20px; border-bottom: 1px solid var(--border);
      background: var(--surface); flex-shrink: 0; min-height: 54px;
    }
    #session-title {
      font-size: 13px; font-weight: 600; color: var(--text);
      letter-spacing: 0.05em; flex: 1; min-width: 0;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    #session-title.placeholder { color: var(--muted); font-weight: 400; }
    .topbar-btn {
      background: none; border: 1px solid var(--border2); color: var(--muted);
      font-family: 'IBM Plex Mono', monospace; font-size: 9px; padding: 4px 10px;
      border-radius: 3px; cursor: pointer; letter-spacing: 0.08em; text-transform: uppercase;
      transition: color 0.2s, border-color 0.2s; flex-shrink: 0;
    }
    .topbar-btn:hover { color: var(--text); border-color: var(--border2); }
    .topbar-btn.active { color: var(--accent2); border-color: var(--accent2); background: rgba(34,211,238,0.05); }

    /* System prompt bar */
    #sysprompt-bar {
      display: none; background: #0d1117; border-bottom: 1px solid var(--border);
      padding: 10px 20px; flex-shrink: 0;
    }
    #sysprompt-bar.open { display: flex; gap: 10px; align-items: flex-start; }
    .sysprompt-label { font-size: 9px; color: var(--accent2); letter-spacing: 0.12em; text-transform: uppercase; padding-top: 8px; flex-shrink: 0; }
    #sysprompt-input {
      flex: 1; background: var(--bg); border: 1px solid var(--border2); color: var(--text);
      font-family: 'IBM Plex Sans', sans-serif; font-size: 12px; padding: 6px 10px;
      border-radius: 4px; outline: none; resize: none; min-height: 36px; max-height: 100px;
      line-height: 1.5; transition: border-color 0.2s;
    }
    #sysprompt-input:focus { border-color: var(--accent2); }
    #sysprompt-input::placeholder { color: var(--muted); }
    #sysprompt-save {
      background: none; border: 1px solid var(--border2); color: var(--muted);
      font-family: 'IBM Plex Mono', monospace; font-size: 9px; padding: 4px 10px;
      border-radius: 3px; cursor: pointer; letter-spacing: 0.08em; text-transform: uppercase;
      transition: color 0.2s, border-color 0.2s; flex-shrink: 0; margin-top: 3px;
    }
    #sysprompt-save:hover { color: var(--accent2); border-color: var(--accent2); }
    #sysprompt-save.saved { color: var(--accent); border-color: var(--accent); }

    /* Messages */
    #messages { flex: 1; overflow-y: auto; padding: 20px 0; scroll-behavior: smooth; }
    #messages::-webkit-scrollbar { width: 4px; }
    #messages::-webkit-scrollbar-track { background: transparent; }
    #messages::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
    .message { display: flex; gap: 14px; padding: 14px 20px; animation: fadeIn 0.2s ease; border-bottom: 1px solid var(--border); }
    @keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
    .message.user      { background: var(--user-bg); }
    .message.assistant { background: var(--ai-bg); }
    .msg-avatar { width: 26px; height: 26px; border-radius: 4px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; margin-top: 2px; }
    .message.user .msg-avatar      { background: rgba(34,211,238,0.12); border: 1px solid rgba(34,211,238,0.3); color: var(--accent2); }
    .message.assistant .msg-avatar { background: rgba(74,222,128,0.08); border: 1px solid rgba(74,222,128,0.25); color: var(--accent); }
    .msg-body { flex: 1; min-width: 0; }
    .msg-header { font-size: 9px; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }
    .msg-header span { color: var(--text); }
    .msg-image { max-width: 300px; max-height: 220px; border-radius: 6px; border: 1px solid var(--border2); margin-bottom: 8px; display: block; object-fit: contain; }
    .msg-content { font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; line-height: 1.75; color: var(--text); word-break: break-word; }
    .msg-content p { margin-bottom: 0.75em; }
    .msg-content p:last-child { margin-bottom: 0; }
    .msg-content h1,.msg-content h2,.msg-content h3,.msg-content h4 { font-family: 'IBM Plex Mono', monospace; color: var(--accent); margin: 1em 0 0.4em; font-weight: 600; letter-spacing: 0.05em; }
    .msg-content h1{font-size:1.3em}.msg-content h2{font-size:1.15em}.msg-content h3{font-size:1em}
    .msg-content ul,.msg-content ol { padding-left: 1.4em; margin-bottom: 0.75em; }
    .msg-content li { margin-bottom: 0.25em; }
    .msg-content strong { color: #e2e8f0; font-weight: 600; }
    .msg-content em { color: var(--accent2); font-style: italic; }
    .msg-content a  { color: var(--accent2); text-decoration: underline; }
    .msg-content blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--muted); margin: 0.5em 0; font-style: italic; }
    .msg-content table { width: 100%; border-collapse: collapse; margin-bottom: 0.75em; font-size: 13px; }
    .msg-content th { background: var(--surface); color: var(--accent); font-family: 'IBM Plex Mono', monospace; padding: 6px 10px; border: 1px solid var(--border2); text-align: left; }
    .msg-content td { padding: 6px 10px; border: 1px solid var(--border2); }
    .msg-content tr:nth-child(even) { background: rgba(255,255,255,0.02); }
    .msg-content code:not(pre code) { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; background: var(--code-bg); color: var(--accent2); padding: 2px 6px; border-radius: 3px; border: 1px solid var(--border2); }
    .code-block-wrap { position: relative; margin: 0.75em 0; border-radius: 6px; border: 1px solid var(--border2); overflow: hidden; }
    .code-block-header { display: flex; justify-content: space-between; align-items: center; background: #0a0c0f; padding: 6px 12px; border-bottom: 1px solid var(--border2); }
    .code-lang { font-size: 10px; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; }
    .copy-btn { background: none; border: 1px solid var(--border2); color: var(--muted); font-family: 'IBM Plex Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 3px; cursor: pointer; transition: color 0.2s, border-color 0.2s; letter-spacing: 0.05em; text-transform: uppercase; }
    .copy-btn:hover { color: var(--accent); border-color: var(--accent); }
    .copy-btn.copied { color: var(--accent); border-color: var(--accent); }
    .msg-content pre { margin: 0; }
    .msg-content pre code.hljs { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; background: var(--code-bg) !important; padding: 14px 16px !important; border-radius: 0; display: block; overflow-x: auto; line-height: 1.6; }
    .cursor { display: inline-block; width: 8px; height: 15px; background: var(--accent); vertical-align: text-bottom; margin-left: 2px; animation: blink 1s step-end infinite; }
    @keyframes blink { 0%,100%{opacity:1}50%{opacity:0} }

    /* Empty states */
    #empty-state, #no-session-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 12px; color: var(--muted); }
    .empty-icon { width: 44px; height: 44px; border: 1px solid var(--border2); border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 4px; }
    .empty-icon svg { width: 22px; height: 22px; stroke: var(--muted); fill: none; }
    .empty-title { font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; }
    .empty-sub { font-size: 10px; letter-spacing: 0.05em; }

    /* Input area */
    .input-area { border-top: 1px solid var(--border); background: var(--surface); padding: 12px 20px; flex-shrink: 0; }
    #image-preview-strip { display: none; align-items: center; gap: 8px; margin-bottom: 8px; padding: 7px 10px; background: var(--bg); border: 1px solid var(--border2); border-radius: 6px; }
    #image-preview-strip.visible { display: flex; }
    #preview-thumb { width: 44px; height: 44px; border-radius: 4px; object-fit: cover; border: 1px solid var(--border2); flex-shrink: 0; }
    .preview-info { flex: 1; min-width: 0; }
    .preview-name { font-size: 11px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .preview-size { font-size: 10px; color: var(--muted); }
    #remove-image { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 15px; padding: 2px 4px; transition: color 0.2s; }
    #remove-image:hover { color: var(--error); }
    .input-wrapper { display: flex; gap: 10px; align-items: flex-end; background: var(--bg); border: 1px solid var(--border2); border-radius: 6px; padding: 9px 12px; transition: border-color 0.2s, box-shadow 0.2s; }
    .input-wrapper:focus-within { border-color: var(--accent); box-shadow: 0 0 0 2px var(--glow); }
    .prompt-prefix { color: var(--accent); font-size: 14px; font-weight: 500; flex-shrink: 0; padding-bottom: 1px; user-select: none; }
    #attach-btn { background: none; border: 1px solid var(--border2); color: var(--muted); border-radius: 4px; cursor: pointer; padding: 4px 7px; flex-shrink: 0; transition: color 0.2s, border-color 0.2s; display: flex; align-items: center; }
    #attach-btn:hover { color: var(--accent2); border-color: var(--accent2); }
    #attach-btn svg { width: 14px; height: 14px; stroke: currentColor; fill: none; }
    #file-input { display: none; }
    #user-input { flex: 1; background: transparent; border: none; outline: none; color: var(--text); font-family: 'IBM Plex Mono', monospace; font-size: 13px; line-height: 1.6; resize: none; max-height: 160px; min-height: 22px; }
    #user-input::placeholder { color: var(--muted); }
    #send-btn { background: var(--accent); border: none; color: #0d0f12; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; padding: 6px 14px; border-radius: 4px; cursor: pointer; flex-shrink: 0; transition: opacity 0.2s, transform 0.1s; text-transform: uppercase; }
    #send-btn:hover:not(:disabled) { opacity: 0.85; }
    #send-btn:active:not(:disabled) { transform: scale(0.97); }
    #send-btn:disabled { opacity: 0.35; cursor: not-allowed; }
    .input-footer { display: flex; justify-content: space-between; margin-top: 8px; font-size: 10px; color: var(--muted); letter-spacing: 0.05em; }
    body.drag-over .input-wrapper { border-color: var(--accent2); box-shadow: 0 0 0 2px rgba(34,211,238,0.15); }

    /* Modal */
    #modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000; align-items: center; justify-content: center; }
    #modal-overlay.open { display: flex; }
    #modal { background: var(--surface); border: 1px solid var(--border2); border-radius: 8px; padding: 24px; width: 420px; max-width: 90vw; animation: fadeIn 0.15s ease; }
    .modal-title { font-size: 12px; font-weight: 600; color: var(--accent); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 18px; }
    .modal-field { margin-bottom: 14px; }
    .modal-label { font-size: 10px; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }
    .modal-input, .modal-textarea { width: 100%; background: var(--bg); border: 1px solid var(--border2); color: var(--text); font-family: 'IBM Plex Mono', monospace; font-size: 12px; padding: 8px 10px; border-radius: 4px; outline: none; transition: border-color 0.2s; }
    .modal-input:focus, .modal-textarea:focus { border-color: var(--accent); }
    .modal-textarea { resize: vertical; min-height: 80px; font-family: 'IBM Plex Sans', sans-serif; line-height: 1.5; }
    .modal-textarea::placeholder, .modal-input::placeholder { color: var(--muted); }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
    .modal-btn { background: none; border: 1px solid var(--border2); color: var(--muted); font-family: 'IBM Plex Mono', monospace; font-size: 10px; padding: 6px 16px; border-radius: 4px; cursor: pointer; letter-spacing: 0.08em; text-transform: uppercase; transition: color 0.2s, border-color 0.2s; }
    .modal-btn:hover { color: var(--text); border-color: var(--text); }
    .modal-btn.primary { background: rgba(74,222,128,0.1); border-color: rgba(74,222,128,0.4); color: var(--accent); }
    .modal-btn.primary:hover { background: rgba(74,222,128,0.2); }

    #toast { position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%) translateY(20px); background: var(--surface); border: 1px solid var(--border2); color: var(--error); font-size: 12px; padding: 10px 18px; border-radius: 4px; opacity: 0; transition: opacity 0.2s, transform 0.2s; pointer-events: none; white-space: nowrap; letter-spacing: 0.05em; z-index: 2000; }
    #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    #toast.success { color: var(--accent); border-color: rgba(74,222,128,0.3); }
  </style>
</head>
<body>

<!-- Sidebar -->
<div id="sidebar">
  <div class="sidebar-header">
    <div class="logo">
      <div class="logo-icon">
        <svg viewBox="0 0 16 16"><path d="M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z"/></svg>
      </div>
      <div class="logo-text">Ollama Chat</div>
    </div>
    <button id="new-session-btn">New Session</button>
  </div>
  <div id="session-list">
    <div id="no-sessions-hint" style="padding:16px 8px;font-size:10px;color:var(--muted);letter-spacing:0.05em;">
      No sessions yet. Create one to start.
    </div>
  </div>
  <div class="sidebar-footer">
    <div class="model-bar">
      <div class="status-dot" id="status-dot"></div>
      <span class="model-label">model</span>
    </div>
    <select id="model-select"><option value="">Loading...</option></select>
  </div>
</div>

<!-- Main -->
<div id="main">
  <div id="topbar">
    <div id="session-title" class="placeholder">Select or create a session</div>
    <button class="topbar-btn" id="sysprompt-toggle-btn" style="display:none">System Prompt</button>
    <button class="topbar-btn" id="clear-btn" style="display:none">Clear Chat</button>
  </div>

  <div id="sysprompt-bar">
    <span class="sysprompt-label">sys//</span>
    <textarea id="sysprompt-input" rows="1" placeholder="Enter a system prompt for this session..."></textarea>
    <button id="sysprompt-save">Save</button>
  </div>

  <div id="messages">
    <div id="no-session-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"/></svg>
      </div>
      <div class="empty-title">No session selected</div>
      <div class="empty-sub">Create a new session from the sidebar</div>
    </div>
  </div>

  <div class="input-area" id="input-area" style="display:none">
    <div id="image-preview-strip">
      <img id="preview-thumb" src="" alt="preview">
      <div class="preview-info">
        <div class="preview-name" id="preview-name"></div>
        <div class="preview-size" id="preview-size"></div>
      </div>
      <button id="remove-image">✕</button>
    </div>
    <div class="input-wrapper">
      <span class="prompt-prefix">&gt;_</span>
      <textarea id="user-input" rows="1" placeholder="Type a message..."></textarea>
      <button id="attach-btn" title="Attach image">
        <svg viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"/></svg>
      </button>
      <input type="file" id="file-input" accept="image/*">
      <button id="send-btn">Send</button>
    </div>
    <div class="input-footer">
      <span id="model-info">No model selected</span>
    </div>
  </div>
</div>

<!-- New Session Modal -->
<div id="modal-overlay">
  <div id="modal">
    <div class="modal-title">◆ New Session</div>
    <div class="modal-field">
      <div class="modal-label">Session Name</div>
      <input class="modal-input" id="modal-name" type="text" placeholder="e.g. Python Help, Creative Writing...">
    </div>
    <div class="modal-field">
      <div class="modal-label">System Prompt <span style="color:var(--muted);font-size:9px">(optional)</span></div>
      <textarea class="modal-textarea" id="modal-sysprompt" placeholder="You are a helpful assistant specialized in..."></textarea>
    </div>
    <div class="modal-actions">
      <button class="modal-btn" id="modal-cancel">Cancel</button>
      <button class="modal-btn primary" id="modal-create">Create</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
  // ── Marked config ──
  marked.setOptions({
    highlight: (code, lang) => {
      if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
      return hljs.highlightAuto(code).value;
    },
    breaks: true, gfm: true
  });
  const renderer = new marked.Renderer();
  renderer.code = (code, lang) => {
    const highlighted = lang && hljs.getLanguage(lang)
      ? hljs.highlight(code, { language: lang }).value
      : hljs.highlightAuto(code).value;
    const displayLang = lang || 'plaintext';
    const escaped = code.replace(/`/g, '&#96;');
    return `<div class="code-block-wrap">
      <div class="code-block-header">
        <span class="code-lang">${displayLang}</span>
        <button class="copy-btn" onclick="copyCode(this,\`${escaped.replace(/\\/g,'\\\\').replace(/`/g,'\\`')}\`)">Copy</button>
      </div>
      <pre><code class="hljs language-${displayLang}">${highlighted}</code></pre>
    </div>`;
  };
  marked.use({ renderer });

  function copyCode(btn, code) {
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = 'Copied!'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    });
  }

  // ── State ──
  let sessions = {};
  let activeSessionId = null;
  let isStreaming = false;
  let pendingImageB64 = null;
  let pendingImageDataUrl = null;

  // ── DOM refs ──
  const sessionListEl   = document.getElementById('session-list');
  const noSessionsHint  = document.getElementById('no-sessions-hint');
  const newSessionBtn   = document.getElementById('new-session-btn');
  const modelSelect     = document.getElementById('model-select');
  const statusDot       = document.getElementById('status-dot');
  const modelInfo       = document.getElementById('model-info');
  const sessionTitle    = document.getElementById('session-title');
  const messagesEl      = document.getElementById('messages');
  const inputArea       = document.getElementById('input-area');
  const inputEl         = document.getElementById('user-input');
  const sendBtn         = document.getElementById('send-btn');
  const clearBtn        = document.getElementById('clear-btn');
  const attachBtn       = document.getElementById('attach-btn');
  const fileInput       = document.getElementById('file-input');
  const previewStrip    = document.getElementById('image-preview-strip');
  const previewThumb    = document.getElementById('preview-thumb');
  const previewName     = document.getElementById('preview-name');
  const previewSize     = document.getElementById('preview-size');
  const removeImgBtn    = document.getElementById('remove-image');
  const toast           = document.getElementById('toast');
  const modalOverlay    = document.getElementById('modal-overlay');
  const modalName       = document.getElementById('modal-name');
  const modalSysprompt  = document.getElementById('modal-sysprompt');
  const modalCancel     = document.getElementById('modal-cancel');
  const modalCreate     = document.getElementById('modal-create');
  const syspromptBar    = document.getElementById('sysprompt-bar');
  const syspromptInput  = document.getElementById('sysprompt-input');
  const syspromptSave   = document.getElementById('sysprompt-save');
  const syspromptToggle = document.getElementById('sysprompt-toggle-btn');

  // ── Toast ──
  function showToast(msg, success = false) {
    toast.textContent = msg;
    toast.classList.toggle('success', success);
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show', 'success'), 3000);
  }

  // ── Load sessions ──
  async function loadSessions() {
    try {
      const res = await fetch('/api/sessions');
      sessions = await res.json();
      renderSessionList();
    } catch (e) { showToast('Could not load sessions'); }
  }

  // ── Render sidebar ──
  function renderSessionList() {
    [...sessionListEl.querySelectorAll('.session-item')].forEach(el => el.remove());
    const ids = Object.keys(sessions);
    noSessionsHint.style.display = ids.length === 0 ? 'block' : 'none';
    ids.sort((a, b) => sessions[b].createdAt - sessions[a].createdAt);
    ids.forEach(id => {
      const s = sessions[id];
      const item = document.createElement('div');
      item.className = 'session-item' + (id === activeSessionId ? ' active' : '');
      item.dataset.id = id;

      const dot  = document.createElement('div'); dot.className = 'session-dot';
      const info = document.createElement('div'); info.className = 'session-info';
      const name = document.createElement('div'); name.className = 'session-name'; name.textContent = s.name;
      const meta = document.createElement('div'); meta.className = 'session-meta';
      const msgCount = Math.floor(s.history.length / 2);
      meta.textContent = msgCount + ' msg' + (msgCount !== 1 ? 's' : '');
      const del = document.createElement('button'); del.className = 'session-del'; del.textContent = '✕'; del.title = 'Delete session';
      del.addEventListener('click', (e) => { e.stopPropagation(); deleteSession(id); });

      info.appendChild(name); info.appendChild(meta);
      item.appendChild(dot); item.appendChild(info); item.appendChild(del);
      item.addEventListener('click', () => switchSession(id));
      sessionListEl.insertBefore(item, noSessionsHint);
    });
  }

  // ── Switch session ──
  function switchSession(id) {
    activeSessionId = id;
    const s = sessions[id];
    sessionTitle.textContent = s.name;
    sessionTitle.classList.remove('placeholder');
    inputArea.style.display = 'block';
    syspromptToggle.style.display = 'inline-block';
    clearBtn.style.display = 'inline-block';
    syspromptBar.classList.remove('open');
    syspromptToggle.classList.remove('active');
    syspromptInput.value = s.systemPrompt || '';
    renderMessages();
    renderSessionList();
    modelInfo.textContent = modelSelect.value ? `model: ${modelSelect.value}` : 'No model selected';
    inputEl.focus();
  }

  // ── Render messages ──
  function renderMessages() {
    messagesEl.innerHTML = '';
    const s = sessions[activeSessionId];
    if (!s || s.history.length === 0) {
      messagesEl.innerHTML = `<div id="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/></svg></div>
        <div class="empty-title">Session ready</div><div class="empty-sub">Start chatting below</div>
      </div>`;
      return;
    }
    s.history.forEach(msg => addMessageBubble(msg.role, msg.content));
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessageBubble(role, text) {
    const wrap = document.createElement('div'); wrap.className = `message ${role}`;
    const avatar = document.createElement('div'); avatar.className = 'msg-avatar';
    avatar.textContent = role === 'user' ? 'YOU' : 'AI';
    const body = document.createElement('div'); body.className = 'msg-body';
    const header = document.createElement('div'); header.className = 'msg-header';
    header.innerHTML = `<span>${role === 'user' ? 'user' : (modelSelect.value || 'assistant')}</span>`;
    const contentEl = document.createElement('div'); contentEl.className = 'msg-content';
    if (role === 'assistant') contentEl.innerHTML = marked.parse(text);
    else contentEl.textContent = text;
    body.appendChild(header); body.appendChild(contentEl);
    wrap.appendChild(avatar); wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    return contentEl;
  }

  function addMessage(role, text = '') {
    const empty = messagesEl.querySelector('#empty-state, #no-session-state');
    if (empty) empty.remove();
    const el = addMessageBubble(role, text);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function addCursor(el) {
    const c = document.createElement('span'); c.className = 'cursor'; el.appendChild(c); return c;
  }

  // ── New session modal ──
  newSessionBtn.addEventListener('click', () => {
    modalName.value = ''; modalSysprompt.value = '';
    modalOverlay.classList.add('open');
    setTimeout(() => modalName.focus(), 50);
  });
  modalCancel.addEventListener('click', () => modalOverlay.classList.remove('open'));
  modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) modalOverlay.classList.remove('open'); });
  modalName.addEventListener('keydown', (e) => { if (e.key === 'Enter') modalCreate.click(); });
  modalCreate.addEventListener('click', async () => {
    const name = modalName.value.trim();
    if (!name) { modalName.focus(); return; }
    try {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, systemPrompt: modalSysprompt.value.trim() })
      });
      const session = await res.json();
      sessions[session.id] = session;
      modalOverlay.classList.remove('open');
      renderSessionList();
      switchSession(session.id);
      showToast('Session created', true);
    } catch (e) { showToast('Failed to create session'); }
  });

  // ── Delete session ──
  async function deleteSession(id) {
    if (!confirm(`Delete "${sessions[id].name}"? This cannot be undone.`)) return;
    try {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
      delete sessions[id];
      if (activeSessionId === id) {
        activeSessionId = null;
        sessionTitle.textContent = 'Select or create a session';
        sessionTitle.classList.add('placeholder');
        inputArea.style.display = 'none';
        syspromptToggle.style.display = 'none';
        clearBtn.style.display = 'none';
        syspromptBar.classList.remove('open');
        messagesEl.innerHTML = `<div id="no-session-state">
          <div class="empty-icon"><svg viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"/></svg></div>
          <div class="empty-title">No session selected</div>
          <div class="empty-sub">Create a new session from the sidebar</div>
        </div>`;
      }
      renderSessionList();
      showToast('Session deleted', true);
    } catch (e) { showToast('Failed to delete session'); }
  }

  // ── System prompt ──
  syspromptToggle.addEventListener('click', () => {
    const open = syspromptBar.classList.toggle('open');
    syspromptToggle.classList.toggle('active', open);
    if (open) setTimeout(() => syspromptInput.focus(), 50);
  });
  syspromptInput.addEventListener('input', () => {
    syspromptInput.style.height = 'auto';
    syspromptInput.style.height = Math.min(syspromptInput.scrollHeight, 100) + 'px';
  });
  syspromptSave.addEventListener('click', async () => {
    if (!activeSessionId) return;
    try {
      await fetch(`/api/sessions/${activeSessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ systemPrompt: syspromptInput.value.trim() })
      });
      sessions[activeSessionId].systemPrompt = syspromptInput.value.trim();
      syspromptSave.textContent = 'Saved!'; syspromptSave.classList.add('saved');
      setTimeout(() => { syspromptSave.textContent = 'Save'; syspromptSave.classList.remove('saved'); }, 2000);
    } catch (e) { showToast('Failed to save system prompt'); }
  });

  // ── Clear chat ──
  clearBtn.addEventListener('click', async () => {
    if (!activeSessionId || !confirm('Clear all messages in this session?')) return;
    try {
      await fetch(`/api/sessions/${activeSessionId}/clear`, { method: 'POST' });
      sessions[activeSessionId].history = [];
      renderMessages(); renderSessionList();
      showToast('Chat cleared', true);
    } catch (e) { showToast('Failed to clear chat'); }
  });

  // ── Image handling ──
  attachBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => { if (e.target.files[0]) loadImage(e.target.files[0]); });
  removeImgBtn.addEventListener('click', clearImage);
  document.addEventListener('dragover', (e) => { e.preventDefault(); document.body.classList.add('drag-over'); });
  document.addEventListener('dragleave', (e) => { if (!e.relatedTarget) document.body.classList.remove('drag-over'); });
  document.addEventListener('drop', (e) => {
    e.preventDefault(); document.body.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) loadImage(file);
  });
  document.addEventListener('paste', (e) => {
    const item = [...e.clipboardData.items].find(i => i.type.startsWith('image/'));
    if (item) { e.preventDefault(); loadImage(item.getAsFile()); }
  });
  function loadImage(file) {
    if (!file.type.startsWith('image/')) { showToast('Only image files are supported'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      pendingImageDataUrl = ev.target.result; pendingImageB64 = ev.target.result.split(',')[1];
      previewThumb.src = ev.target.result; previewName.textContent = file.name;
      previewSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
      previewStrip.classList.add('visible'); inputEl.focus();
    };
    reader.readAsDataURL(file);
  }
  function clearImage() {
    pendingImageB64 = null; pendingImageDataUrl = null;
    previewStrip.classList.remove('visible'); previewThumb.src = ''; fileInput.value = '';
  }

  // ── Textarea ──
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
  });
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!isStreaming) sendMessage(); }
  });
  sendBtn.addEventListener('click', () => { if (!isStreaming) sendMessage(); });
  modelSelect.addEventListener('change', () => {
    modelInfo.textContent = modelSelect.value ? `model: ${modelSelect.value}` : 'No model selected';
  });

  // ── Send message ──
  async function sendMessage() {
    if (!activeSessionId) return;
    const text = inputEl.value.trim();
    if (!text && !pendingImageB64) return;
    const model = modelSelect.value;
    if (!model) { showToast('Please select a model first'); return; }

    const imageB64 = pendingImageB64;
    const imageDataUrl = pendingImageDataUrl;
    const userMsg = imageB64
      ? { role: 'user', content: text || 'Analyze this image.', images: [imageB64] }
      : { role: 'user', content: text };

    sessions[activeSessionId].history.push(userMsg);
    const userEl = addMessage('user', text);
    if (imageDataUrl) {
      const img = document.createElement('img'); img.className = 'msg-image';
      img.src = imageDataUrl; img.alt = 'attached';
      userEl.parentElement.insertBefore(img, userEl);
    }
    clearImage();
    inputEl.value = ''; inputEl.style.height = 'auto';
    renderSessionList();

    const aiContentEl = addMessage('assistant', '');
    const cursor = addCursor(aiContentEl);
    isStreaming = true; sendBtn.disabled = true; sendBtn.textContent = '...';

    let fullContent = '';
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          messages: sessions[activeSessionId].history,
          systemPrompt: sessions[activeSessionId].systemPrompt || ''
        })
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value).split('\n').filter(l => l.startsWith('data: '));
        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.error) { showToast(`Error: ${data.error}`); break; }
            if (data.content) {
              fullContent += data.content;
              aiContentEl.innerHTML = marked.parse(fullContent);
              aiContentEl.appendChild(cursor);
              messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          } catch {}
        }
      }
    } catch (err) { showToast('Stream error: ' + err.message); }

    cursor.remove();
    if (fullContent) {
      aiContentEl.innerHTML = marked.parse(fullContent);
      const assistantMsg = { role: 'assistant', content: fullContent };
      sessions[activeSessionId].history.push(assistantMsg);
      await fetch(`/api/sessions/${activeSessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userMsg, assistantMsg })
      }).catch(() => {});
      renderSessionList();
    }
    isStreaming = false; sendBtn.disabled = false; sendBtn.textContent = 'Send';
    inputEl.focus();
  }

  // ── Load models ──
  async function loadModels() {
    try {
      const res = await fetch('/api/models');
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      modelSelect.innerHTML = '';
      if (data.models.length === 0) {
        modelSelect.innerHTML = '<option value="">No models found</option>';
        showToast('No models found. Pull one with: ollama pull llama3.2'); return;
      }
      data.models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m; opt.textContent = m; modelSelect.appendChild(opt);
      });
      statusDot.classList.add('online');
      modelInfo.textContent = `model: ${data.models[0]}`;
    } catch {
      modelSelect.innerHTML = '<option value="">Ollama offline</option>';
      statusDot.classList.add('error');
      showToast('Cannot connect to Ollama — is it running?');
    }
  }

  loadModels();
  loadSessions();
</script>
</body>
</html>"""


# ── Routes ──

@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html"}


@app.route("/api/models")
def get_models():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return jsonify({"models": models})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Ollama"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    return jsonify(sessions)


@app.route("/api/sessions", methods=["POST"])
def create_session():
    data = request.json
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "name": data.get("name", "New Session").strip(),
        "systemPrompt": data.get("systemPrompt", "").strip(),
        "history": [],
        "createdAt": datetime.now().timestamp()
    }
    sessions[session_id] = session
    save_sessions(sessions)
    return jsonify(session)


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    sessions.pop(session_id, None)
    save_sessions(sessions)
    return jsonify({"status": "ok"})


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
def update_session(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    if "systemPrompt" in data:
        sessions[session_id]["systemPrompt"] = data["systemPrompt"]
    if "name" in data:
        sessions[session_id]["name"] = data["name"]
    save_sessions(sessions)
    return jsonify(sessions[session_id])


@app.route("/api/sessions/<session_id>/clear", methods=["POST"])
def clear_session(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Not found"}), 404
    sessions[session_id]["history"] = []
    save_sessions(sessions)
    return jsonify({"status": "ok"})


@app.route("/api/sessions/<session_id>/message", methods=["POST"])
def save_message(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    history = sessions[session_id].setdefault("history", [])
    user_msg = data.get("userMsg")
    assistant_msg = data.get("assistantMsg")
    # Sync server history — avoid duplicating if already pushed
    if user_msg and (len(history) < 2 or history[-2] != user_msg):
        history.append(user_msg)
    if assistant_msg and (not history or history[-1] != assistant_msg):
        history.append(assistant_msg)
    save_sessions(sessions)
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    model = data.get("model")
    messages = data.get("messages", [])
    system_prompt = data.get("systemPrompt", "").strip()

    if not model:
        return jsonify({"error": "No model specified"}), 400

    final_messages = list(messages)
    if system_prompt:
        final_messages = [{"role": "system", "content": system_prompt}] + final_messages

    def generate():
        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": model, "messages": final_messages, "stream": True},
                stream=True, timeout=180
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            done = chunk.get("done", False)
                            yield f"data: {json.dumps({'content': content, 'done': done})}\n\n"
                            if done:
                                break
                        except json.JSONDecodeError:
                            continue
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama', 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


if __name__ == "__main__":
    print("Starting Ollama Chat at http://localhost:5000")
    print("Sessions saved to: ./sessions.json")
    app.run(debug=True, host="0.0.0.0", port=5000)
