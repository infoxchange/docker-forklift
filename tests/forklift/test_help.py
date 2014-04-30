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

import io
import tempfile

from tests.base import (
    TestCase,
    TestForklift,
    redirect_stream,
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
            with redirect_stream(tmpfile.file.fileno()):
                self.run_forklift('help')

            with open(tmpfile.name) as saved_output:
                help_text = saved_output.read()
                help_text = help_text.replace('()', '').strip()
                self.assertEqual("Help yourself.", help_text)
