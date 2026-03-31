# Online Gomoku

## Group Members

| Name | Student ID | Email |
| :--- | :--- | :--- |
| Alex (replace with full name) | (replace) | (replace) |
| Teammate (replace) | (replace) | (replace) |

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

```powershell
python server.py 127.0.0.1 9999
python client.py 127.0.0.1 9999
python client.py 127.0.0.1 9999
```

`client.py` starts the GUI client.

## 2. System Limitations & Edge Cases

- The server uses threads and is designed for coursework-scale usage, not high-concurrency production workloads.
- If the server process is closed, connected clients will detect disconnect and stop normal gameplay.
- If one player closes a client window, the GUI attempts a forfeit and the opponent is notified; if the connection drops abruptly, the server still ends the match cleanly.
- The GUI closes its socket cleanly and attempts to forfeit when a match is active, which keeps the server responsive.
- Chat and move messages are line-delimited JSON over TCP; malformed client messages are rejected by the server.
- If an invalid port or unreachable host is entered in GUI tools, a connection/validation error is shown.

## 3. Video Demo

Add your demo link here:

- [Project Demo Video](https://example.com)

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

The project uses a newline-delimited JSON protocol over TCP.

Common message types:
- `HELLO`: sent by server when a client connects.
- `JOIN`: sent by client with player name.
- `WAIT`: sent by server while waiting for an opponent.
- `START`: sent by server to both players with assigned color and opponent name.
- `MOVE`: sent by client with `row` and `col`.
- `UPDATE`: sent by server after valid moves.
- `WIN` / `DRAW`: sent by server when game ends.
- `CHAT`: relayed between players by server.
- `FORFEIT`: sent when a player gives up.
- `DISCONNECT`: sent to opponent when a peer disconnects.
- `ERROR`: sent when the message format/state is invalid.

Serialization helpers are in `protocol.py` via `send_msg` and `recv_msg`.

## 7. Academic Integrity & References

Academic integrity statement:
- This codebase was developed for CMPT 371 coursework.
- External help/tools were used for planning and documentation support only where declared by the team.
- Final understanding, integration, and submission responsibility remain with the group members.

References:
- Python socket programming HOWTO: https://docs.python.org/3/howto/sockets.html
- Python threading documentation: https://docs.python.org/3/library/threading.html
- Tkinter documentation: https://docs.python.org/3/library/tkinter.html