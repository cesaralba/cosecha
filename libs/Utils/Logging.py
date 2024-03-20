import logging

DEFAULTLEVEL = logging.WARNING
DEFAULTLOGFORMAT = (
    '%(asctime)s [%(process)d:%(threadName)10s@%(name)s %(levelname)s %(relativeCreated)14dms]:%(pathname)s@%('
    'lineno)d %(message)s')


def prepareLogger(logger: logging.Logger, level=DEFAULTLEVEL, logformat=DEFAULTLOGFORMAT, handler=None):
    logger.setLevel(level)
    formatter = logging.Formatter(logformat)
    ch = handler or logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
