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
Common declarations.
"""

import os
import socket
import time


def free_port():
    """
    Find a free TCP port.
    """

    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


def wait_for(func, allowed_exceptions=(), timeout=60):
    """
    Wait for a function to return a truthy value, possibly ignoring some
    exceptions if they are to occur

    Parameters:
        func - the function to continually call until truthy
        allowed_exceptions - list of exceptions to ignore
        timeout - the minimum time to try for (NOTE: this is not a maximum)

    Return value:
        True if the function returned a truthy value within the timout, False
        if the timout occurred before a truthy value was returned
    """

    timeout = int(timeout)
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if func():
                return True
        except allowed_exceptions:
            pass

        time.sleep(1)

    return False


class ImproperlyConfigured(Exception):
    """
    The host is not properly configured for running Docker.
    """

    pass

try:
    import subprocess
    DEVNULL = subprocess.DEVNULL  # pylint:disable=no-member
except AttributeError:
    DEVNULL = open(os.devnull)
