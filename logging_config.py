import time


from colorama import Fore, Style, init
import logging

init(autoreset=True)  # reset colors automatically after each print
PROGRAM_START = time.monotonic()


class IgnoreRustNotify(logging.Filter):
    def filter(self, record):
        # Return True to allow, False to ignore
        return "rust notify timeout" not in record.getMessage()


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    LEVEL_NAMES = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO ",
        logging.WARNING: "WARN ",
        logging.ERROR: "ERROR",
    }

    def format(self, record):
        # Let base class build full message (including exceptions)
        super().format(record)

        # Time formatting
        elapsed = time.monotonic() - PROGRAM_START
        seconds = int(elapsed)
        millis = int((elapsed - seconds) * 1000)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        timestamp = f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"

        # Color + level name
        color = self.LEVEL_COLORS.get(record.levelno, "")
        level = self.LEVEL_NAMES.get(record.levelno, record.levelname.upper())
        logger_name = record.name.split(".")[-1]

        # Recombine with formatted message (which already includes exceptions)
        return (
            f"{color}{timestamp} [{level}] "
            f"{logger_name}: {record.getMessage()}"
            f"{'' if record.exc_text is None else '\n' + record.exc_text}"
        )


ch = logging.StreamHandler()
ch.setFormatter(ColoredFormatter())
logging.basicConfig(level="INFO", handlers=[ch])

watchfiles_logger = logging.getLogger("watchfiles.main")
watchfiles_logger.addFilter(IgnoreRustNotify())
watchfiles_logger.setLevel(logging.WARNING)


def setup():
    pass
