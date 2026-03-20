import queue
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog

from game import BLACK, BOARD_SIZE, EMPTY
from protocol import recv_msg, send_msg


GRID_SPACING = 32
MARGIN = 24
STONE_RADIUS = 12
CANVAS_SIZE = MARGIN * 2 + GRID_SPACING * (BOARD_SIZE - 1)


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
        # The GUI stays on the main thread; socket reads happen in a background thread.
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
        if self.running:
            send_msg(self.sock, **message)

    def close(self):
        self.running = False
        try:
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
    def __init__(self, root, host, port, name):
        self.root = root
        self.root.title("Online Gomoku")

        self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.color = None
        self.opponent = None
        self.name = name
        self.my_turn = False
        self.game_over = False
        self.status_var = tk.StringVar(value="Connecting...")
        self.chat_inbox = queue.Queue()
        self.net = NetworkClient(host, port, name, self.chat_inbox)

        self.build_ui()
        self.net.connect()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll_messages)

    def build_ui(self):
        main = tk.Frame(self.root, padx=12, pady=12)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=False)

        right = tk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.canvas = tk.Canvas(
            left,
            width=CANVAS_SIZE,
            height=CANVAS_SIZE,
            bg="#d8b26e",
            highlightthickness=1,
            highlightbackground="#7b5a29",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_board_click)

        self.status_label = tk.Label(
            left,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            width=48,
        )
        self.status_label.pack(fill="x", pady=(10, 0))

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

        self.draw_board()

    def draw_board(self):
        self.canvas.delete("all")
        # Redraw the full board each time to keep Canvas state simple and reliable.
        for i in range(BOARD_SIZE):
            x = MARGIN + i * GRID_SPACING
            self.canvas.create_line(x, MARGIN, x, CANVAS_SIZE - MARGIN, fill="#5b3d1f")
            y = MARGIN + i * GRID_SPACING
            self.canvas.create_line(MARGIN, y, CANVAS_SIZE - MARGIN, y, fill="#5b3d1f")

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                color = self.board[row][col]
                if color == EMPTY:
                    continue
                self.draw_stone(row, col, color)

    def draw_stone(self, row, col, color):
        x = MARGIN + col * GRID_SPACING
        y = MARGIN + row * GRID_SPACING
        fill = "#111111" if color == BLACK else "#f5f5f5"
        outline = "#000000" if color == BLACK else "#999999"
        self.canvas.create_oval(
            x - STONE_RADIUS,
            y - STONE_RADIUS,
            x + STONE_RADIUS,
            y + STONE_RADIUS,
            fill=fill,
            outline=outline,
            width=2,
        )

    def on_board_click(self, event):
        if self.game_over:
            return
        if not self.my_turn:
            self.set_status("It is not your turn yet")
            return

        col = round((event.x - MARGIN) / GRID_SPACING)
        row = round((event.y - MARGIN) / GRID_SPACING)
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return
        self.net.send(type="MOVE", row=row, col=col)

    def send_chat(self, _event=None):
        message = self.chat_entry.get().strip()
        if not message:
            return
        self.net.send(type="CHAT", message=message)
        self.chat_entry.delete(0, tk.END)

    def forfeit(self):
        if self.game_over:
            return
        self.net.send(type="FORFEIT")

    def poll_messages(self):
        # Move messages from the network thread into Tk's main loop safely.
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
            self.set_status("Connected. Waiting for matchmaking...")
            return

        if msg_type == "WAIT":
            self.set_status("Waiting for an opponent...")
            return

        if msg_type == "START":
            self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
            self.draw_board()
            self.color = msg.get("color")
            self.opponent = msg.get("opponent")
            self.my_turn = self.color == BLACK
            self.game_over = False
            self.set_status(f"Game started. You are {self.color}.")
            self.update_info()
            return

        if msg_type == "UPDATE":
            row = msg["row"]
            col = msg["col"]
            color = msg["color"]
            self.board[row][col] = color
            self.my_turn = self.color == msg.get("next_turn")
            self.draw_board()
            if msg.get("next_turn") is None:
                self.set_status(f"Final move: {color} at ({row}, {col})")
            else:
                self.set_status(f"Move: {color} at ({row}, {col})")
            self.update_info(next_turn=msg.get("next_turn"))
            return

        if msg_type == "WIN":
            row = msg.get("row")
            col = msg.get("col")
            color = msg.get("color")
            if row is not None and col is not None and color:
                self.board[row][col] = color
            self.draw_board()
            self.my_turn = False
            self.game_over = True
            winner = msg.get("winner")
            winner_name = msg.get("winner_name")
            self.set_status(f"{winner_name} wins as {winner}")
            self.update_info()
            return

        if msg_type == "DRAW":
            self.my_turn = False
            self.game_over = True
            self.set_status("Game ended in a draw")
            self.update_info()
            return

        if msg_type == "FORFEIT":
            self.my_turn = False
            self.game_over = True
            winner = msg.get("winner")
            if winner == self.color:
                self.set_status("Opponent forfeited. You win.")
            else:
                self.set_status("You forfeited.")
            self.update_info()
            return

        if msg_type == "DISCONNECT" or msg_type == "_LOCAL_DISCONNECT":
            self.my_turn = False
            self.game_over = True
            self.set_status("Opponent disconnected")
            self.update_info()
            return

        if msg_type == "ERROR":
            self.set_status(f"Error: {msg.get('message', 'Unknown error')}")
            return

        if msg_type == "CHAT":
            self.append_chat(f"{msg.get('name', 'Opponent')}: {msg.get('message', '')}")
            return

    def append_chat(self, text):
        # Text widgets are toggled writable only for the append operation.
        self.chat_log.configure(state="normal")
        self.chat_log.insert(tk.END, text + "\n")
        self.chat_log.see(tk.END)
        self.chat_log.configure(state="disabled")

    def set_status(self, text):
        self.status_var.set(text)

    def update_info(self, next_turn=None):
        parts = [f"You: {self.name} ({self.color or '?'})"]
        parts.append(f"Opponent: {self.opponent or '?'}")
        if self.game_over:
            parts.append("Result: finished")
        elif next_turn:
            parts.append(f"Next turn: {next_turn}")
        else:
            parts.append(f"My turn: {'yes' if self.my_turn else 'no'}")
        self.info_label.configure(text=" | ".join(parts))

    def on_close(self):
        self.net.close()
        self.root.destroy()


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999

    bootstrap = tk.Tk()
    bootstrap.withdraw()
    name = simpledialog.askstring("Name", "Enter your name:", parent=bootstrap) or "Player"
    bootstrap.destroy()

    root = tk.Tk()
    try:
        app = GomokuGUI(root, host, port, name)
    except OSError as exc:
        root.destroy()
        messagebox.showerror("Connection Error", str(exc))
        return
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_close()


if __name__ == "__main__":
    main()
