# 📡 DXCC Need List Tracker
*A Flet-based desktop/web application for Amateur Radio operators*

The **DXCC Need List Tracker** is a modern, cross-platform logging companion tool built using **Python** and **Flet**. It allows amateur radio operators to manage, track, and analyze their DXCC progress with features normally seen in full-scale logging programs — but in a lightweight, user-friendly interface.

## 🌟 Features

### ✔ User Authentication
- Log in using your ham radio callsign
- Each user has their **own isolated data file**
- Passwords stored securely using SHA-256 hashing

### ✔ DXCC Tracking
- Full list of **340+ ARRL DXCC entities**
- Add QSOs manually
- Edit entries with dialog UI
- Delete entries
- Save & reload to/from Excel

### ✔ Dashboard Summary
Displays real-time stats including:
- Total QSOs
- Worked DXCC entities
- Needed / Requested / Confirmed
- Remaining DXCC count

### ✔ ADIF Import
Import QSOs directly from your logging software (.adi / .adif files).
Auto-detects:
- Callsign
- Country
- QSO Date
- QSL status (maps LoTW/eQSL/paper flags automatically)

### ✔ Sorting & Filtering
- Filter by QSL Status (All, Needed, Requested, Confirmed)
- Sort by:
  - Country
  - Callsign
  - QSO Date
  - QSL Status

### ✔ Multi-Platform
Runs on:
- Windows
- macOS
- Linux
- Web (with limited filesystem access)

## 🛠 Technology Stack

- **Python 3.10+**
- **Flet 0.28.3** (Flutter UI in Python)
- **OpenPyXL** for Excel storage
- **Regex** & custom parser for ADIF import
- **SHA-256** for password hashing

## 📦 Project Structure

```
dxcc-tracker/
│
├── app/
│   ├── main.py              # Main Flet application
│   ├── auth.py              # Login / registration logic
│   ├── data_manager.py      # Excel saving/loading
│   ├── dxcc_list.py         # Full DXCC entity list
│   ├── adif_import.py       # ADIF (.adi) parser
│   ├── ui_components.py     # Shared UI elements
│   └── users/               # Auto-created Excel files per user
│
├── README.md
├── requirements.txt
└── .gitignore
```

## 🚀 Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/dxcc-tracker.git
cd dxcc-tracker
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate    # macOS / Linux
venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python -m app.main
```

## 📁 User Data Storage

Each callsign gets its own Excel file stored in:

```
app/users/<CALLSIGN>.xlsx
```

## 📥 ADIF Import

Export from your logging software using **ADIF format**, then import via the UI.

## 🧭 Roadmap

- Band/Mode matrix
- Color-coded rows
- Cloud sync
- SQLite database option
- DX Cluster integration
- Mobile builds

## 📝 License

MIT License.

## 🤝 Contributions

Pull requests welcome!
