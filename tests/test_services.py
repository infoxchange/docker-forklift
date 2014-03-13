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

import operator
import os
import subprocess
import unittest

from functools import reduce
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
except (subprocess.CalledProcessError, OSError):
    pass

docker = unittest.skipUnless(DOCKER_AVAILABLE, "Docker is unavailable")


def merge_dicts(*dicts):
    """
    Merge an arbitrary number of dictionaries together.
    """
    return dict(reduce(operator.or_, (d.items() for d in dicts)))


class TestService(forklift.Service):
    """
    A test service.
    """

    def __init__(self, host, one, two):
        self.host = host
        self.one = one
        self.two = two

    allow_overrides = ('host', 'one', 'two')

    is_available = True

    def available(self):
        return self.is_available

    def environment(self):
        return {
            'FOO': '{host}-{one}-{two}'.format(**self.__dict__)
        }


class TestExecutioner(forklift.Executioner):
    """
    Mock some executioner parameters for ease of testing.
    """

    def base_environment(self):
        env = super().base_environment()
        env['DEVNAME'] = 'myself'
        return env

    def serve_port(self):
        return 9999


class SaveOutputDirect(forklift.Direct, TestExecutioner):
    """
    An executioner saving the last run result.
    """

    outputs = []

    @staticmethod
    def valid_target(target):
        return False

    @classmethod
    def next_output(cls):
        return cls.outputs.pop(0)

    def run(self, *command):
        """
        Clean the environment before running the command.
        """

        original_environ = os.environ.copy()
        try:
            os.environ.clear()
            return super().run(*command)
        finally:
            os.environ.update(original_environ)


    def _run(self, command):
        """
        Save the command output.
        """
        output = subprocess.check_output(command)
        self.outputs.append(output)
        # TODO: preserve the exit code if needed
        return 0


class TestForklift(forklift.Forklift):
    """
    Forklift with a test service.
    """

    executioners = merge_dicts({'save_output': SaveOutputDirect},
                               forklift.Forklift.executioners)

    services = merge_dicts({'test': TestService},
                           forklift.Forklift.services)


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return TestForklift(['forklift'] + list(args)).main()


class ReturnCodeTestCase(TestCase):
    """
    Test passing return code from commands.
    """

    def test_direct_run(self):
        """
        Test running a command directly.
        """

        self.assertEqual(0, self.run_forklift('/bin/true'))
        self.assertNotEqual(0, self.run_forklift('/bin/false'))

    @docker
    def test_docker(self):
        """
        Test running a command through Docker.
        """

        self.assertEqual(0, self.run_forklift('ubuntu', '/bin/true'))
        self.assertNotEqual(0, self.run_forklift('ubuntu', '/bin/false'))


class EnvironmentTestCase(TestCase):
    """
    Test that environment is passed to the commands.
    """

    @staticmethod
    def parse_environment(env_output):
        """
        Parse the output of 'env' into a dict.
        """

        return dict(
            item.split('=') for item in env_output.decode().split()
        )


    def test_direct_basic_environment(self):
        """
        Test passing basic environment to the command.
        """

        self.assertEqual(0, self.run_forklift(
            '--executioner', 'save_output',
            '/usr/bin/env'))


        self.assertDictEqual(
            self.parse_environment(SaveOutputDirect.next_output()),
            {
                'DEVNAME': 'myself',
                'ENVIRONMENT': 'dev_local',
                'SITE_PROTOCOL': 'http',
                'SITE_DOMAIN': 'localhost:9999',
            }
        )
