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
Test SSH daemon setup.
"""

import subprocess

from tests.base import (
    docker,
    DOCKER_BASE_IMAGE,
    merge_dicts,
    TestCase,
    TestForklift,
)

import forklift


class SaveSSHDetailsDocker(forklift.Docker):
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

    executioners = merge_dicts({
        'save_ssh_command_docker': SaveSSHDetailsDocker,
    }, TestForklift.executioners)


@docker
class SSHTestCase(TestCase):
    """
    Test setting up an SSH daemon via Docker.
    """

    forklift_class = SSHTestForklift

    def test_sshd(self):
        """
        Test setting up an SSH daemon.
        """

        self.assertEqual(0, self.run_forklift(
            '--executioner', 'save_ssh_command_docker',
            '--rm',
            DOCKER_BASE_IMAGE, 'sshd',
            '--identity', 'tests/test_id_rsa',
        ))

        command, available = SaveSSHDetailsDocker.next_ssh_command()

        self.assertTrue(available)
        self.assertEqual(0, subprocess.call(
            command + ' /bin/true',
            shell=True
        ))