# -*- coding: utf-8 -*-

# Copyright (c) 2019, Pamela D McA'Nulty

"""Top-level package for Multiprocessing Tools."""

__author__ = """Pamela D McA'Nulty"""
__email__ = "pamela@mcanulty.org"
__version__ = "0.2.0"

from mptools._mptools import (
    EventMessage,
    MainContext,
    MPQueue,
    Proc,
    ProcWorker,
    QueueProcWorker,
    SignalObject,
    TerminateInterrupt,
    TimerProcWorker,
    _sleep_secs,
    default_signal_handler,
    init_signal,
    init_signals,
    proc_worker_wrapper,
)

__all__ = [
    "MPQueue",
    "_sleep_secs",
    "SignalObject",
    "init_signal",
    "init_signals",
    "default_signal_handler",
    "ProcWorker",
    "proc_worker_wrapper",
    "TimerProcWorker",
    "QueueProcWorker",
    "Proc",
    "EventMessage",
    "MainContext",
    "TerminateInterrupt",
]
