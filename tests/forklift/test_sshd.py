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
import subprocess

from tests.base import (
    docker,
    DOCKER_BASE_IMAGE,
    merge_dicts,
    TestCase,
    TestForklift,
)

from forklift.drivers import Docker


class SaveSSHDetailsDocker(Docker):
    """
    Save SSH command the container ran.
    """

    ssh_commands = []

    def ssh_command(self, *args, **kwargs):
        """
        Save the SSH command for later inspection.
        """

        command, available = super().ssh_command(*args, **kwargs)
        self.ssh_commands.append((command, available))
        return command, available

    @classmethod
    def next_ssh_command(cls):
        """
        Return the next (FIFO) SSH command.
        """

        return cls.ssh_commands.pop(0)


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

        os.chmod(self.private_key, 0o600)

        self.assertEqual(0, self.run_forklift(
            '--driver', 'save_ssh_command_docker',
            DOCKER_BASE_IMAGE, 'sshd',
            '--identity', self.private_key,
        ))

        command, available = SaveSSHDetailsDocker.next_ssh_command()

        self.assertTrue(available)
        self.assertEqual(0, subprocess.call(
            command + ' /bin/true',
            shell=True
        ))
