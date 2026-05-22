***

# 🎛️ GridDash

<img width="1054" height="776" alt="image" src="https://github.com/user-attachments/assets/37ae6b05-ee3a-460a-8403-03f96ff872e0" />

<br>

**GridDash** is a sleek, high-performance Windows Heads-Up Display (HUD) and productivity dashboard. Designed as the visual software companion to the **Gridflow** hardware ecosystem, GridDash provides deep system telemetry, native media controls, and integrated task management in a beautifully rounded, borderless UI.

Whether you are using the physical Gridflow macro pad or running GridDash standalone, it serves as the ultimate command center for your desktop.

## 🚀 Key Features
- **Deep System Telemetry:** Real-time monitoring of CPU, RAM, Network I/O, Disk usage, and Core Temperatures.
- **Intelligent Health Engine:** Calculates a live "System Health" score based on resource loads, mapping states from *Optimal* to *Critical*.
- **Native Media Integration:** Pulls live track info, album art, and timeline progress natively from Windows (supports Spotify, browsers, etc.) with built-in playback controls.
- **Live Theming Engine:** 100% customizable JSON-based UI. Edit colors, fonts, and backgrounds in your config and watch the UI update instantly — no restarts required.
- **Gridflow Sync:** Automatically reads shared state to display your Arduino's connection status, port, and current LCD mode.
- **Productivity Suite:** Built-in auto-saving Notepad and an interactive "Core Objectives" task manager.

---

## 💻 System Requirements
- **OS:** Windows 10 / Windows 11 (required for WinRT media and WMI temperature telemetry).
- **GPU (Optional):** NVIDIA graphics card recommended for GPU usage and temperature stats via NVML. Ensure your NVIDIA drivers are up to date.

---

## ⚙️ Configuration & Theming

GridDash is designed for zero-friction setup. On first launch, it automatically generates its configuration file and directory.

1. **Locate config:** Press the gear icon `⚙` in the top-right of the dashboard, or navigate manually to `%APPDATA%\GridDash\griddash_config.json`.
2. **Personalize:** Open the JSON file in any text editor.
   - **Data:** Your `notes` and `tasks` are stored here.
   - **Theme:** Modify the `"theme"` object to change the look of the app. Every color, border, and text element is mapped using standard hex codes (e.g. `#adc6ff`).
3. **Hot-reload:** Save the file. GridDash instantly applies your changes to the live window.

---

## 📋 Installation (Development)

Requires Python 3.x.

```bash
# Clone the repository
git clone https://github.com/Acceltrx/GridDash.git
cd GridDash

# Install dependencies
pip install -r requirements.txt

# Run the application
python "src/GridDash Main.pyw"
```

---

## 🛠️ Deployment

### Compiling to a Standalone Executable

1. Install the compiler: `pip install auto-py-to-exe`
2. Launch it by running `auto-py-to-exe` in your terminal.
3. **Script Location:** Select `src/GridDash Main.pyw`.
4. **Output:** Choose *One File* and *Window Based (hide the console)*.
5. **Icon:** Select `assets/GridDash.ico`.
6. **Additional Files:** Add the `assets` folder and map it to `assets` so the bundled executable can locate the icon at runtime.
7. **Version Info (Optional):** Link your `version_info.txt` to apply file properties such as copyright and version number.
8. Click **Convert .py to .exe**. The compiled executable will appear in the `output` folder.

> **Note:** The `assets` folder must be explicitly included in the "Additional Files" section. Without it, the system tray icon will fail to load and the minimize-to-tray button will not work.

### Launch on Startup

To have GridDash launch automatically and minimize to the system tray on sign-in:

1. Press `Win + R`, type `shell:startup`, and press **Enter**.
2. Create a shortcut to your `GridDash.exe`.
3. Move the shortcut into the Startup folder. GridDash will now boot silently with Windows.

---
