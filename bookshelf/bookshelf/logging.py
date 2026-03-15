import logging

class ColoredFormatter(logging.Formatter):
    """
    A custom formatter to add colors to the console output.
    """
    # ANSI escape codes for colors
    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    def format(self, record):
        if record.levelno == logging.WARNING:
            record.levelname = f"{self.YELLOW}{record.levelname}{self.RESET}"
        elif record.levelno >= logging.ERROR:
            record.levelname = f"{self.RED}{record.levelname}{self.RESET}"
        return super().format(record)
