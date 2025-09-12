import logging

logger = logging.getLogger("poselib")
logger.setLevel(logging.INFO)

if not len(logger.handlers):
    formatter = logging.Formatter(
        fmt="%(asctime)-15s - %(levelname)s - %(module)s - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("logger initialized")
