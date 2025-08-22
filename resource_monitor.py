import customtkinter as ctk
import psutil
import platform
import time
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ResourceMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Compact System Monitor")
        self.geometry("900x400")
        self.minsize(600, 350)
        self.resizable(True, True)  # Allow resizing

        self.prev_disk_io = psutil.disk_io_counters()
        self.prev_time = time.time()

        # CPU Frame
        self.cpu_frame = ctk.CTkFrame(self)
        self.cpu_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(self.cpu_frame, text="🧠 CPU Usage", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        self.cpu_content_label = ctk.CTkLabel(
            self.cpu_frame,
            text="",
            cursor="hand2",
            wraplength=880,
            justify="left",
            font=ctk.CTkFont(family="Courier New", size=12)  # Fixed width font for alignment
        )
        self.cpu_content_label.pack(anchor="w", padx=10)
        self.cpu_content_label.bind("<Button-1>", lambda e: self.show_cpu_info())

        # Memory Frame
        self.mem_frame = ctk.CTkFrame(self)
        self.mem_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(self.mem_frame, text="📦 Memory", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        self.mem_content_label = ctk.CTkLabel(self.mem_frame, text="", cursor="hand2", wraplength=880, justify="left")
        self.mem_content_label.pack(anchor="w", padx=10)
        self.mem_content_label.bind("<Button-1>", lambda e: self.show_ram_info())

        self.swap_content_label = ctk.CTkLabel(self.mem_frame, text="", cursor="hand2", wraplength=880, justify="left")
        self.swap_content_label.pack(anchor="w", padx=10, pady=(2, 0))
        self.swap_content_label.bind("<Button-1>", lambda e: self.show_swap_info())

        # Disk I/O Frame
        self.disk_io_frame = ctk.CTkFrame(self)
        self.disk_io_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(self.disk_io_frame, text="💾 Disk I/O", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        self.disk_io_content_label = ctk.CTkLabel(self.disk_io_frame, text="", cursor="hand2", wraplength=880, justify="left")
        self.disk_io_content_label.pack(anchor="w", padx=10)
        self.disk_io_content_label.bind("<Button-1>", lambda e: self.show_disk_info())

        # Disk Devices Frame
        self.disk_devices_frame = ctk.CTkFrame(self)
        self.disk_devices_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        ctk.CTkLabel(self.disk_devices_frame, text="🧱 Disk Devices", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")

        self.disk_devices_content_label = ctk.CTkLabel(
            self.disk_devices_frame,
            text="",
            wraplength=880,
            justify="left",
            cursor="hand2",
            font=ctk.CTkFont(family="Courier New", size=12)
        )
        self.disk_devices_content_label.pack(anchor="w", padx=10, fill="both", expand=True)
        self.disk_devices_content_label.bind("<Button-1>", lambda e: self.show_disk_info())

        self.update_usage()

    def update_usage(self):
        # CPU: fixed width columns
        cpu_percents = psutil.cpu_percent(percpu=True)
        cpu_text_lines = []
        for i, p in enumerate(cpu_percents):
            # Format each CPU value as fixed width (e.g. 12 chars per CPU: "CPU 0: 12.3% "
            cpu_text_lines.append(f"CPU {i:2d}: {p:5.1f}%")
        # Join with fixed spacing and then split into multiple lines of 4 CPUs each
        # This way the display is neat vertically too
        grouped = [cpu_text_lines[i:i+4] for i in range(0, len(cpu_text_lines), 4)]
        cpu_text = "\n".join(["   ".join(group) for group in grouped])
        self.cpu_content_label.configure(text=cpu_text)

        # Memory
        mem = psutil.virtual_memory()
        ram_text = f"RAM: {mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent}%)"
        self.mem_content_label.configure(text=ram_text)

        # Swap
        swap = psutil.swap_memory()
        if swap.total > 0:
            swap_text = f"Swap: {swap.used / (1024**3):.1f} GB / {swap.total / (1024**3):.1f} GB ({swap.percent}%)"
        else:
            swap_text = "Swap: Not present"
        self.swap_content_label.configure(text=swap_text)

        # Disk I/O
        current_time = time.time()
        current_io = psutil.disk_io_counters()
        time_diff = current_time - self.prev_time
        read_diff = current_io.read_bytes - self.prev_disk_io.read_bytes
        write_diff = current_io.write_bytes - self.prev_disk_io.write_bytes
        read_speed = self.format_bytes_per_sec(read_diff / time_diff)
        write_speed = self.format_bytes_per_sec(write_diff / time_diff)
        self.disk_io_content_label.configure(text=f"Read: {read_speed} | Write: {write_speed}")
        self.prev_disk_io = current_io
        self.prev_time = current_time

        # Disk Devices: vertical list with one device per line
        parts = psutil.disk_partitions(all=False)
        devices = []
        seen = set()
        for part in parts:
            if part.device in seen:
                continue
            seen.add(part.device)
            # Filter out virtual filesystems
            if any(x in part.fstype.lower() for x in ['tmpfs', 'devtmpfs', 'proc', 'sysfs', 'squashfs']):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                if usage.total < 2 * 1024**3:
                    continue
                devices.append(
                    f"{part.device:<15} @ {part.mountpoint:<20} — {usage.used / (1024**3):6.1f} / {usage.total / (1024**3):6.1f} GB ({usage.percent:3.0f}%)"
                )
            except PermissionError:
                continue

        disk_devices_text = "\n".join(devices) if devices else "No usable disks found."
        self.disk_devices_content_label.configure(text=disk_devices_text)

        self.after(1000, self.update_usage)

    def format_bytes_per_sec(self, bps):
        if bps > 1024**2:
            return f"{bps / (1024**2):.2f} MB/s"
        elif bps > 1024:
            return f"{bps / 1024:.2f} KB/s"
        else:
            return f"{bps:.0f} B/s"

    def show_popup(self, title, content):
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("450x300")
        textbox = ctk.CTkTextbox(popup, wrap="word")
        textbox.insert("0.0", content)
        textbox.configure(state="disabled")
        textbox.pack(expand=True, fill="both", padx=10, pady=10)

    def show_cpu_info(self):
        freq = psutil.cpu_freq()
        info = f"""CPU Info:
Logical CPUs: {psutil.cpu_count(logical=True)}
Physical CPUs: {psutil.cpu_count(logical=False)}
Frequency: {freq.current:.2f} MHz
System: {platform.system()} {platform.release()}
Processor: {platform.processor()}
"""
        self.show_popup("CPU Details", info)

    def show_ram_info(self):
        mem = psutil.virtual_memory()
        info = f"""RAM Info:
Total: {mem.total / (1024**3):.2f} GB
Available: {mem.available / (1024**3):.2f} GB
Used: {mem.used / (1024**3):.2f} GB
Percent: {mem.percent}%
"""
        self.show_popup("RAM Details", info)

    def show_swap_info(self):
        swap = psutil.swap_memory()
        info = f"""Swap Info:
Total: {swap.total / (1024**3):.2f} GB
Used: {swap.used / (1024**3):.2f} GB
Free: {swap.free / (1024**3):.2f} GB
Percent: {swap.percent}%
"""
        if os.name == "posix":
            try:
                with open("/proc/swaps") as f:
                    swaps = f.read()
                    info += f"\nSwap Devices:\n{swaps}"
            except Exception:
                pass
        self.show_popup("Swap Details", info)

    def show_disk_info(self):
        parts = psutil.disk_partitions(all=False)
        info = "Device          Mount                Used / Total       % Used\n"
        info += "-" * 60 + "\n"

        seen = set()
        for part in parts:
            if part.device in seen:
                continue
            seen.add(part.device)

            if any(x in part.fstype.lower() for x in ['tmpfs', 'devtmpfs', 'proc', 'sysfs', 'squashfs']):
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)
                if usage.total < 2 * 1024**3:
                    continue

                used = usage.used / (1024**3)
                total = usage.total / (1024**3)
                percent = usage.percent
                info += (
                    f"{part.device:<15} {part.mountpoint:<20} "
                    f"{used:6.1f} GB / {total:6.1f} GB   {percent:3.0f}%\n"
                )
            except PermissionError:
                continue

        self.show_popup("Disk Device Details", info)


if __name__ == "__main__":
    app = ResourceMonitorApp()
    app.mainloop()
