"""Gunicorn configuration with Uvicorn worker settings"""
import multiprocessing
import json
import os
import signal
from pathlib import Path
import glob

# Create logs directory in the project
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

# Find all Python files to watch
def get_python_files():
    base_dir = Path(__file__).parent
    python_files = []
    for pattern in ["app/**/*.py", "*.py"]:
        python_files.extend([str(p) for p in base_dir.glob(pattern)])
    return python_files

# Gunicorn settings
workers = min(multiprocessing.cpu_count(), 5)  # Cap at 4 workers
worker_class = "uvicorn.workers.UvicornWorker"

# Server mechanics
daemon = False
raw_env = []
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None
secure_scheme_headers = {
    "X-FORWARDED-PROTOCOL": "ssl",
    "X-FORWARDED-PROTO": "https",
    "X-FORWARDED-SSL": "on"
}

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
worker_connections = 1000
timeout = 120
graceful_timeout = 15
keepalive = 5
max_requests = 500
max_requests_jitter = 50

# Logging
accesslog = str(log_dir / "access.log")
errorlog = str(log_dir / "error.log")
loglevel = "debug"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = None

# Server mechanics
preload_app = False  # Changed to False to prevent memory issues
reload = True  # Enable auto-reload in development
reload_extra_files = get_python_files()  # Watch all Python files

def when_ready(server):
    """Server ready handler"""
    server.log.info("Server is ready. Watching for file changes...")
    server.log.info(f"Watching files: {reload_extra_files}")

def on_starting(server):
    """Server startup handler"""
    server.log.info("Server is starting up...")
    # Store the original SIGTERM handler
    server.old_term_handler = signal.getsignal(signal.SIGTERM)
    
    def graceful_shutdown(signum, frame):
        """Custom shutdown handler"""
        server.log.info("Received shutdown signal, waiting for workers to finish...")
        # Call the original SIGTERM handler
        if server.old_term_handler:
            server.old_term_handler(signum, frame)
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, graceful_shutdown)

def post_worker_init(worker):
    """Post worker initialization"""
    worker.log.info(f"Worker {worker.pid} initialized")
    
    # Set up worker signal handlers
    def worker_signal_handler(signum, frame):
        worker.log.info(f"Worker {worker.pid} received signal {signum}")
        if signum in (signal.SIGTERM, signal.SIGINT):
            worker.log.info(f"Worker {worker.pid} shutting down...")
    
    signal.signal(signal.SIGTERM, worker_signal_handler)
    signal.signal(signal.SIGINT, worker_signal_handler)

def worker_abort(worker):
    """Worker abort handler"""
    worker.log.warning(f"Worker {worker.pid} was aborted!")

def worker_exit(server, worker):
    """Worker exit handler"""
    server.log.info(f"Worker {worker.pid} exited, spawning new worker...")

def worker_init(worker):
    """Worker initialization"""
    worker.log.info(f"Initializing worker {worker.pid}")
    
    # Uvicorn worker settings
    worker.cfg.timeout_keep_alive = 5       # Keep-alive timeout
    worker.cfg.limit_concurrency = 100      # Max concurrent connections per worker
    worker.cfg.forwarded_allow_ips = "*"    # Trust X-Forwarded-* headers
    worker.cfg.proxy_headers = True         # Enable proxy headers
    worker.cfg.access_log = True            # Enable access log
    
    # WebSocket settings if you use them
    worker.cfg.ws_ping_interval = 20        # Ping every 20 seconds
    worker.cfg.ws_ping_timeout = 20         # Wait 20 seconds for pong response
    
    # HTTP settings
    worker.cfg.h11_max_incomplete_size = 16384  # Max header size
    
    settings = {
        "timeout_keep_alive": worker.cfg.timeout_keep_alive,
        "limit_concurrency": worker.cfg.limit_concurrency,
        "workers": workers,
        "max_requests": max_requests,
        "graceful_timeout": graceful_timeout
    }
    worker.log.info(f"Worker {worker.pid} configured with settings: {json.dumps(settings, indent=2)}")

def on_exit(server):
    """Server shutdown handler"""
    server.log.info("Server is shutting down gracefully...")
    
    def force_exit(signum, frame):
        server.log.warning("Forcing exit after timeout...")
        exit(1)
    
    # Set a force exit timer
    signal.signal(signal.SIGALRM, force_exit)
    signal.alarm(30)  # Force exit after 30 seconds
