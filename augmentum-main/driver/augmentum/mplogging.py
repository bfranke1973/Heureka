# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import datetime
import logging
from logging import handlers

from mptools import MPQueue, QueueProcWorker

# Logging for multiprocessing Adapted from: https://fanchenbao.medium.com/python3-logging-with-multiprocessing-f51f460b8778


def parse_log_level(log_level):
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s" % log_level)

    return numeric_level


class DeltaTimeFormatter(logging.Formatter):
    """Log output formatter using elapsed time since start"""

    def format(self, record):
        duration = datetime.datetime.utcfromtimestamp(record.relativeCreated / 1000)
        record.delta = duration.strftime("%H:%M:%S.%f")[0:-3]
        return super().format(record)


class LogListener(QueueProcWorker):
    """
    This log listener receives log messages from running
    processes and funnels them into a single output.
    """

    def init_args(self, args):
        (
            self.work_q,
            self.log_file,
            self.log_level,
        ) = args

    def startup(self):
        root = logging.getLogger()
        file_handler = handlers.RotatingFileHandler(self.log_file)
        console_handler = logging.StreamHandler()
        LOGFORMAT = "+%(delta)s - %(asctime)s %(processName)-12s %(name)-25s %(levelname)-8s %(message)s"
        formatter = DeltaTimeFormatter(LOGFORMAT)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.addHandler(console_handler)
        root.setLevel(parse_log_level(self.log_level))

        # set log level for asyncio
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    def shutdown(self):
        pass

    def main_loop(self):
        while not self.shutdown_event.is_set():
            item = self.work_q.safe_get()
            if not item:
                continue
            if item == "END":
                break
            else:
                self.main_func(item)

    def main_func(self, record):
        logger = logging.getLogger(record.name)
        logger.handle(record)


def configure_root_logging(queue: MPQueue, log_level):
    h = handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(parse_log_level(log_level))
