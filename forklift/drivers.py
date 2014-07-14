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
Drivers that can execute applications.
"""


import fcntl
import os
import pwd
import re
import socket
import struct
import subprocess
import sys

# pylint:disable=no-name-in-module,import-error
from distutils.spawn import find_executable
# pylint:enable=no-name-in-module,import-error

import docker

from forklift.base import (
    DEVNULL,
    free_port,
    ImproperlyConfigured,
    wait_for,
    wait_for_parent,
)
from forklift.registry import Registry


register = Registry()  # pylint:disable=invalid-name


class Driver(object):
    """
    A method of executing the application with supplied services.
    """

    def __init__(self, target, services, environment, conf):
        """
        Initialise the driver with the specified target and services.
        """

        self.target = target
        self.services = services
        self.added_environment = environment
        self.conf = conf

    # pylint:disable=unused-argument
    @staticmethod
    def valid_target(target):
        """
        Guess whether a target is valid for the given driver.

        Override to have driver chosen automatically based on target
        given.
        """

        return False

    def run(self, *command):
        """
        Run the command on the target.
        """

        raise NotImplementedError("Please override run().")

    def _run(self, command):
        """
        Run the command AS THE CURRENT PROCESS (you will be replaced).

        We also fork and add the child to its own process group. This means
        that the child will persist after the parent completes and will not
        receive signals (SIGTERM, SIGKILL, SIGSTOP, etc) from the parent
        pgroup, and will also not grab standard input from the parent process.

        When the parent process finishes, we return (in the child process) so
        that the main code path can complete
        """
        child_pid = os.fork()
        if child_pid:
            os.execvp(command[0], command)
        else:
            os.setpgrp()
            wait_for_parent()

    def base_environment(self):
        """
        The service-independent environment to supply to the application.
        """

        return {
            'ENVIRONMENT': 'dev_local',
            'DEVNAME': pwd.getpwuid(os.getuid())[0],
            # TODO: TZ
            'SITE_PROTOCOL': 'http',
            'SITE_DOMAIN': 'localhost:{0}'.format(self.serve_port()),
        }

    def environment(self):
        """
        The environment to supply to the application.
        """

        env = self.base_environment()

        for service in self.services:
            env.update(service.environment())

        env.update(self.added_environment)

        return env

    @staticmethod
    def _free_port():
        """
        Find a free port to serve on.

        Overridden in tests for reproducibility.
        """

        return free_port()

    def serve_port(self):
        """
        The port for application to serve in.

        If not explicitly given in the configuration, pick a free one.
        """

        if self.conf.serve_port:
            return self.conf.serve_port

        # pylint:disable=access-member-before-definition
        # pylint:disable=attribute-defined-outside-init
        if hasattr(self, '_serve_port'):
            return self._serve_port

        self._serve_port = self._free_port()
        return self._serve_port

    @classmethod
    def add_arguments(cls, add_argument):
        """
        Add driver configuration arguments to the parser.
        """

        add_argument('--serve_port', type=int, default=None,
                     help="The port to expose the application on")


def ip_address(ifname):
    """
    Get the IP address associated with an interface.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tmp_socket:
        return socket.inet_ntoa(fcntl.ioctl(
            tmp_socket.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode())
        )[20:24])


@register('docker')
class Docker(Driver):
    """
    Execute the application packaged as a Docker container.
    """

    @classmethod
    def add_arguments(cls, add_argument):
        """
        Add Docker-specific options.
        """

        super().add_arguments(add_argument)

        add_argument('--rm', default=False, action='store_true',
                     help="Remove the container after the command exit")
        add_argument('--privileged', default=False, action='store_true',
                     help="Run the container in privileged mode")
        add_argument('--interactive', default=False, action='store_true',
                     help="Run the command in interactive mode")
        add_argument('--mount-root',
                     help="The directory to bind the root directory of the " +
                     "container to")
        add_argument('--storage',
                     help="The directory to mount under /storage in the " +
                     "container")
        add_argument('--user', default='app',
                     help="The user to set up for SSH in the container")
        add_argument('--host_uid', default=os.getuid(),
                     help="The UID for the user inside the container")
        add_argument('--identity',
                     help="The public key to authorise logging in as")

    def run(self, *command):
        """
        Run the command in Docker container.
        """

        # Check resolv.conf for local nameservers
        with open('/etc/resolv.conf') as rcfile:
            nameservers = [l for l in rcfile.read().splitlines()
                           if 'nameserver' in l and not l.startswith('#')]
            if any('127.0.0.1' in l or '127.0.1.1' in l
                   for l in nameservers):
                print(
                    "/etc/resolv.conf on the host specifies localhost "
                    "as the name server. This will make Docker use Google "
                    "Public DNS inside the container, and accessing Intranet "
                    "resources will fail.\n"
                    "Please fix /etc/resolv.conf on the host before "
                    "continuing.",
                    file=sys.stderr,
                )

        if list(command) == ['sshd']:
            return self.run_sshd()
        else:
            command = self.docker_command(*command)
            return self._run(command)

    def environment(self):
        """
        Change every service's host attribute from localhost.
        """

        for service in self.services:
            if 'host' in service.allow_override:
                if service.host == 'localhost':
                    service.host = ip_address('docker0')

        return super().environment()

    def docker_command(self, *command, use_sshd=False):
        """
        The Docker command to start a container.
        """

        docker_command = [
            'docker', 'run',
            '-p', '{0}:8000'.format(self.serve_port()),
        ]

        if self.conf.rm:
            docker_command += ['--rm']

        if use_sshd:
            docker_command += [
                '-d',
                '-p', '22',
                '--entrypoint=/bin/bash',
                '-u=root',
            ]
        else:
            for key, value in self.environment().items():
                docker_command += ['-e', '{0}={1}'.format(key, value)]

        if self.conf.privileged:
            docker_command += [
                '--privileged',
            ]

        if self.conf.interactive:
            docker_command += [
                '-i', '-t',
            ]

        if self.conf.storage:
            storage = self.conf.storage
            subprocess.check_call(['mkdir', '-p', storage])
            docker_command += [
                '-v', '{0}:/storage'.format(storage),
            ]
        docker_command += [self.target]
        docker_command += command

        return docker_command

    def mount_root(self, container):
        """
        Mount the container's root directory on the host.
        """

        # If requested, mount the working directory
        if self.conf.mount_root:
            mount_root = self.conf.mount_root

            subprocess.call(['sudo', 'umount', mount_root],
                            stderr=DEVNULL)
            subprocess.check_call(['mkdir', '-p', mount_root])

            driver = docker.Client().inspect_container(container)['Driver']
            rootfs_path = \
                '/var/lib/docker/{driver}/mnt/{container}'.format(
                    driver=driver,
                    container=container,
                )

            # AUFS and DeviceMapper use different paths
            if driver == 'devicemapper':
                rootfs_path += '/rootfs'

            subprocess.check_call(['sudo', 'mount', '-o', 'bind',
                                   rootfs_path,
                                   mount_root])
            print("Container filesystem mounted on {mount_root}".format(
                mount_root=mount_root))

    def run_sshd(self):
        """
        Run SSH server in a container.
        """

        # determine the user's SSH key(s)
        identity = None
        if not self.conf.identity:
            # provide the entire set of keys
            # pylint:disable=no-member
            ssh_key = (subprocess
                       .check_output(['ssh-add', '-L'])
                       .decode()
                       .strip())
            if ssh_key == '':
                raise ImproperlyConfigured(
                    "You don't seem to have any SSH keys! "
                    "How do you do any work?")
        else:
            identity = self.conf.identity
            if not os.path.exists(identity):
                identity = os.path.expanduser(
                    '~/.ssh/{}'.format(self.conf.identity))
            with open(identity + '.pub') as id_file:
                ssh_key = id_file.read().strip()

        commands = [
            'DEBIAN_FRONTEND=noninteractive apt-get -qq install dropbear sudo',
        ] + [
            # TODO: this only passes the environment to shells.
            # Commands run directly (ssh ... command) get no environment.
            'echo \'export {0}={1}\' >> /etc/profile'.format(*env)
            for env in self.environment().items()
        ] + [
            '(useradd -m {user} || true)',
            'mkdir -p ~{user}/.ssh',
            'echo \'{ssh_key}\' >> ~{user}/.ssh/authorized_keys',
            'chown -R {user} ~{user}/.ssh',
            'chmod -R go-rwx ~{user}/.ssh',
            'chsh -s /bin/bash {user}',
            'usermod -p zzz {user}',
            'chown -R --from={user} {host_uid} ~{user}',
            'usermod -u {host_uid} {user}',
            'chown {user} ~{user}',
            'chmod go-w ~{user}',
            'echo \'{user} ALL=(ALL) NOPASSWD: ALL\' >> /etc/sudoers',
            'echo Starting SSH...',
            '/usr/sbin/dropbear -F',
        ]

        args = {
            'user': self.conf.user,
            'host_uid': self.conf.host_uid,
            'ssh_key': ssh_key,
        }

        command = self.docker_command(
            '-c',
            ' && '.join(cmd.format(**args) for cmd in commands),
            use_sshd=True
        )
        container = subprocess.check_output(command).decode().strip()
        self.mount_root(container)

        ssh_command, ssh_available = self.ssh_command(container, identity)
        if not ssh_available:
            print("Timed out waiting for SSH setup. You can still try "
                  "the command below but it might also indicate a problem "
                  "with SSH setup.")
        print(ssh_command)

        return 0

    def ssh_command(self, container, identity=None):
        """
        Wait for SSH service to start and print the command to SSH to
        the container.

        Returns a tuple of (command, available), where command is the command
        to run and available is an indication of whether the self-test
        succeeded.
        """

        with docker.Client() as docker_client:
            ssh_port = docker_client.port(container, 22)[0]['HostPort']

        ssh_command = [
            'ssh',
            '{0}@localhost'.format(self.conf.user),
            '-p',
            ssh_port,
            '-A',
        ]

        if identity:
            ssh_command += ('-i', identity)

        available = False
        try:
            available = wait_for(
                lambda: subprocess.check_call(
                    ssh_command + [
                        '-o', 'StrictHostKeyChecking=no',
                        '-o', 'PasswordAuthentication=no',
                        '-o', 'NoHostAuthenticationForLocalhost=yes',
                        '/bin/true',
                    ],
                    stdin=DEVNULL,
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                ) or True,
                expected_exceptions=(subprocess.CalledProcessError,)
            )
        except (subprocess.CalledProcessError, OSError) as ex:
            print(ex)

        return (' '.join(ssh_command), available)


@register('container_recycler')
class ContainerRecycler(Driver):
    """
    Cleans up Docker's mess
    """

    @classmethod
    def add_arguments(cls, add_argument):
        """
        Add recycler-specific options.
        """

        super().add_arguments(add_argument)

        add_argument('--include-running', default=False, action='store_true',
                     help="Remove running containers as well")
        add_argument('--include-tagged', default=False, action='store_true',
                     help="Remove tagged images as well")

    def run(self, *command):
        """
        Recycle old containers and images
        """

        self.recycle_containers(include_running=self.conf.include_running)
        self.recycle_images(include_tagged=self.conf.include_tagged)

    def recycle_containers(self, include_running=False):
        """
        Clean up old stopped (and optionally running) containers
        """
        all_containers = set(
            subprocess.check_output(('docker', 'ps', '-aq'))
            .split()
        )

        running_containers = set(
            subprocess.check_output(('docker', 'ps', '-q'))
            .split()
        )

        if include_running:
            containers = all_containers

        else:
            if running_containers:
                print("You have running containers, pass "
                      "--include-running to remove")

            containers = all_containers - running_containers

        if containers:
            print("Removing old containers...")
            subprocess.check_call(('docker', 'rm', '-f') + tuple(containers))

    def recycle_images(self, include_tagged=False):
        """
        Clean up untagged (and optionally tagged) images
        """
        images = set()
        tagged_images = set()

        output = subprocess.check_output(('docker', 'images'),
                                         universal_newlines=True)
        output = output.strip().split('\n')

        # the first line contains the offsets
        header = output[0]
        remainder = output[1:]

        # calculate the column widths from the header by calculating the
        # offsets of the columns
        columns = [header.index(l)
                   for l in re.split(r'\s\s+', header)] + [len(header)]
        columns = [(a, b) for a, b in zip(columns, columns[1:])]

        for line in remainder:
            repo, tag, image, _, _ = (line[a:b].strip() for a, b in columns)
            images.add(image)

            if repo != '<none>' and tag != '<none>':
                tagged_images.add(image)

        if include_tagged:
            pass

        else:
            if tagged_images:
                print("You have tagged images, pass "
                      "--include-tagged to remove")

            images -= tagged_images

        if images:
            print("Removing old images...")
            subprocess.check_call(('docker', 'rmi') + tuple(images))

    @staticmethod
    def valid_target(target):

        return target == 'recycle'


@register('direct')
class Direct(Driver):
    """
    Execute the application directly.
    """

    def run(self, *command):
        """
        Run the application directly.
        """

        for key, value in self.environment().items():
            os.environ[key] = value

        return self._run([self.target] + list(command))

    @staticmethod
    def valid_target(target):
        """
        Check if the target is directly executable.
        """

        return find_executable(target)
