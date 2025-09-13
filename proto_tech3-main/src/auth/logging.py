
import logging.config
import os

os.makedirs("log",exist_ok=True)
logging.config.fileConfig("logging.conf")


logger = logging.getLogger()

