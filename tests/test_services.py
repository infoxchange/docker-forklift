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

import contextlib
import tempfile
import yaml

from tests.base import (
    docker,
    DOCKER_BASE_IMAGE,
    SaveOutputMixin,
    TestCase,
    TestForklift,
)


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

        self.assertEqual(0, self.run_forklift(DOCKER_BASE_IMAGE, '/bin/true'))
        self.assertNotEqual(0,
                            self.run_forklift(DOCKER_BASE_IMAGE, '/bin/false'))


class CaptureEnvironmentMixin(object):
    """
    Mixin with tests to ensure environment is passed to commands correctly.
    """

    @staticmethod
    def executioner():
        """
        The executioner to use when running the commands.
        """
        raise NotImplementedError("Please override executioner().")

    def capture_env(self, *args, prepend_args=None):
        """
        Run Forklift to capture the environment.
        """

        prepend_args = prepend_args or []

        forklift_args = prepend_args + [
            '--executioner', self.executioner(),
            '/usr/bin/env', '-0',
        ] + list(args)

        self.assertEqual(0, self.run_forklift(*forklift_args))

        output = SaveOutputMixin.next_output().decode()
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
            TestForklift.configuration_files.append(conffile.name)
            yaml.dump(configuration, conffile, encoding='utf-8')

            yield

            TestForklift.configuration_files.pop()

    @staticmethod
    def localhost_reference():
        """
        The local host, as seen from inside the executioner.
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
            self.assertEqual(self.capture_env()['FOO'],
                             '{0}-1-2'.format(self.localhost_reference()))

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
            'environment': {
                'BAR': 'additional',
            },
        }):
            self.assertEqual(self.capture_env()['BAR'], 'additional')


class DirectEnvironmentTestCase(CaptureEnvironmentMixin, TestCase):
    """
    Test that environment is passed to the commands using direct executioner.
    """

    @staticmethod
    def executioner():
        return 'save_output_direct'


@docker
class DockerEnvironmentTestCase(CaptureEnvironmentMixin, TestCase):
    """
    Test environment passed to the commands using Docker.
    """

    @staticmethod
    def executioner():
        return 'save_output_docker'

    @staticmethod
    def localhost_reference():
        # TODO: Can this change?
        return '172.17.42.1'

    def capture_env(self, *args, prepend_args=None):
        """
        Run Forklift to capture the environment.
        """

        prepend_args = prepend_args or []
        prepend_args.append(DOCKER_BASE_IMAGE)

        return super().capture_env(*args, prepend_args=prepend_args)
