#!/bin/bash

# Function to kill Celery processes
kill_celery_processes() {
    echo "Stopping Celery processes..."

    # Kill all Celery workers
    pkill -f "celery worker"
    
    # Kill all Celery beat processes
    pkill -f "celery beat"
    
    # Kill specific named workers
    pkill -f "blog_generation_worker"
    
    # Additional cleanup for any lingering Celery processes
    pkill -f "celery"
    
    # Wait a moment to ensure processes are terminated
    sleep 2
    
    # Forcefully kill any remaining processes
    pkill -9 -f "celery"
}

# Function to verify process termination
verify_termination() {
    echo "Checking for remaining Celery processes..."
    
    # List any remaining Celery processes
    pgrep -f "celery" && {
        echo "Warning: Some Celery processes could not be terminated"
        return 1
    }
    
    echo "All Celery processes have been stopped successfully"
    return 0
}

# Main execution
main() {
    kill_celery_processes
    verify_termination
}

# Run the main function
main
