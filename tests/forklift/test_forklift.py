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
import re
import sys
import tempfile
import yaml

import forklift
from forklift.drivers import ip_address
from tests.base import (
    docker,
    parse_environment,
    redirect_stream,
    DOCKER_BASE_IMAGE,
    SaveOutputMixin,
    TestCase,
)


class UsageTestCase(TestCase):
    """
    Test running forklift with no arguments.
    """

    # Do not override any drivers or services
    forklift_class = forklift.Forklift

    def test_usage(self):
        """
        Test usage message with no arguments.
        """
        with tempfile.NamedTemporaryFile() as tmpfile:
            with redirect_stream(tmpfile.file.fileno(), stream=sys.stderr):
                with self.assertRaises(SystemExit):
                    self.run_forklift()

            with open(tmpfile.name) as saved_stderr:
                usage_test = saved_stderr.read()
                self.assertIn("usage: ", usage_test)


class SmokeTestCase(TestCase):
    """
    Test running basic commands.
    """

    def test_commands(self):
        """
        Test running basic commands.
        """

        self.assertEqual(0, self.run_forklift('true'))
        self.assertNotEqual(0, self.run_forklift('false'))


class CommandsMixin(object):
    """
    Mixin with tests to ensure commands are run correctly.
    """

    def run_command(self, *command):
        """
        Run a command in Forklift.

        Override to pass extra options.
        """

        return self.run_forklift(*command)

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

    default_driver = 'direct'


@docker
class DockerCommandsTestCase(CommandsMixin, TestCase):
    """
    Test running commands via Docker.
    """

    default_driver = 'docker'

    def run_command(self, *command):
        """
        Run a command via Docker.
        """

        return self.run_forklift(
            '--rm',
            DOCKER_BASE_IMAGE,
            *command
        )


class CaptureEnvironmentMixin(object):
    """
    Mixin with tests to ensure environment is passed to commands correctly.
    """

    def capture_env(self, *args, prepend_args=None):
        """
        Run Forklift to capture the environment.
        """

        prepend_args = prepend_args or []

        if any(arg.startswith('--') for arg in prepend_args):
            prepend_args.insert(0, '--')

        forklift_args = \
            list(args) + \
            list(prepend_args) + \
            ['/usr/bin/env', '-0']

        self.assertEqual(0, self.run_forklift(*forklift_args))

        return parse_environment(SaveOutputMixin.last_output())

    @contextlib.contextmanager
    def configuration_file(self, configuration):
        """
        Run a command with configuration written to the configuration file.
        """

        with tempfile.NamedTemporaryFile() as conffile:
            self.forklift_class.configuration_file_list.append(conffile.name)
            if isinstance(configuration, str):
                conffile.write(configuration.encode())
            else:
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
        self.assertTrue(re.match(r'^localhost:\d+$', env['SITE_DOMAIN']))

        env = self.capture_env('--serve_port', '9998')
        self.assertEqual(env['SITE_DOMAIN'], 'localhost:9998')

    def test_service_environment(self):
        """
        Test passing service environment to the command.
        """

        with self.configuration_file({'services': ['test']}):
            self.assertEqual(
                self.capture_env()['FOO'],
                '{0}-test_app-2'.format(self.localhost_reference())
            )

            empty_file = \
                """
                # An empty YAML file.
                """
            with self.configuration_file(empty_file):
                self.assertEqual(
                    self.capture_env()['FOO'],
                    '{0}-test_app-2'.format(self.localhost_reference())
                )

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

    def test_nargs(self):
        """
        Test multiple arguments
        """

        with self.configuration_file({
            'services': ['test'],
            'test': {
                'list': ['1', '2'],
            },
        }):
            self.assertEqual(
                self.capture_env()['BAR'],
                '1|2')

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

    default_driver = 'direct'


@docker
class DockerEnvironmentTestCase(CaptureEnvironmentMixin, TestCase):
    """
    Test environment passed to the commands using Docker.
    """

    default_driver = 'docker'

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
