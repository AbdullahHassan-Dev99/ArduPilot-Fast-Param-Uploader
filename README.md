# ArduPilot Fast MAVLink Parameter Uploader 🚀

High-performance Python CLI tool and library for uploading, converting, and managing **ArduPilot / Mission Planner** parameter files (`.param`, `.params`, `.json`) over MAVLink at Mission Planner speed.

## 🌟 Key Features

- ⚡ **Mission Planner Speed Burst Uploading:** Uses pipelined MAVLink `PARAM_SET` streaming with high-speed burst pacing.
- 🧠 **Smart Parameter Diffing:** Automatically pre-fetches existing vehicle parameters and skips unchanged parameters (`SKIP`).
- 🔄 **Format Conversion:** Easily convert between `.param` / `.params` text format and `.json` format.
- 🛡️ **Robust Connection Handling:** Auto-detects UDP, TCP, and Serial connections with auto-fallbacks for SITL simulation.
- 📊 **Detailed Summary Reports:** Displays real-time progress bars and lists updated, skipped, and unsupported parameters.

---

## 🛠️ Installation

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### 1. Upload Parameter File to Vehicle (Smart Diff Mode)
```bash
python main.py -f "your_params.param" -c "COM7" -b 115200
```
*For SITL / UDP simulation:*
```bash
python main.py -f "your_params.param" -c "udpout:127.0.0.1:14551"
```

### 2. Force Upload All Parameters (Bypass Smart Diffing)
```bash
python main.py -f "your_params.param" --force-all
```

### 3. Convert `.param` File to `.json` Format
```bash
python main.py -f "input.param" --convert json -o "output.json"
```

### 4. Validate Parameter File Without Connection (Dry Run)
```bash
python main.py -f "input.param" --dry-run
```

---

## 📜 License

MIT License. Free for open-source and commercial use.
