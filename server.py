import logging
import socket
import sys
import threading

from game import BLACK, WHITE, GomokuGame
from protocol import recv_msg, send_msg


DEFAULT_PORT = 9999
HOST = "0.0.0.0"


class ClientSession:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        # A file wrapper plus readline() avoids TCP packet boundary issues.
        self.file = sock.makefile("r", encoding="utf-8")
        self.name = None
        self.room = None
        self.color = None
        self.connected = True
        self.lock = threading.Lock()

    def send(self, **message):
        with self.lock:
            if not self.connected:
                return
            send_msg(self.sock, **message)

    def close(self):
        self.connected = False
        try:
            self.file.close()
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class Room:
    def __init__(self, player_black, player_white):
        self.players = {BLACK: player_black, WHITE: player_white}
        self.game = GomokuGame()
        # All state transitions inside one match must be atomic.
        self.lock = threading.Lock()
        self.active = True

        player_black.room = self
        player_white.room = self
        player_black.color = BLACK
        player_white.color = WHITE

        logging.info(
            "Room created: %s (%s) vs %s (%s)",
            player_black.name,
            BLACK,
            player_white.name,
            WHITE,
        )

    def other_player(self, client):
        for player in self.players.values():
            if player is not client:
                return player
        return None

    def start(self):
        black_player = self.players[BLACK]
        white_player = self.players[WHITE]
        black_player.send(type="START", color=BLACK, opponent=white_player.name)
        white_player.send(type="START", color=WHITE, opponent=black_player.name)

    def handle_move(self, client, row, col):
        with self.lock:
            if not self.active:
                client.send(type="ERROR", message="Room is no longer active")
                return

            if self.game.is_over():
                client.send(type="ERROR", message="The game is already over")
                return

            if client.color != self.game.current_turn:
                client.send(type="ERROR", message="It is not your turn")
                return

            # The server is authoritative: clients never validate moves for real.
            result = self.game.make_move(row, col)
            if not result["success"]:
                client.send(type="ERROR", message=result["message"])
                return

            color = client.color
            winner = result["winner"]
            if winner == "DRAW":
                self.broadcast(
                    type="UPDATE",
                    row=row,
                    col=col,
                    color=color,
                    next_turn=None,
                )
                self.broadcast(type="DRAW")
                self.active = False
                return

            if winner in (BLACK, WHITE):
                self.broadcast(
                    type="WIN",
                    winner=winner,
                    winner_name=client.name,
                    row=row,
                    col=col,
                    color=color,
                )
                self.active = False
                return

            self.broadcast(
                type="UPDATE",
                row=row,
                col=col,
                color=color,
                next_turn=self.game.current_turn,
            )

    def handle_chat(self, client, message):
        if not message:
            client.send(type="ERROR", message="Chat message cannot be empty")
            return
        other = self.other_player(client)
        if other is None:
            client.send(type="ERROR", message="No opponent connected")
            return
        self.broadcast(type="CHAT", name=client.name, message=message)

    def handle_forfeit(self, client):
        with self.lock:
            if not self.active:
                return
            self.active = False
            opponent = self.other_player(client)
            winner = opponent.color if opponent is not None else None
            self.broadcast(type="FORFEIT", winner=winner, loser=client.name)

    def handle_disconnect(self, client):
        with self.lock:
            if not self.active:
                return
            self.active = False
            other = self.other_player(client)
            if other and other.connected:
                other.send(type="DISCONNECT")

    def broadcast(self, **message):
        for player in self.players.values():
            if player.connected:
                try:
                    player.send(**message)
                except OSError:
                    logging.exception("Failed to send to %s", player.name)


class GameServer:
    def __init__(self, host=HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_sock = None
        self.waiting_player = None
        self.waiting_lock = threading.Lock()
        self.running = False

    def serve_forever(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()
        self.running = True

        logging.info("Server listening on %s:%s", self.host, self.port)

        try:
            while self.running:
                client_sock, addr = self.server_sock.accept()
                logging.info("Accepted connection from %s:%s", *addr)
                client = ClientSession(client_sock, addr)
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client,),
                    daemon=True,
                )
                thread.start()
        except KeyboardInterrupt:
            logging.info("Server shutting down")
        finally:
            self.running = False
            if self.server_sock:
                self.server_sock.close()

    def handle_client(self, client):
        try:
            client.send(type="HELLO")

            join_msg = recv_msg(client.file)
            if join_msg is None:
                logging.info("Client %s disconnected before JOIN", client.addr)
                return
            if join_msg.get("type") != "JOIN":
                client.send(type="ERROR", message="Expected JOIN as the first message")
                return

            name = str(join_msg.get("name", "")).strip()
            if not name:
                client.send(type="ERROR", message="Name cannot be empty")
                return

            client.name = name
            logging.info("Player joined: %s from %s", client.name, client.addr)
            self.match_player(client)

            while client.connected:
                msg = recv_msg(client.file)
                if msg is None:
                    logging.info("Connection lost: %s", client.name)
                    break
                self.dispatch_message(client, msg)
        except (ConnectionResetError, BrokenPipeError, OSError):
            logging.info("Connection error for %s", client.name or client.addr)
        except Exception:
            logging.exception("Unexpected error while handling client %s", client.addr)
            try:
                client.send(type="ERROR", message="Internal server error")
            except OSError:
                pass
        finally:
            self.cleanup_client(client)

    def match_player(self, client):
        with self.waiting_lock:
            waiting = self.waiting_player
            if waiting is None or not waiting.connected:
                self.waiting_player = client
                client.send(type="WAIT")
                logging.info("%s is waiting for an opponent", client.name)
                return

            self.waiting_player = None
            # The waiting player becomes black so the match starts immediately.
            room = Room(waiting, client)
            room.start()

    def dispatch_message(self, client, msg):
        msg_type = msg.get("type")

        if msg_type == "MOVE":
            if client.room is None:
                client.send(type="ERROR", message="You are not in a room yet")
                return
            row = msg.get("row")
            col = msg.get("col")
            if not isinstance(row, int) or not isinstance(col, int):
                client.send(type="ERROR", message="MOVE requires integer row and col")
                return
            client.room.handle_move(client, row, col)
            return

        if msg_type == "CHAT":
            if client.room is None:
                client.send(type="ERROR", message="You are not in a room yet")
                return
            client.room.handle_chat(client, str(msg.get("message", "")).strip())
            return

        if msg_type == "FORFEIT":
            if client.room is None:
                client.send(type="ERROR", message="You are not in a room yet")
                return
            client.room.handle_forfeit(client)
            return

        client.send(type="ERROR", message=f"Unknown message type: {msg_type}")

    def cleanup_client(self, client):
        client.connected = False
        with self.waiting_lock:
            if self.waiting_player is client:
                self.waiting_player = None

        if client.room is not None:
            client.room.handle_disconnect(client)

        client.close()
        logging.info("Cleaned up client %s", client.name or client.addr)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(threadName)s %(message)s",
    )
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = GameServer(port=port)
    server.serve_forever()


if __name__ == "__main__":
    main()
