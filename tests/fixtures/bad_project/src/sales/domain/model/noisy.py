from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def announce() -> None:
    logger.info("something happened")
