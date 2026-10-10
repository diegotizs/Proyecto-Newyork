import pygame
import random

# Configuración
WIDTH, HEIGHT = 480, 640
FPS = 60
GRAVITY = 0.45
FLAP_FORCE = -8
PIPE_SPEED = 2.5
PIPE_GAP = 150
PIPE_INTERVAL = 1400
GROUND_HEIGHT = 90

pygame.init()
pygame.display.set_caption("Flappy Bird 2D")
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("arialblack", 32)
small_font = pygame.font.SysFont("arial", 20)

bg_color = (112, 197, 255)
ground_color = (70, 160, 80)
pipe_color = (78, 199, 90)
pipe_dark = (48, 136, 60)


class Bird:
    def __init__(self):
        self.x = 110
        self.y = HEIGHT // 2
        self.radius = 18
        self.velocity = 0
        self.rotation = 0

    def flap(self):
        self.velocity = FLAP_FORCE

    def update(self):
        self.velocity += GRAVITY
        self.y += self.velocity
        self.rotation = min(max(self.velocity * 3, -30), 90)

    def draw(self, surface):
        rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)
        pygame.draw.ellipse(surface, (255, 217, 61), rect)
        pygame.draw.ellipse(surface, (255, 198, 30), (rect.x + 6, rect.y + 4, 10, 10))
        pygame.draw.circle(surface, (0, 0, 0), (int(self.x + 6), int(self.y - 4)), 3)
        pygame.draw.polygon(surface, (255, 140, 0), [
            (self.x + self.radius - 2, self.y - 2),
            (self.x + self.radius + 14, self.y),
            (self.x + self.radius - 2, self.y + 6)
        ])

    def collides_with(self, pipe):
        bird_left = self.x - self.radius
        bird_right = self.x + self.radius
        bird_top = self.y - self.radius
        bird_bottom = self.y + self.radius

        if bird_right < pipe.x or bird_left > pipe.x + pipe.width:
            return False

        if bird_top < pipe.top_height or bird_bottom > pipe.top_height + pipe.gap:
            if bird_left < pipe.x + pipe.width and bird_right > pipe.x:
                return True
        return False


class Pipe:
    def __init__(self, x):
        self.x = x
        self.width = 70
        self.gap = PIPE_GAP
        self.top_height = random.randint(80, HEIGHT - GROUND_HEIGHT - self.gap - 80)
        self.scored = False

    def update(self):
        self.x -= PIPE_SPEED

    def draw(self, surface):
        top_rect = pygame.Rect(self.x, 0, self.width, self.top_height)
        bottom_y = self.top_height + self.gap
        bottom_height = HEIGHT - GROUND_HEIGHT - bottom_y
        bottom_rect = pygame.Rect(self.x, bottom_y, self.width, bottom_height)

        pygame.draw.rect(surface, pipe_color, top_rect)
        pygame.draw.rect(surface, pipe_dark, (self.x, self.top_height - 18, self.width, 18))
        pygame.draw.rect(surface, pipe_color, bottom_rect)
        pygame.draw.rect(surface, pipe_dark, (self.x, bottom_y, self.width, 18))


class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.bird = Bird()
        self.pipes = []
        self.score = 0
        self.started = False
        self.game_over = False
        self.pipe_timer = 0
        self.last_time = pygame.time.get_ticks()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if not self.started:
                        self.started = True
                    if not self.game_over:
                        self.bird.flap()
                if event.key == pygame.K_r and self.game_over:
                    self.reset()
        return True

    def update(self):
        if not self.started or self.game_over:
            return

        self.bird.update()

        self.pipe_timer += clock.get_time()
        if self.pipe_timer >= PIPE_INTERVAL:
            self.pipes.append(Pipe(WIDTH + 40))
            self.pipe_timer = 0

        for pipe in self.pipes:
            pipe.update()
            if not pipe.scored and pipe.x + pipe.width < self.bird.x:
                self.score += 1
                pipe.scored = True

            if self.bird.collides_with(pipe):
                self.game_over = True

        if self.bird.y + self.bird.radius >= HEIGHT - GROUND_HEIGHT:
            self.game_over = True

        if self.bird.y - self.bird.radius <= 0:
            self.bird.y = self.bird.radius
            self.bird.velocity = 0

        self.pipes = [pipe for pipe in self.pipes if pipe.x + pipe.width > -20]

    def draw(self):
        screen.fill(bg_color)

        # Nubes
        for i in range(4):
            x = (i * 140 + (pygame.time.get_ticks() // 15) % 140) % (WIDTH + 80) - 40
            y = 70 + (i % 2) * 40
            pygame.draw.ellipse(screen, (255, 255, 255), (x, y, 90, 40))
            pygame.draw.ellipse(screen, (255, 255, 255), (x + 25, y - 10, 60, 40))

        for pipe in self.pipes:
            pipe.draw(screen)

        # Suelo
        pygame.draw.rect(screen, ground_color, (0, HEIGHT - GROUND_HEIGHT, WIDTH, GROUND_HEIGHT))
        for x in range(0, WIDTH + 30, 30):
            pygame.draw.rect(screen, (85, 200, 90), (x, HEIGHT - GROUND_HEIGHT, 20, 10))

        self.bird.draw(screen)

        score_text = font.render(str(self.score), True, (255, 255, 255))
        score_rect = score_text.get_rect(center=(WIDTH // 2, 80))
        pygame.draw.rect(screen, (0, 0, 0, 90), score_rect.inflate(30, 18), border_radius=12)
        screen.blit(score_text, score_rect)

        if not self.started and not self.game_over:
            msg = font.render("Presiona ESPACIO", True, (255, 255, 255))
            msg_rect = msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
            screen.blit(msg, msg_rect)
            sub = small_font.render("o haz click en la ventana", True, (255, 255, 255))
            sub_rect = sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
            screen.blit(sub, sub_rect)

        if self.game_over:
            over = font.render("Game Over", True, (255, 255, 255))
            over_rect = over.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30))
            screen.blit(over, over_rect)
            restart = small_font.render("Pulsa R para jugar otra vez", True, (255, 255, 255))
            restart_rect = restart.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
            screen.blit(restart, restart_rect)

        pygame.display.flip()


def main():
    game = Game()
    running = True
    while running:
        clock.tick(FPS)
        running = game.handle_events()
        game.update()
        game.draw()

    pygame.quit()


if __name__ == "__main__":
    main()
