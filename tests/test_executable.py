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
# limitations under the License.3

"""
Test running Forklift executable directly.
"""

import os
import subprocess
import unittest


class ExecutableTest(unittest.TestCase):
    """
    Test running Forklift executable directly.
    """

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return subprocess.call(['./forklift'] + list(args))

    def test_executable(self):
        """
        Test running a command directly.
        """

        self.assertEqual(0, self.run_forklift('/bin/true'))
        self.assertNotEqual(0, self.run_forklift('/bin/false'))
