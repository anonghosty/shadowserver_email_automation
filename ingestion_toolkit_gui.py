import sys
import os
import threading
import queue
import subprocess
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
import json
import time
import signal
import time
import random
from collections import deque
from customtkinter import CTkScrollbar
from resource_monitor import ResourceMonitorApp
import io
import csv

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AsyncConsoleRedirector:
    """Thread-safe console redirector with buffering"""
    def __init__(self, output_queue, max_buffer=1000):
        self.output_queue = output_queue
        self.buffer = deque(maxlen=max_buffer)
        self.lock = threading.Lock()

    def write(self, message):
        if message.strip():
            with self.lock:
                self.buffer.append(message.strip())
                if len(self.buffer) > 10:  # Batch send to reduce GUI updates
                    messages = list(self.buffer)
                    self.buffer.clear()
                    self.output_queue.put(("batch_output", messages))
                else:
                    self.output_queue.put(("output", message.strip()))

    def flush(self):
        with self.lock:
            if self.buffer:
                messages = list(self.buffer)
                self.buffer.clear()
                self.output_queue.put(("batch_output", messages))

class ProcessManager:
    """Manages running processes with proper cleanup"""
    def __init__(self):
        self.processes = {}
        self.lock = threading.Lock()
    
    def add_process(self, command, process):
        with self.lock:
            self.processes[command] = process
    
    def remove_process(self, command):
        with self.lock:
            if command in self.processes:
                del self.processes[command]
    
    def send_sigint(self, command):
        """Send SIGINT (Ctrl+C) to a process"""
        with self.lock:
            if command in self.processes:
                process = self.processes[command]
                try:
                    if process.poll() is None:  # Process is still running
                        if sys.platform == 'win32':
                            # On Windows, send Ctrl+C signal
                            process.send_signal(signal.CTRL_C_EVENT)
                        else:
                            # On Unix-like systems, send SIGINT to process group
                            os.killpg(os.getpgid(process.pid), signal.SIGINT)
                except Exception as e:
                    print(f"Error sending SIGINT to process {command}: {e}")
                    # Fallback to terminate if SIGINT fails
                    self.terminate_process(command)
    
    def terminate_process(self, command):
        """Terminate process (fallback method)"""
        with self.lock:
            if command in self.processes:
                process = self.processes[command]
                try:
                    if process.poll() is None:  # Process is still running
                        process.terminate()
                        # Give it a moment to terminate gracefully
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()  # Force kill if it doesn't terminate
                except Exception as e:
                    print(f"Error terminating process {command}: {e}")
                finally:
                    if command in self.processes:
                        del self.processes[command]
    
    def cleanup_all(self):
        """Clean up all processes on application exit"""
        with self.lock:
            for command, process in list(self.processes.items()):
                try:
                    if process.poll() is None:
                        # First try SIGINT
                        if sys.platform == 'win32':
                            process.send_signal(signal.CTRL_C_EVENT)
                        else:
                            os.killpg(os.getpgid(process.pid), signal.SIGINT)
                        
                        # Wait a bit for graceful shutdown
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            # If SIGINT didn't work, terminate
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()  # Last resort
                except Exception as e:
                    print(f"Error cleaning up process {command}: {e}")
            self.processes.clear()

class ModernCommandGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Shadow Command Center")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Thread-safe queues with larger capacity
        self.command_queue = queue.Queue()
        self.output_queue = queue.Queue(maxsize=10000)
        
        # Process management
        self.process_manager = ProcessManager()
        
        # Initialize UI attributes first
        self.console_text = None
        self.auto_scroll_var = None
        self.console_buffer = deque(maxlen=5000)
        
        # Archive folders to check
        self.archive_folders = {
            "sorted_attachments": {
                "path": "sorted_attachments",
                "description": "Organized email attachments by type"
            },
            "received_shadowserver_reports": {
                "path": "shadowserver_analysis_system/received_shadowserver_reports",
                "description": "Raw Shadowserver security reports"
            }
        }
        
        # Mapping files to edit
        self.mapping_files = {
            "env_file": {
                "path": ".env",
                "display_name": "Environmental Variables",
                "description": "Environment configuration settings",
                "type": "env",
                "icon": "š§"
            },
            "constituent_map": {
                "path": "shadowserver_analysis_system/detected_companies/constituent_map.csv",
                "display_name": "Constituent Map",
                "description": "Company constituent mapping configuration",
                "type": "csv",
                "icon": "š"
            }
        }
        
        # Form windows
        self.active_forms = {}
        
        # Available commands
        self.commands = {
            "email": {"color": "#FF6B6B", "icon": "š§", "desc": "Pull Emails Or Reports From API"},
            "migrate": {"color": "#4ECDC4", "icon": "š", "desc": "Unzip and Move Downloaded Files"},
            "refresh": {"color": "#45B7D1", "icon": "š", "desc": "Refresh ASN Metadata"},
            "process": {"color": "#96CEB4", "icon": "āļø", "desc": "Process Data By Cached ASN Data or Automaticaly Retrieve ASN Data"},
            "country": {"color": "#FFEAA7", "icon": "š", "desc": "Sort Processed Data By Country"},
            "service": {"color": "#DDA0DD", "icon": "š ļø", "desc": "Create Service Folders and Sort Per Organisation"},
            "ingest": {"color": "#FFB347", "icon": "š„", "desc": "Ingest Into Knowledgebase"},
            "all": {"color": "#FFB347", "icon": "ā”", "desc": "Run All Processes Related to Building the Knowledgebase"}
        }
        
        self.running_commands = set()
        self.command_history = []
        
        # Performance optimization flags
        self.batch_update_pending = False
        self.last_update_time = time.time()
        
        # Navigation dropdown state
        self.archive_dropdown_menu = None
        self.mapping_dropdown_menu = None
        self.dropdown_visible = False
        self.mapping_dropdown_visible = False
        
        self.setup_ui()
        self.setup_animations()
        self.start_output_monitor()
        
        # Handle application closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def check_folder_exists(self, folder_path):
        """Check if a folder exists and return status"""
        return os.path.exists(folder_path) and os.path.isdir(folder_path)
        
    def open_folder_in_explorer(self, folder_path):
        """Open folder in system file explorer"""
        try:
            if os.path.exists(folder_path):
                if sys.platform == "win32":
                    os.startfile(folder_path)
                elif sys.platform == "darwin":  # macOS
                    subprocess.run(["open", folder_path])
                else:  # Linux
                    subprocess.run(["xdg-open", folder_path])
                self.log_message(f"š Opened folder: {folder_path}", "info")
            else:
                self.log_message(f"ā Cannot open folder - does not exist: {folder_path}", "error")
        except Exception as e:
            self.log_message(f"ā Error opening folder {folder_path}: {str(e)}", "error")
        
    def setup_ui(self):
        """Setup the main UI components"""
        # Main container with padding
        main_frame = ctk.CTkFrame(self.root, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.create_header(main_frame)
        
        # Navigation bar
        self.create_navigation_bar(main_frame)
        
        # Command buttons section
        self.create_command_section(main_frame)
        
        # Console section
        self.create_console_section(main_frame)
        
        # Status bar
        self.create_status_bar(main_frame)
        
    def create_header(self, parent):
        """Create the header section"""
        header_frame = ctk.CTkFrame(parent, height=80, corner_radius=10)
        header_frame.pack(fill="x", padx=10, pady=(10, 15))
        header_frame.pack_propagate(False)
        
        # Title with gradient effect simulation
        title_label = ctk.CTkLabel(
            header_frame, 
            text="Shadow Command Center",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00D4FF"
        )
        title_label.pack(side="left", padx=20, pady=20)
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            header_frame,
            text="ā Ready",
            font=ctk.CTkFont(size=16),
            text_color="#00FF88"
        )
        self.status_indicator.pack(side="right", padx=20, pady=20)

    def create_navigation_bar(self, parent):
        nav_frame = ctk.CTkFrame(parent, height=60, corner_radius=10, fg_color=("#2B2B2B", "#1a1a1a"))
        nav_frame.pack(fill="x", padx=10, pady=(0, 15))
        nav_frame.pack_propagate(False)

        # Navigation container
        nav_container = ctk.CTkFrame(nav_frame, fg_color="transparent")
        nav_container.pack(fill="both", expand=True, padx=15, pady=8)

        # Archive Folders Dropdown
        self.create_archive_dropdown(nav_container)

        # Add separator
        separator = ctk.CTkFrame(nav_container, width=2, height=40, fg_color="#444444")
        separator.pack(side="left", padx=15, pady=5)

        # Mapping Files Dropdown
        self.create_mapping_dropdown(nav_container)

        # Add separator
        separator2 = ctk.CTkFrame(nav_container, width=2, height=40, fg_color="#444444")
        separator2.pack(side="left", padx=15, pady=5)

        # Report Generation dropdown
        report_options = {
            "Get Shadowserver Report Types": "get_shadowserver_report_types.py",
            "Generate Statistics Reported": "generate_statistics_reported_from_shadowserver_unverified.py",
            "Generate Malicious Reports": "generate_reported_malicious_communication_reports_old.py"
        }

        self.report_dropdown = ctk.CTkOptionMenu(
            nav_container,
            values=list(report_options.keys()),
            command=lambda choice: self.open_script_runner(report_options[choice], choice),
            width=180,              # wider for better look
            height=40,              # taller for better click area
            corner_radius=8,        # rounded corners
            font=ctk.CTkFont(size=14, weight="bold"),  # larger, bold font
            fg_color="#3B4252",     # dark slate background
        )
        self.report_dropdown.set("š Report Generation")
        self.report_dropdown.pack(side="left", padx=(10, 0))
        # Add separator
        separator3 = ctk.CTkFrame(nav_container, width=2, height=40, fg_color="#444444")
        separator3.pack(side="left", padx=15, pady=5)

        # Folder status indicator
        self.create_folder_status_indicator(nav_container)

        # Refresh folders button
        refresh_btn = ctk.CTkButton(
            nav_container,
            text="š Refresh",
            width=80,  # reduced width
            height=30, # reduced height
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#4ECDC4",
            hover_color="#45B7A8",
            command=self.refresh_folder_status
        )
        refresh_btn.pack(side="right", padx=(10, 0))

        # Resource Monitor button
        resource_monitor_btn = ctk.CTkButton(
            nav_container,
            text="š§  Resources",
            width=80,  # reduced width
            height=30,  # reduced height
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#6A82FB",
            hover_color="#576CDF",
            command=self.open_resource_monitor
        )
        resource_monitor_btn.pack(side="right", padx=(10, 0))


    def open_script_runner(self, script_path, display_name):
        if not os.path.isfile(script_path):
            print(f"Script not found: {script_path}")
            return

        runner_window = ctk.CTkToplevel()
        runner_window.title(f"{display_name}")
        runner_window.geometry("700x400")

        textbox = ctk.CTkTextbox(runner_window, wrap="word")
        textbox.pack(expand=True, fill="both", padx=10, pady=10)
        textbox.insert("end", f"ā¶ļø Running: {display_name}\n\n")
        textbox.configure(state="disabled")

        def append_line_safe(line):
            textbox.configure(state="normal")
            textbox.insert("end", line)
            textbox.see("end")
            textbox.configure(state="disabled")

        def run_script():
            try:
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )

                for line in iter(process.stdout.readline, ''):
                    runner_window.after(0, append_line_safe, line)

                process.stdout.close()
                process.wait()

                runner_window.after(0, append_line_safe, "\n\nā Done. Closing in 10 seconds...")

                def delayed_close():
                    time.sleep(10)
                    if runner_window.winfo_exists():
                        runner_window.destroy()

                threading.Thread(target=delayed_close, daemon=True).start()

            except Exception as e:
                runner_window.after(0, append_line_safe, f"\nā Error: {e}")

        threading.Thread(target=run_script, daemon=True).start()





    def open_resource_monitor(self):
        # Check if already open
        if hasattr(self, "resource_monitor_window") and self.resource_monitor_window.winfo_exists():
            self.resource_monitor_window.lift()  # Bring to front
        else:
            # Create new window instance
            self.resource_monitor_window = ResourceMonitorApp()
            self.resource_monitor_window.focus()

        
    def create_archive_dropdown(self, parent):
        """Create the Archive Folders dropdown menu"""
        dropdown_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dropdown_frame.pack(side="left", pady=5)
        
        # Main dropdown button
        self.archive_dropdown_btn = ctk.CTkButton(
            dropdown_frame,
            text="š Archive Folders ā¼",
            width=180,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#3B4252",
            hover_color="#434C5E",
            command=self.toggle_archive_dropdown
        )
        self.archive_dropdown_btn.pack()
        
        # Dropdown menu (initially hidden)
        self.archive_dropdown_menu = None
        self.dropdown_visible = False
        
    def create_folder_status_indicator(self, parent):
        """Create folder status indicator"""
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(side="left", padx=20)
        
        self.folder_status_label = ctk.CTkLabel(
            status_frame,
            text="š Checking folders...",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.folder_status_label.pack()
        
        # Initial folder check
        self.refresh_folder_status()
		
    def hide_dropdown(self):
        """Hide archive folders dropdown menu"""
        if self.archive_dropdown_menu:
            self.archive_dropdown_menu.destroy()
            self.archive_dropdown_menu = None

        self.archive_dropdown_btn.configure(
            text="š Archive Folders ā¼",
            fg_color="#3B4252"
        )
        self.dropdown_visible = False  # Archive dropdown flag

    def hide_mapping_dropdown(self):
        """Hide mapping files dropdown menu"""
        if self.mapping_dropdown_menu:
            self.mapping_dropdown_menu.destroy()
            self.mapping_dropdown_menu = None

        self.mapping_dropdown_btn.configure(
            text="š Mapping Files ā¼",
            fg_color="#5D4E75"
        )
    
        self.mapping_dropdown_visible = False  # Mapping dropdown flag
	
    def toggle_archive_dropdown(self):
        """Toggle the archive folders dropdown menu"""
        if self.dropdown_visible:
            self.hide_dropdown()
        else:
            self.show_dropdown()
			
    def toggle_mapping_dropdown(self):
        if self.mapping_dropdown_visible:
            self.hide_mapping_dropdown()
        else:
            self.show_mapping_dropdown()
		
    def create_mapping_dropdown(self, parent):
        """Create the Mapping Files dropdown menu"""
        dropdown_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dropdown_frame.pack(side="left", pady=5)
        
        # Main dropdown button
        self.mapping_dropdown_btn = ctk.CTkButton(
            dropdown_frame,
            text="š Mapping Files ā¼",
            width=180,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#5D4E75",
            hover_color="#6A5688",
            command=self.toggle_mapping_dropdown
        )
        self.mapping_dropdown_btn.pack()
        
    def toggle_mapping_dropdown(self):
        """Toggle the mapping files dropdown menu"""
        if self.mapping_dropdown_visible:
            self.hide_mapping_dropdown()
        else:
            self.show_mapping_dropdown()
            
    def show_mapping_dropdown(self):
        """Show the mapping files dropdown menu"""
        if self.mapping_dropdown_menu:
            self.hide_mapping_dropdown()
            
        # Create dropdown menu
        dropdown_x = self.mapping_dropdown_btn.winfo_rootx()
        dropdown_y = self.mapping_dropdown_btn.winfo_rooty() + self.mapping_dropdown_btn.winfo_height() + 5
        
        self.mapping_dropdown_menu = ctk.CTkToplevel(self.root)
        self.mapping_dropdown_menu.withdraw()  # Hide initially
        self.mapping_dropdown_menu.overrideredirect(True)
        self.mapping_dropdown_menu.configure(fg_color=("#2B2B2B", "#1a1a1a"))
        
        # Calculate menu width and height
        menu_width = 350
        menu_height = len(self.mapping_files) * 70 + 60
        
        self.mapping_dropdown_menu.geometry(f"{menu_width}x{menu_height}+{dropdown_x}+{dropdown_y}")
        
        # Menu header
        header_frame = ctk.CTkFrame(self.mapping_dropdown_menu, height=40, corner_radius=0, fg_color="#5D4E75")
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(
            header_frame,
            text="š Mapping Files",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ECEFF4"
        )
        header_label.pack(pady=10)
        
        # File items
        for file_key, file_info in self.mapping_files.items():
            self.create_mapping_dropdown_item(self.mapping_dropdown_menu, file_key, file_info)
            
        # Show menu with fade-in effect
        self.mapping_dropdown_menu.deiconify()
        self.mapping_dropdown_menu.attributes('-alpha', 0.0)
        self.fade_in_mapping_menu()
        
        # Update button appearance
        self.mapping_dropdown_btn.configure(
            text="š Mapping Files ā²",
            fg_color="#6A5688"
        )
        
        self.mapping_dropdown_visible = True
        
        # Bind click outside to close
        self.root.bind("<Button-1>", self.on_click_outside_mapping_dropdown)
        
    def create_mapping_dropdown_item(self, parent, file_key, file_info):
        """Create a dropdown menu item for a mapping file"""
        file_exists = os.path.exists(file_info["path"])
        
        item_frame = ctk.CTkFrame(parent, height=60, corner_radius=8, fg_color="transparent")
        item_frame.pack(fill="x", padx=10, pady=2)
        item_frame.pack_propagate(False)
        
        # Main item button
        item_btn = ctk.CTkFrame(item_frame, corner_radius=6, fg_color=("#E5E5E5", "#2D2D30"))
        item_btn.pack(fill="both", expand=True)
        
        # Content frame
        content_frame = ctk.CTkFrame(item_btn, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=8)
        
        # Left side - file info
        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        
        # File name with status icon
        status_icon = "ā" if file_exists else "ā"
        name_label = ctk.CTkLabel(
            left_frame,
            text=f"{status_icon} {file_info['icon']} {file_info['display_name']}",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            text_color="#2E3440" if file_exists else "#BF616A"
        )
        name_label.pack(fill="x")
        
        # File description
        desc_label = ctk.CTkLabel(
            left_frame,
            text=file_info["description"],
            font=ctk.CTkFont(size=10),
            anchor="w",
            text_color="#5E81AC"
        )
        desc_label.pack(fill="x")
        
        # Right side - action button
        if file_exists:
            action_btn = ctk.CTkButton(
                content_frame,
                text="āļø Edit",
                width=70,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#81A1C1",
                hover_color="#6F8CAF",
                command=lambda: self.open_file_editor(file_key, file_info)
            )
        else:
            action_btn = ctk.CTkButton(
                content_frame,
                text="ā Create",
                width=80,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#A3BE8C",
                hover_color="#8FA878",
                command=lambda: self.create_file_editor(file_key, file_info)
            )
        action_btn.pack(side="right", padx=(10, 0))
        
    def fade_in_mapping_menu(self):
        """Create fade-in effect for mapping dropdown menu"""
        if self.mapping_dropdown_menu and self.mapping_dropdown_menu.winfo_exists():
            current_alpha = self.mapping_dropdown_menu.attributes('-alpha')
            if current_alpha < 1.0:
                new_alpha = min(1.0, current_alpha + 0.1)
                self.mapping_dropdown_menu.attributes('-alpha', new_alpha)
                self.root.after(20, self.fade_in_mapping_menu)
                
    def hide_mapping_dropdown(self):
        """Hide the mapping files dropdown menu"""
        if self.mapping_dropdown_menu:
            self.mapping_dropdown_menu.destroy()
            self.mapping_dropdown_menu = None
            
        self.mapping_dropdown_btn.configure(
            text="š Mapping Files ā¼",
            fg_color="#5D4E75"
        )
        
        self.mapping_dropdown_visible = False
        self.root.unbind("<Button-1>")
        
    def on_click_outside_mapping_dropdown(self, event):
        """Handle clicking outside mapping dropdown to close it"""
        if self.mapping_dropdown_menu and event.widget not in [self.mapping_dropdown_menu, self.mapping_dropdown_btn]:
            try:
                dropdown_x = self.mapping_dropdown_menu.winfo_rootx()
                dropdown_y = self.mapping_dropdown_menu.winfo_rooty()
                dropdown_width = self.mapping_dropdown_menu.winfo_width()
                dropdown_height = self.mapping_dropdown_menu.winfo_height()
                
                click_x = event.x_root
                click_y = event.y_root
                
                if not (dropdown_x <= click_x <= dropdown_x + dropdown_width and 
                       dropdown_y <= click_y <= dropdown_y + dropdown_height):
                    self.hide_mapping_dropdown()
            except:
                self.hide_mapping_dropdown()
                
    def open_file_editor(self, file_key, file_info):
        """Open file editor for existing file"""
        self.hide_mapping_dropdown()
        if file_key in self.active_forms:
            # Bring existing form to front
            self.active_forms[file_key].lift()
            self.active_forms[file_key].focus()
            return
            
        try:
            with open(file_info["path"], 'r', encoding='utf-8') as f:
                content = f.read()
            self.create_file_form(file_key, file_info, content, is_new=False)
        except Exception as e:
            self.log_message(f"ā Error reading file {file_info['path']}: {str(e)}", "error")
            
    def create_file_editor(self, file_key, file_info):
        """Create new file editor"""
        self.hide_mapping_dropdown()
        if file_key in self.active_forms:
            self.active_forms[file_key].lift()
            self.active_forms[file_key].focus()
            return
            
        # Create default content based on file type
        if file_info["type"] == "env":
            default_content = "# Environment Variables\n# Add your configuration here\n\n"
        else:  # CSV
            default_content = "# CSV Mapping File\n# Add your mappings here\n\n"
            
        self.create_file_form(file_key, file_info, default_content, is_new=True)
        
    def create_file_form(self, file_key, file_info, content, is_new=False):
        """Create a reactive form for editing files"""
        # Create form window
        form_window = ctk.CTkToplevel(self.root)
        form_window.title(f"Edit {file_info['display_name']}")
        form_window.geometry("800x600")
        form_window.minsize(600, 400)
        
        # Configure window
        form_window.configure(fg_color=("#F0F0F0", "#1a1a1a"))
        self.active_forms[file_key] = form_window
        
        # Handle window closing
        form_window.protocol("WM_DELETE_WINDOW", lambda: self.close_file_form(file_key))
        
        # Main container
        main_container = ctk.CTkFrame(form_window, corner_radius=15)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.create_form_header(main_container, file_info, is_new)
        
        # Content area based on file type
        if file_info["type"] == "env":
            self.create_env_editor(main_container, file_key, file_info, content, is_new)
        elif file_info["type"] == "csv":
            self.create_csv_editor(main_container, file_key, file_info, content, is_new)
            
    def create_form_header(self, parent, file_info, is_new):
        """Create header for file form"""
        header_frame = ctk.CTkFrame(parent, height=80, corner_radius=10, fg_color="#3B4252")
        header_frame.pack(fill="x", padx=10, pady=(10, 15))
        header_frame.pack_propagate(False)
        
        # Title
        status_text = "Create New" if is_new else "Edit"
        title_label = ctk.CTkLabel(
            header_frame,
            text=f"{file_info['icon']} {status_text} {file_info['display_name']}",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#ECEFF4"
        )
        title_label.pack(side="left", padx=20, pady=20)
        
        # File path info
        path_label = ctk.CTkLabel(
            header_frame,
            text=f"š {file_info['path']}",
            font=ctk.CTkFont(size=12),
            text_color="#D8DEE9"
        )
        path_label.pack(side="right", padx=20, pady=20)
        
    def create_env_editor(self, parent, file_key, file_info, content, is_new):
        """Create environment variables editor with fields for KEY=VALUE pairs"""
        editor_frame = ctk.CTkFrame(parent, corner_radius=10)
        editor_frame.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        # Instructions
        inst_frame = ctk.CTkFrame(editor_frame, height=50, corner_radius=8, fg_color="#4C566A")
        inst_frame.pack(fill="x", padx=15, pady=15)
        inst_frame.pack_propagate(False)

        inst_label = ctk.CTkLabel(
            inst_frame,
            text="⚙ Enter environment variables as key-value pairs",
            font=ctk.CTkFont(size=12),
            text_color="#ECEFF4"
        )
        inst_label.pack(pady=15)

        # Scrollable frame for key-value rows
        scroll_container = ctk.CTkScrollableFrame(editor_frame, fg_color="#2E3440")
        scroll_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Parse content into dict
        env_vars = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

        # Store entries here for access on save
        self.env_entries = []

        # Create header row for the table
        header_frame = ctk.CTkFrame(scroll_container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0,5))
        ctk.CTkLabel(header_frame, text="Key", width=200, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5,0))
        ctk.CTkLabel(header_frame, text="Value", width=400, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5,0))

        # For each env var, create a row with two entries: key and value
        for key, val in env_vars.items():
            row_frame = ctk.CTkFrame(scroll_container, fg_color="#3B4252", corner_radius=8)
            row_frame.pack(fill="x", pady=3, padx=5)

            key_entry = ctk.CTkEntry(row_frame, width=200)
            key_entry.insert(0, key)
            key_entry.pack(side="left", padx=(5, 10), pady=5)

            val_entry = ctk.CTkEntry(row_frame, width=400)
            val_entry.insert(0, val)
            val_entry.pack(side="left", padx=(0, 5), pady=5)

            self.env_entries.append((key_entry, val_entry))

        # Add a button to add a new empty row
        add_row_btn = ctk.CTkButton(editor_frame, text="+ Add Variable", width=120, command=self.add_env_var_row)
        add_row_btn.pack(pady=(0, 10))

        # Store references for saving
        self.active_forms[file_key].env_entries = self.env_entries
        self.active_forms[file_key].file_info = file_info
        self.active_forms[file_key].is_new = is_new

        # Action buttons
        self.create_form_buttons(editor_frame, file_key, file_info, is_new)


    def add_env_var_row(self):
        """Helper function to add a new empty key-value row to the env editor"""

        # Find the current env editor scroll container (assumes only one active form open)
        # Or you can adjust this to pass form_window or parent if needed
        for form_window in self.active_forms.values():
            scroll_container = None
            for child in form_window.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ctk.CTkScrollableFrame):
                            scroll_container = subchild
                            break
                if scroll_container:
                    break

            if scroll_container:
                row_frame = ctk.CTkFrame(scroll_container, fg_color="#3B4252", corner_radius=8)
                row_frame.pack(fill="x", pady=3, padx=5)

                key_entry = ctk.CTkEntry(row_frame, width=200)
                key_entry.pack(side="left", padx=(5, 10), pady=5)

                val_entry = ctk.CTkEntry(row_frame, width=400)
                val_entry.pack(side="left", padx=(0, 5), pady=5)

                # Append new entries to the stored env_entries list
                if hasattr(form_window, 'env_entries'):
                    form_window.env_entries.append((key_entry, val_entry))

                break  # only add to the first found active form



    def create_csv_editor(self, parent, file_key, file_info, content, is_new):
        """Create CSV editor with a table/grid interface using Entry widgets"""
        import csv
        from io import StringIO

        editor_frame = ctk.CTkFrame(parent, corner_radius=10)
        editor_frame.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        # Instructions
        inst_frame = ctk.CTkFrame(editor_frame, height=50, corner_radius=8, fg_color="#4C566A")
        inst_frame.pack(fill="x", padx=15, pady=15)
        inst_frame.pack_propagate(False)

        inst_label = ctk.CTkLabel(
            inst_frame,
            text="🗒 Edit CSV data in grid - rows and columns editable",
            font=ctk.CTkFont(size=12),
            text_color="#ECEFF4"
        )
        inst_label.pack(pady=15)

        # Scrollable frame for the CSV grid
        scroll_container = ctk.CTkScrollableFrame(editor_frame, fg_color="#2E3440")
        scroll_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Parse CSV content
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)

        # If empty or new file, provide default CSV data
        if (not rows or len(rows) == 0 or (len(rows) == 1 and all(not c.strip() for c in rows[0]))) and is_new:
            rows = [
                ["column1", "column2", "column3"],
                ["value1", "value2", "value3"]
            ]

        self.csv_entries = []

        # Create grid of Entry widgets
        for r, row in enumerate(rows):
            row_entries = []
            for c, cell in enumerate(row):
                e = ctk.CTkEntry(scroll_container, width=120)
                e.grid(row=r, column=c, padx=2, pady=2)
                e.insert(0, cell)
                row_entries.append(e)
            self.csv_entries.append(row_entries)

        # Add buttons to add/remove rows and columns below the grid
        btn_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)

        def add_row():
            row_idx = len(self.csv_entries)
            row_entries = []
            for c in range(len(self.csv_entries[0]) if self.csv_entries else 3):
                e = ctk.CTkEntry(scroll_container, width=120)
                e.grid(row=row_idx, column=c, padx=2, pady=2)
                row_entries.append(e)
            self.csv_entries.append(row_entries)

        def add_column():
            col_idx = len(self.csv_entries[0]) if self.csv_entries else 0
            for r, row_entries in enumerate(self.csv_entries):
                e = ctk.CTkEntry(scroll_container, width=120)
                e.grid(row=r, column=col_idx, padx=2, pady=2)
                row_entries.append(e)

        def remove_row():
            if not self.csv_entries:
                return
            last_row = self.csv_entries.pop()
            for e in last_row:
                e.destroy()

        def remove_column():
            if not self.csv_entries or not self.csv_entries[0]:
                return
            col_idx = len(self.csv_entries[0]) - 1
            for row_entries in self.csv_entries:
                e = row_entries.pop()
                e.destroy()

        add_row_btn = ctk.CTkButton(btn_frame, text="Add Row", width=100, command=add_row)
        add_row_btn.pack(side="left", padx=5)
        remove_row_btn = ctk.CTkButton(btn_frame, text="Remove Row", width=100, command=remove_row)
        remove_row_btn.pack(side="left", padx=5)
        add_col_btn = ctk.CTkButton(btn_frame, text="Add Column", width=100, command=add_column)
        add_col_btn.pack(side="left", padx=5)
        remove_col_btn = ctk.CTkButton(btn_frame, text="Remove Column", width=120, command=remove_column)
        remove_col_btn.pack(side="left", padx=5)

        # Save reference for saving
        setattr(self.active_forms[file_key], 'csv_entries', self.csv_entries)
        setattr(self.active_forms[file_key], 'file_info', file_info)
        setattr(self.active_forms[file_key], 'is_new', is_new)

        # Action buttons
        self.create_form_buttons(editor_frame, file_key, file_info, is_new)

        
    def create_form_buttons(self, parent, file_key, file_info, is_new):
        """Create action buttons for file forms"""
        button_frame = ctk.CTkFrame(parent, height=60, corner_radius=8, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 15))
        button_frame.pack_propagate(False)
        
        # Left side - info
        info_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="y")
        
        status_text = "Creating new file" if is_new else "Editing existing file"
        status_label = ctk.CTkLabel(
            info_frame,
            text=f"š {status_text}",
            font=ctk.CTkFont(size=12),
            text_color="#5E81AC"
        )
        status_label.pack(pady=20)
        
        # Right side - buttons
        btn_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        btn_frame.pack(side="right", pady=10)
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="ā Cancel",
            width=100,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#BF616A",
            hover_color="#A54B5B",
            command=lambda: self.close_file_form(file_key)
        )
        cancel_btn.pack(side="left", padx=5)
        
        # Save button
        save_btn = ctk.CTkButton(
            btn_frame,
            text="š¾ Save",
            width=100,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#A3BE8C",
            hover_color="#8FA878",
            command=lambda: self.save_file(file_key)
        )
        save_btn.pack(side="left", padx=5)
        
        # Save & Close button
        save_close_btn = ctk.CTkButton(
            btn_frame,
            text="š¾ Save & Close",
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#5E81AC",
            hover_color="#4C6B8A",
            command=lambda: self.save_and_close_file(file_key)
        )
        save_close_btn.pack(side="left", padx=5)
    def save_file(self, file_key):
        """Save file content"""
        if file_key not in self.active_forms:
            return

        form_window = self.active_forms[file_key]
        file_info = form_window.file_info

        try:
            if file_info["type"] == "env":
                # Collect key=value pairs from env_entries
                env_pairs = []
                for key_entry, val_entry in getattr(form_window, "env_entries", []):
                    key = key_entry.get().strip()
                    val = val_entry.get().strip()
                    if key:  # only save entries with a key
                        env_pairs.append(f"{key}={val}")
                content = "\n".join(env_pairs)

            elif file_info["type"] == "csv":
                # Collect CSV data from grid entries
                csv_rows = []
                for row_entries in getattr(form_window, "csv_entries", []):
                    row_values = [e.get() for e in row_entries]
                    csv_rows.append(row_values)


                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerows(csv_rows)
                content = output.getvalue()

            else:
                # For other types, get content from text_widget
                text_widget = getattr(form_window, "text_widget", None)
                if not text_widget:
                    self.log_message(f"Error: No text widget found for {file_info['display_name']}", "error")
                    return
                content = text_widget.get("1.0", tk.END).rstrip()

            # Create directory if it doesn't exist
            file_dir = os.path.dirname(file_info["path"])
            if file_dir and not os.path.exists(file_dir):
                os.makedirs(file_dir, exist_ok=True)
                self.log_message(f"š Created directory: {file_dir}", "info")

            # Save file
            with open(file_info["path"], 'w', encoding='utf-8') as f:
                f.write(content)

            self.log_message(f"š¾ Successfully saved: {file_info['display_name']}", "success")

            # Update form status
            form_window.is_new = False

            # Refresh status indicators
            self.refresh_folder_status()

        except Exception as e:
            self.log_message(f"ā Error saving {file_info['display_name']}: {str(e)}", "error")


    def save_and_close_file(self, file_key):
        self.log_message(f"Attempting to save and close form for: {file_key}", "info")
        self.save_file(file_key)
        self.log_message(f"Save complete, now closing form for: {file_key}", "info")
        self.close_file_form(file_key)



        
    def close_file_form(self, file_key):
        """Close file form"""
        if file_key in self.active_forms:
            self.active_forms[file_key].destroy()
            del self.active_forms[file_key]
        """Toggle the archive folders dropdown menu"""
        if self.dropdown_visible:
            self.hide_dropdown()
        else:
            self.show_dropdown()
            
    def show_dropdown(self):
        """Show the archive folders dropdown menu"""
        # Close mapping dropdown if open
        if self.mapping_dropdown_visible:
            self.hide_mapping_dropdown()
            
        if self.archive_dropdown_menu:
            self.hide_dropdown()
            
        # Create dropdown menu
        dropdown_x = self.archive_dropdown_btn.winfo_rootx()
        dropdown_y = self.archive_dropdown_btn.winfo_rooty() + self.archive_dropdown_btn.winfo_height() + 5
        
        self.archive_dropdown_menu = ctk.CTkToplevel(self.root)
        self.archive_dropdown_menu.withdraw()  # Hide initially
        self.archive_dropdown_menu.overrideredirect(True)
        self.archive_dropdown_menu.configure(fg_color=("#2B2B2B", "#1a1a1a"))
        
        # Calculate menu width
        menu_width = 320
        menu_height = len(self.archive_folders) * 70 + 80
        
        self.archive_dropdown_menu.geometry(f"{menu_width}x{menu_height}+{dropdown_x}+{dropdown_y}")
        
        # Menu header
        header_frame = ctk.CTkFrame(self.archive_dropdown_menu, height=40, corner_radius=0, fg_color="#3B4252")
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(
            header_frame,
            text="š Archive Folders",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ECEFF4"
        )
        header_label.pack(pady=10)
        
        # Folder items
        for folder_name, folder_info in self.archive_folders.items():
            self.create_dropdown_item(self.archive_dropdown_menu, folder_name, folder_info)
            
        # Add "Run All" option at the bottom
        self.create_run_all_item(self.archive_dropdown_menu)
        
        # Show menu with fade-in effect
        self.archive_dropdown_menu.deiconify()
        self.archive_dropdown_menu.attributes('-alpha', 0.0)
        self.fade_in_menu()
        
        # Update button appearance
        self.archive_dropdown_btn.configure(
            text="š Archive Folders ā²",
            fg_color="#434C5E"
        )
        
        self.dropdown_visible = True
        
        # Bind click outside to close
        self.root.bind("<Button-1>", self.on_click_outside_dropdown)
        
    def create_dropdown_item(self, parent, folder_name, folder_info):
        """Create a dropdown menu item for a folder"""
        folder_exists = self.check_folder_exists(folder_info["path"])
        
        item_frame = ctk.CTkFrame(parent, height=60, corner_radius=8, fg_color="transparent")
        item_frame.pack(fill="x", padx=10, pady=2)
        item_frame.pack_propagate(False)
        
        # Main item button
        item_btn = ctk.CTkFrame(item_frame, corner_radius=6, fg_color=("#E5E5E5", "#2D2D30"))
        item_btn.pack(fill="both", expand=True)
        
        # Content frame
        content_frame = ctk.CTkFrame(item_btn, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=8)
        
        # Left side - folder info
        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        
        # Folder name with status icon
        status_icon = "ā" if folder_exists else "ā"
        name_label = ctk.CTkLabel(
            left_frame,
            text=f"{status_icon} {folder_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            text_color="#2E3440" if folder_exists else "#BF616A"
        )
        name_label.pack(fill="x")
        
        # Folder description
        desc_label = ctk.CTkLabel(
            left_frame,
            text=folder_info["description"],
            font=ctk.CTkFont(size=10),
            anchor="w",
            text_color="#5E81AC"
        )
        desc_label.pack(fill="x")
        
        # Right side - action button
        if folder_exists:
            action_btn = ctk.CTkButton(
                content_frame,
                text="š Open",
                width=70,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#A3BE8C",
                hover_color="#8FA878",
                command=lambda: self.open_folder_action(folder_info["path"])
            )
        else:
            action_btn = ctk.CTkButton(
                content_frame,
                text="ā ļø Missing",
                width=80,
                height=30,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#BF616A",
                hover_color="#A54B5B",
                command=lambda: self.suggest_run_all(folder_name)
            )
        action_btn.pack(side="right", padx=(10, 0))
        
    def create_run_all_item(self, parent):
        """Create the 'Run All' item at the bottom of dropdown"""
        # Separator
        separator = ctk.CTkFrame(parent, height=1, fg_color="#444444")
        separator.pack(fill="x", padx=20, pady=5)
        
        # Run All button
        run_all_frame = ctk.CTkFrame(parent, height=40, corner_radius=8, fg_color="transparent")
        run_all_frame.pack(fill="x", padx=10, pady=5)
        run_all_frame.pack_propagate(False)
        
        run_all_btn = ctk.CTkButton(
            run_all_frame,
            text="ā” Run All Commands (Creates Missing Folders)",
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#FFB347",
            hover_color="#E5A042",
            command=self.run_all_from_dropdown
        )
        run_all_btn.pack(fill="x", padx=5, pady=2)
        
    def open_folder_action(self, folder_path):
        """Handle opening folder from dropdown"""
        self.hide_dropdown()
        self.open_folder_in_explorer(folder_path)
        
    def suggest_run_all(self, folder_name):
        """Suggest running 'all' command when folder is missing"""
        self.hide_dropdown()
        self.log_message(f"ā ļø Folder '{folder_name}' does not exist!", "warning")
        self.log_message("š” Suggestion: Run the 'ALL' command to create missing folders and build the complete system", "info")
        self.log_message("š Click the 'ALL' button below or use 'Run All Commands' from Archive Folders menu", "info")
        
    def run_all_from_dropdown(self):
        """Run 'all' command from dropdown menu"""
        self.hide_dropdown()
        self.log_message("š Running ALL commands from Archive Folders menu...", "info")
        self.execute_command("all")
        
    def fade_in_menu(self):
        """Create fade-in effect for dropdown menu"""
        if self.archive_dropdown_menu and self.archive_dropdown_menu.winfo_exists():
            current_alpha = self.archive_dropdown_menu.attributes('-alpha')
            if current_alpha < 1.0:
                new_alpha = min(1.0, current_alpha + 0.1)
                self.archive_dropdown_menu.attributes('-alpha', new_alpha)
                self.root.after(20, self.fade_in_menu)
                
 
        self.root.unbind("<Button-1>")
        
    def on_click_outside_dropdown(self, event):
        """Handle clicking outside dropdown to close it"""
        if self.archive_dropdown_menu and event.widget not in [self.archive_dropdown_menu, self.archive_dropdown_btn]:
            # Check if click was inside dropdown
            try:
                dropdown_x = self.archive_dropdown_menu.winfo_rootx()
                dropdown_y = self.archive_dropdown_menu.winfo_rooty()
                dropdown_width = self.archive_dropdown_menu.winfo_width()
                dropdown_height = self.archive_dropdown_menu.winfo_height()
                
                click_x = event.x_root
                click_y = event.y_root
                
                if not (dropdown_x <= click_x <= dropdown_x + dropdown_width and 
                       dropdown_y <= click_y <= dropdown_y + dropdown_height):
                    self.hide_dropdown()
            except:
                self.hide_dropdown()
                
        # Also check mapping dropdown
        if self.mapping_dropdown_menu and event.widget not in [self.mapping_dropdown_menu, self.mapping_dropdown_btn]:
            try:
                dropdown_x = self.mapping_dropdown_menu.winfo_rootx()
                dropdown_y = self.mapping_dropdown_menu.winfo_rooty()
                dropdown_width = self.mapping_dropdown_menu.winfo_width()
                dropdown_height = self.mapping_dropdown_menu.winfo_height()
                
                click_x = event.x_root
                click_y = event.y_root
                
                if not (dropdown_x <= click_x <= dropdown_x + dropdown_width and 
                       dropdown_y <= click_y <= dropdown_y + dropdown_height):
                    self.hide_mapping_dropdown()
            except:
                self.hide_mapping_dropdown()
                
    def refresh_folder_status(self):
        """Refresh the folder status indicator"""
        existing_folders = 0
        total_folders = len(self.archive_folders)
        
        for folder_name, folder_info in self.archive_folders.items():
            if self.check_folder_exists(folder_info["path"]):
                existing_folders += 1
                
        # Also check mapping files
        existing_files = 0
        total_files = len(self.mapping_files)
        
        for file_key, file_info in self.mapping_files.items():
            if os.path.exists(file_info["path"]):
                existing_files += 1
                
        if existing_folders == total_folders and existing_files == total_files:
            status_text = f"ā All ready ({existing_folders}/{total_folders} folders, {existing_files}/{total_files} files)"
            status_color = "#A3BE8C"
        elif existing_folders > 0 or existing_files > 0:
            status_text = f"ā ļø Partial setup ({existing_folders}/{total_folders} folders, {existing_files}/{total_files} files)"
            status_color = "#EBCB8B"
        else:
            status_text = f"ā Setup needed ({existing_folders}/{total_folders} folders, {existing_files}/{total_files} files)"
            status_color = "#BF616A"
            
        if hasattr(self, 'folder_status_label'):
            self.folder_status_label.configure(
                text=status_text,
                text_color=status_color
            )
        
        # Log folder status
        self.log_message(f"š System Status: {status_text}", "info")
        
    def on_closing(self):
        """Handle application closing"""
        # Hide dropdowns if visible
        if self.dropdown_visible:
            self.hide_dropdown()
        if self.mapping_dropdown_visible:
            self.hide_mapping_dropdown()

        # Close all active forms
        for file_key in list(self.active_forms.keys()):
            self.close_file_form(file_key)

        # Stop all running processes
        self.process_manager.cleanup_all()

        # Clear running commands
        self.running_commands.clear()

        # Destroy the window
        self.root.destroy()

    def on_click_outside_mapping_dropdown(self, event):
        """Hide mapping dropdown if clicked outside of it"""
        try:
            dropdown_x = self.archive_dropdown_menu.winfo_rootx()
            dropdown_y = self.archive_dropdown_menu.winfo_rooty()
            dropdown_width = self.archive_dropdown_menu.winfo_width()
            dropdown_height = self.archive_dropdown_menu.winfo_height()

            click_x = event.x_root
            click_y = event.y_root

            if not (dropdown_x <= click_x <= dropdown_x + dropdown_width and 
                    dropdown_y <= click_y <= dropdown_y + dropdown_height):
                self.hide_mapping_dropdown()
        except Exception:
            self.hide_mapping_dropdown()

                
    def refresh_folder_status(self):
        """Refresh the folder status indicator"""
        existing_folders = 0
        total_folders = len(self.archive_folders)
        
        for folder_name, folder_info in self.archive_folders.items():
            if self.check_folder_exists(folder_info["path"]):
                existing_folders += 1
                
        if existing_folders == total_folders:
            status_text = f"ā All folders ready ({existing_folders}/{total_folders})"
            status_color = "#A3BE8C"
        elif existing_folders > 0:
            status_text = f"ā ļø Some folders missing ({existing_folders}/{total_folders})"
            status_color = "#EBCB8B"
        else:
            status_text = f"ā No folders found ({existing_folders}/{total_folders})"
            status_color = "#BF616A"
            
        self.folder_status_label.configure(
            text=status_text,
            text_color=status_color
        )
        
        # Log folder status
        self.log_message(f"š Folder Status: {status_text}", "info")
        
    def create_command_section(self, parent):
        """Create the command buttons section"""
        cmd_frame = ctk.CTkFrame(parent, corner_radius=10)
        cmd_frame.pack(fill="x", padx=10, pady=(0, 20))
        
        # Section title
        cmd_title = ctk.CTkLabel(
            cmd_frame,
            text="šļø Command Panel",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        cmd_title.pack(pady=(15, 10))
        
        # Button container with grid layout
        button_container = ctk.CTkFrame(cmd_frame, fg_color="transparent")
        button_container.pack(fill="x", padx=20, pady=(0, 15))
        
        self.command_buttons = {}
        self.stop_buttons = {}
        
        # Create buttons in a grid (3 columns)
        for i, (cmd, info) in enumerate(self.commands.items()):
            row = i // 3
            col = i % 3
            
            btn_frame = ctk.CTkFrame(button_container, corner_radius=8)
            btn_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            # Command button container
            button_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
            button_row.pack(fill="x", padx=5, pady=5)
            
            # Main command button
            btn = ctk.CTkButton(
                button_row,
                text=f"{info['icon']} {cmd.upper()}",
                font=ctk.CTkFont(size=14, weight="bold"),
                height=50,
                corner_radius=8,
                hover_color=info['color'],
                command=lambda c=cmd: self.execute_command(c)
            )
            btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            # Stop button (initially hidden)
            stop_btn = ctk.CTkButton(
                button_row,
                text="Stop",
                width=50,
                height=50,
                corner_radius=8,
                fg_color="#FF4444",
                hover_color="#FF6666",
                command=lambda c=cmd: self.stop_command(c),
                font=ctk.CTkFont(size=12, weight="bold")
            )
            self.stop_buttons[cmd] = stop_btn
            
            # Description label
            desc_label = ctk.CTkLabel(
                btn_frame,
                text=info['desc'],
                font=ctk.CTkFont(size=10),
                text_color="#888888"
            )
            desc_label.pack(pady=(0, 5))
            
            self.command_buttons[cmd] = btn
            
        # Configure grid weights for responsive design
        for i in range(3):
            button_container.grid_columnconfigure(i, weight=1)
            
    def on_mouse_wheel(self, event):
        if event.delta != 0:
            direction = "down" if event.delta < 0 else "up"
            self.console_text.yview_scroll(-1 if direction == "down" else 1, "units")
        return "break"

    def on_scrollbar_drag(self, event):
        # This ensures the scrollbar gets updated smoothly while dragging
        self.console_text.yview_scroll(event.delta, "units")

    def create_console_section(self, parent):
        """Create the console output section"""
        console_frame = ctk.CTkFrame(parent, corner_radius=10)
        console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
        # Console header
        console_header = ctk.CTkFrame(console_frame, height=40, corner_radius=8)
        console_header.pack(fill="x", padx=10, pady=(10, 5))
        console_header.pack_propagate(False)
    
        console_title = ctk.CTkLabel(
            console_header,
            text="š» Console Output",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        console_title.pack(side="left", padx=15, pady=10)
    
        # Control buttons
        button_frame = ctk.CTkFrame(console_header, fg_color="transparent")
        button_frame.pack(side="right", padx=15, pady=7)
    
        # Auto-scroll toggle
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_check = ctk.CTkCheckBox(
            button_frame,
            text="Auto-scroll",
            variable=self.auto_scroll_var,
            width=80,
            height=25,
            font=ctk.CTkFont(size=12)
        )
        auto_scroll_check.pack(side="left", padx=5)
    
        # Keyboard shortcut label
        shortcut_label = ctk.CTkLabel(
            button_frame,
            text="āC to stop",
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        shortcut_label.pack(side="left", padx=5)
    
        # Clear button
        clear_btn = ctk.CTkButton(
            button_frame,
            text="šļø Clear",
            width=80,
            height=25,
            font=ctk.CTkFont(size=12),
            command=self.clear_console
        )
        clear_btn.pack(side="left", padx=5)
    
        # Console text area with custom styling
        console_container = ctk.CTkFrame(console_frame, fg_color="#1a1a1a")
        console_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
        self.console_text = tk.Text(
            console_container,
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            cursor="arrow",
            selectbackground="#264f78",
            selectforeground="#ffffff",
            insertbackground="#c9d1d9"
        )
    
        # Scrollbar for console
        scrollbar = CTkScrollbar(console_container, command=self.console_text.yview)
        self.console_text.config(yscrollcommand=scrollbar.set)
    
        # Bind mouse events
        self.console_text.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.console_text.bind("<B1-Motion>", self.on_scrollbar_drag)
    
        self.console_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)
    
        # Configure text tags for colored output
        self.console_text.tag_configure("info", foreground="#58a6ff")
        self.console_text.tag_configure("success", foreground="#3fb950")
        self.console_text.tag_configure("warning", foreground="#d29922")
        self.console_text.tag_configure("error", foreground="#f85149")
        self.console_text.tag_configure("timestamp", foreground="#8b949e")
        
    def create_status_bar(self, parent):
        """Create the status bar"""
        status_frame = ctk.CTkFrame(parent, height=35, corner_radius=8)
        status_frame.pack(fill="x", padx=10, pady=(0, 10))
        status_frame.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready to execute commands",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=15, pady=8)
        
        # Running commands counter
        self.running_count_label = ctk.CTkLabel(
            status_frame,
            text="Running: 0",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.running_count_label.pack(side="right", padx=15, pady=8)
        
    def setup_animations(self):
        """Setup animation effects"""
        self.animation_states = {}
        
    def animate_button(self, button, state="active"):
        """Animate button with pulsing effect (optimized)"""
        if state == "active" and button.winfo_exists():
            # Simple color toggle without frequent updates
            current_fg = button.cget("fg_color")
            if isinstance(current_fg, list):
                button.configure(fg_color="#FFD700")
            else:
                button.configure(fg_color=["#3B8ED0", "#1F538D"])
                
    def execute_command(self, command):
        """Execute a command in a separate thread"""
        if command in self.running_commands:
            self.log_message(f"Command '{command}' is already running!", "warning")
            return
            
        self.running_commands.add(command)
        self.update_status_indicator()
        
        # Show stop button
        self.stop_buttons[command].pack(side="right", padx=(5, 0))
        self.animate_button(self.command_buttons[command], "active")
        
        # Start command in thread with higher priority for UI responsiveness
        thread = threading.Thread(target=self._run_command, args=(command,), daemon=True)
        thread.start()
        
    def stop_command(self, command):
        """Stop a running command using SIGINT (Ctrl+C)"""
        if command in self.running_commands:
            self.process_manager.send_sigint(command)
            self.log_message(f"š Sending Ctrl+C to command: {command}", "warning")
        
    def _run_command(self, command):
        """Run command in subprocess with proper process management"""
        process = None
        try:
            self.log_message(f"š Starting command: {command}", "info")
            
            # Check if the original file exists
            script_path = "shadow_server_data_analysis_system_builder_and_updater.py"
            if not os.path.exists(script_path):
                # Create a mock script for demonstration
                self.log_message(f"ā ļø Original script not found. Running simulation for '{command}'...", "warning")
                self._simulate_command(command)
            else:
                # Run the actual command with proper buffering
                cmd = [sys.executable, script_path, command]
                
                # Configure process creation for proper signal handling
                if sys.platform == 'win32':
                    # On Windows, create new process group for Ctrl+C handling
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,  # Line buffered
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    # On Unix-like systems, create new process group
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,  # Line buffered
                        preexec_fn=os.setsid  # Create new process group
                    )
                
                # Register process for management
                self.process_manager.add_process(command, process)
                
                # Read output with timeout to prevent blocking
                output_lines = []
                while True:
                    try:
                        # Check if process is still running
                        if process.poll() is not None:
                            # Process finished, read remaining output
                            remaining = process.stdout.read()
                            if remaining:
                                for line in remaining.splitlines():
                                    if line.strip():
                                        output_lines.append(line.strip())
                            break
                            
                        # Read available output without blocking
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line.strip())
                            
                            # Batch output updates to reduce GUI load
                            if len(output_lines) >= 10:
                                self.output_queue.put(("batch_output", output_lines.copy()))
                                output_lines.clear()
                        else:
                            time.sleep(0.01)  # Small delay to prevent CPU spinning
                            
                    except Exception as e:
                        self.output_queue.put(("error", f"Error reading output: {str(e)}"))
                        break
                
                # Send any remaining output
                if output_lines:
                    self.output_queue.put(("batch_output", output_lines))
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    self.output_queue.put(("success", f"ā Command '{command}' completed successfully"))
                    # Refresh folder status after successful command completion
                    self.root.after(1000, self.refresh_folder_status)
                else:
                    self.output_queue.put(("error", f"ā Command '{command}' failed with code {return_code}"))
                    
        except Exception as e:
            self.output_queue.put(("error", f"ā Error executing '{command}': {str(e)}"))
        finally:
            # Clean up
            if process:
                self.process_manager.remove_process(command)
            self.output_queue.put(("finish", command))
            
    def _simulate_command(self, command):
        """Simulate command execution for testing"""
        messages = [
            f"Initializing {command} module...",
            f"Loading configuration for {command}...",
            f"Connecting to database...",
            f"Processing {command} request...",
            f"Validating {command} parameters...",
            f"Executing {command} operations...",
        ]
        
        # Simulate intensive processing with periodic output
        for i in range(50):  # Simulate more intensive task
            if i % 10 == 0 and i < len(messages):
                self.output_queue.put(("output", f"[{command.upper()}] {messages[i//10]}"))
            
            # Simulate work
            time.sleep(0.1)
            
            # Check if command should be stopped (simulating Ctrl+C check)
            if command not in self.running_commands:
                self.output_queue.put(("warning", f"[{command.upper()}] Command interrupted (Ctrl+C)"))
                return
                
            # Occasional progress update
            if i % 5 == 0:
                progress = int((i / 50) * 100)
                self.output_queue.put(("output", f"[{command.upper()}] Progress: {progress}%"))
        
        # Simulate folder creation for 'all' command
        if command == "all":
            for folder_name, folder_info in self.archive_folders.items():
                self.output_queue.put(("output", f"[ALL] Creating folder: {folder_info['path']}"))
                # Simulate creating the folder
                try:
                    os.makedirs(folder_info["path"], exist_ok=True)
                    self.output_queue.put(("success", f"[ALL] ā Created folder: {folder_info['path']}"))
                except Exception as e:
                    self.output_queue.put(("error", f"[ALL] ā Failed to create folder {folder_info['path']}: {str(e)}"))
        
        # Simulate success/failure
        if random.random() > 0.2:  # 80% success rate
            self.output_queue.put(("success", f"ā Command '{command}' simulation completed successfully"))
        else:
            self.output_queue.put(("error", f"ā Command '{command}' simulation failed"))
            
    def start_output_monitor(self):
        """Start monitoring output queue with optimized updates"""
        self.check_output_queue()
        
    def check_output_queue(self):
        """Check for new output messages with batching"""
        messages_processed = 0
        max_messages_per_update = 500  # Limit messages per GUI update
        
        try:
            while messages_processed < max_messages_per_update:
                msg_type, content = self.output_queue.get_nowait()
                
                if msg_type == "finish":
                    self.running_commands.discard(content)
                    self.update_status_indicator()
                    # Reset button appearance
                    self.command_buttons[content].configure(fg_color=["#3B8ED0", "#1F538D"])
                    # Hide stop button
                    self.stop_buttons[content].pack_forget()
                    
                elif msg_type == "batch_output":
                    # Handle batch output efficiently
                    for message in content:
                        if message.strip():
                            self.log_message_batch(message, "output")
                    self.flush_console_batch()
                    
                elif msg_type in ["output", "info", "success", "warning", "error"]:
                    self.log_message(content, msg_type)
                    
                messages_processed += 1
                    
        except queue.Empty:
            pass
            
        # Schedule next check with adaptive timing
        delay = 10 if self.running_commands else 50
        self.root.after(delay, self.check_output_queue)
    
    def log_message_batch(self, message, msg_type="info"):
        """Add message to batch without immediately updating GUI"""
        if self.console_text is None:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_buffer.append({
            "timestamp": timestamp,
            "message": message,
            "type": msg_type
        })
    
    def flush_console_batch(self):
        """Flush batched messages to console"""
        if not self.console_buffer or self.console_text is None:
            return

        self.console_text.config(state=tk.NORMAL)

        # Collect all the batched messages into one string
        output = ""
        for msg_data in self.console_buffer:
            timestamp = msg_data["timestamp"]
            message = msg_data["message"]
            msg_type = msg_data["type"]

            # Add timestamp
            output += f"[{timestamp}] "

            # Add message with appropriate color
            if msg_type == "success":
                output += f"{message}\n"
            elif msg_type == "warning":
                output += f"{message}\n"
            elif msg_type == "error":
                output += f"{message}\n"
            elif msg_type == "info":
                output += f"{message}\n"
            else:
                output += f"{message}\n"

        self.console_text.insert(tk.END, output)  # Insert all at once
        self.console_text.config(state=tk.DISABLED)

        # Auto-scroll if enabled, and smoothly update the scrollbar position
        if self.auto_scroll_var and self.auto_scroll_var.get():
            self.console_text.see(tk.END)  # This ensures auto-scroll is smooth

        # Clear the buffer after flush
        self.console_buffer.clear()

        
    def log_message(self, message, msg_type="info"):
        """Log a message to the console (single message)"""
        if self.console_text is None:
            # Store in buffer if console not ready yet
            self.console_buffer.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": message,
                "type": msg_type
            })
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.console_text.config(state=tk.NORMAL)
        
        # Add timestamp
        self.console_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        # Add message with appropriate color
        if msg_type == "success":
            self.console_text.insert(tk.END, f"{message}\n", "success")
        elif msg_type == "warning":
            self.console_text.insert(tk.END, f"{message}\n", "warning")
        elif msg_type == "error":
            self.console_text.insert(tk.END, f"{message}\n", "error")
        elif msg_type == "info":
            self.console_text.insert(tk.END, f"{message}\n", "info")
        else:
            self.console_text.insert(tk.END, f"{message}\n")
            
        self.console_text.config(state=tk.DISABLED)
        
        # Auto-scroll if enabled
        if self.auto_scroll_var and self.auto_scroll_var.get():
            self.console_text.see(tk.END)
        
        # Update command history (limited)
        if len(self.command_history) > 1000:
            self.command_history = self.command_history[-500:]  # Keep only recent history
        
        self.command_history.append({
            "timestamp": timestamp,
            "message": message,
            "type": msg_type
        })
        
    def clear_console(self):
        """Clear the console output"""
        if self.console_text is None:
            return
            
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        self.console_text.config(state=tk.DISABLED)
        self.console_buffer.clear()
        self.log_message("Console cleared", "info")
        
    def update_status_indicator(self):
        """Update the status indicator"""
        running_count = len(self.running_commands)
        
        if running_count == 0:
            self.status_indicator.configure(text="ā Ready", text_color="#00FF88")
            self.status_label.configure(text="Ready to execute commands")
        else:
            self.status_indicator.configure(text="ā Running", text_color="#FFD700")
            self.status_label.configure(text=f"Executing {running_count} command(s)...")
            
        self.running_count_label.configure(text=f"Running: {running_count}")
    
    def on_closing(self):
        """Handle application closing"""
        # Hide dropdown if visible
        if self.dropdown_visible:
            self.hide_dropdown()
            
        # Stop all running processes
        self.process_manager.cleanup_all()
        
        # Clear running commands
        self.running_commands.clear()
        
        # Destroy the window
        self.root.destroy()
        
    def run(self):
        """Start the GUI application"""
        # Wait for UI to be fully initialized
        self.root.update_idletasks()
        
        # Now that console is ready, flush any buffered messages
        if self.console_buffer and self.console_text:
            self.flush_console_batch()
            
        self.log_message("š Shadow Command Center initialized", "success")
        self.log_message("š Archive folder status checked - see navigation bar", "info")
        self.log_message("Click any command button to execute", "info")
        
        # Center window on screen
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
        
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        app = ModernCommandGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
