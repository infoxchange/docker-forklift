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

import psutil

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


def wait_for_parent():
    """
    Use wait_for_pid to wait for your parent process
    """
    wait_for_pid(os.getppid())


def wait_for_pid(pid):
    """
    Wait for a given PID in the best way possible. If PID is a child, we use
    os.waitpid. Otherwise, we fall back to a polling approach.
    """
    try:
        # Try to wait for a child
        os.waitpid(pid, 0)
    except OSError:
        # Fallback to polling process status
        try:
            proc = psutil.Process(pid)
            while proc.status() not in ('zombie', 'dead'):
                time.sleep(1)
        except psutil.NoSuchProcess:
            pass


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


def rm_tree_root_owned(path):
    """
    Do an equivalent of shutil.rmtree, but as root
    """
    subprocess.check_call(['sudo', 'rm', '-rf', path])


class ImproperlyConfigured(Exception):
    """
    The host is not properly configured for running Docker.
    """

    pass

try:
    DEVNULL = subprocess.DEVNULL  # pylint:disable=no-member
except AttributeError:
    DEVNULL = open(os.devnull)
