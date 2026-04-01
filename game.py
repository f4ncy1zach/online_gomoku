"""
This is for local server
"""

# Board constants shared by the server, client, and local test mode.
BOARD_SIZE = 15
EMPTY = "."
BLACK = "X"
WHITE = "O"

DIRECTIONS = [
    (0, 1),   # column
    (1, 0),   # row
    (1, 1),   # positive slope diagonal
    (1, -1),  # negative slope diagonal
]


class GomokuGame:
    def __init__(self):
        # Start every match with an empty board, Black to move first, and no winner yet.
        self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current_turn = BLACK       # Black goes first
        self.winner = None              # None / BLACK / WHITE / "DRAW"
        self.move_count = 0

    def make_move(self, row: int, col: int) -> dict:
        """
        Attempt to place a stone.
        Returns a dict:
          success  : bool
          message  : str (reason for failure or "OK")
          winner   : None / BLACK / WHITE / "DRAW"
        """
        # Validate the requested move before mutating the board.
        error = self._validate(row, col)
        if error:
            return {"success": False, "message": error, "winner": None}

        # Place the stone and record the move count.
        self.board[row][col] = self.current_turn
        self.move_count += 1

        # Check whether this move created five in a row.
        if self._check_win(row, col, self.current_turn):
            self.winner = self.current_turn
            return {"success": True, "message": "OK", "winner": self.winner}

        # If the board is full and nobody won, the result is a draw.
        if self.move_count == BOARD_SIZE * BOARD_SIZE:
            self.winner = "DRAW"
            return {"success": True, "message": "OK", "winner": "DRAW"}

        # Otherwise pass the turn to the other player.
        self.current_turn = WHITE if self.current_turn == BLACK else BLACK
        return {"success": True, "message": "OK", "winner": None}


    def _validate(self, row: int, col: int) -> str:
        """Return an error message string; return empty string if valid."""
        # Reject moves after the game is already over.
        if self.winner:
            return "The game is already over"
        # Reject coordinates outside the 15x15 board.
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return f"Out of bounds: ({row}, {col}), valid range is 0-{BOARD_SIZE - 1}"
        # Reject moves that land on an occupied cell.
        if self.board[row][col] != EMPTY:
            return f"Cell ({row}, {col}) is already occupied"
        return ""


    def _check_win(self, row: int, col: int, color: str) -> bool:
        # Count in each of the four line directions and look for any run of five.
        for dr, dc in DIRECTIONS:
            count = 1  # The current placed stone itself
            count += self._count_direction(row, col, dr, dc, color)
            count += self._count_direction(row, col, -dr, -dc, color)
            if count >= 5:
                return True
        return False

    def _count_direction(self, row: int, col: int, dr: int, dc: int, color: str) -> int:
        """Count consecutive stones of the same color in one direction."""
        # Walk outward until the line breaks or the edge of the board is reached.
        count = 0
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == color:
            count += 1
            r += dr
            c += dc
        return count

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────
    def is_over(self) -> bool:
        # A match ends as soon as a winner or a draw is recorded.
        return self.winner is not None

    def get_board(self) -> list:
        """Return a deep copy of the board (for network module serialization)."""
        # Return a copy so callers cannot mutate internal state accidentally.
        return [row[:] for row in self.board]

    def reset(self):
        """Reset the board, can be used for 'play again'."""
        # Reinitialize the game to the default starting state.
        self.__init__()

    def display(self):
        """Print the current board in the terminal (ASCII art)."""
        # Build a simple text board for local debugging and manual play.
        col_header = "   " + " ".join(f"{c:2}" for c in range(BOARD_SIZE))
        print(col_header)
        print("   " + "--" * BOARD_SIZE)
        for r, row in enumerate(self.board):
            cells = " ".join(f" {cell}" for cell in row)
            print(f"{r:2} |{cells}")
        print()
        if self.winner:
            if self.winner == "DRAW":
                print("Result: Draw!")
            else:
                print(f"Result: {'Black (X)' if self.winner == BLACK else 'White (O)'} wins!")
        else:
            turn_name = "Black (X)" if self.current_turn == BLACK else "White (O)"
            print(f"Current turn: {turn_name}")


# ══════════════════════════════════════════════
# Local two-player mode (for testing, no network needed)
# ══════════════════════════════════════════════
def local_game():
    # Interactive terminal mode for quick manual testing without the network layer.
    game = GomokuGame()
    print("=== Gomoku Local Test Mode ===")
    print("Input format: row col (for example: 7 7)")
    print("Enter 'q' to quit\n")

    while not game.is_over():
        # Show the current state, then ask the active player for a move.
        game.display()
        turn = "Black (X)" if game.current_turn == BLACK else "White (O)"
        raw = input(f"{turn} move > ").strip()

        if raw.lower() == "q":
            print("Exited.")
            break

        parts = raw.split()
        if len(parts) != 2:
            print("Invalid format, please enter: row col\n")
            continue

        try:
            row, col = int(parts[0]), int(parts[1])
        except ValueError:
            print("Please enter integer coordinates\n")
            continue

        result = game.make_move(row, col)
        if not result["success"]:
            print(f"Invalid move: {result['message']}\n")

    game.display()


# ══════════════════════════════════════════════
# Unit tests
# ══════════════════════════════════════════════
def run_tests():
    # Minimal built-in checks for the core game rules.
    print("=== Running Unit Tests ===\n")
    passed = 0
    failed = 0

    def check(name, condition):
        # Small helper so each test prints a consistent pass/fail line.
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {name}")
        if condition:
            passed += 1
        else:
            failed += 1

    # Test 1: Out-of-bounds move
    g = GomokuGame()
    res = g.make_move(-1, 0)
    check("Out-of-bounds move (negative row) is rejected", not res["success"])

    res = g.make_move(0, BOARD_SIZE)
    check("Out-of-bounds move (column too large) is rejected", not res["success"])

    # Test 2: Repeated move
    g = GomokuGame()
    g.make_move(7, 7)
    res = g.make_move(7, 7)
    check("Repeated move is rejected", not res["success"])

    # Test 3: Turn switching logic
    g = GomokuGame()
    check("Black moves first initially", g.current_turn == BLACK)
    g.make_move(0, 0)
    check("Turn switches to White after a move", g.current_turn == WHITE)
    g.make_move(0, 1)
    check("Turn switches back to Black after another move", g.current_turn == BLACK)

    # Test 4: Horizontal five-in-a-row
    g = GomokuGame()
    moves = [(0,0),(1,0),(0,1),(1,1),(0,2),(1,2),(0,3),(1,3),(0,4)]
    for r, c in moves:
        res = g.make_move(r, c)
    check("Black wins with horizontal five-in-a-row", res["winner"] == BLACK)

    # Test 5: Vertical five-in-a-row
    g = GomokuGame()
    moves = [(0,0),(0,1),(1,0),(1,1),(2,0),(2,1),(3,0),(3,1),(4,0)]
    for r, c in moves:
        res = g.make_move(r, c)
    check("Black wins with vertical five-in-a-row", res["winner"] == BLACK)

    # Test 6: Diagonal five-in-a-row
    g = GomokuGame()
    moves = [(0,0),(0,1),(1,1),(1,2),(2,2),(2,3),(3,3),(3,4),(4,4)]
    for r, c in moves:
        res = g.make_move(r, c)
    check("Black wins with diagonal five-in-a-row", res["winner"] == BLACK)

    # Test 7: Anti-diagonal five-in-a-row
    g = GomokuGame()
    moves = [(0,4),(0,0),(1,3),(1,1),(2,2),(2,5),(3,1),(3,6),(4,0)]
    for r, c in moves:
        res = g.make_move(r, c)
    check("Black wins with anti-diagonal five-in-a-row", res["winner"] == BLACK)

    # Test 8: No moves allowed after game ends
    g = GomokuGame()
    for r, c in [(0,0),(1,0),(0,1),(1,1),(0,2),(1,2),(0,3),(1,3),(0,4)]:
        g.make_move(r, c)
    res = g.make_move(5, 5)
    check("Move is rejected after the game is over", not res["success"])

    # Test 9: Reset clears the board
    g = GomokuGame()
    g.make_move(7, 7)
    g.reset()
    check("Board is cleared after reset", g.board[7][7] == EMPTY)
    check("Black moves first again after reset", g.current_turn == BLACK)

    # Print the final summary so local test runs are easy to read.
    print(f"\nResult: {passed} passed / {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        success = run_tests()
        sys.exit(0 if success else 1)
    else:
        local_game()