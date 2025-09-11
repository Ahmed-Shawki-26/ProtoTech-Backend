#!/usr/bin/env python3
"""
Production Deployment Script for ProtoTech Backend
Handles environment validation, database setup, and server startup
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'DATABASE_URL',
        'ENCODING_SECRET_KEY',
        'STRIPE_SECRET_KEY',
        'STRIPE_WEBHOOK_SECRET',
        'ODOO_URL',
        'ODOO_DB',
        'ODOO_USERNAME',
        'ODOO_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        return False
    
    logger.info("All required environment variables are set")
    return True

def install_dependencies():
    """Install Python dependencies"""
    try:
        logger.info("Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True, text=True)
        logger.info("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        return False

def run_database_migrations():
    """Run database migrations if Alembic is configured"""
    try:
        if os.path.exists("alembic.ini"):
            logger.info("Running database migrations...")
            subprocess.run(["alembic", "upgrade", "head"], check=True, capture_output=True, text=True)
            logger.info("Database migrations completed")
        else:
            logger.info("No Alembic configuration found, skipping migrations")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run migrations: {e}")
        return False

def start_server():
    """Start the production server"""
    try:
        logger.info("Starting production server...")
        
        # Use Gunicorn for production
        cmd = [
            "gunicorn",
            "main:app",
            "--bind", "0.0.0.0:8000",
            "--workers", "4",
            "--worker-class", "uvicorn.workers.UvicornWorker",
            "--timeout", "120",
            "--keep-alive", "5",
            "--max-requests", "1000",
            "--max-requests-jitter", "100"
        ]
        
        logger.info(f"Starting server with command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Server failed to start: {e}")
        return False
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return True

def main():
    """Main deployment function"""
    logger.info("Starting ProtoTech Backend deployment...")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Run migrations
    if not run_database_migrations():
        sys.exit(1)
    
    # Start server
    if not start_server():
        sys.exit(1)

if __name__ == "__main__":
    main()
