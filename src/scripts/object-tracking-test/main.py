import pygame
import argparse
import sys
import math
import csv
import yaml
import os

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 30
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GRAY = (100, 100, 100)
POS_FILE = ".position"

class Target:
    def __init__(self, target_id, start_pos, radius, speed_x, speed_y, path_type="linear"):
        self.id = target_id
        self.start_pos = start_pos
        self.radius = radius
        self.speed_x = speed_x
        self.speed_y = speed_y
        self.path_type = path_type
        self.x = start_pos[0]
        self.y = start_pos[1]

    def update(self, frame):
        if self.path_type == "linear":
            self.x = self.start_pos[0] + self.speed_x * frame
            self.y = self.start_pos[1] + self.speed_y * frame
        elif self.path_type == "sine":
            self.x = self.start_pos[0] + self.speed_x * frame
            self.y = self.start_pos[1] + math.sin(frame * 0.1) * 100
        elif self.path_type == "circular":
            # speed_x = Orbit Radius (pixels)
            # speed_y = Angular Velocity (radians per frame)
            # start_pos = Center of the orbit
            self.x = self.start_pos[0] + self.speed_x * math.cos(frame * self.speed_y)
            self.y = self.start_pos[1] + self.speed_x * math.sin(frame * self.speed_y)
        
        self.x %= WIDTH
        self.y %= HEIGHT

    def draw(self, surface):
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), self.radius)

class Occlusion:
    def __init__(self, rect, color=GRAY):
        self.rect = pygame.Rect(rect)
        self.color = color

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)

def load_test_case(config_file, test_id):
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)

    if not config or "tests" not in config:
        return [], [], 0

    test_data = next((t for t in config["tests"] if t.get("id") == test_id), None)
    
    if not test_data:
        return [], [], 0

    duration_frames = test_data.get("duration_frames", 300)

    targets = []
    for t_data in test_data.get("targets", []):
        targets.append(Target(
            target_id=t_data["id"],
            start_pos=tuple(t_data["start_pos"]),
            radius=t_data["radius"],
            speed_x=t_data["speed_x"],
            speed_y=t_data["speed_y"],
            path_type=t_data.get("path_type", "linear")
        ))

    occlusions = []
    for o_data in test_data.get("occlusions", []):
        color = tuple(o_data.get("color", GRAY))
        occlusions.append(Occlusion(tuple(o_data["rect"]), color))

    return targets, occlusions, duration_frames

def load_window_position():
    """Reads the .position file and sets the SDL environment variable."""
    if os.path.exists(POS_FILE):
        try:
            with open(POS_FILE, "r") as f:
                x, y = f.read().strip().split(',')
                os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"
        except Exception as e:
            print(f"Warning: Failed to load window position: {e}")

def save_window_position():
    """Retrieves the current window position and saves it to .position."""
    try:
        # Pygame 2.4+ standard window API
        if hasattr(pygame, 'Window'):
            window = pygame.Window.from_display_module()
            x, y = window.position
        else:
            # Fallback for earlier Pygame 2.x versions
            from pygame._sdl2.video import Window
            window = Window.from_display_module()
            x, y = window.position

        current_pos_str = f"{x},{y}"
        
        # Only write if the position has changed or file doesn't exist
        update_needed = True
        if os.path.exists(POS_FILE):
            with open(POS_FILE, "r") as f:
                if f.read().strip() == current_pos_str:
                    update_needed = False
                    
        if update_needed:
            with open(POS_FILE, "w") as f:
                f.write(current_pos_str)
            print(f"Window position saved: {current_pos_str}")

    except Exception as e:
        print(f"Warning: Could not save window position (requires Pygame 2.x): {e}")

def run_test(test_id, csv_writer, config_file, target_display):
    targets, occlusions, duration_frames = load_test_case(config_file, test_id)
    if not targets:
        print(f"Test {test_id} not found in {config_file}.")
        return

    # Load previously saved position before initializing display
    load_window_position()

    pygame.init()
    pygame.font.init()
    
    num_displays = pygame.display.get_num_displays()
    if target_display >= num_displays:
        print(f"Warning: Display {target_display} not found. Defaulting to Display 0. (Available: {num_displays})")
        target_display = 0

    screen = pygame.display.set_mode((WIDTH, HEIGHT), display=target_display)
    pygame.display.set_caption(f"Tracking Test Case {test_id}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    print(f"--- Starting Test {test_id} ---")
    
    # --- Alignment and Start Sequence ---
    waiting = True
    prompt_text = font.render(f"Test {test_id} Ready. Press SPACE to start.", True, WHITE)
    text_rect = prompt_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                save_window_position()
                waiting = False

        screen.fill(BLACK)
        
        for target in targets:
            target.update(0)
            target.draw(screen)
            
        for occ in occlusions:
            occ.draw(screen)

        screen.blit(prompt_text, text_rect)
        pygame.display.flip()
        clock.tick(FPS)

    # --- Main Tracking Sequence ---
    for frame in range(duration_frames):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill(BLACK)
        timestamp_ms = (frame / FPS) * 1000.0

        for target in targets:
            target.update(frame)
            target.draw(screen)
            csv_writer.writerow([test_id, frame, timestamp_ms, target.id, target.x, target.y, target.radius])

        for occ in occlusions:
            occ.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Event Sensor Tracking Test Suite")
    parser.add_argument("--test", type=int, help="Run a specific test case ID")
    parser.add_argument("--all", action="store_true", help="Run all test cases sequentially")
    parser.add_argument("--out", type=str, default="tracking_log.csv", help="Output CSV file for sync data")
    parser.add_argument("--config", type=str, default="tests.yaml", help="Path to the YAML configuration file")
    parser.add_argument("--display", type=int, default=0, help="Display index to run the tests on (0 is primary)")
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.print_help()
        sys.exit(1)

    try:
        with open(args.config, "r") as f:
            config_data = yaml.safe_load(f)
            available_tests = [t["id"] for t in config_data.get("tests", []) if "id" in t]
    except FileNotFoundError:
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)

    with open(args.out, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["test_id", "frame_number", "timestamp_ms", "object_id", "pos_x", "pos_y", "radius"])
        
        tests_to_run = sorted(available_tests) if args.all else [args.test]

        for t in tests_to_run:
            run_test(t, writer, args.config, args.display)

    print(f"Testing complete. Synchronization data saved to {args.out}")

if __name__ == "__main__":
    main()
