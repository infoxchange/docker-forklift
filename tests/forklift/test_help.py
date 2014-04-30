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
Tests for help invocation.
"""

import contextlib
import io
import os
import sys
import tempfile

from tests.base import (
    TestCase,
    TestForklift,
)


class HelpTestForklift(TestForklift):
    """
    Mock _readme_stream for tests.
    """

    @staticmethod
    def _readme_stream():
        """
        Dummy stream.
        """

        return io.BytesIO("Help yourself.".encode())


@contextlib.contextmanager
def redirect_stdout_fd(target_fd):
    """
    Redirect the standard output to the target, including from child processes.
    """

    stdout_fileno = sys.stdout.fileno()
    saved_stdout = os.dup(stdout_fileno)
    os.close(stdout_fileno)
    os.dup2(target_fd, stdout_fileno)

    yield

    os.close(stdout_fileno)
    os.dup2(saved_stdout, stdout_fileno)


class HelpTestCase(TestCase):
    """
    Test help invocation.
    """

    forklift_class = HelpTestForklift

    def test_help(self):
        """
        Test help invocation.
        """

        with tempfile.NamedTemporaryFile() as tmpfile:
            with redirect_stdout_fd(tmpfile.file.fileno()):
                self.run_forklift('help')

            with open(tmpfile.name) as saved_output:
                help_text = saved_output.read()
                help_text = help_text.replace('()', '').strip()
                self.assertEqual("Help yourself.", help_text)
