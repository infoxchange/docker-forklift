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
Base utilities for tests.
"""

import operator
import os
import subprocess
import unittest

from functools import reduce
try:
    from subprocess import DEVNULL  # pylint:disable=no-name-in-module
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

docker = unittest.skipUnless(  # pylint:disable=invalid-name
    DOCKER_AVAILABLE, "Docker is unavailable")


DOCKER_BASE_IMAGE = 'debian:wheezy'


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

    allow_override = ('host', 'one', 'two')

    is_available = True

    def available(self):
        return self.is_available

    def environment(self):
        return {
            'FOO': '{host}-{one}-{two}'.format(**self.__dict__)
        }

    providers = ('here',)

    @classmethod
    def here(cls):
        """
        A sample provider.
        """
        return cls('localhost', '1', '2')


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

    @staticmethod
    def valid_target(target):
        return False


class SaveOutputMixin(forklift.Executioner):
    """
    A mixin to executioners to examine the commands output.
    """

    outputs = []

    @classmethod
    def next_output(cls):
        """
        Return and discard the next recorded output.
        """
        return cls.outputs.pop(0)

    def _run(self, command):
        """
        Save the command output.
        """
        output = subprocess.check_output(command)
        self.outputs.append(output)
        # TODO: preserve the exit code if needed
        return 0


class SaveOutputDirect(SaveOutputMixin, TestExecutioner, forklift.Direct):
    """
    A direct executioner augmented for testing.
    """

    pass


class SaveOutputDocker(SaveOutputMixin, TestExecutioner, forklift.Docker):
    """
    A Docker executioner augmented for testing.
    """

    pass


class TestForklift(forklift.Forklift):
    """
    Forklift with a test service.
    """

    executioners = merge_dicts({
        'save_output_direct': SaveOutputDirect,
        'save_output_docker': SaveOutputDocker,
    }, forklift.Forklift.executioners)

    services = merge_dicts({'test': TestService},
                           forklift.Forklift.services)

    configuration_files = []


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    forklift_class = TestForklift

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        return self.forklift_class(['forklift'] + list(args)).main()
