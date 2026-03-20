import os
import socket
import sys
import threading

from game import BLACK, BOARD_SIZE, EMPTY
from protocol import recv_msg, send_msg


class GomokuClient:
    def __init__(self, host, port, name):
        self.host = host
        self.port = port
        self.name = name
        self.sock = None
        self.file = None
        self.running = True
        self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.color = None
        self.opponent = None
        self.my_turn = False
        self.status = "Connecting..."
        self.print_lock = threading.Lock()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.file = self.sock.makefile("r", encoding="utf-8")

    def start(self):
        self.connect()
        # Keep network reads off the input loop so incoming moves/chat stay responsive.
        receiver = threading.Thread(target=self.receive_loop, daemon=True)
        receiver.start()

        try:
            while self.running:
                raw = input("> ").strip()
                if not raw:
                    continue
                if raw.lower() == "f":
                    send_msg(self.sock, type="FORFEIT")
                    continue
                if raw.lower().startswith("c "):
                    message = raw[2:].strip()
                    send_msg(self.sock, type="CHAT", message=message)
                    continue

                parts = raw.split()
                if len(parts) != 2:
                    self.safe_print("Input format: row col, or `c message`, or `f` to forfeit")
                    continue
                try:
                    row = int(parts[0])
                    col = int(parts[1])
                except ValueError:
                    self.safe_print("Row and column must be integers")
                    continue
                send_msg(self.sock, type="MOVE", row=row, col=col)
        except (EOFError, KeyboardInterrupt):
            self.safe_print("\nClient exiting")
        finally:
            self.running = False
            self.close()

    def receive_loop(self):
        try:
            while self.running:
                msg = recv_msg(self.file)
                if msg is None:
                    self.safe_print("Disconnected from server")
                    self.running = False
                    return
                self.handle_message(msg)
        except (ConnectionResetError, OSError):
            self.safe_print("Network connection closed unexpectedly")
        finally:
            self.running = False

    def handle_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "HELLO":
            send_msg(self.sock, type="JOIN", name=self.name)
            self.status = "JOIN sent, waiting for matchmaking"
            self.render()
            return

        if msg_type == "WAIT":
            self.status = "Waiting for another player..."
            self.render()
            return

        if msg_type == "START":
            self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
            self.color = msg.get("color")
            self.opponent = msg.get("opponent")
            self.my_turn = self.color == BLACK
            self.status = f"Match started. You are {self.color}, opponent: {self.opponent}"
            self.render()
            return

        if msg_type == "UPDATE":
            row = msg["row"]
            col = msg["col"]
            color = msg["color"]
            self.board[row][col] = color
            next_turn = msg["next_turn"]
            self.my_turn = self.color == next_turn
            if next_turn is None:
                self.status = f"Final move: {color} -> ({row}, {col})"
            else:
                self.status = f"Move: {color} -> ({row}, {col}), next turn: {next_turn}"
            self.render()
            return

        if msg_type == "WIN":
            row = msg.get("row")
            col = msg.get("col")
            color = msg.get("color")
            if row is not None and col is not None and color:
                self.board[row][col] = color
            winner = msg.get("winner")
            winner_name = msg.get("winner_name")
            self.my_turn = False
            self.status = f"Winner: {winner_name} ({winner})"
            self.render()
            self.running = False
            return

        if msg_type == "DRAW":
            self.my_turn = False
            self.status = "Draw"
            self.render()
            self.running = False
            return

        if msg_type == "FORFEIT":
            winner = msg.get("winner")
            loser = msg.get("loser", "Opponent")
            self.my_turn = False
            if self.color == winner:
                self.status = f"{loser} forfeited. You win."
            else:
                self.status = "You forfeited."
            self.render()
            self.running = False
            return

        if msg_type == "DISCONNECT":
            self.my_turn = False
            self.status = "Opponent disconnected. Match over."
            self.render()
            self.running = False
            return

        if msg_type == "ERROR":
            self.status = f"Error: {msg.get('message', 'Unknown error')}"
            self.render()
            return

        if msg_type == "CHAT":
            name = msg.get("name", "Opponent")
            message = msg.get("message", "")
            self.status = f"[Chat] {name}: {message}"
            self.render()
            return

        self.safe_print(f"Unhandled message: {msg}")

    def render(self):
        with self.print_lock:
            # Redraw the whole terminal view after every state change.
            os.system("cls" if os.name == "nt" else "clear")
            print(self.format_board())
            print()
            print(f"Status: {self.status}")
            if self.color:
                print(f"You: {self.name} ({self.color})  Opponent: {self.opponent}")
            turn_text = "Yes" if self.my_turn else "No"
            print(f"Your turn: {turn_text}")
            print("Enter `row col` to move, `c message` to chat, `f` to forfeit")

    def format_board(self):
        header = "   " + " ".join(f"{i:2}" for i in range(BOARD_SIZE))
        lines = [header, "   " + "--" * BOARD_SIZE]
        for r, row in enumerate(self.board):
            cells = " ".join(f" {cell}" for cell in row)
            lines.append(f"{r:2} |{cells}")
        return "\n".join(lines)

    def safe_print(self, text):
        with self.print_lock:
            print(text)

    def close(self):
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


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    name = input("Enter your name: ").strip() or "Player"
    client = GomokuClient(host, port, name)
    client.start()


if __name__ == "__main__":
    main()
