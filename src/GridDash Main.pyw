import os
import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Shared directories & files (AppData/Roaming/GridDash)
MAIN_DIR = os.path.join(os.environ['APPDATA'], 'GridDash')
SHARED_DIR = os.path.join(os.environ['APPDATA'], 'GridFlow')
os.makedirs(MAIN_DIR, exist_ok=True)  # Create directory if it doesn't exist

# GridDash's own config and logs moved to AppData
DASH_CONFIG   = os.path.join(MAIN_DIR, 'griddash_config.json')
LOG_FILE      = os.path.join(MAIN_DIR, 'griddash_debug_log.txt')

# Shared status — written by Gridflow, read by GridDash
SHARED_STATUS = os.path.join(SHARED_DIR, 'gridflow_status.json')

import logging
import webbrowser

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("--- GridDash Startup ---")

try:
    import serial
    import time
    import psutil
    import pynvml
    import pyautogui
    import threading
    import subprocess
    import asyncio
    import json
    import ctypes
    from datetime import datetime
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    import winrt.windows.media.control as wmc
    import winrt.windows.storage.streams as streams
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
    import platform
    import cpuinfo
    import wmi
    import serial.tools.list_ports
    import io
    logging.info("All modules loaded successfully.")
except ImportError as e:
    logging.error(f"CRITICAL: Missing library! {e}")
    sys.exit(1)
except Exception as e:
    logging.error(f"Unexpected error during import: {e}")
    sys.exit(1)

# -----------------------------------------------------------------------
# UI Theme Dictionary & Live Engine
# -----------------------------------------------------------------------
ICON_FONT = "JetBrainsMono NFP"

DEFAULT_THEME = {
    "font": {"main_font": "JetBrains Mono"},
    "app": {"bg": "#111011"},
    "topbar": {"bg": "#101218", "title": "#adc6ff", "clock": "#d2ac14", "date": "#c2c6d6", "icons": "#c2c6d6", "power_icon": "#ffb4ab", "divider": "#2e2e2e"},
    "stats": {"card_bg": "#171717", "border": "#4a5368", "title": "#c2c6d6", "value": "#e1e2ec", "subtext": "#c2c6d6", "bar_bg": "#2e2e2e", "bar_fill": "#adc6ff"},
    "storage": {"card_bg": "#171717", "border": "#2e2e2e", "title": "#c2c6d6", "text": "#c2c6d6", "bar_bg": "#2e2e2e", "bar_fill": "#e1e2ec"},
    "network": {"card_bg": "#171717", "border": "#2e2e2e", "title": "#c2c6d6", "up_icon": "#4ae176", "down_icon": "#adc6ff"},
    "health": {"card_bg": "#171717", "border": "#2e2e2e", "title": "#c2c6d6", "circle_bg": "#171717", "circle_border": "#2e2e2e", "box_core_bg": "#1a211d", "box_stab_bg": "#202124", "box_runt_bg": "#242424", "box_text_dim": "#c2c6d6", "box_text": "#e1e2ec", "health_score": "#c2c6d6"},
    "media": {"card_bg": "#171717", "border": "#5d4f6a", "title": "#ddb7ff", "artist": "#c2c6d6", "time": "#c2c6d6", "controls_active": "#ddb7ff", "controls_inactive": "#c2c6d6", "bar_bg": "#2e2e2e", "bar_fill": "#ddb7ff"},
    "notepad": {"card_bg": "#171717", "border": "#2e2e2e", "title": "#e1e2ec", "text_bg": "#2e2e2e", "text_fg": "#c2c6d6", "cursor": "#e1e2ec"},
    "tasks": {"card_bg": "#171717", "border": "#2e2e2e", "header": "#4ae176", "header_divider": "#2e2e2e", "prog_box_bg": "#1a211d", "prog_text": "#4ae176", "prog_sub": "#c2c6d6", "task_done_icon": "#4ae176", "task_done_text": "#e1e2ec", "task_pend_icon": "#8c909f", "task_pend_text": "#c2c6d6", "del_icon": "#8c909f", "entry_bg": "#171717", "entry_fg": "#c2c6d6", "entry_fg_active": "#e1e2ec", "entry_divider": "#2e2e2e", "add_border": "#4ae176", "add_bg": "#171717", "add_fg": "#4ae176", "add_active_bg": "#00b954", "add_active_fg": "#101218", "purge_border": "#e14a4a", "purge_bg": "#171717", "purge_fg": "#ffb4ab", "purge_active_bg": "#ffb4ab", "purge_active_fg": "#101218"},
    "gridflow": {"card_bg": "#171717", "border": "#2e2e2e", "title": "#4ae176", "divider": "#2e2e2e", "label": "#c2c6d6", "port": "#e1e2ec", "mode": "#ddb7ff"},
    "status": {"optimal": "#4ae176", "moderate": "#ddb7ff", "elevated": "#d2ac14", "critical": "#cf1313", "cool_temp": "#4ae176", "warm_temp": "#d2ac14", "hot_temp": "#d26a14", "danger_temp": "#cf1313", "online": "#4ae176", "offline": "#ffb4ab"}
}

dash_config = {}
THEME = {}
THEMED_WIDGETS = []

def T(widget, **theme_mapping):
    """
    Live Theming Engine Wrapper:
    Registers a widget and its expected theme pathways. Applies colors immediately.
    Usage: T(tk.Label(...), bg=("app", "bg"), fg=("topbar", "title"))
    """
    THEMED_WIDGETS.append((widget, theme_mapping))
    config_args = {k: THEME[v[0]][v[1]] for k, v in theme_mapping.items() if v}
    widget.config(**config_args)
    return widget

def get_merged_theme(default_t, user_t):
    merged = {}
    for category, properties in default_t.items():
        merged[category] = properties.copy()
        if category in user_t and isinstance(user_t[category], dict):
            merged[category].update(user_t[category])
    return merged

def load_dash_config():
    global dash_config, THEME
    
    if not os.path.exists(DASH_CONFIG):
        # Create base config
        dash_config = {"notes": "", "tasks": []}
    else:
        try:
            with open(DASH_CONFIG, 'r', encoding='utf-8') as f:
                dash_config = json.load(f)
        except Exception as e:
            logging.error(f"Error loading dash config: {e}")
            dash_config = {"notes": "", "tasks": []}

    # Auto-generate theme if it doesn't exist yet
    if "theme" not in dash_config:
        dash_config["theme"] = DEFAULT_THEME
        save_dash_config()
        THEME = DEFAULT_THEME
    else:
        THEME = get_merged_theme(DEFAULT_THEME, dash_config["theme"])
        
    return dash_config

def save_dash_config():
    try:
        with open(DASH_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(dash_config, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving dash config: {e}")

load_dash_config()

# Data & Variables
sys_status = ["OPTIMAL", "MODERATE", "ELEVATED", "CRITICAL"]
sys_label  = ["SYS_OK", "SYS_MOD", "SYS_HIGH", "SYS_CRIT"]
sys_stat_display = 0
sys_index_color  = ""
temp_color       = ""

media_artist  = ""
media_title   = ""
media_thumb   = None
media_pos     = 0
media_dur     = 0
media_is_playing = False
running       = True

# Hardware Info Detection
try:
    # Use native WMI instead of cpuinfo to prevent PyInstaller fork-bombs
    w_cpu = wmi.WMI()
    CPU_MODEL = w_cpu.Win32_Processor()[0].Name.strip()
except: 
    CPU_MODEL = platform.processor()

try:
    w         = wmi.WMI()
    ram_info  = w.Win32_PhysicalMemory()[0]
    RAM_SPEED = ram_info.Speed
    ram_total = psutil.virtual_memory().total / (1024**3)
    RAM_LABEL = f"{ram_total:.0f}GB DDR4-{RAM_SPEED}"
except:
    ram_total = psutil.virtual_memory().total / (1024**3)
    RAM_LABEL = f"{ram_total:.0f}GB RAM"

try:
    pynvml.nvmlInit()
    nvml_available = True
    handle    = pynvml.nvmlDeviceGetHandleByIndex(0)
    GPU_MODEL = pynvml.nvmlDeviceGetName(handle)
except:
    nvml_available = False
    GPU_MODEL = "No NVIDIA GPU"

def load_shared_status():
    try:
        if os.path.exists(SHARED_STATUS):
            with open(SHARED_STATUS, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"connected": False, "port": "—", "display_mode": 0}

# -----------------------------------------------------------------------
# System Tray (Minimize to Hidden Apps)
# -----------------------------------------------------------------------
def get_tray_icon():
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        icon_path = os.path.join(base, 'assets', 'GridDash.ico')
    else:
        script_dir   = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        icon_path    = os.path.join(project_root, 'assets', 'GridDash.ico')

    return Image.open(icon_path)

def on_tray_restore(icon, item):
    icon.stop()
    window.after(0, window.deiconify)

def on_tray_quit(icon, item):
    global running
    running = False
    icon.stop()
    window.after(0, window.destroy)
    os._exit(0)

def minimize_to_tray():
    try:
        window.withdraw()
        icon_img = get_tray_icon() 
        menu = pystray.Menu(
            pystray.MenuItem('Open', on_tray_restore, default=True),
            pystray.MenuItem('Exit', on_tray_quit)
        )
        tray_icon = pystray.Icon("GridDash", icon_img, "GridDash HUD", menu)
        threading.Thread(target=tray_icon.run, daemon=True).start()
    except Exception as e:
        logging.error(f"Critical error spawning tray icon: {e}") 
        window.deiconify()
# -----------------------------------------------------------------------
# Window Setup
# -----------------------------------------------------------------------
window = tk.Tk()
window.title("GridDash HUD")
window.geometry("1030x750")
window.configure(bg=THEME["app"]["bg"])
window.overrideredirect(True)

# --- Apply Native Windows Rounded Corners ---
window.update()  # Force the window to draw so we can grab its dimensions
hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
if hwnd == 0:
    hwnd = window.winfo_id()

corner_radius = 25  # Change this number to make it more or less round
# CreateRoundRectRgn(Left, Top, Right, Bottom, WidthEllipse, HeightEllipse)
region = ctypes.windll.gdi32.CreateRoundRectRgn(
    0, 0, window.winfo_width(), window.winfo_height(), corner_radius, corner_radius
)
ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
# -------------------------------------------------

window.grid_rowconfigure(0, minsize=55)
window.grid_rowconfigure(1, minsize=2)
window.grid_rowconfigure(2, weight=1)

# -----------------------------------------------------------------------
# LIVE FONT ENGINE
# -----------------------------------------------------------------------
LIVE_FONTS = {}

def live_font(*args):
    """Generates a dynamic Tkinter font that instantly updates when the config changes."""
    size = args[0]
    weight = "normal"
    slant = "roman"
    
    # Parse whether the font needs to be bold or italic
    for arg in args[1:]:
        if arg == "bold": weight = "bold"
        elif arg == "italic": slant = "italic"
        
    key = (size, weight, slant)
    if key not in LIVE_FONTS:
        # Create a dynamic Tkinter Font object
        LIVE_FONTS[key] = tkfont.Font(family=THEME["font"]["main_font"], size=size, weight=weight, slant=slant)
    
    return LIVE_FONTS[key]


def start_drag(event):
    window._drag_x = event.x
    window._drag_y = event.y

def do_drag(event):
    x = window.winfo_x() + event.x - window._drag_x
    y = window.winfo_y() + event.y - window._drag_y
    window.geometry(f"+{x}+{y}")

style = ttk.Style()
style.theme_use('default')

def update_ttk_styles():
    style.configure("Stats.Horizontal.TProgressbar",
        troughcolor=THEME["stats"]["bar_bg"], background=THEME["stats"]["bar_fill"], thickness=4)
    style.configure("Storage.Horizontal.TProgressbar",
        troughcolor=THEME["storage"]["bar_bg"], background=THEME["storage"]["bar_fill"], thickness=4)
    style.configure("Media.Horizontal.TProgressbar",
        troughcolor=THEME["media"]["bar_bg"], background=THEME["media"]["bar_fill"], thickness=0.5)

update_ttk_styles()

def make_card(parent, bg_path, border_path, row, col, rowspan=1, colspan=1, pad=8):
    frame = T(tk.Frame(parent, highlightthickness=1), bg=bg_path, highlightbackground=border_path)
    frame.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, padx=pad, pady=pad, sticky="nsew")
    return frame

def make_circle(parent, widthsize, heightsize, row, col, rowspan=1, colspan=1, pad=20, canvas_bg_path=None):
    canvas = tk.Canvas(parent, width=widthsize, height=heightsize, highlightthickness=0)
    T(canvas, bg=canvas_bg_path)
    canvas.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, padx=pad, pady=pad, sticky="nsew")

    outer_pad = 10
    canvas.create_oval(outer_pad, outer_pad, widthsize-outer_pad, heightsize-outer_pad, width=2, tags="static_oval",
                       outline=THEME["health"]["circle_border"], fill=THEME["health"]["circle_bg"])
    arc_id = canvas.create_arc(outer_pad, outer_pad, widthsize-outer_pad, heightsize-outer_pad, width=2, style="arc", start=90, extent=0)
    
    inner_pad = 25
    canvas.create_oval(inner_pad, inner_pad, widthsize-inner_pad, heightsize-inner_pad, width=2, tags="static_oval",
                       outline=THEME["health"]["circle_border"], fill=THEME["health"]["circle_bg"])
    inner_arc_id = canvas.create_arc(inner_pad, inner_pad, widthsize-inner_pad, heightsize-inner_pad, width=2, style="arc", start=90, extent=0)
    
    return canvas, arc_id, inner_arc_id

# -----------------------------------------------------------------------
# TOP BAR
# -----------------------------------------------------------------------
top_bar = T(tk.Frame(window, height=55), bg=("topbar", "bg"))
top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
top_bar.grid_propagate(False)
top_bar.grid_columnconfigure(2, weight=1)
top_bar.grid_rowconfigure(0, weight=1)

bottom_border = T(tk.Frame(window, height=2), bg=("topbar", "divider"))
bottom_border.grid(row=1, column=0, columnspan=3, sticky="ew")

top_bar.bind("<ButtonPress-1>", start_drag)
top_bar.bind("<B1-Motion>", do_drag)

try:
    if getattr(sys, 'frozen', False):
        # If running as .exe, PyInstaller extracts to a temp _MEIPASS folder
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        icon_path = os.path.join(base_path, 'assets', 'GridDash.ico')
    else:
        # If running as a normal .pyw script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        icon_path = os.path.join(project_root, 'assets', 'GridDash.ico')
    
    topbar_icon_img = Image.open(icon_path).resize((28, 28), Image.Resampling.LANCZOS)
    topbar_icon_tk = ImageTk.PhotoImage(topbar_icon_img)
    
    logo_label = T(tk.Label(top_bar, image=topbar_icon_tk, bd=0), bg=("topbar", "bg"))
    logo_label.image = topbar_icon_tk
    logo_label.grid(row=0, column=0, padx=(20, 15), sticky="w")
except Exception as e:
    logging.error(f"Failed to load topbar icon: {e}")
    T(tk.Label(top_bar, text="GridDash v1.0.0", font=live_font(11, "bold")), fg=("topbar", "title"), bg=("topbar", "bg")).grid(row=0, column=0, padx=(20, 15), sticky="w")

T(tk.Frame(top_bar, width=1, height=35), bg=("topbar", "divider")).grid(row=0, column=1)

center_frame = T(tk.Frame(top_bar), bg=("topbar", "bg"))
center_frame.grid(row=0, column=2, sticky="w", padx=(15,0))

clock_time = tk.StringVar()
T(tk.Label(center_frame, textvariable=clock_time, font=live_font(13, "bold"), pady=0, bd=0), fg=("topbar", "clock"), bg=("topbar", "bg")).grid(row=0, column=0, sticky="sw")

clock_date = tk.StringVar()
T(tk.Label(center_frame, textvariable=clock_date, font=live_font(8), pady=0, bd=0), fg=("topbar", "date"), bg=("topbar", "bg")).grid(row=1, column=0, sticky="nw")

right_bar = T(tk.Frame(top_bar), bg=("topbar", "bg"))
right_bar.grid(row=0, column=3, padx=20, sticky="e")

arduino_dot = T(tk.Label(right_bar, text="\uf111", font=(ICON_FONT, 8)), bg=("topbar", "bg"))
arduino_dot.grid(row=0, column=0, padx=(0,3))

arduino_text = T(tk.Label(right_bar, text="OFFLINE", font=live_font(8)), bg=("topbar", "bg"))
arduino_text.grid(row=0, column=1, padx=(0,15))

T(tk.Frame(right_bar, width=1, height=20), bg=("topbar", "divider")).grid(row=0, column=3, padx=(0,10))

T(tk.Button(right_bar, text="\uf013", relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=lambda: subprocess.Popen(["notepad", DASH_CONFIG])), fg=("topbar", "icons"), bg=("topbar", "bg"), activebackground=("topbar", "bg")).grid(row=0, column=4, padx=3)
T(tk.Button(right_bar, text="\uf120", relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=lambda: subprocess.Popen(["notepad", LOG_FILE])), fg=("topbar", "icons"), bg=("topbar", "bg"), activebackground=("topbar", "bg")).grid(row=0, column=5, padx=3)
T(tk.Button(right_bar, text="\uf068", relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=minimize_to_tray), fg=("topbar", "icons"), bg=("topbar", "bg"), activebackground=("topbar", "bg")).grid(row=0, column=6, padx=(3,0))

# -----------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------
window.grid_columnconfigure(0, weight=3)
window.grid_columnconfigure(1, weight=4)
window.grid_columnconfigure(2, weight=2)

layout_wrapper = T(tk.Frame(window), bg=("app", "bg"))
layout_wrapper.grid(row=2, column=0, columnspan=3, sticky="nsew")

layout_wrapper.grid_rowconfigure(0, weight=0) 
layout_wrapper.grid_rowconfigure(1, weight=1) 
layout_wrapper.grid_columnconfigure(0, weight=38) 
layout_wrapper.grid_columnconfigure(1, weight=25) 
layout_wrapper.grid_columnconfigure(2, weight=37) 

left_panel   = T(tk.Frame(layout_wrapper), bg=("app", "bg"))
center_panel = T(tk.Frame(layout_wrapper), bg=("app", "bg"))
right_panel  = T(tk.Frame(layout_wrapper), bg=("app", "bg"))

left_panel.grid_columnconfigure(0, weight=1)
center_panel.grid_columnconfigure(0, weight=1)
right_panel.grid_columnconfigure(0, weight=1)

left_panel.grid(row=0, column=0, sticky="nsew", padx=(7, 0), pady=(10, 0))
center_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=(10, 0))
right_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 7), pady=(10, 0))

# -----------------------------------------------------------------------
# LEFT PANEL
# -----------------------------------------------------------------------
def stat_card(parent, row, title, model_text, bar_style="Stats.Horizontal.TProgressbar"):
    card = make_card(parent, ("stats", "card_bg"), ("stats", "border"), row, 0)
    card.grid_columnconfigure(0, weight=1)
    
    T(tk.Label(card, text=title, font=live_font(9, "bold")), fg=("stats", "title"), bg=("stats", "card_bg")).grid(row=0, column=0, sticky="w", padx=10, pady=(8,0))
             
    pct_var = tk.StringVar(value="0%")
    T(tk.Label(card, textvariable=pct_var, font=live_font(9)), fg=("stats", "value"), bg=("stats", "card_bg")).grid(row=0, column=1, sticky="e", padx=10, pady=(8,0))
             
    bar = ttk.Progressbar(card, maximum=100, length=340, style=bar_style)
    bar.grid(row=1, column=0, columnspan=2, padx=10, pady=4, sticky="ew")
    
    T(tk.Label(card, text=model_text, font=live_font(7)), fg=("stats", "subtext"), bg=("stats", "card_bg")).grid(row=2, column=0, sticky="w", padx=10, pady=(0,8))
             
    sub_right = tk.StringVar(value="")
    T(tk.Label(card, textvariable=sub_right, font=live_font(7)), fg=("stats", "subtext"), bg=("stats", "card_bg")).grid(row=2, column=1, sticky="e", padx=10, pady=(0,8))
             
    return bar, pct_var, sub_right

def storage_card(parent, row):
    card = make_card(parent, ("storage", "card_bg"), ("storage", "border"), row, 0)
    card.grid_columnconfigure(0, weight=1)
    card.grid_columnconfigure(1, weight=1)
    
    T(tk.Label(card, text="STORAGE CLUSTERS", font=live_font(9, "bold")), fg=("storage", "title"), bg=("storage", "card_bg")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8,4))
    T(tk.Label(card, text="Main_Drive (C:)", font=live_font(7)), fg=("storage", "text"), bg=("storage", "card_bg")).grid(row=1, column=0, sticky="w", padx=10)
             
    stor_sub = tk.StringVar(value="— / —")
    T(tk.Label(card, textvariable=stor_sub, font=live_font(7)), fg=("storage", "text"), bg=("storage", "card_bg")).grid(row=1, column=1, sticky="e", padx=10)
             
    bar = ttk.Progressbar(card, maximum=100, length=340, style="Storage.Horizontal.TProgressbar")
    bar.grid(row=2, column=0, columnspan=2, padx=10, pady=(4,8), sticky="ew")
    return bar, stor_sub

def network_card(parent, row):
    card = make_card(parent, ("network", "card_bg"), ("network", "border"), row, 0)
    card.grid_columnconfigure(0, weight=1)
    card.grid_columnconfigure(1, weight=1)
    
    T(tk.Label(card, text="NETWORK TELEMETRY", font=live_font(9, "bold")), fg=("network", "title"), bg=("network", "card_bg")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8,4))
             
    # Upload Frame (Left aligned)
    up_frame = T(tk.Frame(card), bg=("network", "card_bg"))
    up_frame.grid(row=1, column=0, sticky="w", padx=10, pady=(0,8))
    
    T(tk.Label(up_frame, text="\uf062", font=(ICON_FONT, 9)), fg=("network", "up_icon"), bg=("network", "card_bg")).pack(side="left", padx=(0,4))
    net_up_sub = tk.StringVar(value="0 KB/s")
    T(tk.Label(up_frame, textvariable=net_up_sub, font=live_font(8)), fg=("network", "up_icon"), bg=("network", "card_bg")).pack(side="left")
             
    # Download Frame (Right aligned)
    down_frame = T(tk.Frame(card), bg=("network", "card_bg"))
    down_frame.grid(row=1, column=1, sticky="e", padx=10, pady=(0,8))
    
    T(tk.Label(down_frame, text="\uf063", font=(ICON_FONT, 9)), fg=("network", "down_icon"), bg=("network", "card_bg")).pack(side="left", padx=(0,4))
    net_down_sub = tk.StringVar(value="0 KB/s")
    T(tk.Label(down_frame, textvariable=net_down_sub, font=live_font(8)), fg=("network", "down_icon"), bg=("network", "card_bg")).pack(side="left")
             
    return net_up_sub, net_down_sub

cpu_bar,  cpu_pct,  cpu_sub  = stat_card(left_panel, 0, "CPU USAGE",  CPU_MODEL)
ram_bar,  ram_pct,  ram_sub  = stat_card(left_panel, 1, "RAM USAGE",  RAM_LABEL)
gpu_bar,  gpu_pct,  gpu_sub  = stat_card(left_panel, 2, "GPU USAGE",  GPU_MODEL)
stor_bar, stor_sub           = storage_card(left_panel, 3)
net_up_sub, net_down_sub     = network_card(left_panel, 4)

# -----------------------------------------------------------------------
# CENTER PANEL
# -----------------------------------------------------------------------
def get_sys_health():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    gpu = 0
    if nvml_available:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        except: pass
    score = ((100-cpu) * 0.35) + ((100-ram) * 0.40) + ((100-gpu) * 0.25)
    return round(score)

def sys_health_card(parent, card_row, width, height, circle_row, circle_col):
    card = make_card(parent, ("health", "card_bg"), ("health", "border"), card_row, 0)
    card.grid_rowconfigure(5, minsize=50)
    card.grid_rowconfigure(2, minsize=255)

    canvas, arc_id, inner_arc_id = make_circle(card, width, height, circle_row, circle_col, canvas_bg_path=("health", "card_bg"))

    T(tk.Label(card, text="SYSTEM HEALTH", font=live_font(10, "bold")), fg=("health", "title"), bg=("health", "card_bg")).grid(row=0, column=0, columnspan=2, sticky="nw", padx=10, pady=(8,0))

    status_label = T(tk.Label(card, text=sys_status[sys_stat_display], font=live_font(10, "bold")), bg=("health", "card_bg"))
    status_label.grid(row=1, column=0, columnspan=2, sticky="nw", padx=10, pady=(0,2))

    score_id  = canvas.create_text(width/2, height/2 - 10, text="0/100", fill=THEME["health"]["health_score"], font=live_font(18, "bold"))
    status_id = canvas.create_text(width/2, height/2 + 10, text=sys_label[sys_stat_display], fill=THEME["status"]["optimal"], font=live_font(8, "italic"))

    row_frame_core = T(tk.Frame(card), bg=("health", "box_core_bg"))
    row_frame_core.grid(row=3, column=0, columnspan=2, sticky="new", padx=10, pady=2)
    row_frame_core.grid_columnconfigure(0, weight=1)
    T(tk.Label(row_frame_core, text="CORE TEMPERATURE", font=live_font(7)), fg=("health", "box_text_dim"), bg=("health", "box_core_bg")).grid(row=0, column=0, sticky="w", padx=8, pady=4)
    T(tk.Label(row_frame_core, textvariable=core_temp, font=live_font(7)), fg=("health", "box_text"), bg=("health", "box_core_bg")).grid(row=0, column=1, sticky="e", padx=8, pady=4)

    row_frame_stab = T(tk.Frame(card), bg=("health", "box_stab_bg"))
    row_frame_stab.grid(row=4, column=0, columnspan=2, sticky="new", padx=10, pady=2)
    row_frame_stab.grid_columnconfigure(0, weight=1)
    T(tk.Label(row_frame_stab, text="STABILITY INDEX", font=live_font(7)), fg=("health", "box_text_dim"), bg=("health", "box_stab_bg")).grid(row=0, column=0, sticky="w", padx=8, pady=4)
    T(tk.Label(row_frame_stab, textvariable=stability_index, font=live_font(7)), fg=("health", "box_text"), bg=("health", "box_stab_bg")).grid(row=0, column=1, sticky="e", padx=8, pady=4)

    row_frame_runt = T(tk.Frame(card), bg=("health", "box_runt_bg"))
    row_frame_runt.grid(row=5, column=0, columnspan=2, sticky="new", padx=10, pady=2)
    row_frame_runt.grid_columnconfigure(0, weight=1)
    T(tk.Label(row_frame_runt, text="UPTIME", font=live_font(7)), fg=("health", "box_text_dim"), bg=("health", "box_runt_bg")).grid(row=0, column=0, sticky="w", padx=8, pady=4)
    T(tk.Label(row_frame_runt, textvariable=sys_runtime, font=live_font(7)), fg=("health", "box_text"), bg=("health", "box_runt_bg")).grid(row=0, column=1, sticky="e", padx=8, pady=4)

    return core_temp, stability_index, sys_runtime, canvas, arc_id, inner_arc_id, score_id, status_id, status_label

core_temp       = tk.StringVar(value="—")
stability_index = tk.StringVar(value="—")
sys_runtime     = tk.StringVar(value="—")

core_temp, stability_index, sys_runtime, canvas, arc_id, inner_arc_id, score_id, status_id, status_label = sys_health_card(center_panel, 0, 190, 190, 2, 0)

# -----------------------------------------------------------------------
# RIGHT PANEL
# -----------------------------------------------------------------------
def media_player_card(parent, row):
    card = make_card(parent, ("media", "card_bg"), ("media", "border"), row, 0)
    card.grid_columnconfigure(1, weight=1)

    album_label = T(tk.Label(card, width=12, height=6), bg=("media", "border"))
    album_label.grid(row=1, column=0, rowspan=5, padx=10, pady=8, sticky="w")

    song_title  = tk.StringVar(value="Song Name")
    T(tk.Label(card, textvariable=song_title, font=live_font(10, "bold")), fg=("media", "title"), bg=("media", "card_bg")).grid(row=1, column=1, sticky="nw", padx=0, pady=(18,0))
    
    artist_name = tk.StringVar(value="— Artist Name")
    T(tk.Label(card, textvariable=artist_name, font=live_font(8)), fg=("media", "artist"), bg=("media", "card_bg")).grid(row=2, column=1, sticky="nw", padx=0, pady=(0,4))
    
    track_bar = ttk.Progressbar(card, maximum=100, length=200, style="Media.Horizontal.TProgressbar")
    track_bar.grid(row=3, column=1, padx=(0,10), pady=(4,0), sticky="ew")
    
    time_frame = T(tk.Frame(card), bg=("media", "card_bg"))
    time_frame.grid(row=4, column=1, sticky="ew", padx=(0,10))
    time_frame.grid_columnconfigure(0, weight=1)

    time_current = tk.StringVar(value="0:00")
    T(tk.Label(time_frame, textvariable=time_current, font=live_font(7)), fg=("media", "time"), bg=("media", "card_bg")).grid(row=0, column=0, sticky="w")

    time_total = tk.StringVar(value="0:00")
    T(tk.Label(time_frame, textvariable=time_total, font=live_font(7)), fg=("media", "time"), bg=("media", "card_bg")).grid(row=0, column=1, sticky="e")

    btn_frame = T(tk.Frame(card), bg=("media", "card_bg"))
    btn_frame.grid(row=5, column=1, columnspan=2, pady=(0,8))

    T(tk.Button(btn_frame, text="\uf048", relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=lambda: pyautogui.press('prevtrack')), fg=("media", "controls_inactive"), bg=("media", "card_bg"), activebackground=("media", "card_bg")).grid(row=0, column=0, padx=8)

    play_pause_var = tk.StringVar(value="\uf04b")
    T(tk.Button(btn_frame, textvariable=play_pause_var, relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=lambda: pyautogui.press('playpause')), fg=("media", "controls_active"), bg=("media", "card_bg"), activebackground=("media", "card_bg")).grid(row=0, column=1, padx=8)

    T(tk.Button(btn_frame, text="\uf051", relief="flat", font=(ICON_FONT, 12), cursor="hand2", command=lambda: pyautogui.press('nexttrack')), fg=("media", "controls_inactive"), bg=("media", "card_bg"), activebackground=("media", "card_bg")).grid(row=0, column=2, padx=8)

    return album_label, song_title, artist_name, track_bar, time_current, time_total, play_pause_var

notepad_is_editing = False

def notepad_card(parent, row):
    card = make_card(parent, ("notepad", "card_bg"), ("notepad", "border"), row, 0)
    card.grid_columnconfigure(0, weight=1)

    T(tk.Label(card, text="NOTEPAD", font=live_font(10, "bold")), fg=("notepad", "title"), bg=("notepad", "card_bg")).grid(row=0, column=0, columnspan=2, sticky="nw", padx=10, pady=(8,0))
    
    text_sector = T(tk.Frame(card, height=98), bg=("notepad", "text_bg"))
    text_sector.grid(row=1, column=0, rowspan=3, sticky="ew", padx=15, pady=(10,20))
    text_sector.grid_propagate(False)

    notes_text = T(tk.Text(text_sector, font=live_font(8), bd=0, highlightthickness=0, wrap="word", padx=10, pady=10), bg=("notepad", "text_bg"), fg=("notepad", "text_fg"), insertbackground=("notepad", "cursor"))
    notes_text.place(relwidth=1, relheight=1)

    def on_focus_in(event):
        global notepad_is_editing
        notepad_is_editing = True
        if notes_text.get("1.0", "end-1c") == "System notes...":
            notes_text.delete("1.0", tk.END)

    def on_focus_out(event):
        global notepad_is_editing
        notepad_is_editing = False
        save_notes()

    def save_notes(event=None):
        dash_config["notes"] = notes_text.get("1.0", "end-1c")
        save_dash_config()
        window.focus_set()
        return "break"

    def cancel_notes(event=None):
        notes_text.delete("1.0", tk.END)
        saved = dash_config.get("notes", "")
        notes_text.insert("1.0", saved if saved.strip() else "System notes...")
        window.focus_set()
        return "break"

    def shift_enter(event=None):
        notes_text.insert(tk.INSERT, "\n")
        return "break"

    notes_text.bind("<FocusIn>", on_focus_in)
    notes_text.bind("<FocusOut>", on_focus_out)
    notes_text.bind("<Return>", save_notes)
    notes_text.bind("<Shift-Return>", shift_enter)
    notes_text.bind("<Escape>", cancel_notes)

    saved_notes = dash_config.get("notes", "")
    notes_text.insert("1.0", saved_notes if saved_notes.strip() else "System notes...")
    return notes_text

album_label, song_title, artist_name, track_bar, time_current, time_total, play_pause_var = media_player_card(right_panel, 0)
user_notes = notepad_card(right_panel, 1)

# -----------------------------------------------------------------------
# BOTTOM PANEL (Core Objectives)
# -----------------------------------------------------------------------
bottom_panel = T(tk.Frame(layout_wrapper), bg=("app", "bg"))
bottom_panel.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=(7, 7), pady=(0, 10))
bottom_panel.grid_columnconfigure(0, weight=1)
bottom_panel.grid_rowconfigure(0, weight=1)

bottom_card = make_card(bottom_panel, ("tasks", "card_bg"), ("tasks", "border"), 0, 0)
bottom_card.grid_columnconfigure(0, weight=2)
bottom_card.grid_columnconfigure(1, weight=1)
bottom_card.grid_rowconfigure(1, weight=1)

raw_tasks = dash_config.get("tasks", [])
task_data = []
for t in raw_tasks:
    if isinstance(t, str): task_data.append({"text": t, "done": False})
    elif isinstance(t, dict): task_data.append(t)

def sync_and_save():
    dash_config["tasks"] = task_data
    save_dash_config()
sync_and_save()

header_frame = T(tk.Frame(bottom_card), bg=("tasks", "card_bg"))
header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 10))

title_box = T(tk.Frame(header_frame), bg=("tasks", "card_bg"))
title_box.pack(side="left")

title_inner = T(tk.Frame(title_box), bg=("tasks", "card_bg"))
title_inner.pack(anchor="w")
T(tk.Label(title_inner, text="\uf046", font=(ICON_FONT, 10, "bold")), fg=("tasks", "header"), bg=("tasks", "card_bg")).pack(side="left", padx=(0,5))
T(tk.Label(title_inner, text="CORE OBJECTIVES", font=live_font(10, "bold")), fg=("tasks", "header"), bg=("tasks", "card_bg")).pack(side="left")

T(tk.Frame(title_box, height=1, width=250), bg=("tasks", "header_divider")).pack(anchor="w", pady=(2, 0))

prog_box_border = T(tk.Frame(header_frame, padx=1, pady=1), bg=("tasks", "header"))
prog_box_border.pack(side="right")
progress_val = T(tk.Label(prog_box_border, text="0/0 COMPLETED", font=live_font(8, "bold"), padx=5, pady=2), fg=("tasks", "prog_text"), bg=("tasks", "prog_box_bg"))
progress_val.pack()

T(tk.Label(header_frame, text="TODAY'S PROGRESS", font=live_font(8, "bold")), fg=("tasks", "prog_sub"), bg=("tasks", "card_bg")).pack(side="right", padx=(0, 10))

tasks_canvas = tk.Canvas(bottom_card, highlightthickness=0)
T(tasks_canvas, bg=("tasks", "card_bg"))
tasks_canvas.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

tasks_container = T(tk.Frame(tasks_canvas), bg=("tasks", "card_bg"))
tasks_window = tasks_canvas.create_window((0, 0), window=tasks_container, anchor="nw")

def configure_scroll_region(event):
    tasks_canvas.configure(scrollregion=tasks_canvas.bbox("all"))
    tasks_canvas.itemconfig(tasks_window, width=tasks_canvas.winfo_width())

tasks_container.bind("<Configure>", configure_scroll_region)
tasks_canvas.bind("<Configure>", configure_scroll_region)

def _on_mousewheel(event): tasks_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
tasks_canvas.bind("<Enter>", lambda e: tasks_canvas.bind_all("<MouseWheel>", _on_mousewheel))
tasks_canvas.bind("<Leave>", lambda e: tasks_canvas.unbind_all("<MouseWheel>"))

def make_mixed_btn(parent, icon_char, text_str, command, bg_path, fg_path, act_bg_path, act_fg_path):
    f = T(tk.Frame(parent, cursor="hand2"), bg=bg_path)
    f.pack(fill="both", expand=True)
    
    inner = T(tk.Frame(f, cursor="hand2"), bg=bg_path)
    inner.pack(expand=True, pady=3)
    
    lbl_i = T(tk.Label(inner, text=icon_char, font=(ICON_FONT, 8, "bold"), cursor="hand2"), fg=fg_path, bg=bg_path)
    lbl_i.pack(side="left", padx=(0, 4))
    
    lbl_t = T(tk.Label(inner, text=text_str, font=live_font(8, "bold"), cursor="hand2"), fg=fg_path, bg=bg_path)
    lbl_t.pack(side="left")
    
    def enter(e):
        c_bg = THEME[act_bg_path[0]][act_bg_path[1]]
        c_fg = THEME[act_fg_path[0]][act_fg_path[1]]
        f.config(bg=c_bg)
        inner.config(bg=c_bg)
        lbl_i.config(bg=c_bg, fg=c_fg)
        lbl_t.config(bg=c_bg, fg=c_fg)
        
    def leave(e):
        c_bg = THEME[bg_path[0]][bg_path[1]]
        c_fg = THEME[fg_path[0]][fg_path[1]]
        f.config(bg=c_bg)
        inner.config(bg=c_bg)
        lbl_i.config(bg=c_bg, fg=c_fg)
        lbl_t.config(bg=c_bg, fg=c_fg)
        
    def click(e):
        command()
        
    for w in (f, inner, lbl_i, lbl_t):
        w.bind("<Enter>", enter)
        w.bind("<Leave>", leave)
        w.bind("<Button-1>", click)
        
    return f

add_container = T(tk.Frame(bottom_card), bg=("tasks", "card_bg"))
add_container.grid(row=1, column=1, sticky="nwe", padx=15, pady=(0, 15))
add_container.grid_columnconfigure(0, weight=1)

new_task_var = tk.StringVar(value="ENTER NEW OBJECTIVE...")
task_entry = T(tk.Entry(add_container, textvariable=new_task_var, font=live_font(8), bd=0), bg=("tasks", "entry_bg"), fg=("tasks", "entry_fg"), insertbackground=("tasks", "entry_fg_active"))
task_entry.grid(row=0, column=0, sticky="ew", pady=(5,0))

T(tk.Frame(add_container, height=2), bg=("tasks", "entry_divider")).grid(row=1, column=0, sticky="ew", pady=(2, 10))

btn_border = T(tk.Frame(add_container, padx=1, pady=1), bg=("tasks", "add_border"))
btn_border.grid(row=2, column=0, sticky="ew")

make_mixed_btn(btn_border, "\uf067", "ADD TASK", lambda: add_task(), 
               ("tasks", "add_bg"), ("tasks", "add_fg"), 
               ("tasks", "add_active_bg"), ("tasks", "add_active_fg"))

purge_border = T(tk.Frame(add_container, padx=1, pady=1), bg=("tasks", "purge_border"))
purge_border.grid(row=3, column=0, sticky="ew", pady=(10, 0))

def purge_completed():
    global task_data
    task_data = [t for t in task_data if not t['done']]
    sync_and_save()
    render_tasks()

make_mixed_btn(purge_border, "\uf1f8", "PURGE COMPLETED", purge_completed, 
               ("tasks", "purge_bg"), ("tasks", "purge_fg"), 
               ("tasks", "purge_active_bg"), ("tasks", "purge_active_fg"))

def render_tasks():
    for widget in tasks_container.winfo_children(): widget.destroy()
    completed = sum(1 for t in task_data if t['done'])
    total = len(task_data)
    progress_val.config(text=f"{completed}/{total} COMPLETED")

    for i, task in enumerate(task_data):
        col, row = i % 2, i // 2
        icon = "\uf046" if task['done'] else "\uf096"
        color = THEME["tasks"]["task_done_icon"] if task['done'] else THEME["tasks"]["task_pend_icon"]
        text_color = THEME["tasks"]["task_done_text"] if task['done'] else THEME["tasks"]["task_pend_text"]
        
        t_frame = T(tk.Frame(tasks_container), bg=("tasks", "card_bg"))
        t_frame.grid(row=row, column=col, sticky="we", pady=6, padx=(0, 20))
        tasks_container.grid_columnconfigure(col, weight=1)
        
        cb = T(tk.Label(t_frame, text=icon, fg=color, font=(ICON_FONT, 13), cursor="hand2"), bg=("tasks", "card_bg"))
        cb.pack(side="left")
        
        lbl = T(tk.Label(t_frame, text=task['text'], fg=text_color, font=live_font(9, "bold"), cursor="hand2"), bg=("tasks", "card_bg"))
        lbl.pack(side="left", padx=(5,0))
        
        del_btn = T(tk.Label(t_frame, text="\uf00d", font=(ICON_FONT, 10), cursor="hand2"), fg=("tasks", "del_icon"), bg=("tasks", "card_bg"))
        del_btn.pack(side="right")
        
        cb.bind("<Button-1>", lambda e, idx=i: toggle_task(idx))
        lbl.bind("<Button-1>", lambda e, idx=i: toggle_task(idx))
        del_btn.bind("<Button-1>", lambda e, idx=i: delete_task(idx))

def toggle_task(index):
    task_data[index]['done'] = not task_data[index]['done']
    sync_and_save()
    render_tasks()

def delete_task(index):
    task_data.pop(index)
    sync_and_save()
    render_tasks()

def add_task(event=None):
    val = new_task_var.get().strip()
    if val and val != "ENTER NEW OBJECTIVE...":
        if len(val) > 25: val = val[:25] + "..."
        task_data.append({"text": val, "done": False})
        sync_and_save()
        new_task_var.set("")
        render_tasks()
        window.focus_set()

def on_entry_click(e):
    if new_task_var.get() == "ENTER NEW OBJECTIVE...":
        new_task_var.set("")
        task_entry.config(fg=THEME["tasks"]["entry_fg_active"])

def on_focus_out(e):
    if new_task_var.get() == "":
        new_task_var.set("ENTER NEW OBJECTIVE...")
        task_entry.config(fg=THEME["tasks"]["entry_fg"])

def cancel_entry(event=None):
    task_entry.delete("0", tk.END)
    sync_and_save()
    render_tasks()
    window.focus_set()
    return "break"

task_entry.bind("<FocusIn>", on_entry_click)
task_entry.bind("<FocusOut>", on_focus_out)
task_entry.bind("<Return>", add_task)
task_entry.bind("<Escape>", cancel_entry)
render_tasks()

# Gridflow status and connections

modes = ["TIME/DATE", "SYSTEM STATS", "STORAGE/NET", "MEDIA MODE", "CUSTOM TEXT"]
gridflow_card = make_card(right_panel, ("gridflow", "card_bg"), ("gridflow", "border"), 2, 0)
gridflow_card.grid_columnconfigure(0, weight=1)
gridflow_card.grid_columnconfigure(1, weight=1)

# --- Updated: Split Title and Settings Icon with Error Logic ---
gf_title_frame = T(tk.Frame(gridflow_card), bg=("gridflow", "card_bg"))
gf_title_frame.grid(row=0, column=0, sticky="w", padx=10, pady=(8,4))

T(tk.Label(gf_title_frame, text="GRIDFLOW STATUS", font=live_font(9, "bold")), fg=("gridflow", "title"), bg=("gridflow", "card_bg")).pack(side="left")

def open_gridflow_config():
    gf_config_path = os.path.join(os.environ['APPDATA'], 'GridFlow', 'gridflow_config.json')
    if os.path.exists(gf_config_path):
        try:
            subprocess.Popen(["notepad", gf_config_path])
        except Exception as e:
            logging.error(f"Failed to open Gridflow config: {e}")
    else:
        logging.warning("Gridflow config not found! The user may not have Gridflow installed.")

T(tk.Button(gf_title_frame, text="\uf013", relief="flat", font=(ICON_FONT, 9), cursor="hand2", 
            command=open_gridflow_config), 
  fg=("gridflow", "title"), bg=("gridflow", "card_bg"), activebackground=("gridflow", "card_bg")).pack(side="left", padx=(5,0))
# ----------------------------------------------

gf_status_frame = T(tk.Frame(gridflow_card), bg=("gridflow", "card_bg"))
gf_status_frame.grid(row=0, column=1, sticky="e", padx=10, pady=(8,4))
gridflow_status_icon = T(tk.Label(gf_status_frame, text="\uf111", font=(ICON_FONT, 8)), bg=("gridflow", "card_bg"))
gridflow_status_icon.pack(side="left", padx=(0,4))
gridflow_status_text = T(tk.Label(gf_status_frame, text="OFFLINE", font=live_font(8, "bold")), bg=("gridflow", "card_bg"))
gridflow_status_text.pack(side="left")

T(tk.Frame(gridflow_card, height=1), bg=("gridflow", "divider")).grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
T(tk.Label(gridflow_card, text="COMMUNICATION PORT", font=live_font(7)), fg=("gridflow", "label"), bg=("gridflow", "card_bg")).grid(row=2, column=0, sticky="w", padx=10, pady=(6,2))

gridflow_port = T(tk.Label(gridflow_card, text="—", font=live_font(7)), fg=("gridflow", "port"), bg=("gridflow", "card_bg"))
gridflow_port.grid(row=2, column=1, sticky="e", padx=10, pady=(6,2))

T(tk.Label(gridflow_card, text="CURRENT DISPLAY", font=live_font(7)), fg=("gridflow", "label"), bg=("gridflow", "card_bg")).grid(row=3, column=0, sticky="w", padx=10, pady=(2,8))

gridflow_mode = T(tk.Label(gridflow_card, text="—", font=live_font(7)), fg=("gridflow", "mode"), bg=("gridflow", "card_bg"))
gridflow_mode.grid(row=3, column=1, sticky="e", padx=10, pady=(2,8))

# -----------------------------------------------------------------------
# LIVE THEME & CONFIG WATCHER
# -----------------------------------------------------------------------
last_config_mtime = 0

def check_config_updates():
    global last_config_mtime, THEME, THEMED_WIDGETS
    try:
        current_mtime = os.path.getmtime(DASH_CONFIG)
        if last_config_mtime == 0:
            last_config_mtime = current_mtime
        elif current_mtime > last_config_mtime:
            last_config_mtime = current_mtime
            load_dash_config()
            
            # Update Window background
            window.configure(bg=THEME["app"]["bg"])
            update_ttk_styles()

            # Apply mapped styles to all registered live widgets
            active_widgets = []
            for widget, mapping in THEMED_WIDGETS:
                try:
                    config_args = {k: THEME[v[0]][v[1]] for k, v in mapping.items() if v}
                    widget.config(**config_args)
                    active_widgets.append((widget, mapping))
                except tk.TclError:
                    pass # widget was destroyed (e.g. deleted task)
            THEMED_WIDGETS = active_widgets

            # --- Live Font Engine Update ---
            new_family = THEME["font"]["main_font"]
            for f in LIVE_FONTS.values():
                f.configure(family=new_family)

            # Update Canvas static shapes
            canvas.itemconfig("static_oval", outline=THEME["health"]["circle_border"], fill=THEME["health"]["circle_bg"])
            canvas.itemconfig(score_id, fill=THEME["health"]["health_score"])
            
            render_tasks() # Ensure tasks get new pend/done colors applied
    except Exception as e:
        pass
    
    window.after(1000, check_config_updates)

# Start config watcher
window.after(1000, check_config_updates)

# -----------------------------------------------------------------------
# UPDATE LOOP
# -----------------------------------------------------------------------
def update_stats():
    now = datetime.now()
    clock_time.set(now.strftime("%H:%M:%S"))
    clock_date.set(now.strftime("%a // %b %d, %Y"))

    if arduino_connected:
        arduino_dot.config(fg=THEME["status"]["online"])
        arduino_text.config(text="GRIDFLOW CONNECTED", fg=THEME["status"]["online"])
        gridflow_status_icon.config(fg=THEME["status"]["online"])
        gridflow_status_text.config(text="CONNECTED", fg=THEME["status"]["online"])
        gridflow_port.config(text=arduino_port)
        shared = load_shared_status()
        current_mode = shared.get('display_mode', 0)
        gridflow_mode.config(text=modes[current_mode])
    else:
        arduino_dot.config(fg=THEME["status"]["offline"])
        arduino_text.config(text="OFFLINE", fg=THEME["topbar"]["icons"])
        gridflow_status_icon.config(fg=THEME["status"]["offline"])
        gridflow_status_text.config(text="OFFLINE", fg=THEME["status"]["offline"])
        gridflow_port.config(text="—")
        gridflow_mode.config(text="—")

    cpu      = psutil.cpu_percent()
    cpu_freq = psutil.cpu_freq()
    ghz      = f"{cpu_freq.current / 1000:.1f} GHz" if cpu_freq else ""
    cpu_bar["value"] = cpu
    cpu_pct.set(f"{cpu:.1f}%")
    cpu_sub.set(ghz)

    ram     = psutil.virtual_memory()
    used_gb = ram.used / (1024**3)
    ram_bar["value"] = ram.percent
    ram_pct.set(f"{ram.percent:.1f}%")
    ram_sub.set(f"{used_gb:.1f}GB USED")

    gpu_load = 0
    gpu_temp = ""
    if nvml_available:
        try:
            handle   = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_load = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            temp     = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            gpu_temp = f"{temp}°C"
        except: pass
    gpu_bar["value"] = gpu_load
    gpu_pct.set(f"{gpu_load:.1f}%")
    gpu_sub.set(gpu_temp)

    disk     = psutil.disk_usage('C:')
    used_tb  = disk.used  / (1024**4)
    total_tb = disk.total / (1024**4)
    stor_bar["value"] = disk.percent
    if total_tb >= 1:
        stor_sub.set(f"{used_tb:.1f}TB / {total_tb:.1f}TB")
    else:
        used_gb  = disk.used  / (1024**3)
        total_gb = disk.total / (1024**3)
        stor_sub.set(f"{used_gb:.1f}GB / {total_gb:.1f}GB")

    net_counters = psutil.net_io_counters()
    last_recv    = getattr(update_stats, 'last_recv', net_counters.bytes_recv)
    last_sent    = getattr(update_stats, 'last_sent', net_counters.bytes_sent)
    speed_down   = (net_counters.bytes_recv - last_recv) / 1024
    speed_up     = (net_counters.bytes_sent - last_sent) / 1024
    update_stats.last_recv = net_counters.bytes_recv
    update_stats.last_sent = net_counters.bytes_sent
    
    net_down_sub.set(f"{speed_down/1024:.1f} MB/s" if speed_down >= 1024 else f"{speed_down:.1f} KB/s")
    net_up_sub.set(f"{speed_up/1024:.1f} MB/s"   if speed_up   >= 1024 else f"{speed_up:.1f} KB/s")

    cpu_temp_number = 0
    try:
        w_temp    = wmi.WMI(namespace="root\\WMI")
        temp_info = w_temp.MSAcpi_ThermalZoneTemperature()
        cpu_temp_number = (temp_info[0].CurrentTemperature / 10) - 273.15
        core_temp.set(f"{cpu_temp_number:.1f}°C (CPU)")
    except:
        if nvml_available and gpu_temp:
            cpu_temp_number = int(gpu_temp.replace("°C", ""))
            core_temp.set(f"{cpu_temp_number}°C (GPU)")
        else:
            core_temp.set("N/A")

    score = get_sys_health()
    stability_index.set(f"{score:.1f}%")

    uptime_sec = time.time() - psutil.boot_time()
    days    = int(uptime_sec // 86400)
    hours   = int((uptime_sec % 86400) // 3600)
    minutes = int((uptime_sec % 3600) // 60)
    sys_runtime.set(f"{days}d {hours:02d}h {minutes:02d}m")

    global temp_color
    if   cpu_temp_number < 60: temp_color = THEME["status"]["cool_temp"]
    elif cpu_temp_number < 80: temp_color = THEME["status"]["warm_temp"]
    elif cpu_temp_number < 90: temp_color = THEME["status"]["hot_temp"]
    else:                      temp_color = THEME["status"]["danger_temp"]

    global sys_stat_display, sys_index_color
    if   score >= 80: sys_stat_display = 0; sys_index_color = THEME["status"]["optimal"]
    elif score >= 60: sys_stat_display = 1; sys_index_color = THEME["status"]["moderate"]
    elif score >= 40: sys_stat_display = 2; sys_index_color = THEME["status"]["elevated"]
    else:             sys_stat_display = 3; sys_index_color = THEME["status"]["critical"]

    canvas.itemconfig(arc_id,       outline=temp_color,     extent=min(cpu_temp_number * 3.6, 359))
    canvas.itemconfig(inner_arc_id, outline=sys_index_color, extent=score * 3.6)
    canvas.itemconfig(score_id,     text=f"{score}/100")
    canvas.itemconfig(status_id,    text=sys_label[sys_stat_display], fill=sys_index_color)
    status_label.config(text=f"STATUS: {sys_status[sys_stat_display]}", fg=sys_index_color)

    song_title.set(media_title[:20] + "..." if len(media_title) > 20 else media_title)

    if not media_artist == "——":
        artist_name.set("— " + media_artist[:20] + "..." if len(media_artist) > 18 else "— " + media_artist)
    else:
        artist_name.set(media_artist)

    if media_dur > 0:
        track_bar["maximum"] = media_dur
        track_bar["value"]   = media_pos
        def fmt(s): return f"{int(s)//60}:{int(s)%60:02d}"
        time_current.set(fmt(media_pos))
        time_total.set(fmt(media_dur))
    else:
        track_bar["value"] = 0
        time_current.set("0:00")
        time_total.set("0:00")

    if media_thumb:
        try:
            photo = ImageTk.PhotoImage(media_thumb)
            album_label.config(image=photo, width=96, height=96)
            album_label.image = photo 
        except: pass
    else:
        album_label.config(image="", width=12, height=6)
        album_label.image = None

    play_pause_var.set("\uf04c" if media_is_playing else "\uf04b")

    global notepad_is_editing
    if not notepad_is_editing:
        live_config = load_dash_config()
        saved_notes = live_config.get("notes", "")
        if not saved_notes.strip(): saved_notes = "System notes..."
        if user_notes.get("1.0", "end-1c") != saved_notes:
            user_notes.delete("1.0", tk.END)
            user_notes.insert("1.0", saved_notes)

    window.after(1000, update_stats)

def artist_media_update_loop():
    async def fetch():
        global media_artist
        while running:
            try:
                manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    props    = await session.try_get_media_properties_async()
                    media_artist = props.artist
                else: media_artist = "——"
            except: media_artist = "——"
            await asyncio.sleep(2) 
    asyncio.run(fetch())

def title_media_update_loop():
    async def fetch():
        global media_title
        while running:
            try:
                manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    props    = await session.try_get_media_properties_async()
                    media_title  = props.title
                else: media_title  = "No Media Playing"
            except: media_title  = "Media: Idle"
            await asyncio.sleep(2) 
    asyncio.run(fetch())

def timeline_media_update_loop():
    async def fetch():
        global media_pos, media_dur, media_is_playing
        while running:
            try:
                manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    timeline = session.get_timeline_properties()
                    media_pos    = timeline.position.total_seconds()
                    media_dur    = timeline.end_time.total_seconds()
                    playback_info = session.get_playback_info()
                    media_is_playing = (playback_info.playback_status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING)
                else:
                    media_pos, media_dur, media_is_playing = 0, 0, False
            except:
                media_pos, media_dur, media_is_playing = 0, 0, False
            await asyncio.sleep(1)
    asyncio.run(fetch())

def thumbnail_media_update_loop():
    async def fetch():
        global media_thumb
        last_title = None
        while running:
            try:
                manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    props = await session.try_get_media_properties_async()
                    if props.title != last_title:
                        last_title = props.title
                        if props.thumbnail:
                            stream_ref = props.thumbnail
                            stream = await stream_ref.open_read_async()
                            reader = streams.DataReader(stream)
                            await reader.load_async(stream.size)
                            img_buffer = bytearray(stream.size)
                            reader.read_bytes(img_buffer)
                            img = Image.open(io.BytesIO(img_buffer))
                            img = img.resize((96, 96), Image.Resampling.LANCZOS)
                            media_thumb = img
                        else: media_thumb = None
                else:
                    media_thumb, last_title = None, None
            except: media_thumb = None
            await asyncio.sleep(2)
    asyncio.run(fetch())

threading.Thread(target=artist_media_update_loop, daemon=True).start()
threading.Thread(target=title_media_update_loop, daemon=True).start()
threading.Thread(target=timeline_media_update_loop, daemon=True).start()
threading.Thread(target=thumbnail_media_update_loop, daemon=True).start()

arduino_connected = False
arduino_port      = "—"

def connection_manager():
    global arduino_connected, arduino_port
    logging.info("Connection Manager started.")
    while running:
        shared            = load_shared_status()
        arduino_connected = shared.get('connected', False)
        arduino_port      = shared.get('port', '—')
        time.sleep(5)

threading.Thread(target=connection_manager, daemon=True).start()
update_stats()
window.mainloop()