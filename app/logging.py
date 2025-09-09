import logging.config
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logging.config.fileConfig("logging.conf")


logger = logging.getLogger()
