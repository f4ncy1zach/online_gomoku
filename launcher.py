import os
import random
import socket
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BIND_IP = "127.0.0.1"
DEFAULT_CONNECT_IP = "127.0.0.1"
DEFAULT_PORT = 9999
NAME_POOL = ["John", "Tom", "Alice", "Mia", "Leo", "Evan", "Nora", "Sophie"]


def random_name(excluded=None):
    excluded = {value.strip().lower() for value in (excluded or []) if value}
    options = [name for name in NAME_POOL if name.lower() not in excluded]
    return random.choice(options) if options else random.choice(NAME_POOL)

# AI-generated code block: launcher GUI layout.
class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gomoku Launcher")
        self.root.resizable(False, False)

        self.bind_ip_var = tk.StringVar(value=DEFAULT_BIND_IP)
        self.connect_ip_var = tk.StringVar(value=DEFAULT_CONNECT_IP)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.name_a_var = tk.StringVar(value=random_name())
        self.name_b_var = tk.StringVar(value=random_name([self.name_a_var.get()]))
        self.status_var = tk.StringVar(value="Ready. Start the server or launch a pair of clients.")

        self.server_process = None
        self.client_processes = []

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_all)

    def build_ui(self):
        root_frame = tk.Frame(self.root, padx=14, pady=14)
        root_frame.pack(fill="both", expand=True)

        title = tk.Label(root_frame, text="Online Gomoku Launcher", font=("Segoe UI", 13, "bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="w")

        subtitle = tk.Label(
            root_frame,
            text="Start the server separately, then launch one or more 2-player matches from the same server.",
            justify="left",
            anchor="w",
        )
        subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        server_frame = tk.LabelFrame(root_frame, text="Server", padx=10, pady=10)
        server_frame.grid(row=2, column=0, columnspan=2, sticky="we")

        tk.Label(server_frame, text="Bind IP:").grid(row=0, column=0, sticky="w")
        tk.Entry(server_frame, textvariable=self.bind_ip_var, width=20).grid(row=0, column=1, sticky="we", padx=(8, 0))

        tk.Label(server_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        tk.Entry(server_frame, textvariable=self.port_var, width=20).grid(row=1, column=1, sticky="we", padx=(8, 0), pady=(6, 0))

        self.start_server_btn = tk.Button(server_frame, text="Start Server", command=self.start_server)
        self.start_server_btn.grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.stop_server_btn = tk.Button(server_frame, text="Stop Server", command=self.stop_server)
        self.stop_server_btn.grid(row=2, column=1, sticky="e", pady=(10, 0))

        client_frame = tk.LabelFrame(root_frame, text="Clients", padx=10, pady=10)
        client_frame.grid(row=3, column=0, columnspan=2, sticky="we", pady=(12, 0))

        tk.Label(client_frame, text="Connect IP:").grid(row=0, column=0, sticky="w")
        tk.Entry(client_frame, textvariable=self.connect_ip_var, width=20).grid(
            row=0, column=1, sticky="we", padx=(8, 0)
        )

        tk.Label(client_frame, text="Client A Name:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        tk.Entry(client_frame, textvariable=self.name_a_var, width=20).grid(row=1, column=1, sticky="we", padx=(8, 0), pady=(6, 0))
        tk.Button(client_frame, text="Randomize", command=self.randomize_name_a).grid(row=1, column=2, padx=(8, 0), pady=(6, 0))

        tk.Label(client_frame, text="Client B Name:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        tk.Entry(client_frame, textvariable=self.name_b_var, width=20).grid(row=2, column=1, sticky="we", padx=(8, 0), pady=(6, 0))
        tk.Button(client_frame, text="Randomize", command=self.randomize_name_b).grid(row=2, column=2, padx=(8, 0), pady=(6, 0))

        self.launch_client_a_btn = tk.Button(client_frame, text="Launch Client A", command=lambda: self.launch_client("A"))
        self.launch_client_a_btn.grid(row=3, column=0, sticky="w", pady=(10, 0))

        self.launch_client_b_btn = tk.Button(client_frame, text="Launch Client B", command=lambda: self.launch_client("B"))
        self.launch_client_b_btn.grid(row=3, column=1, sticky="w", pady=(10, 0))

        self.launch_pair_btn = tk.Button(client_frame, text="Launch 2 Clients", command=self.launch_pair)
        self.launch_pair_btn.grid(row=3, column=2, sticky="e", pady=(10, 0))

        self.quit_btn = tk.Button(root_frame, text="Quit", command=self.quit_all, width=12)
        self.quit_btn.grid(row=4, column=1, sticky="e", pady=(12, 0))

        status = tk.Label(root_frame, textvariable=self.status_var, anchor="w", justify="left")
        status.grid(row=5, column=0, columnspan=2, sticky="we", pady=(12, 0))

        root_frame.grid_columnconfigure(0, weight=1)
        server_frame.grid_columnconfigure(1, weight=1)
        client_frame.grid_columnconfigure(1, weight=1)

    def set_status(self, text):
        self.status_var.set(text)
        print(f"[Launcher] {text}")

    def parse_network_fields(self):
        bind_ip = self.bind_ip_var.get().strip() or DEFAULT_BIND_IP
        connect_ip = self.connect_ip_var.get().strip() or DEFAULT_CONNECT_IP
        port_text = self.port_var.get().strip()
        try:
            port = int(port_text)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            raise ValueError("Port must be an integer between 1 and 65535.")
        return bind_ip, connect_ip, port

    def server_running(self):
        return self.server_process is not None and self.server_process.poll() is None

    def refresh_server_state(self):
        if self.server_process is not None and self.server_process.poll() is not None:
            self.server_process = None

    def server_reachable(self, connect_ip, port):
        try:
            with socket.create_connection((connect_ip, port), timeout=0.25):
                return True
        except OSError:
            return False

    def can_bind_server(self, bind_ip, port):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((bind_ip, port))
            return True
        except OSError:
            return False
        finally:
            try:
                probe.close()
            except OSError:
                pass

    def cleanup_client_processes(self):
        self.client_processes = [proc for proc in self.client_processes if proc.poll() is None]

    def randomize_names(self):
        first = random_name()
        second = random_name([first])
        self.name_a_var.set(first)
        self.name_b_var.set(second)

    def randomize_name_a(self):
        current_name = self.name_a_var.get().strip()
        self.name_a_var.set(random_name([self.name_b_var.get(), current_name]))

    def randomize_name_b(self):
        current_name = self.name_b_var.get().strip()
        self.name_b_var.set(random_name([self.name_a_var.get(), current_name]))

    def normalize_pair_names(self, raw_name_a, raw_name_b):
        name_a = (raw_name_a or "").strip() or random_name()
        name_b = (raw_name_b or "").strip() or random_name([name_a])
        if name_a.casefold() == name_b.casefold():
            name_b = f"{name_b} (2)"
        return name_a, name_b

    def launch_client(self, slot):
        self.cleanup_client_processes()
        try:
            bind_ip, connect_ip, port = self.parse_network_fields()
        except ValueError as exc:
            messagebox.showerror("Invalid Port", str(exc))
            return

        if not (self.server_running() or self.server_reachable(connect_ip, port)):
            self.set_status(f"Client launch blocked: no server reachable at {connect_ip}:{port}.")
            messagebox.showerror(
                "Server Not Found",
                f"Cannot launch a client because no server is reachable at {connect_ip}:{port}.\n"
                "Start the server first or check Connect IP/Port.",
            )
            return

        if slot == "A":
            name = (self.name_a_var.get() or "").strip() or random_name([self.name_b_var.get()])
            self.name_a_var.set(name)
        else:
            name = (self.name_b_var.get() or "").strip() or random_name([self.name_a_var.get()])
            self.name_b_var.set(name)

        try:
            client = subprocess.Popen(
                [
                    sys.executable,
                    os.path.join(BASE_DIR, "client.py"),
                    "--host",
                    connect_ip,
                    "--port",
                    str(port),
                    "--name",
                    name,
                    "--raise-window",
                ],
                cwd=BASE_DIR,
            )
            self.client_processes.append(client)
            self.set_status(f"Launched Client {slot} to {connect_ip}:{port} as '{name}'.")
        except OSError as exc:
            messagebox.showerror("Launch Error", f"Failed to launch Client {slot}.\n{exc}")

    def start_server(self):
        self.refresh_server_state()
        if self.server_running():
            self.set_status("Server is already running.")
            return

        try:
            bind_ip, connect_ip, port = self.parse_network_fields()
        except ValueError as exc:
            messagebox.showerror("Invalid Port", str(exc))
            return

        if not self.can_bind_server(bind_ip, port):
            self.set_status(f"Server is already running or port {port} is unavailable on {bind_ip}.")
            messagebox.showinfo(
                "Server Already Running",
                f"The selected bind address {bind_ip}:{port} is already in use.\n"
                "Stop that server first before starting a new one.",
            )
            return

        try:
            self.server_process = subprocess.Popen(
                [sys.executable, os.path.join(BASE_DIR, "server.py"), "--host", bind_ip, "--port", str(port)],
                cwd=BASE_DIR,
            )
            self.set_status(f"Server started on {bind_ip}:{port}.")
        except OSError as exc:
            self.server_process = None
            messagebox.showerror("Server Error", f"Failed to start the server.\n{exc}")

    def stop_server(self):
        self.refresh_server_state()
        if not self.server_running():
            self.set_status("Stop requested, but no launcher-managed server is running.")
            messagebox.showinfo(
                "No Launcher-Managed Server",
                "The launcher does not currently own a running server process.",
            )
            return

        self.terminate_process(self.server_process)
        self.server_process = None
        self.set_status("Server stopped.")

    def launch_pair(self):
        self.cleanup_client_processes()
        try:
            bind_ip, connect_ip, port = self.parse_network_fields()
        except ValueError as exc:
            messagebox.showerror("Invalid Port", str(exc))
            return

        server_ready = self.server_running() or self.server_reachable(connect_ip, port)
        if not server_ready:
            self.set_status(f"Client launch blocked: no server reachable at {connect_ip}:{port}.")
            messagebox.showerror(
                "Server Not Found",
                f"Cannot launch clients because no server is reachable at {connect_ip}:{port}.\n"
                "Start the server first or check Connect IP/Port.",
            )
            return

        if bind_ip and bind_ip != connect_ip and not self.server_running():
            self.set_status(
                f"Launching clients to {connect_ip}:{port} while server binds on {bind_ip}; verify the address is reachable from this machine."
            )

        name_a, name_b = self.normalize_pair_names(self.name_a_var.get(), self.name_b_var.get())
        self.name_a_var.set(name_a)
        self.name_b_var.set(name_b)

        try:
            client_a = subprocess.Popen(
                [
                    sys.executable,
                    os.path.join(BASE_DIR, "client.py"),
                    "--host",
                    connect_ip,
                    "--port",
                    str(port),
                    "--name",
                    name_a,
                    "--raise-window",
                ],
                cwd=BASE_DIR,
            )
            client_b = subprocess.Popen(
                [
                    sys.executable,
                    os.path.join(BASE_DIR, "client.py"),
                    "--host",
                    connect_ip,
                    "--port",
                    str(port),
                    "--name",
                    name_b,
                    "--raise-window",
                ],
                cwd=BASE_DIR,
            )
            self.client_processes.extend([client_a, client_b])
            self.set_status(
                f"Launched 2 clients to {connect_ip}:{port} as '{name_a}' and '{name_b}'."
            )
        except OSError as exc:
            messagebox.showerror("Launch Error", f"Failed to launch client windows.\n{exc}")

    def terminate_process(self, proc):
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
        except OSError:
            pass
        try:
            if proc.poll() is None:
                proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
            except OSError:
                pass

    def terminate_children(self):
        self.cleanup_client_processes()
        for proc in list(self.client_processes):
            self.terminate_process(proc)
        self.client_processes.clear()
        self.terminate_process(self.server_process)
        self.server_process = None

    def quit_all(self):
        self.terminate_children()
        self.set_status("Launcher exiting. All launcher-managed processes were terminated.")
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
