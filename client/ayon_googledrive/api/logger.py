import logging
import os

# Get a logger
log = logging.getLogger("ayon.googledrive")
log.setLevel(logging.DEBUG)  # Ensure logs of all levels are captured

# # Prevent interference from inherited handlers
# log.propagate = False

# Clear existing handlers to avoid duplicates
log.handlers.clear()

# Add file handler
file_path = os.path.join(os.path.expanduser("~"), "ayon_googledrive_debug.log")
file_handler = logging.FileHandler(file_path)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.DEBUG)
log.addHandler(file_handler)

# Optional: Also log to console
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
stream_handler.setLevel(logging.DEBUG)
log.addHandler(stream_handler)