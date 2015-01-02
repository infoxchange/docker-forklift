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
Base utilities for tests.
"""

import contextlib
import operator
import os
import sys
import subprocess
import tempfile
import unittest

from functools import reduce
try:
    from subprocess import DEVNULL  # pylint:disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull)

import forklift
import forklift.drivers
import forklift.services

from forklift.services.base import transient_provider


DOCKER_AVAILABLE = False
try:
    subprocess.check_call(['docker', 'version'],
                          stdout=DEVNULL,
                          stderr=DEVNULL)
    DOCKER_AVAILABLE = True
except (subprocess.CalledProcessError, OSError):
    pass

requires_docker = unittest.skipUnless(  # pylint:disable=invalid-name
    DOCKER_AVAILABLE, "Docker is unavailable")


def docker_image_available(image_name):
    """
    Check whether a Docker image is available.
    """

    import docker
    import requests.exceptions

    try:
        with docker.Client() as client:
            client.inspect_image(image_name)
        return True
    except (docker.errors.APIError, requests.exceptions.ConnectionError):
        return False


def requires_docker_image(image_name):
    """
    Mark a test as requiring a Docker image to run.
    """

    return unittest.skipUnless(
        docker_image_available(image_name),
        "Docker image {0} is required.".format(image_name)
    )


DOCKER_BASE_IMAGE = 'debian:wheezy'


def merge_dicts(*dicts):
    """
    Merge an arbitrary number of dictionaries together.
    """
    return dict(reduce(operator.or_, (d.items() for d in dicts)))


class TestService(forklift.services.Service):
    """
    A test service.
    """

    def __init__(self, host=None, one=None, two=None, list_=None):
        self.host = host
        self.one = one
        self.two = two
        self.list = list_ or []

    allow_override = ('host', 'one', 'two')
    allow_override_list = ('list',)

    def check_available(self):
        return True

    def environment(self):
        return {
            'FOO': '{host}-{one}-{two}'.format(**self.__dict__),
            'BAR': '|'.join(self.list),
        }

    providers = ('here', 'here_occasionally')

    @classmethod
    def here(cls, application_id):
        """
        A sample provider.
        """
        return cls('localhost', application_id, '2')

    @classmethod
    @transient_provider
    def here_occasionally(cls, application_id):
        """
        A sample transient provider.
        """
        return cls(None, application_id, '2')


class TestDriver(forklift.drivers.Driver):
    """
    Mock some driver parameters for ease of testing.
    """

    def base_environment(self):
        env = super().base_environment()
        env['DEVNAME'] = 'myself'
        return env


class SaveOutputMixin(forklift.drivers.Driver):
    """
    A mixin to drivers to examine the commands output.
    """

    _last_output = [None]

    @classmethod
    def last_output(cls):
        """
        Return the output of the last command.
        """
        return cls._last_output[0]

    def _run(self, command):
        """
        Run the command, saving the output.
        """

        with tempfile.NamedTemporaryFile() as tmpfile:
            with redirect_stream(tmpfile.file.fileno()):
                pid = os.fork()
                assert pid >= 0
                if pid == 0:
                    super()._run(command)

                    # We MUST exit here, or the test suite will continue to
                    # run in the child process.
                    # Also must be os._exit rather than sys.exit because this
                    # is a child process so should not clean up/etc
                    os._exit(0)  # pylint:disable=protected-access
                else:
                    _, status = os.waitpid(pid, 0)
                    retcode = status >> 8

                    with open(tmpfile.name) as saved_output:
                        self._last_output[0] = saved_output.read()

                    return retcode


class SaveOutputDirect(SaveOutputMixin, TestDriver, forklift.drivers.Direct):
    """
    A direct driver augmented for testing.
    """

    pass


class SaveOutputDocker(SaveOutputMixin, TestDriver, forklift.drivers.Docker):
    """
    A Docker driver augmented for testing.
    """

    pass


class TestForklift(forklift.Forklift):
    """
    Forklift with a test service.
    """

    drivers = {
        # Drivers MUST always inherit from SaveOutputMixin. See the comment in
        # the fork code of _run there for reasoning
        'direct': SaveOutputDirect,
        'docker': SaveOutputDocker,
    }

    def get_driver(self, conf):
        """
        Use the driver specified in a test as default.
        """

        return getattr(self, '_driver', None) \
            or super().get_driver(conf)

    @contextlib.contextmanager
    def set_driver(self, driver):
        """
        Set the default driver to use in context.
        """

        setattr(self, '_driver', driver)

        try:
            yield
        finally:
            delattr(self, '_driver')

    services = merge_dicts({'test': TestService},
                           forklift.Forklift.services)

    configuration_file_list = []

    def configuration_files(self, conf):
        """
        Override the configuration files.
        """
        return self.configuration_file_list

    def implicit_configuration(self):
        """
        Override application ID.
        """
        return [
            '--application_id', 'test_app',
        ]


class TestCase(unittest.TestCase):
    """
    Base test case.
    """

    forklift_class = TestForklift

    default_driver = None

    def run_forklift(self, *args):
        """
        Run Forklift with specified arguments.
        """

        instance = self.forklift_class(['forklift'] + list(args))
        if self.default_driver:
            with instance.set_driver(self.default_driver):
                return instance.main()
        else:
            return instance.main()


@contextlib.contextmanager
def redirect_stream(target_fd, stream=None):
    """
    Redirect the standard output to the target, including from child processes.

    If 'stream' is specified, redirect that stream instead (e.g. sys.stderr).
    """

    stream = stream or sys.stdout

    stream_fileno = stream.fileno()
    saved_stream = os.dup(stream_fileno)
    os.close(stream_fileno)
    os.dup2(target_fd, stream_fileno)

    yield

    os.close(stream_fileno)
    os.dup2(saved_stream, stream_fileno)


def parse_environment(env_string):
    """
    Parse the output of 'env -0' into a dictionary.
    """

    if type(env_string) is bytes:
        env_string = env_string.decode()

    return dict(
        item.split('=', 1)
        for item in env_string.rstrip('\0').split('\0')
    )
