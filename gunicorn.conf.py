# Gunicorn Configuration for School Production
# Save as gunicorn.conf.py

import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', 8001)}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 300  # Increased to 5 minutes for long-running operations like marks saving
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = os.getenv('ERROR_LOG', '-')  # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')
accesslog = os.getenv('ACCESS_LOG', '-')  # stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'school'

# Server mechanics
daemon = False
pidfile = '/tmp/school.pid'
user = os.getenv('USER')
group = os.getenv('GROUP')
tmp_upload_dir = None

# SSL (uncomment for HTTPS)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Environment
raw_env = [
    f'FLASK_ENV={os.getenv("FLASK_ENV", "production")}',
]

# Preload application for better performance
preload_app = True

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting SmartGardenHub server...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading SmartGardenHub server...")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")