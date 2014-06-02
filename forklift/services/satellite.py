#
# Copyright 2014  Infoxchange Australia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Satellite processes started by Forklift itself to provide services.
"""

import os
from multiprocessing import Process  # pylint:disable=no-name-in-module
from time import sleep
from threading import Thread


def start_satellite(target, args=(), kwargs=None, stop=None):
    """
    Start a process configured to run the target but kill it after the parent
    exits.
    """

    if kwargs is None:
        kwargs = {}

    proc = Process(target=_satellite, args=(target, args, kwargs, stop))
    proc.daemon = True
    proc.start()


def _satellite(target, args, kwargs, stop):
    """
    Run the target, killing it after the parent exits.
    """

    # Run target daemonized.
    payload = Thread(
        target=target,
        args=args,
        kwargs=kwargs,
    )
    payload.daemon = True
    payload.start()

    # Cannot wait for the process that's not our child
    ppid = os.getppid()
    try:
        while True:
            os.kill(ppid, 0)
            sleep(1)
    except OSError:
        if stop:
            stop()
