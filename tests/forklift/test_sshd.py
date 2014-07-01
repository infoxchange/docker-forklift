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
Test SSH daemon setup.
"""

import os
import re
import subprocess

from tests.base import (
    docker,
    DOCKER_BASE_IMAGE,
    merge_dicts,
    parse_environment,
    TestCase,
    TestDriver,
    TestForklift,
)

from forklift.base import DEVNULL
from forklift.drivers import Docker


class SaveSSHDetailsDocker(TestDriver, Docker):
    """
    Save SSH command the container ran.
    """

    log = []

    def ssh_command(self, container, identity=None):
        """
        Save the SSH command for later inspection.
        """

        command, available = super().ssh_command(container, identity=identity)
        self.log.append((command, available, container))
        return command, available

    @classmethod
    def last_details(cls):
        """
        Return the next (FIFO) SSH command.
        """

        return cls.log.pop(0)


class SSHTestForklift(TestForklift):
    """
    Test Forklift saving SSH commands.
    """

    drivers = merge_dicts({
        'save_ssh_command_docker': SaveSSHDetailsDocker,
    }, TestForklift.drivers)


@docker
class SSHTestCase(TestCase):
    """
    Test setting up an SSH daemon via Docker.
    """

    private_key = 'tests/test_id_rsa'

    forklift_class = SSHTestForklift

    def test_sshd(self):
        """
        Test setting up an SSH daemon.
        """

        container = None
        try:
            os.chmod(self.private_key, 0o600)

            self.assertEqual(0, self.run_forklift(
                '--driver', 'save_ssh_command_docker',
                DOCKER_BASE_IMAGE, 'sshd',
                '--identity', self.private_key,
            ))

            command, available, container = SaveSSHDetailsDocker.last_details()

            def in_container(inside_command):
                """
                Command line to execute a command inside the container
                via SSH.
                """

                # TODO: run commands directly when environment is passed
                # properly.
                return "echo '{0}' | ".format(inside_command) + \
                    command + \
                    ' -T' + \
                    ' -o NoHostAuthenticationForLocalhost=yes' + \
                    ' -o PasswordAuthentication=no'

            self.assertTrue(available)
            self.assertEqual(
                subprocess.call(in_container('/bin/true'), shell=True),
                0
            )

            ssh_env = parse_environment(
                subprocess.check_output(in_container('/usr/bin/env -0'),
                                        shell=True),
            )

            self.assertEqual(ssh_env['DEVNAME'], 'myself')
            self.assertEqual(ssh_env['ENVIRONMENT'], 'dev_local')
            self.assertEqual(ssh_env['SITE_PROTOCOL'], 'http')
            self.assertTrue(
                re.match(r'^localhost:\d+$', ssh_env['SITE_DOMAIN']))

        finally:
            # Kill and remove the started container
            if container is not None:
                for action in ('stop', 'rm'):
                    subprocess.check_call(
                        ('docker', action, container),
                        stdout=DEVNULL,
                    )
