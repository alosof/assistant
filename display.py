import itertools
import threading
import time

# ANSI styles
BOLD = "\033[1m"
RESET = "\033[0m"
BLUE = "\033[94m"
GREEN = "\033[92m"
DIM = "\033[2m"


class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Recherche en cours..."):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        for frame in itertools.cycle(self.FRAMES):
            if self._stop_event.is_set():
                break
            print(f"\r\r{DIM}{frame} {self.message}{RESET}", end="", flush=True)
            time.sleep(0.1)
        # Clear the spinner line
        print(f"\r{' ' * (len(self.message) + 4)}\r", end="", flush=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()
