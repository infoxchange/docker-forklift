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
Tests for miscellaneous utilities
"""

import multiprocessing as mp
import os
import threading
import time
import unittest

from forklift.base import wait_for_pid


# multiprocessing has a LOT of no-member issues
# pylint:disable=no-member


def wait_thread(pid, lock):
    """
    Lock, wait for pid, unlock
    """
    lock.acquire()
    wait_for_pid(pid)
    lock.release()


class WaitForPidTestCase(unittest.TestCase):
    """
    Tests for the wait_for_pid function
    """

    def test_wait_for_child(self):
        """
        Test for wait_for_pid when the pid we are waiting on is a forked
        child
        """
        waiting = mp.Lock()

        proc = mp.Process(target=time.sleep, args=(1000,))
        proc.start()

        thread = threading.Thread(target=wait_thread,
                                  args=(proc.pid, waiting))
        thread.start()

        time.sleep(1)
        self.assertFalse(waiting.acquire(False))

        proc.terminate()
        time.sleep(2)
        self.assertTrue(waiting.acquire(False))

    def test_wait_for_parent(self):
        """
        Test for wait_for_pid when the pid we are waiting on is the waiting
        forks parent
        """
        def parent_proc(lock):
            """
            Start a process to wait on this one then sleep
            """
            child = mp.Process(target=wait_thread,
                               args=(os.getpid(), lock))
            child.start()
            time.sleep(1000)

        waiting = mp.Lock()
        proc = mp.Process(target=parent_proc,
                          args=(waiting,))

        proc.start()

        time.sleep(1)
        self.assertFalse(waiting.acquire(False))

        proc.terminate()
        time.sleep(2)
        self.assertTrue(waiting.acquire(False))
