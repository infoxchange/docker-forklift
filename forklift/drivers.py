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


import json
import os
import pwd
import subprocess
import time

from forklift.base import DEVNULL, free_port, ImproperlyConfigured


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
        Execute a command on the OS.

        A hook point for overriding in tests.
        """
        return subprocess.call(command)

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

    def serve_port(self):
        """
        Find a free port to serve on.
        """

        if 'serve_port' in self.conf:
            return self.conf['serve_port']

        # pylint:disable=access-member-before-definition
        # pylint:disable=attribute-defined-outside-init
        if hasattr(self, '_serve_port'):
            return self._serve_port

        self._serve_port = free_port()
        return self._serve_port

    def print_url(self):
        """
        Print the URL the container is accessible on.
        """

        print('http://localhost:{0}'.format(self.serve_port()))


class Docker(Driver):
    """
    Execute the application packaged as a Docker container.
    """

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
                raise ImproperlyConfigured(
                    "/etc/resolv.conf on the host specifies localhost "
                    "as the name server. This will make Docker use Google "
                    "Public DNS inside the container, and using apt-get "
                    "on Infoxchange images will fail.\n"
                    "Please fix /etc/resolv.conf on the host before "
                    "continuing."
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
                    service.host = '172.17.42.1'

        return super().environment()

    def docker_command(self, *command, use_sshd=False):
        """
        The Docker command to start a container.
        """

        docker_command = [
            'docker', 'run',
            '-p', '{0}:8000'.format(self.serve_port()),
        ]
        if self.conf.get('rm'):
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
        if self.conf.get('privileged'):
            docker_command += [
                '--privileged',
            ]
        if self.conf.get('interactive'):
            docker_command += [
                '-i', '-t',
            ]
        if self.conf.get('storage'):
            subprocess.check_call(['mkdir', '-p', self.conf['storage']])
            docker_command += [
                '-v', '{storage}:/storage'.format(self.conf),
            ]
        docker_command += [self.target]
        docker_command += command

        return docker_command

    @staticmethod
    def container_details(container):
        """
        Get the details of a container.
        """
        return json.loads(
            # pylint:disable=no-member
            subprocess.check_output(
                ['docker', 'inspect', container]
            ).decode()
        )[0]

    def mount_root(self, container):
        """
        Mount the container's root directory on the host.
        """

        # If requested, mount the working directory
        if self.conf.get('mount-root'):
            mount_root = self.conf['mount-root']

            subprocess.call(['sudo', 'umount', mount_root],
                            stderr=DEVNULL)
            subprocess.check_call(['mkdir', '-p', mount_root])

            driver = self.container_details(container)['Driver']
            rootfs_path = \
                '/var/lib/docker/{driver}/mnt/{container}'.format(
                    driver=driver,
                    container=container.decode(),
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
        if 'identity' not in self.conf:
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
            identity = self.conf['identity']
            if not os.path.exists(identity):
                identity = os.path.expanduser(
                    '~/.ssh/{}'.format(self.conf['identity']))
            with open(identity + '.pub') as id_file:
                ssh_key = id_file.read().strip()

        commands = [
            'DEBIAN_FRONTEND=noninteractive apt-get -qq install ssh sudo',
            'invoke-rc.d ssh stop',
            ('echo \'AuthorizedKeysFile /etc/ssh/%u/authorized_keys\' >> ' +
                '/etc/ssh/sshd_config'),
            'echo \'PermitUserEnvironment yes\' >> /etc/ssh/sshd_config',
        ] + [
            'echo \'{0}={1}\' >> /etc/environment'.format(*env)
            for env in self.environment().items()
        ] + [
            '(useradd -m {user} || true)',
            'mkdir -p /etc/ssh/{user}',
            'echo \'{ssh_key}\' > /etc/ssh/{user}/authorized_keys',
            'chsh -s /bin/bash {user}',
            'usermod -p zzz {user}',
            'chown -R --from={user} {host_uid} ~app',
            'usermod -u {host_uid} {user}',
            'chown -R {user} /etc/ssh/{user}',
            'chmod -R go-rwx /etc/ssh/{user}',
            'echo \'{user} ALL=(ALL) NOPASSWD: ALL\' >> /etc/sudoers',
            'mkdir -p /var/run/sshd',
            'chmod 0755 /var/run/sshd',
            '/usr/sbin/sshd -D',
        ]

        args = {
            'user': self.conf.get('user', 'app'),
            'host_uid': self.conf.get('host-uid', os.getuid()),
            'ssh_key': ssh_key,
        }

        command = self.docker_command(
            '-c',
            ' && '.join(cmd.format(**args) for cmd in commands),
            use_sshd=True
        )
        container = subprocess.check_output(command).strip()
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

        container_details = self.container_details(container)
        port_config = container_details['HostConfig']['PortBindings']
        ssh_port = port_config['22/tcp'][0]['HostPort']
        ssh_command = [
            'ssh',
            '{0}@localhost'.format(self.conf.get('user', 'app')),
            '-p',
            ssh_port,
            '-A',
        ]

        if identity:
            ssh_command += ('-i', identity)

        for _ in range(1, 20):
            try:
                subprocess.check_call(
                    ssh_command + ['-o', 'StrictHostKeyChecking=no',
                                   '-o', 'PasswordAuthentication=no',
                                   'true'],
                    stdin=DEVNULL,
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                )
                available = True
                break
            except subprocess.CalledProcessError:
                pass
            time.sleep(1)
        else:
            available = False

        return (' '.join(ssh_command), available)


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

        return os.path.exists(target)
