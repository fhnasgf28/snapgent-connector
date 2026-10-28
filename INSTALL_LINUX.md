# Snapgent Connector - Panduan Instalasi & Penggunaan di Linux

Dokumen ini dirancang sebagai panduan lengkap dan terstandarisasi untuk **manusia maupun AI Coding Agent** agar dapat menginstal, mengonfigurasi, dan menjalankan **Snapgent Connector** di lingkungan sistem operasi Linux.

---

## 1. Arsitektur Komponen

Snapgent di Linux bekerja melalui 2 komponen utama yang saling terhubung:

```
┌─────────────────────────────────┐       WebSocket (JSON-RPC)       ┌─────────────────────────────────┐
│        Browser Extension        │ ◄──────────────────────────────► │          Local Bridge           │
│      (Chrome / Brave / Edge)    │       ws://127.0.0.1:17613       │      (Python 3 + websockets)    │
│  `snapgent-extension/` (MV3)    │                                  │     `bridge.py` & `start.sh`    │
└─────────────────────────────────┘                                  └─────────────────────────────────┘
                 │                                                                    │
                 ▼                                                                    ▼
┌─────────────────────────────────┐                                  ┌─────────────────────────────────┐
│     AI Chat Web Interface       │                                  │        Workspace MCP Tools      │
│ (Gemini, DeepSeek, ChatGPT, dll)│                                  │      `vscode_mcp.py` (Local)    │
└─────────────────────────────────┘                                  └─────────────────────────────────┘
```

1. **Browser Extension (`snapgent-extension/`)**: Ekstensi Manifest V3 murni (HTML/JS/CSS) yang menginjeksi kontrol UI ke halaman AI chat dan meneruskan perintah JSON ke local bridge.
2. **Local Bridge (`bridge.py`)**: Server WebSocket lokal (`127.0.0.1:17613`) berbasis Python native yang menerima permintaan dari browser dan mengeksekusi operasi file/terminal pada workspace lokal.
3. **Workspace Tools (`vscode_mcp.py`)**: Kumpulan 9 tools workspace (baca, tulis, ganti teks, cari file, dan jalankan perintah terminal) tanpa dependensi ke Roblox Studio.

---

## 2. Prasyarat Sistem

- **Sistem Operasi**: Linux (Ubuntu, Debian, Fedora, Arch, dll.)
- **Python**: Python 3.9 atau lebih baru (`python3`)
- **Pustaka Python**: `websockets`
- **Browser**: Browser berbasis Chromium (Google Chrome, Brave, Microsoft Edge, atau Chromium)

---

## 3. Langkah Instalasi Otomatis (Agent Executable)

Jalankan perintah berikut di terminal:

### Langkah 3.1: Install Dependensi Python
```bash
python3 -m pip install --user websockets
```

### Langkah 3.2: Berikan Izin Eksekusi pada Script
```bash
chmod +x start.sh bridge.py vscode_mcp.py
```

### Langkah 3.3: Konfigurasi Workspace Path (Opsional)
Secara default, bridge akan menggunakan direktori kerja saat ini (`cwd`). Jika ingin mengunci workspace ke folder tertentu:
```bash
export WORKSPACE_PATH="/path/ke/proyek/anda"
```

---

## 4. Memasang Ekstensi di Browser

1. Buka browser berbasis Chromium Anda di Linux:
   - Google Chrome / Chromium: `chrome://extensions`
   - Brave Browser: `brave://extensions`
   - Microsoft Edge: `edge://extensions`
2. Aktifkan sakelar **Developer mode** (Mode Pengembang) di pojok kanan atas.
3. Klik tombol **Load unpacked** (Muat yang belum diekstrak).
4. Pilih folder:
   ```
   <repo-path>/snapgent-extension
   ```
5. Ekstensi **snapgentV3 × VS Code & MCP Agent** akan terpasang di browser.

> [!NOTE]
> Jika file di dalam `snapgent-extension/` mengalami perubahan di kemudian hari, pastikan menekan tombol **Reload (ikon 🔄)** pada kartu ekstensi di halaman `chrome://extensions`.

---

## 5. Cara Menjalankan Bridge

### Opsi A: Menjalankan di Terminal Foreground (Rekomendasi saat Pengujian)
```bash
./start.sh
```
*(Biarkan jendela terminal tetap terbuka selama Anda menggunakan ekstensi).*

### Opsi B: Menjalankan di Background (Daemon Mode)
Jika Anda ingin bridge tetap berjalan di latar belakang:
```bash
nohup ./start.sh > logs/bridge_daemon.log 2>&1 &
```
Untuk menghentikan bridge background:
```bash
fuser -k 17613/tcp
```

---

## 6. Cara Penggunaan di AI Chat (Gemini / DeepSeek / ChatGPT)

1. Buka provider AI yang didukung (misalnya [gemini.google.com](https://gemini.google.com), [chat.deepseek.com](https://chat.deepseek.com), atau [chatgpt.com](https://chatgpt.com)).
2. **PENTING:** Buka **Obrolan Baru (New Chat)** yang bersih/kosong.
3. Periksa bilah bar **snapgentV3** di atas kotak chat:
   - Target harus tertulis: **VS Code**
   - Status indikator: **Ready** (warna hijau)
4. Klik tombol **`▶︎ Start`** pada bar tersebut.
5. Ekstensi akan otomatis menginjeksi inisialisasi awal ke AI. AI akan memanggil `list_commands` dan melaporkan bahwa ia telah siap.
6. Berikan instruksi langsung dalam bahasa manusia, contohnya:
   - **Manipulasi File & Folder:**
     - *"Tolong cek isi folder ini menggunakan list_dir"*
     - *"Baca isi file config.json"*
     - *"Lihat isi folder parent di atas menggunakan list_dir dengan path '..'"*
     - *"Ganti workspace aktif ke '../project-lain'"*
     - *"Cari kata kunci 'bridge' di semua file"*
     - *"Buatkan file script baru bernama halo.py"*
     - *"Jalankan python3 halo.py dan tunjukkan hasilnya"*
   - **Integrasi OpenClaw (50+ Skills & Multi-Channel):**
     - *"Cek daftar skills yang tersedia di OpenClaw"* (AI memanggil `openclaw_command(command="skills list")`)
     - *"Cek status OpenClaw gateway dan bot"* (AI memanggil `openclaw_command(command="status")`)
     - *"Tampilkan model AI yang terkonfigurasi di OpenClaw"* (AI memanggil `openclaw_command(command="models status")`)
   - **Integrasi Antigravity (AGY) & Hermes:**
     - *"Cek status Antigravity CLI menggunakan agy_command"*
     - *"Jalankan evaluasi model dengan hermes_command"*

---

## 7. Daftar Tools Workspace yang Tersedia

AI yang terhubung memiliki akses ke 13 tool berikut dengan dukungan **Path Relatif Portabel** (`.`, `..`, `../..`, `./subfolder`), path home (`~`), maupun integrasi agen eksternal:

| Nama Tool | Parameter | Deskripsi |
|---|---|---|
| `list_dir` | `path` (opsional) | Melihat file & folder di direktori mana saja (contoh: `.`, `..`, `../folder-lain`). |
| `read_file` | `path`, `start_line` (opsional), `end_line` (opsional) | Membaca isi teks file (contoh: `file.txt`, `../proyek/config.json`). |
| `write_file` | `path`, `content` | Menulis/menimpa isi file (bisa relatif ke mana saja). |
| `append_file` | `path`, `content` | Menambahkan teks di baris akhir file apa saja. |
| `replace_in_file` | `path`, `old_text`, `new_text` | Mengganti potongan string tertentu di file mana saja. |
| `delete_file` | `path` | Menghapus file di path mana saja. |
| `search_files` | `query`, `path` (opsional) | Mencari teks di dalam file pada folder mana saja (default `.`). |
| `run_command` | `command`, `cwd` (opsional) | Menjalankan perintah bash/shell (bisa tentukan direktori kerja relatif `cwd`). |
| `set_workspace` | `path` | Mengganti direktori kerja aktif default (contoh: `../folder-lain` atau `../../`). |
| `get_workspace_info` | `path` (opsional) | Mengambil info path root, jumlah file, dan ukuran folder apa saja. |
| `openclaw_command` | `command` | Menjalankan perintah **OpenClaw CLI** (akses 50+ skills, bot multi-channel, gateway). |
| `agy_command` | `command` | Menjalankan perintah **Antigravity (AGY) CLI** & agentapi. |
| `hermes_command` | `command` | Menjalankan perintah agen **Hermes CLI** / script evaluasi. |

### 7.1 Detail Integrasi Eksternal (OpenClaw, AGY, Hermes)

#### OpenClaw (`openclaw_command`)
Sistem secara otomatis mendeteksi biner `openclaw` dari PATH, NVM Node, `~/.local/bin`, atau `/usr/local/bin`.
- Perintah umum:
  - `skills list` - Menampilkan status 50+ skill OpenClaw.
  - `status` - Memeriksa gateway, channel bot (Telegram, Discord, Slack), dan active sessions.
  - `plugins list` - Melihat plugin yang aktif.
  - `agent --message "<teks>"` - Mengirimkan tugas ke agen OpenClaw.

#### Antigravity (`agy_command`)
Mengeksekusi perintah Antigravity CLI dan `agentapi` untuk integrasi sub-agent dan workflow.

#### Hermes (`hermes_command`)
Menjalankan runner Hermes untuk inferensi, function calling, dan evaluasi penalaran model.

---

## 8. Troubleshooting

| Gejala Masalah | Penyebab | Solusi |
|---|---|---|
| **Status bar "Bridge offline"** | Bridge belum dijalankan di port `17613`. | Jalankan `./start.sh` di terminal. |
| **Error `Address already in use` saat start.sh** | Port 17613 masih tertahan oleh proses sebelumnya. | Jalankan `fuser -k 17613/tcp` lalu ulangi `./start.sh`. |
| **Pesan "Use an empty chat" saat klik Start** | Sesi `Start` dijalankan pada obrolan yang sudah ada riwayatnya. | Klik **Chat Baru (+)** terlebih dahulu sebelum menekan `▶︎ Start`. |
| **AI menjawab "Saya tidak bisa akses file lokal"** | Tombol `▶︎ Start` belum ditekan sebelum mengetik chat. | Tekan tombol `▶︎ Start` agar AI menerima prompt sistem agen. |
| **Perubahan kode tidak terdeteksi di browser** | Browser masih memuat cache ekstensi lama. | Buka `chrome://extensions` dan klik ikon **Reload 🔄**. |
