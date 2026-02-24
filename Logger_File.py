import logging
from logging.handlers import TimedRotatingFileHandler
import os

# <> This is a new thing I am excited to try out. Classes have not been something I have made use of much nor
# have I done anything with logging in this capacity. Hopefully I learn a thing or two <> #
# SOURCE: https://jonathanserrano.medium.com/deal-with-python-logging-the-easy-way-bf7d41bd48f6 #

class Logger:
    def __init__(self, name = 'log', log_level ='DEBUG', 
                 prefix = 'current', log_dir = 'Log_Location'):
        # Create the logger
        self.logger = logging.getLogger(name)

        # Set the severity threshold
        self.logger.setLevel(log_level)

        # Create the rotation period
        handler = TimedRotatingFileHandler(
            os.path.join(log_dir, prefix), when='D', interval=15
        )
    
        # Add the date
        handler.suffix = '%m%d%Y.log'

        # Set Log String Format
        format = logging.Formatter(
            '%(name)-6s %(asctime)s %(levelname)-6s %(message)s'
        )
        handler.setFormatter(format)

        # Handler is now built, add it to the logger
        self.logger.addHandler(handler)
    
    def Get_Logger(self):
        return self.logger