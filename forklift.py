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
A script to install and start an SSH daemon in a Docker image, enabling the
user to log on to it.
"""

import json
import os
import pwd
import socket
import subprocess
import sys
import time
import urllib.request
import yaml

from xdg.BaseDirectory import xdg_config_home

try:
    from subprocess import DEVNULL
except AttributeError:
    DEVNULL = open(os.devnull)


class ImproperlyConfigured(Exception):
    """
    The host is not properly configured for running Docker.
    """

    pass

def application_id():
    """
    A string which identifies the application.

    Use to avoid conflicts between services for different applications.
    """

    # TODO: get something from the image name
    return os.path.basename(os.path.abspath(os.curdir))


class Service(object):
    """
    Base class for services required by the application.
    """

    # A list of class methods to try to find an available service provider.
    providers = ()

    # A list of attributes which can be overridden from a configuration file
    # or the command line.
    allow_override = ()

    @classmethod
    def provide(cls, overrides=None):
        """
        Choose the first available service from the list of providers.
        """

        overrides = overrides or {}

        for provider in cls.providers:
            service = getattr(cls, provider)()

            for key, value in overrides.items():
                if key in cls.allow_override:
                    setattr(service, key, value)

            if service.available():
                return service

        raise ImproperlyConfigured(
            "No available providers for service {0}.".format(cls.__name__))

    @staticmethod
    def available():
        """
        Check whether the service is available. Override to implement
        availability checks to warn the user instead of let the application
        fail.
        """

        return True

    def environment(self):
        """
        The environment, as a dictionary, to let the application know
        the service configuration.
        """

        raise NotImplementedError("Please override environment().")


class PostgreSQLService(Service):
    """
    PostgreSQL service provided by the host machine.
    """

    DATABASE_NAME = 'DEFAULT'

    allow_override = ('name', 'host', 'port', 'user', 'password')

    def __init__(self,
                 name,
                 host='localhost',
                 port=5432,
                 user=None,
                 password=None):
        self.host = host
        self.port = port
        self.name = name
        self.user = user
        self.password = password

    def environment(self):
        """
        The environment needed for the application to connect to PostgreSQL.
        """

        env_name = 'DB_{0}_URL'.format(self.DATABASE_NAME)
        details = {k: v or '' for k, v in self.__dict__.items()}
        url = 'postgres://{user}:{password}@{host}:{port}/{name}'.format(
                **details)
        return {env_name: url}

    def available(self):
        """
        Check whether PostgreSQL is installed on the host and accessible.
        """

        try:
            subprocess.check_output(['psql', '--version'])

            if self.password:
                os.putenv('PGPASSWORD', self.password)
            subprocess.check_output([
                'psql',
                '-h', self.host,
                '-p', str(self.port),
                '-U', self.user,
                self.name,
                '-c', 'select version()',
            ])

            return True
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def localhost(cls):
        """
        The PostgreSQL environment on the local machine.
        """
        return cls(host='localhost',
                   name=application_id(),
                   user=application_id(),
                   )

    providers = ('localhost',)


class ElasticsearchService(Service):
    """
    Elasticsearch service for the application.
    """

    allow_override = ('index_name', 'url')

    def __init__(self, index_name, url):
        self.index_name = index_name
        self.url = url

    def environment(self):
        """
        The environment to access Elasticsearch.
        """

        return {
            'ELASTICSEARCH_INDEX_NAME': self.index_name,
            'ELASTICSEARCH_URLS': self.url,
        }

    def available(self):
        """
        Check whether Elasticsearch is available at a given URL.
        """

        try:
            es_response = urllib.request.urlopen(self.url)
            es_status = json.loads(es_response.read().decode())
            return es_status['status'] == 200
        except (urllib.request.URLError, ValueError):
            return False

    @classmethod
    def localhost(cls):
        """
        The Elasticsearch environment on the local machine.
        """
        return cls(index_name=application_id(),
                   url='http://localhost:9200')

    providers = ('localhost',)


class ProxyService(Service):
    """
    Proxy service for the application.
    """

    allow_override = ('host', 'port')

    def __init__(self, host=None, port=None):
        self.host = host
        self.port = port

    def environment(self):
        """
        The environment to access the proxy.
        """

        if self.host:
            return {
                'HTTP_PROXY': 'http://{host}:{port}'.format(**self.__dict__),
            }
        else:
            return {}


class Executioner(object):
    """
    A method of executing the application with supplied services.
    """

    def __init__(self, target, services, environment, conf):
        """
        Initialise the executioner with the specified target and services.
        """

        self.target = target
        self.services = services
        self.added_environment = environment
        self.conf = conf

    @staticmethod
    def valid_target(target):
        """
        Guess whether a target is valid for the given executioner.

        Override to have executioner chosen automatically based on target
        given.
        """

        return False

    def run(self, *command):
        """
        Run the command on the target.
        """

        raise NotImplementedError("Please override run().")

    def environment(self):
        """
        The environment to supply to the application.
        """

        env = {}

        env['ENVIRONMENT'] = 'dev_local'
        env['DEVNAME'] = pwd.getpwuid(os.getuid())[0]

        # TODO: TZ

        env['SITE_PROTOCOL'] = 'http'
        env['SITE_DOMAIN'] = 'localhost:{0}'.format(self.serve_port())

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

        if hasattr(self, '_serve_port'):
            return self._serve_port

        with socket.socket() as sock:
            sock.bind(('', 0))
            self._serve_port = sock.getsockname()[1]
        return self._serve_port

    def print_url(self):
        """
        Print the URL the container is accessible on.
        """

        print('http://localhost:{0}'.format(self.serve_port()))


class Docker(Executioner):
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

        if command == ['sshd']:
            return self.run_sshd()
        else:
            command = self.docker_command(*command)
            return subprocess.call(command)

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
                '-privileged',
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
        if 'identity' not in self.conf:
            # provide the entire set of keys
            ssh_key = (subprocess
                        .check_output(['ssh-add', '-L'])
                        .decode()
                        .strip())
            if ssh_key == '':
                raise ImproperlyConfigured(
                    "You don't seem to have any SSH keys! "
                    "How do you do any work?")
        else:
            path = os.path.expanduser(
                '~/.ssh/{}.pub'.format(self.conf['identity']))
            with open(path) as id_file:
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
            'mkdir -p /etc/ssh/{user}',
            'echo \'{ssh_key}\' > /etc/ssh/{user}/authorized_keys',
            'chsh -s /bin/bash {user}',
            'usermod -p zzz {user}',
            'chown -R --from={user} {host_uid} /app',
            'usermod -u {host_uid} {user}',
            'chown -R {user} /etc/ssh/{user}',
            'chmod -R go-rwx /etc/ssh/{user}',
            'echo \'{user} ALL=(ALL) NOPASSWD: ALL\' >> /etc/sudoers',
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
        self.print_ssh_details(container)
        return 0

    def print_ssh_details(self, container):
        """
        Wait for SSH service to start and print the command to SSH to
        the container.
        """

        container_details = self.container_details(container)
        port_config = container_details['HostConfig']['PortBindings']
        ssh_port = port_config['22/tcp'][0]['HostPort']
        ssh_command = [
            'ssh',
            '{user}@localhost'.format(self.conf),
            '-p',
            ssh_port,
            '-A',
        ]

        if self.conf['identity']:
            ssh_command += (
                '-i',
                os.path.expanduser('~/.ssh/{identity}'.format(
                    identity=self.conf['identity']))
            )

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
                break
            except subprocess.CalledProcessError:
                pass
            time.sleep(1)
        else:
            print("Timed out waiting for SSH setup. You can still try "
                  "the command below but it might also indicate a problem "
                  "with SSH setup.")
        print(' '.join(ssh_command))


class Direct(Executioner):
    """
    Execute the application directly.
    """

    def run(self, *command):
        """
        Run the application directly.
        """

        for key, value in self.environment().items():
            os.putenv(key, value)

        return subprocess.call([self.target] + list(command))

    @staticmethod
    def valid_target(target):
        """
        Check if the target is directly executable.
        """

        return os.path.exists(target)


class Forklift(object):
    """
    The main class.
    """

    services = {
        'postgres': PostgreSQLService,
        'elasticsearch': ElasticsearchService,
        'proxy': ProxyService,
        # TODO: Email
        # TODO: Syslog
    }

    executioners = {
        'direct': Direct,
        'docker': Docker,
    }

    def __init__(self, argv):
        """
        Parse the command line and set up the class.
        """

        # Parse the configuration from:
        # - project configuration file
        # - user configuration file
        # - command line

        self.conf = {}
        # TODO: deep merge
        self.conf.update(self.configuration_file('twistlock.yaml'))
        self.conf.update(self.configuration_file(
            os.path.join(xdg_config_home,
                         'forklift',
                         '{0}.yaml'.format(application_id()))))

        (self.args, kwargs) = self.command_line_configuration(argv)
        self.conf.update(kwargs)

    def configuration_file(self, name):
        """
        Parse settings from a configuration file.
        """
        try:
            with open(name) as conffile:
                return yaml.load(conffile)
        except FileNotFoundError:
            return {}

    def command_line_configuration(self, argv):
        """
        Parse settings from the command line.
        """

        args = []
        kwargs = {}

        command_line = argv[1:]
        while command_line:
            arg = command_line.pop(0)
            if arg.startswith('--'):
                kwargs[arg[2:]] = command_line.pop(0)
            else:
                args.append(arg)

        return (args, kwargs)


    def main(self):
        """
        Run the specified application command.
        """

        (target, *command) = self.args

        if 'executioner' in self.conf:
            executioner_class = self.executioners[self.conf['executioner']]
        else:
            for executioner_class in self.executioners.values():
                if executioner_class.valid_target(target):
                    break
            else:
                executioner_class = self.executioners['docker']

        try:
            required_services = self.conf.get('services', [])
            services = [
                self.services[service].provide(self.conf.get(service))
                for service in required_services
            ]

            executioner = executioner_class(
                target=target,
                services=services,
                environment=self.conf.get('environment', {}),
                conf=self.conf,
            )

        except ImproperlyConfigured as ex:
            print(ex)
            return 1

        return executioner.run(*command)
