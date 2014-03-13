"""
Tests for Forklift.
"""

import os
import subprocess
import unittest

from functools import wraps
try:
    from subprocess import DEVNULL
except AttributeError:
    DEVNULL = open(os.devnull)


DOCKER_AVAILABLE = False
try:
    subprocess.check_call(['docker', 'version'],
                          stdout=DEVNULL,
                          stderr=DEVNULL)
    DOCKER_AVAILABLE = True
except (subprocess.CalledProcessError, FileNotFoundError):
    pass

docker = unittest.skipUnless(DOCKER_AVAILABLE, "Docker is unavailable")


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return subprocess.call(['./forklift'] + list(args))

    def assert_forklift_success(self, *args):
        """
        Run Forklift and check the result.
        """

        self.assertEqual(0, self.run_forklift(*args))


class BasicTestCase(TestCase):
    """
    Test basic functionality.
    """

    def test_direct_run(self):
        """
        Test running a command directly.
        """

        self.assert_forklift_success('--executioner', 'direct', '/bin/true')
        self.assertNotEqual(
            0, self.run_forklift('--executioner', 'direct', '/bin/false'))

    @docker
    def test_docker_run(self):
        """
        Test running a command via Docker.
        """

        self.assert_forklift_success('ubuntu', '/bin/true')
