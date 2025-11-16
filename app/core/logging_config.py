import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import datetime
import pytz
import os

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

class ISTFormatter(logging.Formatter):
    """Custom formatter that converts timestamps to IST"""
    def converter(self, timestamp):
        dt = datetime.datetime.fromtimestamp(timestamp)
        ist_tz = pytz.timezone('Asia/Kolkata')
        return dt.astimezone(ist_tz)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]

class UnicodeSafeStreamHandler(logging.StreamHandler):
    """Stream handler that safely handles Unicode characters on Windows"""
    def __init__(self, stream=None, replace_emojis=False):
        super().__init__(stream)
        self.replace_emojis = replace_emojis
        self.emoji_replacements = {
            '✅': '[SUCCESS]',
            '🎯': '[TARGET]',
            '⚡': '[FAST]',
            '📊': '[STATS]',
            '🎨': '[BRAND]',
            '⚠️': '[WARNING]',
            '🔧': '[FIX]',
            '🚀': '[ROCKET]',
            '💡': '[IDEA]',
            '🔥': '[HOT]',
            '⭐': '[STAR]',
            '🎉': '[CELEBRATE]',
            '🔍': '[SEARCH]',
            '📝': '[NOTE]',
            '🔄': '[REFRESH]',
            '⏱️': '[TIMER]',
            '🎪': '[CIRCUS]',
            '🏆': '[TROPHY]',
            '💎': '[DIAMOND]',
            '🌟': '[SPARKLE]'
        }
    
    def emit(self, record):
        try:
            msg = self.format(record)
            
            # Replace emojis with text if requested
            if self.replace_emojis:
                for emoji, replacement in self.emoji_replacements.items():
                    msg = msg.replace(emoji, replacement)
            
            stream = self.stream
            # Write with proper encoding handling
            if hasattr(stream, 'buffer'):
                # For stdout/stderr, use the buffer with UTF-8 encoding
                stream.buffer.write(msg.encode('utf-8'))
                stream.buffer.write(self.terminator.encode('utf-8'))
                stream.buffer.flush()
            else:
                # Fallback for other streams
                stream.write(msg + self.terminator)
                stream.flush()
        except Exception:
            self.handleError(record)

# Configure logging format
log_format = ISTFormatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d"
)

def setup_logger(name: str, replace_emojis: bool = False) -> logging.Logger:
    """
    Setup logger with optional emoji replacement for Windows compatibility
    
    Args:
        name: Logger name
        replace_emojis: If True, replace emoji characters with text equivalents
    """
    logger = logging.getLogger(name)
    # Set to DEBUG to see more detailed logs
    logger.setLevel(logging.DEBUG)

    # Console Handler with Unicode-safe handling
    console_handler = UnicodeSafeStreamHandler(sys.stdout, replace_emojis=replace_emojis)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # File Handler with DEBUG level
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10485760,  # 10MB
        backupCount=5,
        encoding='utf-8'  # Ensure UTF-8 encoding for log files
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # Prevent logs from being propagated to the root logger
    logger.propagate = False

    return logger

# Create main application logger
# Set replace_emojis=True if you want to avoid Unicode issues on Windows
logger = setup_logger("fastapi_app", replace_emojis=False)
