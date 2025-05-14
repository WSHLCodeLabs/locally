import os
import sys
import tkinter as tk
import zipfile
import socket
import threading
import webbrowser
import uuid
import http.server
import socketserver
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple
import json
from PIL import Image

# Set up CustomTkinter appearance and theme
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("./resources/themes/yellow.json")

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".locally", "settings.json")

class Settings:
    # Application settings storage and management
    def __init__(self):
        self.default_port_range = (8000, 9000)
        self.default_site_dir = os.path.join(os.path.expanduser("~"), ".locally", "sites")
        self.default_browser = "default"
        self.use_https = False
        self.https_certfile = ""
        self.https_keyfile = ""
        self.server_timeout = 60
        self.cors_enabled = False
        self.cors_origins = "*"
        self.appearance_mode = "System"
        self.ui_scaling = 1.0
        self.font_size = 12
        self.show_technical_details = True
        self.auto_start_sites = []
        self.remember_last_session = True
        self.start_minimized = False

    def to_dict(self):
        return self.__dict__

    def from_dict(self, d):
        self.__dict__.update(d)

    def save(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self):
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r") as f:
                self.from_dict(json.load(f))

class WebSite:
    # Represents a locally hosted website and its server
    def __init__(self, name: str, path: str, port: int = None, hostname: str = "localhost", settings: Settings = None):
        self.name = name
        self.path = path
        self.settings = settings
        self.port = port or self._find_free_port()
        self.hostname = hostname
        self.server_thread = None
        self.server = None
        self.is_running = False
        self.id = str(uuid.uuid4())[:8]
        
    def _find_free_port(self) -> int:
        # Find a free port for the web server
        if self.settings:
            min_port, max_port = self.settings.default_port_range
            for port in range(min_port, max_port + 1):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', port))
                        return port
                except OSError:
                    continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    def start(self) -> bool:
        # Start the web server for this site
        if self.is_running:
            return False
        os.chdir(self.path)
        parent_app = None
        if hasattr(self, 'settings') and hasattr(self.settings, 'parent_app'):
            parent_app = self.settings.parent_app
        class LoggingHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                msg = "%s - - [%s] %s\n" % (
                    self.client_address[0],
                    self.log_date_time_string(),
                    format % args
                )
                if parent_app:
                    parent_app.log_site(self.server.site_id, msg.strip())
                else:
                    with open(f"site_{self.server.site_id}.log", "a", encoding="utf-8") as f:
                        f.write(msg)
        handler = LoggingHandler
        try:
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.server.site_id = self.id
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.is_running = True
            return True
        except Exception as e:
            print(f"Error starting server: {e}")
            return False
    
    def stop(self) -> bool:
        # Stop the web server for this site
        if not self.is_running:
            return False
        try:
            self.server.shutdown()
            self.server.server_close()
            self.is_running = False
            return True
        except Exception as e:
            print(f"Error stopping server: {e}")
            return False
    
    def get_url(self) -> str:
        # Get the URL for the website
        return f"http://{self.hostname}:{self.port}"
    
    def __str__(self) -> str:
        status = "Running" if self.is_running else "Stopped"
        return f"{self.name} ({status}) - {self.get_url()}"

class LocalHostApp(ctk.CTk):
    # Main application window and logic
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.settings.load()
        self.title("Locally - Web Server Manager")
        self.geometry("900x600")
        self.minsize(800, 500)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./resources/images/icons/appicon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        self.websites: Dict[str, WebSite] = {}
        self.selected_site_id: Optional[str] = None
        self._create_ui()
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
    
    def _create_ui(self):
        # Build the main UI layout
        self.sidebar_frame = ctk.CTkFrame(self, width=200)
        self.sidebar_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(0, weight=0)
        self.sidebar_frame.grid_rowconfigure(1, weight=1)
        self.sidebar_frame.grid_rowconfigure(2, weight=0)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_title = ctk.CTkLabel(self.sidebar_frame, text="Your Locally Sites", font=ctk.CTkFont(size=16, weight="bold"))
        self.sidebar_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="Settings", command=self.open_settings_dialog)
        self.settings_btn.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.logs_btn = ctk.CTkButton(self.sidebar_frame, text="Show Application Logs", command=self.open_logs_dialog)
        self.logs_btn.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.sites_list_frame = ctk.CTkScrollableFrame(self.sidebar_frame)
        self.sites_list_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.sites_list_frame.grid_columnconfigure(0, weight=1)
        self.add_site_frame = ctk.CTkFrame(self.sidebar_frame)
        self.add_site_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.add_site_frame.grid_columnconfigure(0, weight=1)
        self.add_site_frame.grid_columnconfigure(1, weight=1)
        self.add_dir_btn = ctk.CTkButton(self.add_site_frame, text="Add Folder", command=self.add_site_from_directory)
        self.add_dir_btn.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        self.add_zip_btn = ctk.CTkButton(self.add_site_frame, text="Add ZIP", command=self.add_site_from_zip)
        self.add_zip_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_title = ctk.CTkLabel(self.content_frame, text="Welcome!", 
                                         font=ctk.CTkFont(size=20, weight="bold"))
        self.content_title.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.site_details_frame = ctk.CTkFrame(self.content_frame)
        self.site_details_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.site_details_frame.grid_columnconfigure(0, weight=1)
        self.site_details_frame.grid_columnconfigure(1, weight=2)
        self._update_site_details(None)
    
    def _update_sites_list(self):
        # Update the sidebar list of sites
        for widget in self.sites_list_frame.winfo_children():
            widget.destroy()
        for i, (site_id, site) in enumerate(self.websites.items()):
            site_frame = ctk.CTkFrame(self.sites_list_frame)
            site_frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            site_frame.grid_columnconfigure(0, weight=3)
            site_frame.grid_columnconfigure(1, weight=1)
            status_color = "#4CAF50" if site.is_running else "#F44336"
            status_indicator = "●" if site.is_running else "○"
            site_btn = ctk.CTkButton(
                site_frame, 
                text=f"{status_indicator} {site.name}", 
                fg_color="transparent", 
                text_color=("gray10", "gray90"),
                anchor="w",
                command=lambda sid=site_id: self._select_site(sid)
            )
            site_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
            action_text = "Stop" if site.is_running else "Start"
            action_btn = ctk.CTkButton(
                site_frame,
                text=action_text,
                width=70,
                command=lambda sid=site_id: self._toggle_site_status(sid)
            )
            action_btn.grid(row=0, column=1, padx=5, pady=5)
        if not self.websites:
            no_sites_label = ctk.CTkLabel(self.sites_list_frame, text="No sites added yet")
            no_sites_label.grid(row=0, column=0, padx=20, pady=20)
    
    def _update_site_details(self, site: Optional[WebSite]):
        # Update the right panel with site details or intro
        for widget in self.site_details_frame.winfo_children():
            widget.destroy()
        if not site:
            intro_frame = ctk.CTkFrame(self.site_details_frame)
            intro_frame.pack(expand=True, fill="both")
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./resources/images/icons/appicon.png")
            logo_img = ctk.CTkImage(light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(96, 96))
            logo_label = ctk.CTkLabel(intro_frame, image=logo_img, text="")
            logo_label.pack(pady=(40, 10))
            name_label = ctk.CTkLabel(intro_frame, text="Locally", font=ctk.CTkFont(size=28, weight="bold"))
            name_label.pack(pady=(0, 10))
            intro_text = "Start by selecting a site from the list or import a site using the buttons below."
            intro_label = ctk.CTkLabel(intro_frame, text=intro_text, font=ctk.CTkFont(size=14), wraplength=400, justify="center")
            intro_label.pack(pady=(0, 30))
            links_frame = ctk.CTkFrame(intro_frame, fg_color="transparent")
            links_frame.pack(pady=(10, 0))
            github_light = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./resources/images/icons/Github-dark.png")
            github_dark = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./resources/images/icons/Github.png")
            github_img = ctk.CTkImage(light_image=Image.open(github_light), dark_image=Image.open(github_dark), size=(32, 32))
            github_btn = ctk.CTkButton(links_frame, image=github_img, text="", width=40, fg_color="transparent", hover=False, command=lambda: webbrowser.open("https://github.com/WSHLCodeLabs/locally"))
            github_btn.pack(side="left", padx=10)
            return
        row = 0
        status_text = "Running" if site.is_running else "Stopped"
        status_color = "#4CAF50" if site.is_running else "#F44336"
        status_label = ctk.CTkLabel(self.site_details_frame, text="Status:")
        status_label.grid(row=row, column=0, padx=20, pady=(20, 10), sticky="w")
        status_value = ctk.CTkLabel(self.site_details_frame, text=status_text)
        status_value.grid(row=row, column=1, padx=20, pady=(20, 10), sticky="w")
        row += 1
        url_label = ctk.CTkLabel(self.site_details_frame, text="URL:")
        url_label.grid(row=row, column=0, padx=20, pady=10, sticky="w")
        url_frame = ctk.CTkFrame(self.site_details_frame)
        url_frame.grid(row=row, column=1, padx=20, pady=10, sticky="w")
        url_frame.grid_columnconfigure(0, weight=3)
        url_frame.grid_columnconfigure(1, weight=1)
        url_value = ctk.CTkLabel(url_frame, text=site.get_url())
        url_value.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="w")
        open_btn = ctk.CTkButton(url_frame, text="Open", width=70, command=lambda: webbrowser.open(site.get_url()))
        open_btn.grid(row=0, column=1, padx=0, pady=0)
        row += 1
        port_label = ctk.CTkLabel(self.site_details_frame, text="Port:")
        port_label.grid(row=row, column=0, padx=20, pady=10, sticky="w")
        port_value = ctk.CTkLabel(self.site_details_frame, text=str(site.port))
        port_value.grid(row=row, column=1, padx=20, pady=10, sticky="w")
        row += 1
        path_label = ctk.CTkLabel(self.site_details_frame, text="Directory:")
        path_label.grid(row=row, column=0, padx=20, pady=10, sticky="w")
        path_frame = ctk.CTkFrame(self.site_details_frame)
        path_frame.grid(row=row, column=1, padx=20, pady=10, sticky="ew")
        path_frame.grid_columnconfigure(0, weight=3)
        path_frame.grid_columnconfigure(1, weight=1)
        path_value = ctk.CTkLabel(path_frame, text=site.path)
        path_value.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="w")
        open_folder_btn = ctk.CTkButton(path_frame, text="Open Folder", width=100, 
                                      command=lambda: os.startfile(site.path) if sys.platform == 'win32' else os.system(f'open "{site.path}"'))
        open_folder_btn.grid(row=0, column=1, padx=0, pady=0)
        row += 1
        separator = ctk.CTkFrame(self.site_details_frame, height=2, fg_color=("gray70", "gray30"))
        separator.grid(row=row, column=0, columnspan=2, padx=20, pady=20, sticky="ew")
        row += 1
        actions_frame = ctk.CTkFrame(self.site_details_frame)
        actions_frame.grid(row=row, column=0, columnspan=2, padx=20, pady=20, sticky="ew")
        actions_frame.grid_columnconfigure((0, 1, 2), weight=1)
        toggle_text = "Stop Site" if site.is_running else "Start Site"
        toggle_btn = ctk.CTkButton(
            actions_frame, 
            text=toggle_text,
            command=lambda: self._toggle_site_status(site.id)
        )
        toggle_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        open_browser_btn = ctk.CTkButton(
            actions_frame,
            text="Open in Browser",
            command=lambda: webbrowser.open(site.get_url())
        )
        open_browser_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        delete_btn = ctk.CTkButton(
            actions_frame,
            text="Delete Site",
            fg_color="#F44336",
            hover_color="#D32F2F",
            command=lambda: self._delete_site(site.id)
        )
        delete_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        row += 1
        site_log_frame = ctk.CTkFrame(self.site_details_frame)
        site_log_frame.grid(row=row, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")
        site_log_frame.grid_columnconfigure(0, weight=1)
        log_label = ctk.CTkLabel(site_log_frame, text="Site Log:", font=ctk.CTkFont(size=12, weight="bold"))
        log_label.pack(anchor="w", padx=5, pady=(5, 0))
        log_text = ctk.CTkTextbox(site_log_frame, height=80, width=400, state="normal")
        log_text.pack(fill="x", padx=5, pady=5)
        log_text.insert("end", self.get_site_log(site.id))
        log_text.configure(state="disabled")
        clear_btn = ctk.CTkButton(site_log_frame, text="Clear Log", width=80, command=lambda sid=site.id: self.clear_site_log(sid))
        clear_btn.pack(anchor="e", padx=5, pady=(0, 5))
    
    def _select_site(self, site_id: str):
        # Select a site and show its details
        if site_id in self.websites:
            self.selected_site_id = site_id
            site = self.websites[site_id]
            self.content_title.configure(text=site.name)
            self._update_site_details(site)
    
    def _toggle_site_status(self, site_id: str):
        # Start or stop a site server
        if site_id in self.websites:
            site = self.websites[site_id]
            if site.is_running:
                success = site.stop()
                if success:
                    print(f"Site {site.name} stopped")
                    self.log_site(site_id, f"[STOP] Site {site.name} stopped at {__import__('datetime').datetime.now()}")
            else:
                success = site.start()
                if success:
                    print(f"Site {site.name} started at {site.get_url()}")
                    self.log_site(site_id, f"[START] Site {site.name} started at {__import__('datetime').datetime.now()}")
            self._update_sites_list()
            if self.selected_site_id == site_id:
                self._update_site_details(site)
    
    def _delete_site(self, site_id: str):
        # Delete a site from the app
        if site_id in self.websites:
            site = self.websites[site_id]
            confirm = messagebox.askyesno(
                "Confirm Deletion", 
                f"Are you sure you want to delete the site '{site.name}'?\n\nThis will stop the server if it's running."
            )
            if confirm:
                if site.is_running:
                    site.stop()
                del self.websites[site_id]
                self._update_sites_list()
                if self.selected_site_id == site_id:
                    self.selected_site_id = None
                    self.content_title.configure(text="Select a site or add a new one")
                    self._update_site_details(None)
    
    def add_site_from_directory(self):
        # Add a new site from a directory
        directory = filedialog.askdirectory(title="Select Website Directory")
        if not directory:
            return
        site_name = os.path.basename(directory)
        name_dialog = ctk.CTkInputDialog(text="Enter a name for this site:", title="Site Name")
        new_name = name_dialog.get_input()
        if new_name:
            site_name = new_name
        site = WebSite(name=site_name, path=directory, settings=self.settings)
        self.websites[site.id] = site
        self._update_sites_list()
        self._select_site(site.id)
        start = messagebox.askyesno(
            "Start Site", 
            f"Do you want to start the site '{site_name}' now?"
        )
        if start:
            self._toggle_site_status(site.id)
    
    def add_site_from_zip(self):
        # Add a new site from a ZIP file
        zip_file = filedialog.askopenfilename(
            title="Select Website ZIP File",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if not zip_file:
            return
        site_name = os.path.basename(zip_file).replace(".zip", "")
        name_dialog = ctk.CTkInputDialog(text="Enter a name for this site:", title="Site Name")
        new_name = name_dialog.get_input()
        if new_name:
            site_name = new_name
        extract_dir = os.path.join(os.path.expanduser("~"), ".localhost", "sites", site_name)
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            site = WebSite(name=site_name, path=extract_dir, settings=self.settings)
            self.websites[site.id] = site
            self._update_sites_list()
            self._select_site(site.id)
            start = messagebox.askyesno(
                "Start Site", 
                f"Do you want to start the site '{site_name}' now?"
            )
            if start:
                self._toggle_site_status(site.id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract ZIP file: {e}")

    def open_settings_dialog(self):
        # Open the settings dialog window
        for widget in self.winfo_children():
            if isinstance(widget, SettingsDialog):
                widget.focus()
                return
        dialog = SettingsDialog(self, self.settings)
        dialog.focus_force()
    
    def open_logs_dialog(self):
        # Open the application logs dialog
        if hasattr(self, '_logs_dialog') and self._logs_dialog.winfo_exists():
            self._logs_dialog.lift()
            return
        self._logs_dialog = LogsDialog(self)

    def log_app(self, message):
        # Log a message to the application log file
        with open("app.log", "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def log_site(self, site_id, message):
        # Log a message to a site's log file
        log_path = f"site_{site_id}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def get_app_log(self):
        # Retrieve the application log contents
        try:
            with open("app.log", "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return "No application logs yet."

    def clear_app_log(self):
        # Clear the application log file
        open("app.log", "w").close()

    def get_site_log(self, site_id):
        # Retrieve a site's log contents
        log_path = f"site_{site_id}.log"
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return "No logs yet."

    def clear_site_log(self, site_id):
        # Clear a site's log file
        log_path = f"site_{site_id}.log"
        open(log_path, "w").close()
        if self.selected_site_id == site_id:
            self._update_site_details(self.websites[site_id])

    def _apply_settings(self):
        # Apply settings changes to the application
        ctk.set_appearance_mode(self.settings.appearance_mode)
        ctk.set_widget_scaling(self.settings.ui_scaling)

class SettingsDialog(ctk.CTkToplevel):
    # Settings dialog window
    def __init__(self, parent, settings: Settings):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x600")
        self.settings = settings
        self.parent = parent
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = 500
        dialog_height = 600
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        self.resizable(True, True)
        self.minsize(500, 600)
        self.create_widgets()

    def create_widgets(self):
        # Build all settings widgets
        self.main_frame = ctk.CTkScrollableFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        credits_frame = ctk.CTkFrame(self.main_frame)
        credits_frame.pack(fill="x", padx=10, pady=(10, 20))
        credits_frame.grid_columnconfigure(1, weight=1)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./resources/images/icons/appicon.png")
        icon_img = ctk.CTkImage(light_image=Image.open(icon_path), dark_image=Image.open(icon_path), size=(48, 48))
        icon_label = ctk.CTkLabel(credits_frame, image=icon_img, text="")
        icon_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
        app_name_label = ctk.CTkLabel(credits_frame, text="Locally", font=ctk.CTkFont(size=20, weight="bold"))
        app_name_label.grid(row=0, column=1, sticky="w", padx=5, pady=(10, 0))
        author_label = ctk.CTkLabel(credits_frame, text="WSHLCodeLabs", font=ctk.CTkFont(size=12))
        author_label.grid(row=1, column=1, sticky="w", padx=5)
        version_label = ctk.CTkLabel(credits_frame, text="Version: 14052025", font=ctk.CTkFont(size=12))
        version_label.grid(row=2, column=1, sticky="w", padx=5)
        thx_label = ctk.CTkLabel(credits_frame, text="Thank you for using Locally! 🚀", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray")
        thx_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 0))
        thx_label2 = ctk.CTkLabel(credits_frame, text="Made beautifully with CustomTkinter. Github icons by icons8", font=ctk.CTkFont(size=11), text_color="gray")
        thx_label2.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 0))
        section1 = ctk.CTkLabel(self.main_frame, text="Default Settings", font=ctk.CTkFont(size=14, weight="bold"))
        section1.pack(pady=(20, 5), anchor="w", padx=20)
        port_frame = ctk.CTkFrame(self.main_frame)
        port_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(port_frame, text="Default Port Range:").pack(side="left")
        self.port_min = ctk.CTkEntry(port_frame, width=60)
        self.port_min.insert(0, str(self.settings.default_port_range[0]))
        self.port_min.pack(side="left", padx=5)
        ctk.CTkLabel(port_frame, text="-").pack(side="left")
        self.port_max = ctk.CTkEntry(port_frame, width=60)
        self.port_max.insert(0, str(self.settings.default_port_range[1]))
        self.port_max.pack(side="left", padx=5)
        dir_frame = ctk.CTkFrame(self.main_frame)
        dir_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(dir_frame, text="Default Site Directory:").pack(side="left")
        self.site_dir = ctk.CTkEntry(dir_frame, width=250)
        self.site_dir.insert(0, self.settings.default_site_dir)
        self.site_dir.pack(side="left", padx=5)
        browser_frame = ctk.CTkFrame(self.main_frame)
        browser_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(browser_frame, text="Default Browser:").pack(side="left")
        self.browser_entry = ctk.CTkEntry(browser_frame, width=120)
        self.browser_entry.insert(0, self.settings.default_browser)
        self.browser_entry.pack(side="left", padx=5)
        section2 = ctk.CTkLabel(self.main_frame, text="Server Settings", font=ctk.CTkFont(size=14, weight="bold"))
        section2.pack(pady=(20, 5), anchor="w", padx=20)
        self.https_var = tk.BooleanVar(value=self.settings.use_https)
        https_check = ctk.CTkCheckBox(self.main_frame, text="Enable HTTPS", variable=self.https_var)
        https_check.pack(anchor="w", padx=30)
        cert_frame = ctk.CTkFrame(self.main_frame)
        cert_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(cert_frame, text="Certificate File:").pack(side="left")
        self.cert_entry = ctk.CTkEntry(cert_frame, width=200)
        self.cert_entry.insert(0, self.settings.https_certfile)
        self.cert_entry.pack(side="left", padx=5)
        ctk.CTkLabel(cert_frame, text="Key File:").pack(side="left")
        self.key_entry = ctk.CTkEntry(cert_frame, width=200)
        self.key_entry.insert(0, self.settings.https_keyfile)
        self.key_entry.pack(side="left", padx=5)
        timeout_frame = ctk.CTkFrame(self.main_frame)
        timeout_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(timeout_frame, text="Server Timeout (s):").pack(side="left")
        self.timeout_entry = ctk.CTkEntry(timeout_frame, width=60)
        self.timeout_entry.insert(0, str(self.settings.server_timeout))
        self.timeout_entry.pack(side="left", padx=5)
        cors_frame = ctk.CTkFrame(self.main_frame)
        cors_frame.pack(fill="x", padx=20, pady=5)
        self.cors_var = tk.BooleanVar(value=self.settings.cors_enabled)
        ctk.CTkCheckBox(cors_frame, text="Enable CORS", variable=self.cors_var).pack(side="left")
        ctk.CTkLabel(cors_frame, text="Origins:").pack(side="left")
        self.cors_origins_entry = ctk.CTkEntry(cors_frame, width=120)
        self.cors_origins_entry.insert(0, self.settings.cors_origins)
        self.cors_origins_entry.pack(side="left", padx=5)
        section3 = ctk.CTkLabel(self.main_frame, text="UI Settings", font=ctk.CTkFont(size=14, weight="bold"))
        section3.pack(pady=(20, 5), anchor="w", padx=20)
        mode_frame = ctk.CTkFrame(self.main_frame)
        mode_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(mode_frame, text="Appearance Mode:").pack(side="left")
        self.mode_var = tk.StringVar(value=self.settings.appearance_mode)
        ctk.CTkOptionMenu(mode_frame, variable=self.mode_var, values=["System", "Dark", "Light"]).pack(side="left", padx=5)
        scaling_frame = ctk.CTkFrame(self.main_frame)
        scaling_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(scaling_frame, text="UI Scaling:").pack(side="left")
        self.scaling_entry = ctk.CTkEntry(scaling_frame, width=60)
        self.scaling_entry.insert(0, str(self.settings.ui_scaling))
        self.scaling_entry.pack(side="left", padx=5)
        font_frame = ctk.CTkFrame(self.main_frame)
        font_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(font_frame, text="Font Size:").pack(side="left")
        self.font_entry = ctk.CTkEntry(font_frame, width=60)
        self.font_entry.insert(0, str(self.settings.font_size))
        self.font_entry.pack(side="left", padx=5)
        self.tech_var = tk.BooleanVar(value=self.settings.show_technical_details)
        ctk.CTkCheckBox(self.main_frame, text="Show Technical Details", variable=self.tech_var).pack(anchor="w", padx=30)
        section4 = ctk.CTkLabel(self.main_frame, text="Startup Settings", font=ctk.CTkFont(size=14, weight="bold"))
        section4.pack(pady=(20, 5), anchor="w", padx=20)
        self.remember_var = tk.BooleanVar(value=self.settings.remember_last_session)
        ctk.CTkCheckBox(self.main_frame, text="Remember Last Session", variable=self.remember_var).pack(anchor="w", padx=30)
        self.minimize_var = tk.BooleanVar(value=self.settings.start_minimized)
        ctk.CTkCheckBox(self.main_frame, text="Start Minimized to Tray", variable=self.minimize_var).pack(anchor="w", padx=30)
        save_btn = ctk.CTkButton(self.main_frame, text="Save Settings", command=self.save_settings)
        save_btn.pack(pady=20)

    def save_settings(self):
        # Save all settings from UI to the settings object
        self.settings.default_port_range = (int(self.port_min.get()), int(self.port_max.get()))
        self.settings.default_site_dir = self.site_dir.get()
        self.settings.default_browser = self.browser_entry.get()
        self.settings.use_https = self.https_var.get()
        self.settings.https_certfile = self.cert_entry.get()
        self.settings.https_keyfile = self.key_entry.get()
        self.settings.server_timeout = int(self.timeout_entry.get())
        self.settings.cors_enabled = self.cors_var.get()
        self.settings.cors_origins = self.cors_origins_entry.get()
        self.settings.appearance_mode = self.mode_var.get()
        self.settings.ui_scaling = float(self.scaling_entry.get())
        self.settings.font_size = int(self.font_entry.get())
        self.settings.show_technical_details = self.tech_var.get()
        self.settings.remember_last_session = self.remember_var.get()
        self.settings.start_minimized = self.minimize_var.get()
        self.settings.save()
        self.parent._apply_settings()
        self.grab_release()
        self.destroy()
        
    def protocol(self, name, func):
        # Handle window close event
        if name == "WM_DELETE_WINDOW":
            def _close_handler():
                self.grab_release()
                func()
            return super().protocol(name, _close_handler)
        return super().protocol(name, func)

class LogsDialog(ctk.CTkToplevel):
    # Application logs dialog window
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Application Logs")
        self.geometry("700x300")
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.log_text = ctk.CTkTextbox(self, height=15, width=80, state="normal")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.insert("end", parent.get_app_log())
        self.log_text.configure(state="disabled")
        clear_btn = ctk.CTkButton(self, text="Clear Log", command=self.clear_log)
        clear_btn.pack(pady=(0, 10))
        self.parent = parent

    def clear_log(self):
        # Clear the application log from the dialog
        self.parent.clear_app_log()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "")
        self.log_text.configure(state="disabled")

if __name__ == "__main__":
    # Application entry point
    app = LocalHostApp()
    app.log_app(f"[START] Locally started at {__import__('datetime').datetime.now()}")
    app.mainloop()
    app.log_app(f"[STOP] Locally closed at {__import__('datetime').datetime.now()}")