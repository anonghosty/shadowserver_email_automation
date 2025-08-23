import sys
import os
import threading
import queue
import subprocess
import time
import signal
import random
import json
import csv
import io
from datetime import datetime
from collections import deque
from resource_monitor import ResourceMonitorApp

import dearpygui.dearpygui as dpg

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

class ShadowCommandCenter:
    def __init__(self):
        # Initialize DearPyGui
        dpg.create_context()
        
        # Configure themes and styling
        self.setup_theme()
        
        # Thread-safe queues with larger capacity
        self.command_queue = queue.Queue()
        self.output_queue = queue.Queue(maxsize=10000)
        
        # Process management
        self.process_manager = ProcessManager()
        
        # Console buffer
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
            "email": {"color": (255, 107, 107), "icon": "[E]", "desc": "Pull Emails Or Reports From API"},
            "migrate": {"color": (78, 205, 196), "icon": "[M]", "desc": "Unzip and Move Downloaded Files"},
            "refresh": {"color": (69, 183, 209), "icon": "[R]", "desc": "Refresh ASN Metadata"},
            "process": {"color": (150, 206, 180), "icon": "[P]", "desc": "Process Data By Cached ASN Data or Automatically Retrieve ASN Data"},
            "country": {"color": (255, 234, 167), "icon": "[C]", "desc": "Sort Processed Data By Country"},
            "service": {"color": (221, 160, 221), "icon": "[S]", "desc": "Create Service Folders and Sort Per Organisation"},
            "ingest": {"color": (255, 179, 71), "icon": "[I]", "desc": "Ingest Into Knowledgebase"},
            "all": {"color": (255, 179, 71), "icon": "[P]", "desc": "Run All Processes Related to Building the Knowledgebase"}
        }
        
        self.running_commands = set()
        self.command_history = []
        
        # Performance optimization flags
        self.batch_update_pending = False
        self.last_update_time = time.time()
        
        # UI State
        self.auto_scroll = True
        self.dropdown_states = {
            "archive": False,
            "mapping": False,
            "reports": False
        }
        
        # Initialize UI
        self.setup_ui()
        self.start_output_monitor()

    def setup_theme(self):
        """Setup Dear PyGui themes for modern dark appearance"""
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                # Dark theme colors
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (26, 26, 26), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 35), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (42, 42, 42), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (68, 68, 68), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (45, 45, 45), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (55, 55, 55), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (65, 65, 65), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (42, 42, 42), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (59, 66, 82), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, (42, 42, 42), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Button, (59, 139, 208), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (69, 149, 218), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (49, 129, 198), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (59, 66, 82), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (67, 74, 90), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (51, 58, 74), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (0, 212, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Text, (201, 209, 217), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (128, 128, 128), category=dpg.mvThemeCat_Core)
                
                # Styling
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 10, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 6, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 15, 15, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 6, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 6, 4, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_IndentSpacing, 20, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_GrabMinSize, 12, category=dpg.mvThemeCat_Core)
                
        # Button themes for different states
        with dpg.theme() as self.success_button_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (163, 190, 140), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (143, 168, 120), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (123, 148, 100), category=dpg.mvThemeCat_Core)
                
        with dpg.theme() as self.warning_button_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (235, 203, 139), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (215, 183, 119), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (195, 163, 99), category=dpg.mvThemeCat_Core)
                
        with dpg.theme() as self.error_button_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (191, 97, 106), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (171, 77, 86), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (151, 57, 66), category=dpg.mvThemeCat_Core)
                
        with dpg.theme() as self.stop_button_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 68, 68), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 102, 102), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (230, 43, 43), category=dpg.mvThemeCat_Core)
        
        dpg.bind_theme(global_theme)

    def setup_ui(self):
        """Setup the main UI components"""
        with dpg.window(label="Shadow Command Center", tag="primary_window", width=1200, height=800):
            # Header section
            self.create_header()
            
            # Navigation bar
            self.create_navigation_bar()
            
            # Command buttons section
            self.create_command_section()
            
            # Console section
            self.create_console_section()
            
            # Status bar
            self.create_status_bar()

        dpg.create_viewport(title="Shadow Command Center", width=1200, height=800, resizable=True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)

    def create_header(self):
        """Create the header section"""
        with dpg.group(horizontal=True):
            dpg.add_text("Shadow Command Center", color=(0, 212, 255))
            dpg.add_spacer(width=20)
            
            # Status indicator
            dpg.add_text("Ready", tag="status_indicator", color=(0, 255, 136))

    def create_navigation_bar(self):
        """Create the navigation bar with dropdowns"""
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            # Archive Folders
            if dpg.add_button(label="Archive Folders", callback=self.toggle_archive_dropdown):
                pass
                
            dpg.add_spacer(width=15)
            
            # Mapping Files
            if dpg.add_button(label="Mapping Files", callback=self.toggle_mapping_dropdown):
                pass
                
            dpg.add_spacer(width=15)
            
            # Report Generation
            report_options = [
                "Get Shadowserver Report Types",
                "Generate Statistics Reported", 
                "Generate Malicious Reports"
            ]
            dpg.add_combo(report_options, label="<=Report Generation", 
                         callback=self.on_report_selection, width=200)
                         
            dpg.add_spacer(width=20)
            
            # Folder status
            dpg.add_text("Checking folders...", tag="folder_status", color=(136, 136, 136))
            
            dpg.add_spacer(width=10)
            
            # Refresh button
            dpg.add_button(label="Refresh", callback=self.refresh_folder_status)
            
            # Resource Monitor button
            dpg.add_button(label="Resources", callback=self.open_resource_monitor)

    def create_command_section(self):
        """Create the command buttons section"""
        dpg.add_separator()
        dpg.add_text("Command Panel", color=(255, 255, 255))
        dpg.add_spacer(height=10)
        
        # Create command buttons in a grid-like layout
        buttons_per_row = 4
        with dpg.group():
            for i, (cmd, info) in enumerate(self.commands.items()):
                if i % buttons_per_row == 0:
                    if i > 0:
                        dpg.add_spacer(height=5)  # Add some spacing between rows
                    current_row = dpg.add_group(horizontal=True)
                
                with dpg.group(parent=current_row):
                    # Command button
                    button_id = f"cmd_btn_{cmd}"
                    dpg.add_button(
                        label=f"{info['icon']} {cmd.upper()}",
                        tag=button_id,
                        callback=lambda s, a, u: self.execute_command(u),
                        user_data=cmd,
                        width=200,
                        height=50
                    )
                    
                    # Stop button (initially hidden)
                    stop_button_id = f"stop_btn_{cmd}"
                    dpg.add_button(
                        label="Stop",
                        tag=stop_button_id,
                        callback=lambda s, a, u: self.stop_command(u),
                        user_data=cmd,
                        width=80,
                        height=25,
                        show=False
                    )
                    dpg.bind_item_theme(stop_button_id, self.stop_button_theme)
                    
                    # Description
                    dpg.add_text(info['desc'], wrap=180, color=(136, 136, 136))
                    
                if (i + 1) % buttons_per_row != 0 and i < len(self.commands) - 1:
                    dpg.add_spacer(width=20, parent=current_row)

    def create_console_section(self):
        """Create the console output section"""
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text(" Console Output", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            
            # Console controls
            dpg.add_checkbox(label="Auto-scroll", tag="auto_scroll_check", 
                           default_value=self.auto_scroll,  # Use the class variable
                           callback=self.toggle_auto_scroll)
            dpg.add_spacer(width=10)
            dpg.add_text("Experimental", color=(136, 136, 136))
            dpg.add_spacer(width=10)
            dpg.add_button(label=" Clear", callback=self.clear_console)

        dpg.add_spacer(height=5)
        
        # Create a child window for the console with scrollable content
        with dpg.child_window(tag="console_child", width=-1, height=300, horizontal_scrollbar=False):
            # Console text area - using a child window allows better scroll control
            dpg.add_input_text(
                tag="console_output",
                multiline=True,
                readonly=True,
                width=-1,
                height=-1,  # Fill the child window
                default_value="Shadow Command Center initialized\nReady to execute commands...\n"
            )


    def create_status_bar(self):
        """Create the status bar"""
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            dpg.add_text("Ready to execute commands", tag="status_text")
            dpg.add_spacer(width=20)
            dpg.add_text("Running: 0", tag="running_count", color=(136, 136, 136))

    def toggle_archive_dropdown(self):
        """Toggle archive folders dropdown"""
        if not self.dropdown_states["archive"]:
            self.show_archive_popup()
        self.dropdown_states["archive"] = not self.dropdown_states["archive"]

    def show_archive_popup(self):
            """Show archive folders popup window"""
            with dpg.window(label="Archive Folders", modal=True, show=True, 
                           width=400, height=300, pos=(100, 150)):
        
                dpg.add_text(" Archive Folders Status", color=(0, 212, 255))
                dpg.add_separator()
        
                for folder_name, folder_info in self.archive_folders.items():
                    exists = self.check_folder_exists(folder_info["path"])
                    status_icon = "" if exists else ""
                    status_color = (163, 190, 140) if exists else (191, 97, 106)
            
                    with dpg.group(horizontal=True):
                        dpg.add_text(f"{status_icon} {folder_name}", color=status_color)
                        dpg.add_spacer(width=20)
                
                        if exists:
                            # Create a proper closure by using a factory function
                            def make_open_callback(path):
                                return lambda s, a: self.open_folder_in_explorer(path)
                        
                            dpg.add_button(label=" Open", 
                                         callback=make_open_callback(folder_info["path"]))
                        else:
                            # Same fix for the missing folder callback
                            def make_missing_callback(name):
                                return lambda s, a: self.suggest_run_all(name)
                            
                            dpg.add_button(label=" Missing",
                                     callback=make_missing_callback(folder_name))
            
                    dpg.add_text(folder_info["description"], color=(136, 136, 136), wrap=350)
                    dpg.add_spacer(height=5)
        
                dpg.add_separator()
                dpg.add_button(label=" Run All Commands (Creates Missing Folders)", 
                             callback=self.run_all_from_dropdown, width=-1)
				
    def toggle_mapping_dropdown(self):
        """Toggle mapping files dropdown"""
        if not self.dropdown_states["mapping"]:
            self.show_mapping_popup()
        self.dropdown_states["mapping"] = not self.dropdown_states["mapping"]

    def show_mapping_popup(self):
            """Show mapping files popup window"""
            with dpg.window(label="Mapping Files", modal=True, show=True, 
                           width=450, height=350, pos=(120, 170)):
            
                dpg.add_text(" Mapping Files Configuration", color=(0, 212, 255))
                dpg.add_separator()
            
                for file_key, file_info in self.mapping_files.items():
                    exists = os.path.exists(file_info["path"])
                    status_icon = "" if exists else ""
                    status_color = (163, 190, 140) if exists else (191, 97, 106)
                
                    with dpg.group(horizontal=True):
                        dpg.add_text(f"{status_icon} {file_info['icon']} {file_info['display_name']}", 
                               color=status_color)
                        dpg.add_spacer(width=20)
                    
                        if exists:
                            # Create a proper closure by using a factory function
                            def make_edit_callback(fk):
                                return lambda s, a: self.open_file_editor(fk)
                        
                            dpg.add_button(label=" Edit", 
                                         callback=make_edit_callback(file_key))
                        else:
                            # Create a proper closure for create callback
                            def make_create_callback(fk):
                                return lambda s, a: self.create_file_editor(fk)
                        
                            dpg.add_button(label=" Create",
                                     callback=make_create_callback(file_key))
                
                    dpg.add_text(file_info["description"], color=(136, 136, 136), wrap=400)
                    dpg.add_spacer(height=8)

    def on_report_selection(self, sender, app_data):
        """Handle report generation selection"""
        script_mapping = {
            "Get Shadowserver Report Types": "get_shadowserver_report_types.py",
            "Generate Statistics Reported": "generate_statistics_reported_from_shadowserver_unverified.py",
            "Generate Malicious Reports": "generate_reported_malicious_communication_reports_old.py"
        }
        
        if app_data in script_mapping:
            self.open_script_runner(script_mapping[app_data], app_data)

    def open_script_runner(self, script_path, display_name):
        """Open script runner window"""
        if not os.path.isfile(script_path):
            self.log_message(f"Script not found: {script_path}", "error")
            return

        with dpg.window(label=f"Running: {display_name}", width=700, height=400, show=True):
            dpg.add_text(f"Running: {display_name}")
            dpg.add_separator()
            
            output_text = dpg.add_input_text(
                multiline=True,
                readonly=True,
                width=-1,
                height=300,
                default_value=f"Starting script: {script_path}\n\n"
            )
            
            def run_script():
                try:
                    process = subprocess.Popen(
                        [sys.executable, script_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )

                    output = f"Starting script: {script_path}\n\n"
                    dpg.set_value(output_text, output)

                    for line in iter(process.stdout.readline, ''):
                        output += line
                        dpg.set_value(output_text, output)

                    process.stdout.close()
                    process.wait()

                    output += "\n\nā Done. Window will close in 10 seconds..."
                    dpg.set_value(output_text, output)
                    
                    # Auto-close after delay
                    def delayed_close():
                        time.sleep(10)
                        try:
                            dpg.delete_item(dpg.get_item_parent(output_text))
                        except:
                            pass

                    threading.Thread(target=delayed_close, daemon=True).start()

                except Exception as e:
                    output = dpg.get_value(output_text)
                    output += f"\nā Error: {e}"
                    dpg.set_value(output_text, output)

            threading.Thread(target=run_script, daemon=True).start()

    def open_resource_monitor(self):
        """Open resource monitor window"""
        try:
            # Note: This would need to be adapted to work with Dear PyGui
            # For now, we'll show a placeholder
            with dpg.window(label="Resource Monitor", width=600, height=400, show=True):
                dpg.add_text("Resource Monitor")
                dpg.add_separator()
                dpg.add_text("Resource monitoring functionality would be implemented here.")
                dpg.add_text("This requires adaptation of the ResourceMonitorApp to Dear PyGui. Now Worries Give Me Time :) Customtkinter hast it tho")
        except Exception as e:
            self.log_message(f"Error opening resource monitor: {str(e)}", "error")

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

    def suggest_run_all(self, folder_name):
        """Suggest running 'all' command when folder is missing"""
        self.log_message(f"ā ļø Folder '{folder_name}' does not exist!", "warning")
        self.log_message("š” Suggestion: Run the 'ALL' command to create missing folders and build the complete system", "info")

    def run_all_from_dropdown(self):
        """Run 'all' command from dropdown menu"""
        self.log_message("š Running ALL commands from Archive Folders menu...", "info")
        self.execute_command("all")

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
            status_color = (163, 190, 140)
        elif existing_folders > 0 or existing_files > 0:
            status_text = f"ā ļø Partial setup ({existing_folders}/{total_folders} folders, {existing_files}/{total_files} files)"
            status_color = (235, 203, 139)
        else:
            status_text = f"ā Setup needed ({existing_folders}/{total_folders} folders, {existing_files}/{total_files} files)"
            status_color = (191, 97, 106)
            
        dpg.set_value("folder_status", status_text)
        dpg.configure_item("folder_status", color=status_color)
        
        # Log folder status
        self.log_message(f"š System Status: {status_text}", "info")

    def open_file_editor(self, file_key):
        """Open file editor for existing file"""
        file_info = self.mapping_files[file_key]
        
        if file_key in self.active_forms:
            # Bring existing form to front
            return
            
        try:
            with open(file_info["path"], 'r', encoding='utf-8') as f:
                content = f.read()
            self.create_file_form(file_key, file_info, content, is_new=False)
        except Exception as e:
            self.log_message(f"ā Error reading file {file_info['path']}: {str(e)}", "error")

    def create_file_editor(self, file_key):
        """Create new file editor"""
        file_info = self.mapping_files[file_key]
        
        if file_key in self.active_forms:
            return
            
        # Create default content based on file type
        if file_info["type"] == "env":
            default_content = "# Environment Variables\n# Add your configuration here\n\n"
        else:  # CSV
            default_content = "# CSV Mapping File\n# Add your mappings here\n\n"
            
        self.create_file_form(file_key, file_info, default_content, is_new=True)
		

    def create_file_form(self, file_key, file_info, content, is_new=False):
        """Create a form for editing files"""
        window_title = f"{'Create' if is_new else 'Edit'} {file_info['display_name']}"
        
        with dpg.window(label=window_title, width=800, height=600, show=True, tag=f"form_{file_key}"):
            # Header
            dpg.add_text(f"{file_info['icon']} {'Creating new' if is_new else 'Editing'} {file_info['display_name']}", 
                        color=(0, 212, 255))
            dpg.add_text(f" {file_info['path']}", color=(216, 222, 233))
            dpg.add_separator()
            
            if file_info["type"] == "env":
                self.create_env_editor_form(file_key, file_info, content, is_new)
            elif file_info["type"] == "csv":
                self.create_csv_editor_form(file_key, file_info, content, is_new)
            else:
                # Default text editor
                dpg.add_input_text(
                    tag=f"text_content_{file_key}",
                    multiline=True,
                    width=-1,
                    height=400,
                    default_value=content
                )
            
            # Action buttons
            dpg.add_separator()
            with dpg.group(horizontal=True):
                # Create proper closures for button callbacks
                def make_cancel_callback(fk):
                    return lambda s, a: self.close_file_form(fk)
                
                def make_save_callback(fk):
                    return lambda s, a: self.save_file(fk)
                
                def make_save_close_callback(fk):
                    return lambda s, a: self.save_and_close_file(fk)
                
                dpg.add_button(label=" Cancel", 
                             callback=make_cancel_callback(file_key))
                dpg.add_spacer(width=10)
                dpg.add_button(label=" Save", 
                             callback=make_save_callback(file_key))
                dpg.add_spacer(width=10)
                dpg.add_button(label=" Save & Close", 
                             callback=make_save_close_callback(file_key))
        
        self.active_forms[file_key] = {
            "window": f"form_{file_key}",
            "file_info": file_info,
            "is_new": is_new
        }

    def create_env_editor_form(self, file_key, file_info, content, is_new):
        """Create environment variables editor form"""
        dpg.add_text(" Enter environment variables as key-value pairs")
        dpg.add_separator()
        
        # Parse content into key-value pairs
        env_vars = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
        
        # Create table for env vars
        with dpg.table(tag=f"env_table_{file_key}", header_row=True, 
                      borders_innerH=True, borders_outerH=True, 
                      borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Key", width_fixed=True, init_width_or_weight=200)
            dpg.add_table_column(label="Value", width_fixed=True, init_width_or_weight=400)
            dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=100)
            
            # Add existing env vars
            for i, (key, value) in enumerate(env_vars.items()):
                with dpg.table_row():
                    dpg.add_input_text(tag=f"env_key_{file_key}_{i}", default_value=key, width=180)
                    dpg.add_input_text(tag=f"env_val_{file_key}_{i}", default_value=value, width=380)
                    
                    # Create proper closure for remove button
                    def make_remove_callback(fk, row):
                        return lambda s, a: self.remove_env_row(fk, row)
                    
                    dpg.add_button(label="", callback=make_remove_callback(file_key, i))
        
        # Add new variable button
        dpg.add_spacer(height=10)
        
        # Create proper closure for add button
        def make_add_callback(fk):
            return lambda s, a: self.add_env_row(fk)
        
        dpg.add_button(label=" Add Variable", callback=make_add_callback(file_key))

    def create_csv_editor_form(self, file_key, file_info, content, is_new):
        """Create CSV editor form"""
        dpg.add_text(" Edit CSV data in grid format")
        dpg.add_separator()
        
        # Parse CSV content
        try:
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
        except:
            rows = []
        
        # If empty, provide default structure
        if not rows and is_new:
            rows = [
                ["column1", "column2", "column3"],
                ["value1", "value2", "value3"]
            ]
        
        if rows:
            with dpg.table(tag=f"csv_table_{file_key}", header_row=True,
                          borders_innerH=True, borders_outerH=True,
                          borders_innerV=True, borders_outerV=True):
                
                # Create columns based on first row
                for i in range(len(rows[0]) if rows else 3):
                    dpg.add_table_column(label=f"Col {i+1}", width_fixed=True, init_width_or_weight=120)
                
                # Add data rows
                for row_idx, row in enumerate(rows):
                    with dpg.table_row():
                        for col_idx, cell in enumerate(row):
                            dpg.add_input_text(
                                tag=f"csv_cell_{file_key}_{row_idx}_{col_idx}",
                                default_value=cell,
                                width=100
                            )
        
        # CSV manipulation buttons
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            # Create proper closures for all CSV manipulation buttons
            def make_add_row_callback(fk):
                return lambda s, a: self.add_csv_row(fk)
            
            def make_add_col_callback(fk):
                return lambda s, a: self.add_csv_column(fk)
            
            def make_remove_row_callback(fk):
                return lambda s, a: self.remove_csv_row(fk)
            
            def make_remove_col_callback(fk):
                return lambda s, a: self.remove_csv_column(fk)
            
            dpg.add_button(label=" Add Row", callback=make_add_row_callback(file_key))
            dpg.add_spacer(width=10)
            dpg.add_button(label=" Add Column", callback=make_add_col_callback(file_key))
            dpg.add_spacer(width=10)
            dpg.add_button(label=" Remove Row", callback=make_remove_row_callback(file_key))
            dpg.add_spacer(width=10)
            dpg.add_button(label=" Remove Column", callback=make_remove_col_callback(file_key))

    def add_env_row(self, file_key):
        """Add new environment variable row"""
        # This would need more complex implementation in Dear PyGui
        # For now, show a message
        self.log_message("Adding new environment variable row", "info")

    def remove_env_row(self, file_key, row_idx):
        """Remove environment variable row"""
        self.log_message(f"Removing environment variable row {row_idx}", "info")

    def add_csv_row(self, file_key):
        """Add new CSV row"""
        self.log_message("Adding new CSV row", "info")

    def add_csv_column(self, file_key):
        """Add new CSV column"""
        self.log_message("Adding new CSV column", "info")

    def remove_csv_row(self, file_key):
        """Remove CSV row"""
        self.log_message("Removing CSV row", "info")

    def remove_csv_column(self, file_key):
        """Remove CSV column"""
        self.log_message("Removing CSV column", "info")

    def save_file(self, file_key):
        """Save file content"""
        if file_key not in self.active_forms:
            return

        form_info = self.active_forms[file_key]
        file_info = form_info["file_info"]

        try:
            if file_info["type"] == "env":
                # Collect environment variables from form
                content = self.collect_env_content(file_key)
            elif file_info["type"] == "csv":
                # Collect CSV data from form
                content = self.collect_csv_content(file_key)
            else:
                # Get content from text widget
                content = dpg.get_value(f"text_content_{file_key}")

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
            form_info["is_new"] = False

            # Refresh status indicators
            self.refresh_folder_status()

        except Exception as e:
            self.log_message(f"ā Error saving {file_info['display_name']}: {str(e)}", "error")

    def collect_env_content(self, file_key):
        """Collect environment variables content from form"""
        # This would collect from the dynamic table
        # For now, return placeholder
        return "# Environment variables would be collected here\n"

    def collect_csv_content(self, file_key):
        """Collect CSV content from form"""
        # This would collect from the dynamic table
        # For now, return placeholder
        return "column1,column2,column3\nvalue1,value2,value3\n"

    def save_and_close_file(self, file_key):
        """Save and close file"""
        self.save_file(file_key)
        self.close_file_form(file_key)

    def close_file_form(self, file_key):
        """Close file form"""
        if file_key in self.active_forms:
            form_info = self.active_forms[file_key]
            dpg.delete_item(form_info["window"])
            del self.active_forms[file_key]

    def toggle_auto_scroll(self, sender, app_data):
            """Toggle auto-scroll for console"""
            self.auto_scroll = app_data
            # Log the change so user knows it's working
            status = "enabled" if app_data else "disabled"
            self.log_message(f" Auto-scroll {status}", "info")
        
            # If auto-scroll was just enabled, scroll to bottom immediately
            if self.auto_scroll:
                try:
                    dpg.set_y_scroll("console_child", -1.0)
                except:
                    pass

    def clear_console(self):
        """Clear the console output"""
        dpg.set_value("console_output", "")
        self.console_buffer.clear()
        self.log_message("Console cleared", "info")
        
        # If auto-scroll is enabled, make sure we're at the bottom after clearing
        if self.auto_scroll:
            try:
                dpg.set_y_scroll("console_child", -1.0)
            except:
                pass

    def execute_command(self, command):
        """Execute a command in a separate thread"""
        if command in self.running_commands:
            self.log_message(f"Command '{command}' is already running!", "warning")
            return
            
        self.running_commands.add(command)
        self.update_status_indicator()
        
        # Show stop button
        dpg.show_item(f"stop_btn_{command}")
        
        # Change button color to indicate running
        dpg.bind_item_theme(f"cmd_btn_{command}", self.warning_button_theme)
        
        # Start command in thread
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
                # Run the actual command
                cmd = [sys.executable, script_path, command]
                
                # Configure process creation for proper signal handling
                if sys.platform == 'win32':
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        preexec_fn=os.setsid
                    )
                
                # Register process for management
                self.process_manager.add_process(command, process)
                
                # Read output
                output_lines = []
                while True:
                    try:
                        if process.poll() is not None:
                            remaining = process.stdout.read()
                            if remaining:
                                for line in remaining.splitlines():
                                    if line.strip():
                                        output_lines.append(line.strip())
                            break
                            
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line.strip())
                            
                            if len(output_lines) >= 10:
                                self.output_queue.put(("batch_output", output_lines.copy()))
                                output_lines.clear()
                        else:
                            time.sleep(0.01)
                            
                    except Exception as e:
                        self.output_queue.put(("error", f"Error reading output: {str(e)}"))
                        break
                
                if output_lines:
                    self.output_queue.put(("batch_output", output_lines))
                
                return_code = process.wait()
                
                if return_code == 0:
                    self.output_queue.put(("success", f"ā Command '{command}' completed successfully"))
                    # Refresh folder status after successful command completion
                    dpg.split_frame(delay=60)  # Wait 1 second then refresh
                    self.refresh_folder_status()
                else:
                    self.output_queue.put(("error", f"ā Command '{command}' failed with code {return_code}"))
                    
        except Exception as e:
            self.output_queue.put(("error", f"ā Error executing '{command}': {str(e)}"))
        finally:
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
        
        # Simulate intensive processing
        for i in range(50):
            if i % 10 == 0 and i < len(messages):
                self.output_queue.put(("output", f"[{command.upper()}] {messages[i//10]}"))
            
            time.sleep(0.1)
            
            # Check if command should be stopped
            if command not in self.running_commands:
                self.output_queue.put(("warning", f"[{command.upper()}] Command interrupted (Ctrl+C)"))
                return
                
            if i % 5 == 0:
                progress = int((i / 50) * 100)
                self.output_queue.put(("output", f"[{command.upper()}] Progress: {progress}%"))
        
        # Simulate folder creation for 'all' command
        if command == "all":
            for folder_name, folder_info in self.archive_folders.items():
                self.output_queue.put(("output", f"[ALL] Creating folder: {folder_info['path']}"))
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
        """Start monitoring output queue"""
        self.check_output_queue()

    def check_output_queue(self):
        """Check for new output messages"""
        messages_processed = 0
        max_messages_per_update = 500
        
        try:
            while messages_processed < max_messages_per_update:
                msg_type, content = self.output_queue.get_nowait()
                
                if msg_type == "finish":
                    self.running_commands.discard(content)
                    self.update_status_indicator()
                    
                    # Reset button appearance
                    dpg.bind_item_theme(f"cmd_btn_{content}", 0)  # Reset to default theme
                    dpg.hide_item(f"stop_btn_{content}")
                    
                elif msg_type == "batch_output":
                    for message in content:
                        if message.strip():
                            self.log_message_to_console(message, "output")
                            
                elif msg_type in ["output", "info", "success", "warning", "error"]:
                    self.log_message_to_console(content, msg_type)
                    
                messages_processed += 1
                    
        except queue.Empty:
            pass

    def log_message(self, message, msg_type="info"):
        """Log a message (external interface)"""
        self.output_queue.put((msg_type, message))

    def log_message_to_console(self, message, msg_type="info"):
        """Log a message directly to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Get current console content
        current_content = dpg.get_value("console_output")
        
        # Add new message with timestamp
        new_line = f"[{timestamp}] {message}\n"
        updated_content = current_content + new_line
        
        # Limit console buffer to prevent memory issues
        lines = updated_content.split('\n')
        if len(lines) > 1000:  # Keep last 1000 lines
            lines = lines[-1000:]
            updated_content = '\n'.join(lines)
        
        # Update console
        dpg.set_value("console_output", updated_content)
        
        # Auto-scroll if enabled - check the actual checkbox state as backup
        checkbox_state = dpg.get_value("auto_scroll_check")
        if self.auto_scroll and checkbox_state:
            try:
                # Small delay to ensure content is rendered before scrolling
                def delayed_scroll():
                    time.sleep(0.01)  # 10ms delay
                    try:
                        dpg.set_y_scroll("console_child", -1.0)
                    except:
                        pass
                
                # Run scroll in a quick thread to avoid blocking
                threading.Thread(target=delayed_scroll, daemon=True).start()
            except:
                pass
        
        # Update command history
        if len(self.command_history) > 1000:
            self.command_history = self.command_history[-500:]
        
        self.command_history.append({
            "timestamp": timestamp,
            "message": message,
            "type": msg_type
        })

    def update_status_indicator(self):
        """Update the status indicator"""
        running_count = len(self.running_commands)
        
        if running_count == 0:
            dpg.set_value("status_indicator", "ā Ready")
            dpg.configure_item("status_indicator", color=(0, 255, 136))
            dpg.set_value("status_text", "Ready to execute commands")
        else:
            dpg.set_value("status_indicator", "ā Running")
            dpg.configure_item("status_indicator", color=(255, 215, 0))
            dpg.set_value("status_text", f"Executing {running_count} command(s)...")
            
        dpg.set_value("running_count", f"Running: {running_count}")

    def run(self):
        """Start the GUI application"""
        # Initial folder status check
        self.refresh_folder_status()
        
        # Start the output monitor loop
        def monitor_loop():
            while dpg.is_dearpygui_running():
                self.check_output_queue()
                time.sleep(0.01)  # 10ms delay
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        # Log startup messages
        self.log_message("š Shadow Command Center initialized", "success")
        self.log_message("š Archive folder status checked - see navigation bar", "info")
        self.log_message("Click any command button to execute", "info")
        
        # Run the main loop
        dpg.start_dearpygui()

    def cleanup(self):
        """Cleanup resources"""
        # Close all active forms
        for file_key in list(self.active_forms.keys()):
            self.close_file_form(file_key)

        # Stop all running processes
        self.process_manager.cleanup_all()

        # Clear running commands
        self.running_commands.clear()

        # Destroy Dear PyGui context
        dpg.destroy_context()

def main():
    """Main entry point"""
    try:
        app = ShadowCommandCenter()
        app.run()
        app.cleanup()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
