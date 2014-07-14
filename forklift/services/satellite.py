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
from threading import Thread

from forklift.base import wait_for_parent


def start_satellite(target, args=(), kwargs=None, stop=None):
    """
    Start a process configured to run the target but kill it after the parent
    exits.
    """

    if kwargs is None:
        kwargs = {}

    child_pid = os.fork()
    if not child_pid:
        # Make sure signals sent by the shell aren't propagated to the
        # satellite
        os.setpgrp()
        _satellite(target, args, kwargs, stop)


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

    wait_for_parent()
    exit_status = stop() if stop is not None else None
    if exit_status is None:
        exit_status = 0

    # This is in a child process, so exit without additional cleanup
    os._exit(exit_status)  # pylint:disable=protected-access
