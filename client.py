import argparse
import queue
import random
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from game import BLACK, BOARD_SIZE, EMPTY, WHITE
from protocol import recv_msg, send_msg


GRID_SPACING = 32
MARGIN = 24
STONE_RADIUS = 12
CANVAS_SIZE = MARGIN * 2 + GRID_SPACING * (BOARD_SIZE - 1)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9999
DEFAULT_NAMES = ["John", "Tom", "Alice", "Mia", "Leo", "Evan", "Nora", "Sophie"]


class NetworkClient:
    def __init__(self, host, port, name, inbox):
        self.host = host
        self.port = port
        self.name = name
        self.inbox = inbox
        self.sock = None
        self.file = None
        self.running = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.file = self.sock.makefile("r", encoding="utf-8")
        self.running = True
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def receive_loop(self):
        try:
            while self.running:
                msg = recv_msg(self.file)
                if msg is None:
                    self.inbox.put({"type": "_LOCAL_DISCONNECT"})
                    return
                self.inbox.put(msg)
        except (ConnectionResetError, OSError):
            self.inbox.put({"type": "_LOCAL_DISCONNECT"})
        finally:
            self.running = False

    def send(self, **message):
        if not self.running:
            return False
        try:
            send_msg(self.sock, **message)
            return True
        except OSError:
            self.running = False
            self.inbox.put({"type": "_LOCAL_DISCONNECT"})
            return False

    def close(self):
        self.running = False
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            if self.file:
                self.file.close()
        except OSError:
            pass
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass


class GomokuGUI:
    # AI-generated code block: GUI layout.
    def __init__(self, root, host, port, name):
        self.root = root
        self.root.title("Online Gomoku")
        self.is_closing = False

        self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.color = None
        self.opponent = None
        self.name = name
        self.my_turn = False
        self.game_over = False
        self.move_count = 0
        self.last_move = None
        self.first_turn = None
        self.forfeit_requested = False
        self.hover_cell = None
        self.connection_state = "connecting"

        self.banner_var = tk.StringVar(value="Ready to connect")
        self.status_var = tk.StringVar(value="Ready to connect")
        self.chat_inbox = queue.Queue()
        self.net = NetworkClient(host, port, name, self.chat_inbox)

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll_messages)

    def build_ui(self):
        main = tk.Frame(self.root, padx=12, pady=12)
        main.pack(fill="both", expand=True)

        banner = tk.Label(
            main,
            textvariable=self.banner_var,
            anchor="w",
            justify="left",
            bg="#1f3c88",
            fg="white",
            padx=10,
            pady=7,
            font=("Segoe UI", 10, "bold"),
        )
        banner.pack(fill="x", pady=(0, 12))

        body = tk.Frame(main)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.canvas = tk.Canvas(
            left,
            width=CANVAS_SIZE,
            height=CANVAS_SIZE,
            bg="#d8b26e",
            highlightthickness=1,
            highlightbackground="#7b5a29",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_board_click)
        self.canvas.bind("<Motion>", self.on_board_hover)
        self.canvas.bind("<Leave>", self.on_board_leave)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        status_row = tk.Frame(left)
        status_row.pack(fill="x", pady=(10, 0))

        self.status_led = tk.Canvas(status_row, width=14, height=14, highlightthickness=0, bd=0)
        self.status_led.pack(side="left", padx=(0, 8))
        self.status_led_dot = self.status_led.create_oval(2, 2, 12, 12, fill="#f4b400", outline="")

        self.status_label = tk.Label(
            status_row,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            width=48,
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.info_label = tk.Label(left, text="Match has not started yet", anchor="w", justify="left")
        self.info_label.pack(fill="x", pady=(6, 0))

        chat_title = tk.Label(right, text="Chat")
        chat_title.pack(anchor="w")

        self.chat_log = scrolledtext.ScrolledText(right, width=40, height=24, state="disabled")
        self.chat_log.pack(fill="both", expand=True)

        input_row = tk.Frame(right)
        input_row.pack(fill="x", pady=(8, 0))

        self.chat_entry = tk.Entry(input_row)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", self.send_chat)

        send_btn = tk.Button(input_row, text="Send", command=self.send_chat)
        send_btn.pack(side="left", padx=(8, 0))

        forfeit_btn = tk.Button(right, text="Forfeit", command=self.forfeit)
        forfeit_btn.pack(anchor="e", pady=(8, 0))

        self.rematch_btn = tk.Button(right, text="Rematch", command=self.request_rematch, state="disabled")
        self.rematch_btn.pack(anchor="e", pady=(6, 0))

        quit_btn = tk.Button(right, text="Quit Game", command=self.on_close)
        quit_btn.pack(anchor="e", pady=(6, 0))

        self.draw_board()

    def connect(self):
        self.set_status("Connecting...", state="connecting")
        self.net.connect()

    def bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
        except tk.TclError:
            pass

    def set_player_name(self, name):
        self.name = name
        self.net.name = name

    def set_status(self, text, state=None):
        self.status_var.set(text)
        if state is not None:
            self.set_led_state(state)

    def set_led_state(self, state):
        colors = {
            "connecting": "#f4b400",
            "online": "#2ecc71",
            "waiting": "#3498db",
            "your-turn": "#1abc9c",
            "opponent-turn": "#95a5a6",
            "game-over": "#7f8c8d",
            "error": "#e74c3c",
            "closed": "#666666",
        }
        self.connection_state = state
        self.status_led.itemconfigure(self.status_led_dot, fill=colors.get(state, "#f4b400"))

    def canvas_geometry(self):
        # Recompute the grid geometry from the current widget size so the board stays centered when resized.
        width = max(self.canvas.winfo_width(), CANVAS_SIZE)
        height = max(self.canvas.winfo_height(), CANVAS_SIZE)
        spacing = min(width, height) / max(BOARD_SIZE - 1, 1)
        spacing = max(18, min(spacing, 48))
        board_extent = spacing * (BOARD_SIZE - 1)
        margin_x = (width - board_extent) / 2
        margin_y = (height - board_extent) / 2
        radius = max(8, min(STONE_RADIUS, int(spacing * 0.38)))
        return {
            "width": width,
            "height": height,
            "spacing": spacing,
            "margin_x": margin_x,
            "margin_y": margin_y,
            "radius": radius,
        }

    def cell_to_point(self, row, col):
        geom = self.canvas_geometry()
        x = geom["margin_x"] + col * geom["spacing"]
        y = geom["margin_y"] + row * geom["spacing"]
        return x, y

    def point_to_cell(self, x, y):
        # Convert a mouse position back into board coordinates.
        geom = self.canvas_geometry()
        col = round((x - geom["margin_x"]) / geom["spacing"])
        row = round((y - geom["margin_y"]) / geom["spacing"])
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return None
        return row, col

    def draw_board(self):
        self.canvas.delete("all")
        geom = self.canvas_geometry()
        for i in range(BOARD_SIZE):
            x = geom["margin_x"] + i * geom["spacing"]
            self.canvas.create_line(x, geom["margin_y"], x, geom["height"] - geom["margin_y"], fill="#5b3d1f")
            y = geom["margin_y"] + i * geom["spacing"]
            self.canvas.create_line(geom["margin_x"], y, geom["width"] - geom["margin_x"], y, fill="#5b3d1f")

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                color = self.board[row][col]
                if color == EMPTY:
                    continue
                self.draw_stone(row, col, color)

        self.draw_last_move_marker()
        self.draw_hover_preview()

    def draw_stone(self, row, col, color):
        geom = self.canvas_geometry()
        x, y = self.cell_to_point(row, col)
        radius = geom["radius"]
        fill = "#111111" if color == BLACK else "#f5f5f5"
        outline = "#000000" if color == BLACK else "#999999"
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=2,
        )

    def draw_hover_preview(self):
        if self.game_over or not self.my_turn or self.hover_cell is None:
            return
        row, col = self.hover_cell
        if self.board[row][col] != EMPTY:
            return

        geom = self.canvas_geometry()
        x, y = self.cell_to_point(row, col)
        radius = geom["radius"]
        fill = "#4b4b4b" if self.color == BLACK else "#f0e5b8"
        outline = "#222222" if self.color == BLACK else "#b48a3a"
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=2,
            stipple="gray50",
            tags=("hover",),
        )

    def draw_last_move_marker(self):
        if self.last_move is None:
            return

        row, col = self.last_move
        # AI-generated helper block: draw a high-contrast ring around the last move so it stays visible.
        geom = self.canvas_geometry()
        x, y = self.cell_to_point(row, col)
        radius = geom["radius"] + 5
        outline = "#ff4d4d" if self.hover_cell == self.last_move else "#e53935"
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=outline,
            width=3,
            tags=("last-move",),
        )

    def on_canvas_resize(self, _event=None):
        self.draw_board()

    def on_board_hover(self, event):
        cell = self.point_to_cell(event.x, event.y)
        if cell == self.hover_cell:
            return
        self.hover_cell = cell
        self.draw_board()

    def on_board_leave(self, _event=None):
        if self.hover_cell is None:
            return
        self.hover_cell = None
        self.draw_board()

    def on_board_click(self, event):
        if self.game_over:
            return
        if not self.my_turn:
            self.set_banner("It is not your turn yet")
            self.set_status("It is not your turn yet", state="opponent-turn")
            return

        cell = self.point_to_cell(event.x, event.y)
        if cell is None:
            return
        row, col = cell
        if not self.net.send(type="MOVE", row=row, col=col):
            self.set_status("Connection is not available", state="error")

    def send_chat(self, _event=None):
        message = self.chat_entry.get().strip()
        if not message:
            return
        if self.net.send(type="CHAT", message=message):
            self.chat_entry.delete(0, tk.END)
        else:
            self.set_status("Failed to send chat. Connection is closed", state="error")

    def forfeit(self):
        if self.game_over:
            return
        if not messagebox.askyesno("Confirm Forfeit", "Forfeit this match?"):
            return
        if not self.net.send(type="FORFEIT"):
            self.set_status("Connection is not available", state="error")
            return
        self.forfeit_requested = True
        self.set_status("Forfeit sent. You can close the window now.", state="game-over")

    def request_rematch(self):
        if not self.game_over:
            return
        if self.net.send(type="REMATCH"):
            self.rematch_btn.configure(state="disabled")
            self.set_banner("Waiting for a rematch...")
            self.set_status("Rematch requested. Waiting for a new match...", state="waiting")
        else:
            self.set_status("Rematch request failed", state="error")

    def poll_messages(self):
        if self.is_closing:
            return
        while True:
            try:
                msg = self.chat_inbox.get_nowait()
            except queue.Empty:
                break
            self.handle_message(msg)
        self.root.after(100, self.poll_messages)

    def handle_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "HELLO":
            self.net.send(type="JOIN", name=self.name)
            self.set_banner("Connected. Waiting for matchmaking...")
            self.set_status("Connected. Waiting for matchmaking...", state="online")
            return

        if msg_type == "WAIT":
            self.set_banner("Waiting for an opponent...")
            self.set_status("Waiting for an opponent...", state="waiting")
            return

        if msg_type == "START":
            # The server tells us which color opens the match, so the GUI must follow that turn order.
            self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
            self.draw_board()
            self.color = msg.get("color")
            self.opponent = msg.get("opponent")
            self.game_over = False
            self.move_count = 0
            self.last_move = None
            self.first_turn = msg.get("first_turn")
            self.my_turn = self.color == self.first_turn
            self.rematch_btn.configure(state="disabled")
            my_color = self.color_text(self.color)
            self.set_banner(self.turn_banner(next_turn=self.first_turn or BLACK))
            self.set_status(f"Game started. You are {my_color}.", state=("your-turn" if self.my_turn else "opponent-turn"))
            self.update_info()
            return

        if msg_type == "UPDATE":
            # Update the local board first, then refresh the turn banner and the visible last-move cue.
            row = msg["row"]
            col = msg["col"]
            color = msg["color"]
            self.board[row][col] = color
            self.last_move = (row, col)
            self.move_count += 1
            self.my_turn = self.color == msg.get("next_turn")
            self.draw_board()
            if msg.get("next_turn") is None:
                self.set_banner("Game over")
                self.set_status(f"Final move: {color} at ({row}, {col})", state="game-over")
            else:
                self.set_banner(self.turn_banner(next_turn=msg.get("next_turn")))
                self.set_status(
                    f"Move: {color} at ({row}, {col})",
                    state=("your-turn" if self.my_turn else "opponent-turn"),
                )
            self.update_info(next_turn=msg.get("next_turn"))
            return

        if msg_type == "WIN":
            row = msg.get("row")
            col = msg.get("col")
            color = msg.get("color")
            if row is not None and col is not None and color:
                self.board[row][col] = color
                self.last_move = (row, col)
                self.move_count += 1
            self.draw_board()
            self.my_turn = False
            self.game_over = True
            self.rematch_btn.configure(state="normal")
            self.set_banner("Game over")
            winner = msg.get("winner")
            winner_name = msg.get("winner_name")
            self.set_status(f"{winner_name} wins as {self.color_text(winner)}", state="game-over")
            self.update_info()
            return

        if msg_type == "DRAW":
            self.my_turn = False
            self.game_over = True
            self.rematch_btn.configure(state="normal")
            self.set_banner("Game over")
            self.set_status("Game ended in a draw", state="game-over")
            self.update_info()
            return

        if msg_type == "FORFEIT":
            self.my_turn = False
            self.game_over = True
            self.rematch_btn.configure(state="normal")
            self.set_banner("Game over")
            winner = msg.get("winner")
            if winner == self.color:
                self.set_status("Opponent forfeited. You win.", state="game-over")
            else:
                self.set_status("You forfeited.", state="game-over")
            self.update_info()
            return

        if msg_type == "DISCONNECT":
            self.my_turn = False
            self.game_over = True
            self.rematch_btn.configure(state="normal")
            self.set_banner("Opponent disconnected")
            self.set_status("Opponent disconnected", state="game-over")
            self.update_info()
            return

        if msg_type == "_LOCAL_DISCONNECT":
            self.my_turn = False
            self.game_over = True
            self.rematch_btn.configure(state="disabled")
            self.set_banner("Connection closed")
            self.set_status("Connection closed", state="closed")
            self.update_info()
            return

        if msg_type == "ERROR":
            self.set_banner("Action unavailable")
            self.set_status(f"Error: {msg.get('message', 'Unknown error')}", state="error")
            return

        if msg_type == "CHAT":
            self.append_chat(f"{msg.get('name', 'Opponent')}: {msg.get('message', '')}")
            return

    def append_chat(self, text):
        self.chat_log.configure(state="normal")
        self.chat_log.insert(tk.END, text + "\n")
        self.chat_log.see(tk.END)
        self.chat_log.configure(state="disabled")

    def set_banner(self, text):
        self.banner_var.set(text)

    def color_text(self, color):
        if color == BLACK:
            return "Black (X)"
        if color == WHITE:
            return "White (O)"
        return color or "?"

    def turn_banner(self, next_turn):
        next_turn_text = self.color_text(next_turn)
        if self.my_turn:
            if self.move_count == 0:
                return "Your turn - place the first piece"
            return f"Your turn - {next_turn_text} to move"
        return f"Waiting for {next_turn_text} to move"

    def update_info(self, next_turn=None):
        parts = [f"You: {self.name}", f"Color: {self.color_text(self.color)}"]
        parts.append(f"Opponent: {self.opponent or '?'}")
        if self.game_over:
            parts.append("Result: finished")
        elif next_turn:
            parts.append(f"Next turn: {self.color_text(next_turn)}")
        else:
            parts.append(f"My turn: {'yes' if self.my_turn else 'no'}")
        self.info_label.configure(text=" | ".join(parts))

    def on_close(self):
        if self.is_closing:
            return
        self.is_closing = True
        # If the user already forfeited, close silently instead of asking again.
        if self.forfeit_requested or self.game_over:
            self.net.close()
            if self.root.winfo_exists():
                self.root.destroy()
            return

        if self.net.running and self.color is not None and not self.game_over:
            if not messagebox.askyesno("Quit Game", "Leave this match and forfeit?"):
                self.is_closing = False
                return
            try:
                self.net.send(type="FORFEIT")
            except OSError:
                pass
        self.net.close()
        if self.root.winfo_exists():
            self.root.destroy()


def ask_for_name(parent, initial_name=None):
    dialog = tk.Toplevel(parent)
    dialog.title("Choose Name")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    tk.Label(dialog, text="Enter your name:").grid(row=0, column=0, columnspan=3, padx=12, pady=(12, 6), sticky="w")

    name_var = tk.StringVar(value=(initial_name or random.choice(DEFAULT_NAMES)))
    entry = tk.Entry(dialog, textvariable=name_var, width=24)
    entry.grid(row=1, column=0, padx=(12, 6), pady=(0, 12), sticky="we")

    def pick_name(excluded=None):
        excluded = {value.strip().lower() for value in (excluded or []) if value}
        options = [name for name in DEFAULT_NAMES if name.lower() not in excluded]
        return random.choice(options) if options else random.choice(DEFAULT_NAMES)

    def randomize_name():
        # AI-generated helper block: keep randomize from reusing the current name unless there is no alternative.
        current_name = name_var.get().strip()
        name_var.set(pick_name([current_name]))
        entry.icursor(tk.END)

    def confirm():
        dialog.result = name_var.get().strip() or pick_name()
        dialog.destroy()

    def cancel():
        dialog.result = pick_name([name_var.get().strip()])
        dialog.destroy()

    tk.Button(dialog, text="Randomize", command=randomize_name).grid(row=1, column=1, padx=(0, 6), pady=(0, 12))
    tk.Button(dialog, text="OK", width=8, command=confirm).grid(row=1, column=2, padx=(0, 12), pady=(0, 12))

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    entry.select_range(0, tk.END)
    entry.bind("<Return>", lambda _event: confirm())
    parent.wait_window(dialog)
    return getattr(dialog, "result", random.choice(DEFAULT_NAMES))


def run_headless(host, port, name):
    inbox = queue.Queue()
    client = NetworkClient(host, port, name, inbox)
    try:
        client.connect()
    except OSError as exc:
        print(f"Failed to connect to {host}:{port}: {exc}")
        return 1

    print(f"Connected to {host}:{port} as {name}")

    try:
        while client.running:
            try:
                msg = inbox.get(timeout=0.25)
            except queue.Empty:
                continue

            msg_type = msg.get("type")
            if msg_type == "HELLO":
                client.send(type="JOIN", name=name)
                print("Joined matchmaking queue")
                continue
            if msg_type == "WAIT":
                print("Waiting for an opponent...")
                continue
            if msg_type == "START":
                print(f"Match started. You are {msg.get('color')} vs {msg.get('opponent')}")
                continue
            if msg_type == "UPDATE":
                print(f"Move: {msg.get('color')} at ({msg.get('row')}, {msg.get('col')})")
                continue
            if msg_type == "WIN":
                print(f"Winner: {msg.get('winner_name')} ({msg.get('winner')})")
                continue
            if msg_type == "DRAW":
                print("Game ended in a draw")
                continue
            if msg_type == "FORFEIT":
                print("Game ended by forfeit")
                continue
            if msg_type == "DISCONNECT":
                print("Opponent disconnected")
                break
            if msg_type == "_LOCAL_DISCONNECT":
                print("Connection closed")
                break
            if msg_type == "ERROR":
                print(f"Error: {msg.get('message', 'Unknown error')}")
                continue
            if msg_type == "CHAT":
                print(f"{msg.get('name', 'Opponent')}: {msg.get('message', '')}")
                continue
    except KeyboardInterrupt:
        if client.running:
            try:
                client.send(type="FORFEIT")
            except OSError:
                pass
    finally:
        client.close()
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Online Gomoku GUI client")
    parser.add_argument("host", nargs="?", default=None, help="Server host (legacy positional)")
    parser.add_argument("port", nargs="?", type=int, default=None, help="Server port (legacy positional)")
    parser.add_argument("--host", dest="host_flag", help="Server host")
    parser.add_argument("--port", dest="port_flag", type=int, help="Server port")
    parser.add_argument("--name", dest="name", help="Player name")
    parser.add_argument("--autoconnect", action="store_true", help="Skip the name dialog and connect immediately")
    parser.add_argument("--raise-window", action="store_true", help="Bring the client window to the front after launch")
    parser.add_argument("--headless", action="store_true", help="Run without opening a Tkinter window")
    args = parser.parse_args(argv)

    host = args.host_flag or args.host or DEFAULT_HOST
    port = args.port_flag or args.port or DEFAULT_PORT
    return host, port, args.name, args.autoconnect, args.raise_window, args.headless


def main():
    host, port, provided_name, autoconnect, raise_window, headless = parse_args(sys.argv[1:])

    if headless:
        name = (provided_name or random.choice(DEFAULT_NAMES)).strip() or random.choice(DEFAULT_NAMES)
        raise SystemExit(run_headless(host, port, name))

    root = tk.Tk()
    root.withdraw()

    initial_name = (provided_name or random.choice(DEFAULT_NAMES)).strip() or random.choice(DEFAULT_NAMES)
    try:
        app = GomokuGUI(root, host, port, initial_name)
    except OSError as exc:
        root.destroy()
        messagebox.showerror("Connection Error", f"Failed to create the client UI\n{exc}")
        return

    root.deiconify()
    if raise_window:
        app.bring_to_front()

    if autoconnect:
        name = initial_name
    elif provided_name:
        name = provided_name.strip() or random.choice(DEFAULT_NAMES)
    else:
        name = ask_for_name(root, initial_name)

    app.set_player_name(name)

    try:
        app.connect()
    except OSError as exc:
        root.destroy()
        messagebox.showerror("Connection Error", f"Failed to connect to {host}:{port}\n{exc}")
        return

    if raise_window:
        root.after(100, app.bring_to_front)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_close()


if __name__ == "__main__":
    main()