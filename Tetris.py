from collections.abc import Callable
from collections import deque
import random
import sys

import pygame

# Configuración del tablero
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
BLOCK_SIZE = 30

# Colores de cada pieza
COLORS = {
    "I": (0, 255, 255),
    "O": (255, 255, 0),
    "T": (170, 0, 255),
    "S": (0, 255, 0),
    "Z": (255, 0, 0),
    "J": (0, 0, 255),
    "L": (255, 140, 0),
    "GHOST": (130, 130, 130),
}

# Formas de las piezas
SHAPES = {
    "I": [[1, 1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "Z": [[1, 1, 0], [0, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
}

# Pantalla
SCREEN_WIDTH = BOARD_WIDTH * BLOCK_SIZE + 380
SCREEN_HEIGHT = BOARD_HEIGHT * BLOCK_SIZE + 80
BOARD_ORIGIN = (160, 40)
PREVIEW_ORIGIN = (BOARD_ORIGIN[0] + BOARD_WIDTH * BLOCK_SIZE + 40, 110)
HOLD_ORIGIN = (BOARD_ORIGIN[0] + BOARD_WIDTH * BLOCK_SIZE + 40, 300)

# Puntuación por líneas
LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}
LINE_CLEAR_DURATION = 600
LINE_CLEAR_FLASH_INTERVAL = 100
GARBAGE_INTERVAL = 20_000
GARBAGE_COLOR = (125, 125, 135)


class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.matrix = [row[:] for row in SHAPES[kind]]
        self.color = COLORS[kind]
        self.x = 0
        self.y = 0

    def rotate_cw(self):
        new_matrix = list(zip(*self.matrix[::-1]))
        new_matrix = [list(row) for row in new_matrix]
        return new_matrix

    def copy(self):
        piece = Piece(self.kind)
        piece.matrix = [row[:] for row in self.matrix]
        piece.x = self.x
        piece.y = self.y
        return piece


class Tetris:
    def __init__(self, screen=None, multiplayer=False, player_number=1):
        pygame.init()
        self.screen = (
            screen if screen is not None else pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        )
        self.multiplayer = multiplayer
        self.player_number = player_number
        pygame.display.set_caption("Tetris Classic")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arialblack", 28)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.big_font = pygame.font.SysFont("arialblack", 56)

        self.board: list[list[int | tuple[int, int, int]]] = [
            [0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)
        ]
        self.bag = []
        self.next_piece = None
        self.current = None
        self.hold_piece = None
        self.can_hold = True
        self.game_over = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.drop_interval = 800
        self.drop_time = 0
        self.lock_delay = 0
        self.last_move = 0
        self.last_soft_drop = 0
        self.pause = False
        self.clearing_rows = []
        self.line_clear_elapsed = 0
        self.garbage_elapsed = 0
        self.garbage_rows_next = 1
        self.garbage_holes = [random.randrange(BOARD_WIDTH)]
        self.pending_garbage = 0
        self.garbage_timer_elapsed = 0
        self.line_clear_callback: Callable[[int], None] | None = None
        self.feedback = []
        self.start_time = pygame.time.get_ticks()

        self.reset_bag()
        self.spawn_next()
        self.update_next_piece()

    def reset_bag(self):
        self.bag = list(SHAPES.keys())
        random.shuffle(self.bag)

    def take_from_bag(self):
        if not self.bag:
            self.reset_bag()
        return self.bag.pop()

    def spawn_piece(self, kind=None):
        if kind is None:
            kind = self.take_from_bag()
        piece = Piece(kind)
        piece.x = (BOARD_WIDTH - len(piece.matrix[0])) // 2
        piece.y = -1 if piece.matrix[0].count(1) == 0 else -2
        if self.collides(piece):
            self.game_over = True
            return False
        self.current = piece
        self.can_hold = True
        return True

    def spawn_next(self):
        if self.next_piece is None:
            self.next_piece = Piece(self.take_from_bag())
        self.current = self.next_piece
        self.current.x = (BOARD_WIDTH - len(self.current.matrix[0])) // 2
        self.current.y = -1 if self.current.matrix[0].count(1) == 0 else -2
        self.next_piece = Piece(self.take_from_bag())
        self.next_piece.x = 0
        self.next_piece.y = 0
        if self.collides(self.current):
            self.game_over = True

    def update_next_piece(self):
        self.next_piece = Piece(self.take_from_bag())

    def collides(self, piece, dx=0, dy=0, matrix=None):
        if matrix is None:
            matrix = piece.matrix

        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if not cell:
                    continue
                new_x = piece.x + x + dx
                new_y = piece.y + y + dy
                if new_x < 0 or new_x >= BOARD_WIDTH or new_y >= BOARD_HEIGHT:
                    return True
                if new_y >= 0 and self.board[new_y][new_x] != 0:
                    return True
        return False

    def merge_piece(self):
        for y, row in enumerate(self.current.matrix):
            for x, cell in enumerate(row):
                if not cell:
                    continue
                bx = self.current.x + x
                by = self.current.y + y
                if by < 0:
                    self.game_over = True
                    return
                self.board[by][bx] = self.current.color

        if not self.clear_lines():
            self.spawn_next()

    def clear_lines(self):
        full_rows = []
        for y in range(BOARD_HEIGHT):
            if all(cell != 0 for cell in self.board[y]):
                full_rows.append(y)

        if not full_rows:
            return False

        self.clearing_rows = full_rows
        self.line_clear_elapsed = 0
        self.current = None
        return True

    def finish_line_clear(self):
        cleared = len(self.clearing_rows)
        for y in reversed(self.clearing_rows):
            del self.board[y]
        for _ in range(cleared):
            self.board.insert(0, [0 for _ in range(BOARD_WIDTH)])

        self.lines += cleared
        self.score += LINE_SCORES.get(cleared, 0) * self.level
        self.level = self.lines // 10 + 1
        self.drop_interval = max(80, 800 - (self.level - 1) * 60)
        self.clearing_rows = []
        self.line_clear_elapsed = 0
        self.drop_time = 0
        if self.line_clear_callback:
            self.line_clear_callback(cleared)
        else:
            self.garbage_elapsed = 0
        self.spawn_next()

    def add_feedback(self, text, color):
        self.feedback.append({"text": text, "color": color, "elapsed": 0})

    def add_garbage_rows(self, row_count=None):
        solo_mode = row_count is None
        if solo_mode:
            row_count = self.garbage_rows_next
        shifted_board = self.board[row_count:] if row_count < BOARD_HEIGHT else []

        holes = (
            self.garbage_holes[:row_count]
            if solo_mode
            else [random.randrange(BOARD_WIDTH) for _ in range(row_count)]
        )
        for hole in holes:
            row: list[int | tuple[int, int, int]] = [
                GARBAGE_COLOR for _ in range(BOARD_WIDTH)
            ]
            row[hole] = 0
            shifted_board.append(row)

        self.board = shifted_board[-BOARD_HEIGHT:]
        if solo_mode:
            self.garbage_elapsed = 0
            self.garbage_rows_next += 1
            self.garbage_holes = [
                random.randrange(BOARD_WIDTH) for _ in range(self.garbage_rows_next)
            ]

        if self.current:
            for _ in range(min(row_count, BOARD_HEIGHT)):
                if not self.collides(self.current):
                    break
                self.current.y -= 1

    def rotate_piece(self):
        if self.game_over or self.pause or self.clearing_rows:
            return
        rotated = self.current.rotate_cw()
        kicks = [0, -1, 1, -2, 2]
        for offset in kicks:
            if not self.collides(self.current, dx=offset, matrix=rotated):
                self.current.matrix = rotated
                self.current.x += offset
                return

    def move(self, dx, dy):
        if self.game_over or self.pause or self.clearing_rows:
            return
        if not self.collides(self.current, dx=dx, dy=dy):
            self.current.x += dx
            self.current.y += dy
            return True
        return False

    def soft_drop(self):
        if self.game_over or self.pause or self.clearing_rows:
            return
        if not self.collides(self.current, dy=1):
            self.current.y += 1
            self.score += 1
            return True
        self.lock_piece()
        return False

    def hard_drop(self):
        if self.game_over or self.pause or self.clearing_rows:
            return
        distance = 0
        while not self.collides(self.current, dy=1):
            self.current.y += 1
            distance += 1
        self.score += distance * 2
        self.lock_piece()

    def lock_piece(self):
        if self.game_over:
            return
        self.merge_piece()

    def hold(self):
        if self.game_over or self.pause or self.clearing_rows or not self.can_hold:
            return
        if self.hold_piece is None:
            self.hold_piece = Piece(self.current.kind)
            self.spawn_piece(self.take_from_bag())
        else:
            kind = self.current.kind
            self.current = Piece(self.hold_piece.kind)
            self.current.x = (BOARD_WIDTH - len(self.current.matrix[0])) // 2
            self.current.y = -1 if self.current.matrix[0].count(1) == 0 else -2
            if self.collides(self.current):
                self.game_over = True
                return
            self.hold_piece = Piece(kind)
        self.can_hold = False

    def draw_block(self, x, y, color, surface=None, size=BLOCK_SIZE):
        if surface is None:
            surface = self.screen
        rect = pygame.Rect(BOARD_ORIGIN[0] + x * size, BOARD_ORIGIN[1] + y * size, size, size)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (20, 20, 20), rect, 1)

    def draw_piece_matrix(self, matrix, x, y, color, surface=None):
        if surface is None:
            surface = self.screen
        for r, row in enumerate(matrix):
            for c, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(
                        surface,
                        color,
                        (x + c * BLOCK_SIZE, y + r * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                    )
                    pygame.draw.rect(
                        surface,
                        (20, 20, 20),
                        (x + c * BLOCK_SIZE, y + r * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                        1,
                    )

    def draw_board(self):
        board_rect = pygame.Rect(BOARD_ORIGIN[0], BOARD_ORIGIN[1], BOARD_WIDTH * BLOCK_SIZE, BOARD_HEIGHT * BLOCK_SIZE)
        pygame.draw.rect(self.screen, (20, 20, 30), board_rect)
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                if self.board[y][x] != 0:
                    flash_on = (
                        y in self.clearing_rows
                        and (self.line_clear_elapsed // LINE_CLEAR_FLASH_INTERVAL) % 2 == 0
                    )
                    color = (255, 255, 255) if flash_on else self.board[y][x]
                    self.draw_block(x, y, color)

        # Piezas fantasma
        if self.current and not self.game_over:
            ghost = self.current.copy()
            while not self.collides(ghost, dy=1):
                ghost.y += 1
            for y, row in enumerate(ghost.matrix):
                for x, cell in enumerate(row):
                    if cell:
                        rect = pygame.Rect(
                            BOARD_ORIGIN[0] + (ghost.x + x) * BLOCK_SIZE,
                            BOARD_ORIGIN[1] + (ghost.y + y) * BLOCK_SIZE,
                            BLOCK_SIZE,
                            BLOCK_SIZE,
                        )
                        pygame.draw.rect(self.screen, COLORS["GHOST"], rect, 3)

        if self.current:
            self.draw_piece_matrix(self.current.matrix, BOARD_ORIGIN[0] + self.current.x * BLOCK_SIZE, BOARD_ORIGIN[1] + self.current.y * BLOCK_SIZE, self.current.color)

    def draw_preview(self, piece, origin):
        if piece is None:
            return
        size = 24
        matrix = piece.matrix
        offset_x = origin[0] + (4 - len(matrix[0])) * size // 2
        offset_y = origin[1] + (4 - len(matrix)) * size // 2
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(
                        self.screen,
                        piece.color,
                        (offset_x + x * size, offset_y + y * size, size, size),
                    )
                    pygame.draw.rect(
                        self.screen,
                        (20, 20, 20),
                        (offset_x + x * size, offset_y + y * size, size, size),
                        1,
                    )

    def draw_hold(self):
        panel = pygame.Rect(HOLD_ORIGIN[0], HOLD_ORIGIN[1], 130, 120)
        pygame.draw.rect(self.screen, (30, 30, 35), panel)
        label = self.small_font.render("HOLD", True, (255, 255, 255))
        self.screen.blit(label, (HOLD_ORIGIN[0] + 30, HOLD_ORIGIN[1] + 10))
        if self.hold_piece:
            self.draw_preview(self.hold_piece, HOLD_ORIGIN)

    def draw_ui(self):
        garbage_panel = pygame.Rect(15, BOARD_ORIGIN[1], 130, BOARD_HEIGHT * BLOCK_SIZE)
        pygame.draw.rect(self.screen, (25, 25, 30), garbage_panel)

        show_timer = not self.multiplayer or self.pending_garbage > 0
        if show_timer:
            elapsed = (
                self.garbage_timer_elapsed if self.multiplayer else self.garbage_elapsed
            )
            timer_seconds = max(0, (GARBAGE_INTERVAL - elapsed + 999) // 1000)
            timer_text = self.font.render(f"{timer_seconds:02}", True, (255, 255, 255))
            self.screen.blit(
                timer_text,
                (
                    garbage_panel.centerx - timer_text.get_width() // 2,
                    garbage_panel.y + 20,
                ),
            )
            seconds_label = self.small_font.render("SEGUNDOS", True, (200, 200, 200))
            self.screen.blit(
                seconds_label,
                (
                    garbage_panel.centerx - seconds_label.get_width() // 2,
                    garbage_panel.y + 58,
                ),
            )

        rows_to_show = self.pending_garbage if self.multiplayer else self.garbage_rows_next
        rows_label = self.small_font.render(
            f"FILAS: {rows_to_show}", True, (220, 220, 220)
        )
        self.screen.blit(rows_label, (garbage_panel.x + 12, garbage_panel.y + 112))
        preview_cell_size = 8
        preview_x = garbage_panel.centerx - (BOARD_WIDTH * preview_cell_size) // 2
        preview_y = garbage_panel.y + 145
        visible_rows = min(rows_to_show, BOARD_HEIGHT)
        for row_index in range(visible_rows):
            row_y = preview_y + row_index * (preview_cell_size + 2)
            for column in range(BOARD_WIDTH):
                if not self.multiplayer and column == self.garbage_holes[row_index]:
                    continue
                cell_rect = pygame.Rect(
                    preview_x + column * preview_cell_size,
                    row_y,
                    preview_cell_size,
                    preview_cell_size,
                )
                pygame.draw.rect(self.screen, GARBAGE_COLOR, cell_rect)
                pygame.draw.rect(self.screen, (20, 20, 20), cell_rect, 1)

        sidebar = pygame.Rect(BOARD_ORIGIN[0] + BOARD_WIDTH * BLOCK_SIZE + 18, BOARD_ORIGIN[1], 180, BOARD_HEIGHT * BLOCK_SIZE)
        pygame.draw.rect(self.screen, (25, 25, 30), sidebar)

        score_text = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        lines_text = self.font.render(f"Lines: {self.lines}", True, (255, 255, 255))
        level_text = self.font.render(f"Level: {self.level}", True, (255, 255, 255))

        self.screen.blit(score_text, (sidebar.x + 12, sidebar.y + 10))
        self.screen.blit(lines_text, (sidebar.x + 12, sidebar.y + 45))
        self.screen.blit(level_text, (sidebar.x + 12, sidebar.y + 80))

        preview_panel = pygame.Rect(PREVIEW_ORIGIN[0], PREVIEW_ORIGIN[1], 130, 120)
        pygame.draw.rect(self.screen, (30, 30, 35), preview_panel)
        next_label = self.small_font.render("NEXT", True, (255, 255, 255))
        self.screen.blit(next_label, (PREVIEW_ORIGIN[0] + 40, PREVIEW_ORIGIN[1] + 10))
        if self.next_piece:
            self.draw_preview(self.next_piece, PREVIEW_ORIGIN)

        self.draw_hold()

    def draw_feedback(self):
        for index, effect in enumerate(self.feedback):
            progress = effect["elapsed"] / 900
            text = self.big_font.render(effect["text"], True, effect["color"])
            text.set_alpha(max(0, int(255 * (1 - progress))))
            rect = text.get_rect(
                center=(
                    BOARD_ORIGIN[0] + BOARD_WIDTH * BLOCK_SIZE // 2,
                    BOARD_ORIGIN[1] + 80 - int(progress * 50) - index * 35,
                )
            )
            self.screen.blit(text, rect)

    def draw_game_over(self):
        if not self.game_over:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        text = self.big_font.render("GAME OVER", True, (255, 80, 80))
        self.screen.blit(text, (BOARD_ORIGIN[0] + 35, BOARD_ORIGIN[1] + 250))

    def draw_pause(self):
        if not self.pause:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))
        text = self.big_font.render("PAUSA", True, (255, 255, 255))
        self.screen.blit(text, (BOARD_ORIGIN[0] + 70, BOARD_ORIGIN[1] + 250))

    def render(self):
        self.screen.fill((15, 15, 20))
        self.draw_board()
        self.draw_ui()
        self.draw_feedback()
        self.draw_game_over()
        self.draw_pause()
        pygame.display.flip()

    def render_to(self, surface):
        display = self.screen
        self.screen = surface
        try:
            self.screen.fill((15, 15, 20))
            self.draw_board()
            self.draw_ui()
            self.draw_feedback()
            self.draw_game_over()
            self.draw_pause()
        finally:
            self.screen = display

    def process_input(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.pause = not self.pause
            if self.game_over:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.__init__()
                return True
            if self.pause:
                return True

            if event.key == pygame.K_LEFT:
                self.move(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self.move(1, 0)
            elif event.key == pygame.K_DOWN:
                self.soft_drop()
            elif event.key == pygame.K_UP:
                self.rotate_piece()
            elif event.key == pygame.K_z:
                self.rotate_piece()
            elif event.key == pygame.K_x:
                self.hard_drop()
            elif event.key == pygame.K_c:
                self.hold()
            elif event.key == pygame.K_SPACE:
                self.hard_drop()
        return True

    def update(self, dt):
        if self.game_over or self.pause:
            return
        self.feedback = [
            effect
            for effect in self.feedback
            if effect["elapsed"] + dt < 900
        ]
        for effect in self.feedback:
            effect["elapsed"] += dt
        if self.clearing_rows:
            self.line_clear_elapsed += dt
            if self.line_clear_elapsed >= LINE_CLEAR_DURATION:
                self.finish_line_clear()
            return
        if not self.multiplayer:
            self.garbage_elapsed += dt
            if self.garbage_elapsed >= GARBAGE_INTERVAL:
                self.add_garbage_rows()
                if self.game_over:
                    return
        self.drop_time += dt
        if self.drop_time >= self.drop_interval:
            if not self.collides(self.current, dy=1):
                self.current.y += 1
            else:
                self.lock_piece()
            self.drop_time = 0

    def run(self):
        running = True
        last_frame = pygame.time.get_ticks()
        while running:
            now = pygame.time.get_ticks()
            dt = now - last_frame
            last_frame = now

            for event in pygame.event.get():
                if not self.process_input(event):
                    running = False
                    break

            self.update(dt)
            self.render()
            self.clock.tick(60)

        pygame.quit()
        sys.exit()


class MultiplayerGame:
    PLAYER_CONTROLS = (
        {
            pygame.K_LEFT: "left",
            pygame.K_RIGHT: "right",
            pygame.K_DOWN: "down",
            pygame.K_UP: "rotate",
            pygame.K_z: "rotate",
            pygame.K_x: "drop",
            pygame.K_SPACE: "drop",
            pygame.K_c: "hold",
        },
        {
            pygame.K_a: "left",
            pygame.K_d: "right",
            pygame.K_s: "down",
            pygame.K_w: "rotate",
            pygame.K_q: "drop",
            pygame.K_e: "hold",
        },
    )

    def __init__(self, screen, cpu_opponent=False, cpu_difficulty=3):
        self.screen = screen
        self.cpu_opponent = cpu_opponent
        self.cpu_difficulty = max(1, min(5, cpu_difficulty))
        self.cpu_action_interval = {
            1: 280,
            2: 220,
            3: 165,
            4: 115,
            5: 75,
        }[self.cpu_difficulty]
        self.cpu_hard_drop_chance = {
            1: 0.0,
            2: 0.1,
            3: 0.3,
            4: 0.55,
            5: 0.8,
        }[self.cpu_difficulty]
        self.font = pygame.font.SysFont("arialblack", 32)
        self.small_font = pygame.font.SysFont("arial", 20)
        self.panels = [
            pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)),
            pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)),
        ]
        self.paused = False
        self.winner = None
        self.cpu_elapsed = 0
        self.cpu_plan = None
        self.cpu_drop_mode = None
        self.reset_players()

    def reset_players(self):
        self.cpu_elapsed = 0
        self.cpu_plan = None
        self.cpu_drop_mode = None
        self.players = [
            Tetris(self.screen, multiplayer=True, player_number=player_number)
            for player_number in (1, 2)
        ]
        first, second = self.players
        if first.current and second.current and first.current.kind == second.current.kind:
            previous_kind = second.current.kind
            second.current = Piece(second.take_from_bag())
            second.current.x = (BOARD_WIDTH - len(second.current.matrix[0])) // 2
            second.current.y = -1 if second.current.matrix[0].count(1) == 0 else -2
            second.bag.append(previous_kind)
            random.shuffle(second.bag)

        for index, player in enumerate(self.players):
            player.line_clear_callback = (
                lambda cleared, player_index=index: self.on_lines_cleared(
                    player_index, cleared
                )
            )

    def on_lines_cleared(self, player_index, cleared):
        player = self.players[player_index]
        cancelled = min(cleared, player.pending_garbage)
        player.pending_garbage -= cancelled
        for _ in range(cancelled):
            player.add_feedback("-1", (100, 230, 140))

        sent = cleared - cancelled
        if sent:
            opponent = self.players[1 - player_index]
            opponent.pending_garbage += sent
            for _ in range(sent):
                player.add_feedback("+1", (255, 220, 90))

    def find_cpu_move(self, player):
        if player.current is None:
            return None

        piece = player.current
        start_matrix = tuple(tuple(row) for row in piece.matrix)
        start = (start_matrix, piece.x)
        routes = {start: []}
        queue = deque([start])
        reachable = []
        kicks = [0, -1, 1, -2, 2]

        while queue:
            matrix_key, x = queue.popleft()
            route = routes[(matrix_key, x)]
            matrix = [list(row) for row in matrix_key]
            reachable.append((matrix, x, route))

            for direction in (-1, 1):
                next_state = (matrix_key, x + direction)
                candidate = piece.copy()
                candidate.matrix = matrix
                candidate.x = x
                candidate.y = piece.y
                if (
                    next_state not in routes
                    and not player.collides(candidate, dx=direction)
                ):
                    routes[next_state] = route + [
                        "left" if direction < 0 else "right"
                    ]
                    queue.append(next_state)

            rotated = tuple(tuple(row) for row in zip(*matrix[::-1]))
            if rotated != matrix_key:
                for offset in kicks:
                    rotated_state = (rotated, x + offset)
                    candidate = piece.copy()
                    candidate.matrix = [list(row) for row in matrix_key]
                    candidate.x = x
                    candidate.y = piece.y
                    if (
                        rotated_state not in routes
                        and not player.collides(candidate, dx=offset, matrix=rotated)
                    ):
                        routes[rotated_state] = route + ["rotate"]
                        queue.append(rotated_state)
                        break

        best_move = None
        best_score = float("inf")
        for candidate_matrix, x, route in reachable:
            candidate = piece.copy()
            candidate.matrix = candidate_matrix
            candidate.x = x
            candidate.y = piece.y
            while not player.collides(candidate, dy=1):
                candidate.y += 1

            simulated = [row[:] for row in player.board]
            valid = True
            for row_index, row in enumerate(candidate.matrix):
                for column_index, cell in enumerate(row):
                    if not cell:
                        continue
                    board_y = candidate.y + row_index
                    board_x = candidate.x + column_index
                    if board_y < 0:
                        valid = False
                        break
                    simulated[board_y][board_x] = piece.color
                if not valid:
                    break
            if not valid:
                continue

            cleared = sum(all(cell != 0 for cell in row) for row in simulated)
            simulated = [row for row in simulated if not all(cell != 0 for cell in row)]
            simulated = [[0 for _ in range(BOARD_WIDTH)] for _ in range(cleared)] + simulated

            heights = []
            holes = 0
            for column in range(BOARD_WIDTH):
                occupied_rows = [
                    row_index
                    for row_index in range(BOARD_HEIGHT)
                    if simulated[row_index][column] != 0
                ]
                height = BOARD_HEIGHT - occupied_rows[0] if occupied_rows else 0
                heights.append(height)
                if occupied_rows:
                    holes += sum(
                        simulated[row_index][column] == 0
                        for row_index in range(occupied_rows[0], BOARD_HEIGHT)
                    )
            aggregate_height = sum(heights)
            bumpiness = sum(
                abs(heights[index] - heights[index + 1])
                for index in range(BOARD_WIDTH - 1)
            )
            score = (
                aggregate_height * 0.55
                + holes * 8
                + bumpiness * 0.4
                - cleared * 5
                + len(route) * 0.03
            )
            if score < best_score:
                best_score = score
                best_move = route

        return best_move

    def update_cpu(self, dt):
        if not self.cpu_opponent or self.winner is not None or self.paused:
            return

        cpu = self.players[1]
        if cpu.game_over or cpu.current is None or cpu.clearing_rows:
            self.cpu_plan = None
            self.cpu_drop_mode = None
            return

        if self.cpu_plan is None or self.cpu_plan[0] is not cpu.current:
            route = self.find_cpu_move(cpu)
            if route is None:
                cpu.hard_drop()
                return
            self.cpu_plan = (cpu.current, route)
            self.cpu_drop_mode = None

        self.cpu_elapsed += dt
        if self.cpu_elapsed < self.cpu_action_interval:
            return
        self.cpu_elapsed = 0

        _, route = self.cpu_plan
        if not route:
            if self.cpu_drop_mode is None:
                self.cpu_drop_mode = (
                    "hard"
                    if random.random() < self.cpu_hard_drop_chance
                    else "soft"
                )

            if self.cpu_drop_mode == "hard":
                cpu.hard_drop()
                self.cpu_plan = None
                self.cpu_drop_mode = None
            else:
                previous_piece = cpu.current
                cpu.soft_drop()
                if cpu.current is not previous_piece or cpu.game_over:
                    self.cpu_plan = None
                    self.cpu_drop_mode = None
            return

        action = route[0]
        old_x = cpu.current.x
        old_matrix = [row[:] for row in cpu.current.matrix]
        if action == "left":
            cpu.move(-1, 0)
        elif action == "right":
            cpu.move(1, 0)
        else:
            cpu.rotate_piece()

        if cpu.current.x == old_x and cpu.current.matrix == old_matrix:
            self.cpu_plan = None
            self.cpu_drop_mode = None
        else:
            route.pop(0)

    def process_input(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type != pygame.KEYDOWN:
            return True

        if event.key == pygame.K_ESCAPE:
            self.paused = not self.paused
            for player in self.players:
                player.pause = self.paused
            return True

        if self.winner is not None or self.paused:
            return True

        active_players = self.players[:1] if self.cpu_opponent else self.players
        for player, controls in zip(active_players, self.PLAYER_CONTROLS):
            action = controls.get(event.key)
            if action == "left":
                player.move(-1, 0)
            elif action == "right":
                player.move(1, 0)
            elif action == "down":
                player.soft_drop()
            elif action == "rotate":
                player.rotate_piece()
            elif action == "drop":
                player.hard_drop()
            elif action == "hold":
                player.hold()
        return True

    def update(self, dt):
        if self.paused or self.winner is not None:
            return

        for player in self.players:
            player.update(dt)
        self.update_cpu(dt)

        for player in self.players:
            if player.pending_garbage == 0:
                continue
            player.garbage_timer_elapsed += dt
            if player.garbage_timer_elapsed >= GARBAGE_INTERVAL:
                pending = player.pending_garbage
                player.pending_garbage = 0
                player.garbage_timer_elapsed = 0
                player.add_garbage_rows(pending)

        if self.players[0].game_over:
            self.winner = 2
        elif self.players[1].game_over:
            self.winner = 1

    def render(self):
        self.screen.fill((15, 15, 20))
        for index, (player, panel) in enumerate(zip(self.players, self.panels)):
            player.render_to(panel)
            self.screen.blit(panel, (index * SCREEN_WIDTH, 0))
            label = (
                f"CPU NIVEL {self.cpu_difficulty}"
                if self.cpu_opponent and index == 1
                else f"JUGADOR {index + 1}"
            )
            title = self.font.render(label, True, (255, 255, 255))
            self.screen.blit(
                title,
                (
                    index * SCREEN_WIDTH + (SCREEN_WIDTH - title.get_width()) // 2,
                    2,
                ),
            )

        pygame.draw.line(
            self.screen,
            (90, 90, 105),
            (SCREEN_WIDTH, 0),
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            2,
        )

        if self.paused:
            self._draw_center_message("PAUSA", "Pulsa Esc para continuar")
        elif self.winner is not None:
            self._draw_center_message(
                f"GANA JUGADOR {self.winner}", "M: menu   R: revancha"
            )
        pygame.display.flip()

    def _draw_center_message(self, heading, instruction):
        overlay = pygame.Surface((SCREEN_WIDTH * 2, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        title = self.font.render(heading, True, (255, 255, 255))
        detail = self.small_font.render(instruction, True, (230, 230, 230))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH, SCREEN_HEIGHT // 2 - 20)))
        self.screen.blit(detail, detail.get_rect(center=(SCREEN_WIDTH, SCREEN_HEIGHT // 2 + 25)))


class GameApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris Classic")
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("arialblack", 48)
        self.font = pygame.font.SysFont("arialblack", 30)
        self.small_font = pygame.font.SysFont("arial", 21)
        self.mode = "menu"
        self.cpu_difficulty = 3
        self.game: Tetris | MultiplayerGame | None = None

    def start_game(self, mode, cpu_difficulty=None):
        if mode == "single":
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.game = Tetris(self.screen)
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH * 2, SCREEN_HEIGHT))
            self.game = MultiplayerGame(
                self.screen,
                cpu_opponent=(mode == "cpu"),
                cpu_difficulty=cpu_difficulty or self.cpu_difficulty,
            )
            if mode == "cpu":
                self.cpu_difficulty = self.game.cpu_difficulty
        self.mode = mode

    def return_to_menu(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.mode = "menu"
        self.game = None

    def draw_menu(self):
        self.screen.fill((15, 15, 20))
        title = self.title_font.render("TETRIS", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 110)))

        choices = (
            ("1", "1 JUGADOR"),
            ("2", "MULTIJUGADOR"),
            ("3", "JUGAR CON CPU"),
        )
        for index, (key, label) in enumerate(choices):
            text = self.font.render(f"{key}  -  {label}", True, (80, 220, 230))
            self.screen.blit(
                text,
                text.get_rect(center=(SCREEN_WIDTH // 2, 225 + index * 60)),
            )

        instructions = [
            "Jugador 1: flechas mueven, Z rota, X/Espacio caida, C reserva",
            "Jugador 2: A/D/S mueven, W rota, Q caida, E reserva",
            "Esc pausa   |   M vuelve al menu   |   3 inicia modo CPU",
        ]
        for index, line in enumerate(instructions):
            text = self.small_font.render(line, True, (210, 210, 220))
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, 440 + index * 32)))
        pygame.display.flip()

    def draw_cpu_difficulty(self):
        self.screen.fill((15, 15, 20))
        title = self.title_font.render("DIFICULTAD CPU", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 130)))

        levels = [
            ("1", "MUY TRANQUILA", "Se mueve despacio; baja poco a poco"),
            ("2", "TRANQUILA", "Lenta; casi siempre baja poco a poco"),
            ("3", "NORMAL", "Velocidad media; a veces cae de golpe"),
            ("4", "DIFICIL", "Rapida; usa la caida instantanea a menudo"),
            ("5", "MUY DIFICIL", "Muy rapida; casi siempre optimiza la caida"),
        ]
        for index, (key, label, description) in enumerate(levels):
            y = 225 + index * 54
            heading = self.font.render(
                f"{key}  -  {label}", True, (80, 220, 230)
            )
            detail = self.small_font.render(description, True, (210, 210, 220))
            self.screen.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, y)))
            self.screen.blit(
                detail, detail.get_rect(center=(SCREEN_WIDTH // 2, y + 27))
            )

        back = self.small_font.render(
            "Pulsa Esc para volver al menu", True, (180, 180, 190)
        )
        self.screen.blit(back, back.get_rect(center=(SCREEN_WIDTH // 2, 535)))
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                if event.type != pygame.KEYDOWN:
                    continue

                if self.mode == "menu":
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        self.start_game("single")
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        self.start_game("multiplayer")
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        self.mode = "cpu_difficulty"
                    continue

                if self.mode == "cpu_difficulty":
                    if event.key == pygame.K_ESCAPE:
                        self.mode = "menu"
                    elif event.key in (
                        pygame.K_1,
                        pygame.K_2,
                        pygame.K_3,
                        pygame.K_4,
                        pygame.K_5,
                        pygame.K_KP1,
                        pygame.K_KP2,
                        pygame.K_KP3,
                        pygame.K_KP4,
                        pygame.K_KP5,
                    ):
                        difficulty_keys = {
                            pygame.K_1: 1,
                            pygame.K_2: 2,
                            pygame.K_3: 3,
                            pygame.K_4: 4,
                            pygame.K_5: 5,
                            pygame.K_KP1: 1,
                            pygame.K_KP2: 2,
                            pygame.K_KP3: 3,
                            pygame.K_KP4: 4,
                            pygame.K_KP5: 5,
                        }
                        self.start_game(
                            "cpu", cpu_difficulty=difficulty_keys[event.key]
                        )
                    continue

                if event.key == pygame.K_m:
                    self.return_to_menu()
                    continue
                if isinstance(self.game, MultiplayerGame):
                    if event.key == pygame.K_r and self.game.winner is not None:
                        self.game.reset_players()
                        self.game.winner = None
                        self.game.paused = False
                        continue
                    if not self.game.process_input(event):
                        running = False
                else:
                    if not isinstance(self.game, Tetris):
                        continue
                    if self.game.game_over and event.key in (
                        pygame.K_RETURN,
                        pygame.K_SPACE,
                    ):
                        self.start_game("single")
                        continue
                    self.game.process_input(event)

            if not running:
                break

            if self.mode == "menu":
                self.draw_menu()
            elif self.mode == "cpu_difficulty":
                self.draw_cpu_difficulty()
            elif isinstance(self.game, MultiplayerGame):
                self.game.update(dt)
                self.game.render()
            elif isinstance(self.game, Tetris):
                self.game.update(dt)
                self.game.render()

        pygame.quit()


if __name__ == "__main__":
    GameApp().run()
