# Online Gomoku

## Group Members

| Name | Student ID | Email |
| :--- | :--- | :--- |
| Tianxi Huang | 301570931 | tha121@sfu.ca |
| Jinyan Jiang | 301575900 | jja141@sfu.ca |

## 1. Project Overview & Description

This project is a networked Gomoku game (five-in-a-row) built with Python sockets.

It includes:
- A server that matches players into independent 2-player games and enforces game rules.
- A Tkinter GUI client for board interaction, chat, and a current-action banner.
- `client.py` is the GUI client entrypoint.
- A launcher with separate server and client controls so multiple 2-player matches can be started on one server.

Launcher command:

```powershell
python launcher.py
```

Launcher flow:
- Start Server launches the local server on the selected port.
- Launch Client A launches one GUI client.
- Launch Client B launches the second GUI client.
- Launch 2 Clients launches both GUI clients together.
- To move to a different port, stop the current launcher-managed server, edit the port field, and start the server again.

Manual play commands:

Use these if you want to run the server and client directly from separate terminals, which is useful for debugging or when you do not want to use the launcher.

Open a new CLI or terminal window for each command.

1. Start the server:

```powershell
python server.py 127.0.0.1 9999
```

2. Start the first client:

```powershell
python client.py 127.0.0.1 9999
```

3. Start the second client:

```powershell
python client.py 127.0.0.1 9999
```
## 2. System Limitations & Edge Cases

### 2.1 Limitations

- The server uses threads and is designed for local PC usage, not high-concurrency production workloads.
- Each match is limited to two players.
- Matchmaking is intentionally simple and uses one waiting slot per side rather than a full lobby or queue system.
- The launcher expects the bind IP and connect IP to be valid for the current machine and network.
- Network play depends on TCP connectivity between the launcher/client and the server, so firewall rules or blocked ports may prevent clients from connecting.
- Testing was performed on Windows only, so behavior on other operating systems was not validated.

### 2.2 Edge Cases

- Multiple matches can run on the same server.
- If the server process is closed, connected clients will detect disconnect and stop normal gameplay.
- If one player closes a client window, the GUI attempts a forfeit and the opponent is notified; if the connection drops abruptly, the server still ends the match cleanly.
- The GUI closes its socket cleanly and attempts to forfeit when a match is active.
- If an invalid port or unreachable host is entered in GUI tools, a connection/validation error is shown.

## 3. Video Demo

- [Project Demo Video](https://youtu.be/JRtGnOb3TY0)

## 4. Step-by-Step Run Launcher Guide

Use the launcher if you want to start the server and GUI clients from one window.

1. Start the launcher:

```powershell
python launcher.py
```

2. Enter the server bind IP and port if needed.
3. Click `Start Server`.
4. Enter or randomize the two client names.
5. Click `Launch Client A`, `Launch Client B`, or `Launch 2 Clients`.
6. Use `Stop Server` and `Quit` when you are finished.

## 5. Prerequisites (Fresh Environment)

- Python 3.10+ installed.
- Tkinter available in your Python installation.
- No third-party Python packages required.
- (Optional) VS Code or Terminal for running commands.
## 6. Technical Protocol Details

The project uses newline-delimited JSON over TCP. Each message is a JSON object encoded as UTF-8 and terminated by a single newline character.

That framing lets the receiver read one message at a time with `readline()`.

Basic wire format:

```json
{
	"type": "MESSAGE_NAME",
	"...": "message-specific fields"
}
```

The `type` field selects the protocol action. Other fields depend on the message.

Core message flow:
- `HELLO`: sent by the server immediately after a TCP connection is accepted.
- `JOIN`: sent by the client after `HELLO` so the server learns the player name.
- `WAIT`: sent by the server while the client is waiting for an opponent.
- `START`: sent by the server when a match begins. It includes `color`, `opponent`, and `first_turn`.
- `MOVE`: sent by the client with `row` and `col` when the player wants to place a stone.
- `UPDATE`: sent by the server after a valid move. It includes `row`, `col`, `color`, and `next_turn`.
- `WIN` / `DRAW`: sent by the server when the match ends.
- `CHAT`: relays a chat message between players.
- `FORFEIT`: ends the current match when a player gives up.
- `DISCONNECT`: tells the other player that a peer disconnected.
- `ERROR`: reports invalid input or invalid game state.

Example messages:

```json
{ "type": "JOIN", "name": "Alice" }
{ "type": "MOVE", "row": 7, "col": 7 }
{ "type": "UPDATE", "row": 7, "col": 7, "color": "X", "next_turn": "O" }
{ "type": "CHAT", "name": "Alice", "message": "hi" }
```

Serialization helpers live in `protocol.py`:
- `send_msg(sock, **fields)` serializes the message and appends the newline.
- `recv_msg(file_obj)` reads one newline-delimited JSON object and returns it as a dictionary.

## 7. Academic Integrity & References

Academic integrity statement:
- This codebase was developed for CMPT 371.
- AI-assisted code blocks are marked in comments in `client.py` and `launcher.py`.
- The AI-assisted sections cover GUI flow, launcher process control, and related helper logic.
- The remaining code and final integration were reviewed and adjusted by the team.

References:
- Python socket programming HOWTO: https://docs.python.org/3/howto/sockets.html
- Python threading documentation: https://docs.python.org/3/library/threading.html
- Tkinter documentation: https://docs.python.org/3/library/tkinter.html