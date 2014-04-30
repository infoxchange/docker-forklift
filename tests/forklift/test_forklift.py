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
Tests for Forklift.
"""

import contextlib
import tempfile
import yaml

from forklift.drivers import ip_address
from tests.base import (
    docker,
    DOCKER_BASE_IMAGE,
    SaveOutputMixin,
    TestCase,
)


class CommandsMixin(object):
    """
    Mixin with tests to ensure commands are run correctly.
    """

    def run_command(self, *command):
        """
        Run a command in Forklift.

        Override to pass extra options.
        """

        return self.run_forklift('--driver', 'save_output_direct',
                                 *command)

    def test_exit_code(self):
        """
        Test command exit codes.
        """

        self.assertEqual(0, self.run_command('/bin/true'))
        self.assertNotEqual(0, self.run_command('/bin/false'))

    def test_output(self):
        """
        Test echoing things.
        """

        self.assertEqual(0, self.run_command('/bin/echo', 'apple', 'orange'))
        self.assertEqual('apple orange\n', SaveOutputMixin.last_output())

        self.assertEqual(
            0,
            self.run_command('--', '/bin/echo', '--apple', '--orange')
        )
        self.assertEqual('--apple --orange\n', SaveOutputMixin.last_output())


class DirectCommandsTestCase(CommandsMixin, TestCase):
    """
    Test running commands directly.
    """

    pass


@docker
class DockerCommandsTestCase(CommandsMixin, TestCase):
    """
    Test running commands via Docker.
    """

    def run_command(self, *command):
        """
        Run a command via Docker.
        """

        return self.run_forklift(
            '--driver', 'save_output_docker',
            '--rm',
            DOCKER_BASE_IMAGE,
            *command
        )


class CaptureEnvironmentMixin(object):
    """
    Mixin with tests to ensure environment is passed to commands correctly.
    """

    @staticmethod
    def driver():
        """
        The driver to use when running the commands.
        """
        raise NotImplementedError("Please override driver().")

    def capture_env(self, *args, prepend_args=None):
        """
        Run Forklift to capture the environment.
        """

        prepend_args = prepend_args or []

        forklift_args = [
            '--driver', self.driver(),
        ] + list(args) + [
            '--',
        ] + list(prepend_args) + [
            '/usr/bin/env', '-0',
        ]

        self.assertEqual(0, self.run_forklift(*forklift_args))

        output = SaveOutputMixin.last_output()
        return dict(
            item.split('=', 1)
            for item in output.rstrip('\0').split('\0')
        )

    @contextlib.contextmanager
    def configuration_file(self, configuration):
        """
        Run a command with configuration written to the configuration file.
        """

        with tempfile.NamedTemporaryFile() as conffile:
            self.forklift_class.configuration_file_list.append(conffile.name)
            yaml.dump(configuration, conffile, encoding='utf-8')

            try:
                yield
            finally:
                self.forklift_class.configuration_file_list.pop()

    @staticmethod
    def localhost_reference():
        """
        The local host, as seen from inside the driver.
        """
        return 'localhost'

    def test_basic_environment(self):
        """
        Test passing basic environment to the command.
        """

        env = self.capture_env()
        self.assertEqual(env['DEVNAME'], 'myself')
        self.assertEqual(env['ENVIRONMENT'], 'dev_local')
        self.assertEqual(env['SITE_PROTOCOL'], 'http')
        self.assertEqual(env['SITE_DOMAIN'], 'localhost:9999')

    def test_service_environment(self):
        """
        Test passing service environment to the command.
        """

        with self.configuration_file({'services': ['test']}):
            self.assertEqual(
                self.capture_env()['FOO'],
                '{0}-test_app-2'.format(self.localhost_reference()))

        with self.configuration_file({
            'services': ['test'],
            'test': {
                'one': '111',
            },
        }):
            self.assertEqual(self.capture_env()['FOO'],
                             '{0}-111-2'.format(self.localhost_reference()))

            with self.configuration_file({
                'test': {
                    'two': '222',
                },
            }):
                self.assertEqual(
                    self.capture_env()['FOO'],
                    '{0}-111-222'.format(self.localhost_reference()))

                self.assertEqual(
                    self.capture_env('--test.host', 'otherhost')['FOO'],
                    'otherhost-111-222'
                )

    def test_added_environment(self):
        """
        Test passing additional environment to the command.
        """

        with self.configuration_file({
            'environment': [
                'BAR=additional',
            ],
        }):
            self.assertEqual(self.capture_env()['BAR'], 'additional')

        # Environment can be passed as a hash
        with self.configuration_file({
            'environment': {
                'BAR': 'additional',
            },
        }):
            self.assertEqual(self.capture_env()['BAR'], 'additional')


class DirectEnvironmentTestCase(CaptureEnvironmentMixin, TestCase):
    """
    Test that environment is passed to the commands using direct driver.
    """

    @staticmethod
    def driver():
        return 'save_output_direct'


@docker
class DockerEnvironmentTestCase(CaptureEnvironmentMixin, TestCase):
    """
    Test environment passed to the commands using Docker.
    """

    @staticmethod
    def driver():
        return 'save_output_docker'

    @staticmethod
    def localhost_reference():
        # TODO: Can this change?
        return ip_address('docker0')

    def capture_env(self, *args, prepend_args=None):
        """
        Run Forklift to capture the environment.
        """

        prepend_args = prepend_args or []
        prepend_args.append(DOCKER_BASE_IMAGE)

        args = ['--rm'] + list(args)

        return super().capture_env(*args, prepend_args=prepend_args)