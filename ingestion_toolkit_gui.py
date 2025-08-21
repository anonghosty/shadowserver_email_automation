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
        
        # Available commands
        self.commands = {
            "email": {"color": "#FF6B6B", "icon": "📧", "desc": "Pull Emails Or Reports From API"},
            "migrate": {"color": "#4ECDC4", "icon": "🔄", "desc": "Unzip and Move Downloaded Files"},
            "refresh": {"color": "#45B7D1", "icon": "🔄", "desc": "Refresh ASN Metadata"},
            "process": {"color": "#96CEB4", "icon": "⚙️", "desc": "Process Data By Cached ASN Data or Automaticaly Retrieve ASN Data"},
            "country": {"color": "#FFEAA7", "icon": "🌍", "desc": "Sort Processed Data By Country"},
            "service": {"color": "#DDA0DD", "icon": "🛠️", "desc": "Create Service Folders and Sort Per Organisation"},
            "ingest": {"color": "#FFB347", "icon": "📥", "desc": "Ingest Into Knowledgebase"},
            "all": {"color": "#FFB347", "icon": "!!", "desc": "Run All Processes Related to Building the Knowledgebase"}
        }
        
        self.running_commands = set()
        self.command_history = []
        self.console_buffer = deque(maxlen=5000)  # Limit console history
        
        # Performance optimization flags
        self.batch_update_pending = False
        self.last_update_time = time.time()
        
        self.setup_ui()
        self.setup_animations()
        self.start_output_monitor()
        
        # Handle application closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        """Setup the main UI components"""
        # Main container with padding
        main_frame = ctk.CTkFrame(self.root, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.create_header(main_frame)
        
        # Command buttons section
        self.create_command_section(main_frame)
        
        # Console section
        self.create_console_section(main_frame)
        
        # Status bar
        self.create_status_bar(main_frame)
        
    def create_header(self, parent):
        """Create the header section"""
        header_frame = ctk.CTkFrame(parent, height=80, corner_radius=10)
        header_frame.pack(fill="x", padx=10, pady=(10, 20))
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
            text="● Ready",
            font=ctk.CTkFont(size=16),
            text_color="#00FF88"
        )
        self.status_indicator.pack(side="right", padx=20, pady=20)
        
    def create_command_section(self, parent):
        """Create the command buttons section"""
        cmd_frame = ctk.CTkFrame(parent, corner_radius=10)
        cmd_frame.pack(fill="x", padx=10, pady=(0, 20))
        
        # Section title
        cmd_title = ctk.CTkLabel(
            cmd_frame,
            text="🎛️ Command Panel",
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
                text="Stop",  # Ctrl+C symbol
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
            text="💻 Console Output",
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
            text="⌃C to stop",
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        shortcut_label.pack(side="left", padx=5)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑️ Clear",
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
            font=("Consolas", 10),  # Slightly smaller font for performance
            wrap=tk.WORD,
            state=tk.DISABLED,
            cursor="arrow",
            selectbackground="#264f78",
            selectforeground="#ffffff",
            insertbackground="#c9d1d9"
        )
        
        # Scrollbar for console
        scrollbar = tk.Scrollbar(console_container, command=self.console_text.yview)
        self.console_text.config(yscrollcommand=scrollbar.set)
        
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
            self.log_message(f"🛑 Sending Ctrl+C to command: {command}", "warning")
        
    def _run_command(self, command):
        """Run command in subprocess with proper process management"""
        process = None
        try:
            self.log_message(f"🚀 Starting command: {command}", "info")
            
            # Check if the original file exists
            script_path = "shadow_server_data_analysis_system_builder_and_updater.py"
            if not os.path.exists(script_path):
                # Create a mock script for demonstration
                self.log_message(f"⚠️ Original script not found. Running simulation for '{command}'...", "warning")
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
                    self.output_queue.put(("success", f"✅ Command '{command}' completed successfully"))
                else:
                    self.output_queue.put(("error", f"❌ Command '{command}' failed with code {return_code}"))
                    
        except Exception as e:
            self.output_queue.put(("error", f"❌ Error executing '{command}': {str(e)}"))
        finally:
            # Clean up
            if process:
                self.process_manager.remove_process(command)
            self.output_queue.put(("finish", command))
            
    def _simulate_command(self, command):
        

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
                self.output_queue.put(("output", f"[{command.upper()}] {messages[i//100000]}"))
            
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
        
        # Simulate success/failure
        if random.random() > 0.2:  # 80% success rate
            self.output_queue.put(("success", f"✅ Command '{command}' simulation completed successfully"))
        else:
            self.output_queue.put(("error", f"❌ Command '{command}' simulation failed"))
            
    def start_output_monitor(self):
        """Start monitoring output queue with optimized updates"""
        self.check_output_queue()
        
    def check_output_queue(self):
        """Check for new output messages with batching"""
        messages_processed = 0
        max_messages_per_update = 2000  # Limit messages per GUI update
        
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
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_buffer.append({
            "timestamp": timestamp,
            "message": message,
            "type": msg_type
        })
    
    def flush_console_batch(self):
        """Flush batched messages to console"""
        if not self.console_buffer:
            return
            
        self.console_text.config(state=tk.NORMAL)
        
        # Add all batched messages at once
        for msg_data in self.console_buffer:
            timestamp = msg_data["timestamp"]
            message = msg_data["message"]
            msg_type = msg_data["type"]
            
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
        
        self.console_buffer.clear()
        self.console_text.config(state=tk.DISABLED)
        
        # Auto-scroll if enabled
        if self.auto_scroll_var.get():
            self.console_text.see(tk.END)
        
    def log_message(self, message, msg_type="info"):
        """Log a message to the console (single message)"""
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
        if self.auto_scroll_var.get():
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
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        self.console_text.config(state=tk.DISABLED)
        self.console_buffer.clear()
        self.log_message("Console cleared", "info")
        
    def update_status_indicator(self):
        """Update the status indicator"""
        running_count = len(self.running_commands)
        
        if running_count == 0:
            self.status_indicator.configure(text="● Ready", text_color="#00FF88")
            self.status_label.configure(text="Ready to execute commands")
        else:
            self.status_indicator.configure(text="● Running", text_color="#FFD700")
            self.status_label.configure(text=f"Executing {running_count} command(s)...")
            
        self.running_count_label.configure(text=f"Running: {running_count}")
    
    def on_closing(self):
        """Handle application closing"""
        # Stop all running processes
        self.process_manager.cleanup_all()
        
        # Clear running commands
        self.running_commands.clear()
        
        # Destroy the window
        self.root.destroy()
        
    def run(self):
        """Start the GUI application"""
        self.log_message("🎉 Shadow Command Center initialized", "success")
        self.log_message("Click any command button to execute", "info")
        
        # Center window on screen
        self.root.update_idletasks()
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
