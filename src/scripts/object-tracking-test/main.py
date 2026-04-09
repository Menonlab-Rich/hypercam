import argparse
import csv
import json
import math
import os
import sys

import pygame
import yaml

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
    """Reads the position file and sets the SDL environment variable."""
    if os.path.exists(POS_FILE):
        try:
            with open(POS_FILE, "r") as f:
                x, y = f.read().strip().split(',')
                os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"
        except Exception as e:
            print(f"Warning: Failed to load window position: {e}")

_main_window = None

def get_window_position():
    """Retrieves the current absolute window position relative to the monitor."""
    global _main_window
    try:
        if _main_window is None:
            # Pygame 2.4+ standard window API
            if hasattr(pygame, 'Window'):
                _main_window = pygame.Window.from_display_module()
            else:
                # Fallback for earlier Pygame 2.x versions
                from pygame._sdl2.video import Window
                _main_window = Window.from_display_module()
        return _main_window.position
    except Exception as e:
        print(f"Warning: Could not get window position (requires Pygame 2.x): {e}")
        return (0, 0)

def save_window_position():
    """Retrieves the current window position and saves it to .position."""
    try:
        x, y = get_window_position()
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
        print(f"Warning: Could not save window position: {e}")

def run_calibration(screen, font, clock):
    """Executes the pre-test calibration sequence to map screen space to absolute monitor space."""
    pygame.mouse.set_visible(False)
    points = []
    prompts = ["Click TOP-LEFT of visible area", "Click BOTTOM-RIGHT of visible area"]
    
    for prompt_text in prompts:
        waiting = True
        frame = 0
        
        # Pre-render the font surface once per prompt
        text_surf = font.render(prompt_text, True, WHITE)
        text_rect = text_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    points.append(event.pos)
                    waiting = False

            screen.fill(BLACK)
            screen.blit(text_surf, text_rect)
            
            # 30Hz flickering pointer (toggles render state every frame)
            if frame % 2 == 0:
                mx, my = pygame.mouse.get_pos()
                pygame.draw.line(screen, RED, (mx - 10, my), (mx + 10, my), 2)
                pygame.draw.line(screen, RED, (mx, my - 10), (mx, my + 10), 2)
            
            pygame.display.flip()
            clock.tick(FPS)
            frame += 1

    # Force position save and calculate absolute coordinates relative to the monitor
    save_window_position()
    win_x, win_y = get_window_position()
    
    tl_x, tl_y = points[0]
    br_x, br_y = points[1]

    abs_tl = (win_x + tl_x, win_y + tl_y)
    abs_br = (win_x + br_x, win_y + br_y)

    calibration_data = {
        "window_position": [win_x, win_y],
        "relative_fov": {
            "top_left": [tl_x, tl_y],
            "bottom_right": [br_x, br_y]
        },
        "absolute_fov": {
            "top_left": abs_tl,
            "bottom_right": abs_br
        }
    }

    output_file = "calibration.json"
    with open(output_file, "w") as f:
        json.dump(calibration_data, f, indent=4)
    print(f"Calibration constraints saved to {output_file}")

    # Calculate center relative to the window and blink 2x2 for 5 seconds (150 frames)
    center_x = (tl_x + br_x) // 2
    center_y = (tl_y + br_y) // 2

    for frame in range(FPS * 5):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill(BLACK)
        if frame % 2 == 0:
            pygame.draw.rect(screen, WHITE, (center_x - 1, center_y - 1, 2, 2))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.mouse.set_visible(True)

def blink_test_id(screen, font, clock, test_id):
    """Blinks the upcoming Test ID at 15Hz for 2 seconds before starting."""
    text_surf = font.render(f"TEST ID: {test_id}", True, WHITE)
    text_rect = text_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    
    # 2 seconds total duration
    for frame in range(FPS * 2):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill(BLACK)
        
        # 15Hz blink at 30 FPS means toggling state every 1 frame.
        if frame % 2 == 0:
            screen.blit(text_surf, text_rect)

        pygame.display.flip()
        clock.tick(FPS)

def run_test(test_id, csv_writer, config_file, screen, font, clock, no_display=False):
    targets, occlusions, duration_frames = load_test_case(config_file, test_id)
    if not targets:
        print(f"Test {test_id} not found in {config_file}.")
        return

    print(f"--- Starting Test {test_id} ---")
    
    if not no_display:
        blink_test_id(screen, font, clock, test_id)

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
    else:
        for frame in range(duration_frames):
            # Pump events to prevent OS unresponsiveness timeouts
            pygame.event.pump() 
            timestamp_ms = (frame / FPS) * 1000.0

            for target in targets:
                target.update(frame)
                csv_writer.writerow([test_id, frame, timestamp_ms, target.id, target.x, target.y, target.radius])

            clock.tick(FPS)

def main():
    parser = argparse.ArgumentParser(description="Event Sensor Tracking Test Suite")
    parser.add_argument("--test", nargs="+", type=int, help="Run a specific test case ID")
    parser.add_argument("--all", action="store_true", help="Run all test cases sequentially")
    parser.add_argument("--out", type=str, default="tracking_log.csv", help="Output CSV file for sync data")
    parser.add_argument("--config", type=str, default="tests.yaml", help="Path to the YAML configuration file")
    parser.add_argument("--display", type=int, default=0, help="Display index to run the tests on (0 is primary)")
    parser.add_argument("--no-display", action="store_true", help="Bypass display and only produce logs")
    args = parser.parse_args()

    if not args.test and not args.all:
        parser.print_help()
        sys.exit(1)

    # Load previously saved position before initializing display
    load_window_position()

    pygame.init()
    pygame.font.init()

    num_displays = pygame.display.get_num_displays()
    target_display = args.display
    if target_display >= num_displays:
        print(f"Warning: Display {target_display} not found. Defaulting to Display 0. (Available: {num_displays})")
        target_display = 0

    screen = pygame.display.set_mode((WIDTH, HEIGHT), display=target_display)
    pygame.display.set_caption("Tracking Test Suite")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    try:
        with open(args.config, "r") as f:
            config_data = yaml.safe_load(f)
            available_tests = [t["id"] for t in config_data.get("tests", []) if "id" in t]
    except FileNotFoundError:
        print(f"Error: Configuration file '{args.config}' not found.")
        pygame.quit()
        sys.exit(1)

    with open(args.out, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["test_id", "frame_number", "timestamp_ms", "object_id", "pos_x", "pos_y", "radius"])
        
        tests_to_run = sorted(available_tests) if args.all else args.test

        # Run calibration once per batch if display is active
        if not args.no_display:
            run_calibration(screen, font, clock)

        for t in tests_to_run:
            run_test(t, writer, args.config, screen, font, clock, args.no_display)

    print(f"Testing complete. Synchronization data saved to {args.out}")
    pygame.quit()

if __name__ == "__main__":
    main()
