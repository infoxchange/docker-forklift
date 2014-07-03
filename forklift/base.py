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
import subprocess
import tempfile
import time

from contextlib import contextmanager


def free_port():
    """
    Find a free TCP port.
    """

    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


def wait_for(func, expected_exceptions=(), retries=60):
    """
    Wait for a function to return a truthy value, possibly ignoring some
    exceptions if they are raised until the very last retry

    Parameters:
        func - the function to continually call until truthy
        expected_exceptions - list of exceptions to ignore, unless the final
            retry is reached (then any exceptions are reraised)
        retries - number of times to retry before giving up

    Return value:
        The return value of func the last time it was run
    """

    retries = int(retries)
    for retry in range(1, retries + 1):
        try:
            return_value = func()
            if return_value:
                break

        except expected_exceptions:
            if retry == retries:
                raise
            else:
                pass

        time.sleep(1)

    return return_value


@contextmanager
def open_root_owned(source, *args, **kwargs):
    """
    Copy a file as root, open it for writing, then copy it back as root again
    when done
    """
    with tempfile.NamedTemporaryFile(*args, **kwargs) as dest_fh:
        if os.path.isfile(source):
            subprocess.check_call(['sudo', 'cp', source, dest_fh.name])
        yield dest_fh
        subprocess.check_call(['sudo', 'cp', dest_fh.name, source])


class ImproperlyConfigured(Exception):
    """
    The host is not properly configured for running Docker.
    """

    pass

try:
    DEVNULL = subprocess.DEVNULL  # pylint:disable=no-member
except AttributeError:
    DEVNULL = open(os.devnull)
