import logging
import inspect
import threading
from functools import wraps
import contextvars

# Define a context variable for depth with a default value of 0
depth_var = contextvars.ContextVar('depth', default=0)


class HCALogger(logging.Logger):
    """
    Custom Logger that automatically handles indentation based on function depth.
    """
    thread_local = threading.local()

    def __init__(self, name):
        super().__init__(name)

        self.thread_local = threading.local()

        # if not hasattr(self.thread_local, 'depth'):
        #     self.thread_local.depth = 0

    def _adjust_message(self, msg):
        """Add indentation based on the current depth."""
        current_depth = depth_var.get()
        indentation = ' ' * (current_depth * 4)  # 4 spaces for each depth level
        return indentation + msg

    def increase_indent(self):
        """Increase the indentation level (used when entering a function)."""
        # self.thread_local.depth += 1
        current_depth = depth_var.get()
        depth_var.set(current_depth + 1)

    def decrease_indent(self):
        """Decrease the indentation level (used when exiting a function)."""
        # self.thread_local.depth = max(self.thread_local.depth - 1, 0)
        current_depth = depth_var.get()
        if current_depth > 0:
            depth_var.set(current_depth - 1)

    # Override the logging methods to apply indentation
    def info(self, msg, *args, **kwargs):
        super().info(self._adjust_message(msg), *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        super().debug(self._adjust_message(msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        super().warning(self._adjust_message(msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        super().error(self._adjust_message(msg), *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        super().exception(self._adjust_message(msg), *args, **kwargs)


    def log_dictionary(self, label, dictionary):
        """Log the key-value pairs of a dictionary."""
        logger.info(f'Contents of the {label} dictionary:')
        for key, value in dictionary.items():
            logger.info("\t%s: %s", key, value)

    def log_list(self, label, list):
        """Log the key-value pairs of a dictionary."""
        logger.info(f'Contents of the {label} list:')
        for value in list:
            logger.info("\t%s", value)


# The decorator to handle logging entry, exit, and indentation
def log_entry_exit(func):
    @wraps(func)  # Ensure the wrapped function retains its original attributes
    def wrapper(*args, **kwargs):
        # Log entry and increase indentation
        logger.info("Entering %s", func.__name__)
        logger.increase_indent()

        result = None
        try:
            result = func(*args, **kwargs)  # Call the actual wrapped function
        finally:
            # Ensure indentation is decreased even if there's an exception
            logger.decrease_indent()
            logger.info("Exiting %s", func.__name__)  

        return result
    return wrapper
    
def setup_logger(name='app_logger', log_file='app.log', level=logging.INFO):

    logging.setLoggerClass(HCALogger)

 # Check if logger class is set properly
    if logging.getLoggerClass() != HCALogger:
        logging.setLoggerClass(HCALogger)

    # Initialize the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    # Check if logger is None (safety check)
    if logger is None:
        raise RuntimeError("Logger not initialized properly")

    # Create and set up a handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(f'%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    return logger

# Initialize the global logger
logger = setup_logger()

