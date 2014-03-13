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
Tests for Forklift.
"""

import os
import subprocess
import unittest

try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open(os.devnull)

import forklift


DOCKER_AVAILABLE = False
try:
    subprocess.check_call(['docker', 'version'],
                          stdout=DEVNULL,
                          stderr=DEVNULL)
    DOCKER_AVAILABLE = True
except (subprocess.CalledProcessError, FileNotFoundError):
    pass

docker = unittest.skipUnless(DOCKER_AVAILABLE, "Docker is unavailable")


class TestService(forklift.Service):
    """
    A test service.
    """

    pass


class TestForklift(forklift.Forklift):
    """
    Forklift with a test service.
    """

    services = dict(list(forklift.Forklift.services.items()) + list({
        'test': TestService,
    }.items()))


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return TestForklift(['forklift'] + list(args)).main()

    def test_direct_run(self):
        """
        Test running a command directly.
        """

        self.assertEqual(0, self.run_forklift('/bin/true'))
        self.assertNotEqual(0, self.run_forklift('/bin/false'))
