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
    from subprocess import DEVNULL  # pylint:disable=no-name-in-module
except ImportError:
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


def free_port():
    """
    Find a free TCP port.
    """

    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


def port_open(host, port):
    """
    Check whether the specified TCP port is open.
    """

    with socket.socket() as sock:
        try:
            sock.connect((host, int(port)))
            return True
        except socket.error:
            return False


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
                else:
                    raise ImproperlyConfigured(
                        "Invalid parameter {0} for service {1}.".format(
                            key, cls.__name__))

            if service.available():
                return service

        raise ImproperlyConfigured(
            "No available providers for service {0}.".format(cls.__name__))

    def available(self):
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

    URL_SCHEME = 'postgres'

    CHECK_COMMAND = 'select version()'

    allow_override = ('name', 'host', 'port', 'user', 'password')

    # pylint:disable=too-many-arguments
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
        details['scheme'] = self.URL_SCHEME
        url = '{scheme}://{user}:{password}@{host}:{port}/{name}'.format(
            **details)
        return {env_name: url}

    def available(self):
        """
        Check whether PostgreSQL is installed on the host and accessible.
        """

        try:
            subprocess.check_output(['psql', '--version'])

            if self.password:
                os.environ['PGPASSWORD'] = self.password
            subprocess.check_output([
                'psql',
                '-h', self.host,
                '-p', str(self.port),
                '-U', self.user,
                '-w',
                self.name,
                '-c', self.CHECK_COMMAND,
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


class PostGISService(PostgreSQLService):
    """
    PostgreSQL database with PostGIS support.
    """

    URL_SCHEME = 'postgis'

    CHECK_COMMAND = 'select PostGIS_full_version()'


class ElasticsearchService(Service):
    """
    Elasticsearch service for the application.
    """

    allow_override = ('index_name', 'urls')

    def __init__(self, index_name, urls):
        self.index_name = index_name
        self.urls = urls

    def environment(self):
        """
        The environment to access Elasticsearch.
        """

        return {
            'ELASTICSEARCH_INDEX_NAME': self.index_name,
            'ELASTICSEARCH_URLS': self.urls,
        }

    def available(self):
        """
        Check whether Elasticsearch is available at a given URL.
        """

        urls = self.urls.split('|')
        if not urls:
            return False

        for url in urls:
            try:
                es_response = urllib.request.urlopen(url)
                es_status = json.loads(es_response.read().decode())
                if es_status['status'] != 200:
                    return False
            except (urllib.request.URLError, ValueError):
                return False

        return True

    @classmethod
    def localhost(cls):
        """
        The Elasticsearch environment on the local machine.
        """
        return cls(index_name=application_id(),
                   urls='http://localhost:9200')

    providers = ('localhost',)


class ProxyService(Service):
    """
    Proxy service for the application.
    """

    allow_override = ('host', 'port')

    def __init__(self, host=None, port=None):
        self.host = host
        self.port = port

    def available(self):
        """
        Check whether the proxy is available.
        """

        if self.host:
            return port_open(self.host, self.port)
        else:
            return True

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

    @classmethod
    def manual(cls):
        """
        Manually-configured proxy. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    providers = ('manual',)


class EmailService(Service):
    """
    An MTA for the application.
    """

    allow_override = ('host', 'port')

    def __init__(self, host, port=25):
        self.host = host
        self.port = port

    def environment(self):
        """
        The environment to send email.
        """

        return {
            'EMAIL_HOST': self.host,
            'EMAIL_PORT': str(self.port),
        }

    def available(self):
        """
        Check whether the MTA is available.
        """

        return port_open(self.host, self.port)

    @classmethod
    def localhost(cls):
        """
        The MTA on the local machine.
        """
        return cls(host='localhost')

    providers = ('localhost',)


class SyslogService(Service):
    """
    Logging facility for the application.
    """

    DEFAULT_PORT = 514

    allow_override = ('host', 'port', 'proto')

    def __init__(self, host=None, port=DEFAULT_PORT, proto='udp'):
        self.host = host
        self.port = port
        self.proto = proto

    def environment(self):
        """
        The environment to provide logging.
        """

        return {
            'SYSLOG_SERVER': self.host,
            'SYSLOG_PORT': str(self.port),
            'SYSLOG_PROTO': self.proto,
        }

    def available(self):
        """
        Check whether syslog is available.

        If the protocol is UDP, assume it is available if any of the other
        parameters are set.
        """

        if self.host is None:
            return False

        if self.proto == 'udp':
            return True
        else:
            return port_open(self.host, self.port)

    @classmethod
    def manual(cls):
        """
        Manually-configured syslog. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    @classmethod
    def stdout(cls):
        """
        Logger printing all the messages to the standard output of Forklift.
        """

        # Adapted from https://gist.github.com/marcelom/4218010
        import socketserver
        import threading

        class SyslogHandler(socketserver.BaseRequestHandler):
            """
            Handler outputting logging messages received to stdout.
            """
            def handle(self):
                data = self.request[0].strip().decode()
                print(data)

        class ThreadedUDPServer(socketserver.ThreadingMixIn,
                                socketserver.UDPServer):
            """
            Threaded UDP server.
            """
            pass

        port = free_port()
        server = ThreadedUDPServer(('0.0.0.0', port), SyslogHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        return cls('localhost', port)

    providers = ('manual', 'stdout')


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


def dict_deep_merge(left, right):
    """
    Merge two dictionaries recursively, giving the right one preference.
    """

    if not isinstance(right, dict):
        return right

    result = left.copy()
    for key, value in right.items():
        result[key] = dict_deep_merge(result.get(key, {}), value)

    return result


class Forklift(object):
    """
    The main class.
    """

    services = {
        'postgres': PostgreSQLService,
        'postgis': PostGISService,
        'elasticsearch': ElasticsearchService,
        'proxy': ProxyService,
        'email': EmailService,
        'syslog': SyslogService,
    }

    drivers = {
        'direct': Direct,
        'docker': Docker,
    }

    CONFIG_DIR = os.path.join(xdg_config_home, 'forklift')

    configuration_files = (
        'forklift.yaml',
        os.path.join(CONFIG_DIR, '_default.yaml'),
        os.path.join(CONFIG_DIR, '{0}.yaml'.format(application_id())),
    )

    def __init__(self, argv):
        """
        Parse the command line and set up the class.
        """

        # Parse the configuration from:
        # - project configuration file
        # - user configuration file
        # - user per-project configuration file
        # - command line

        self.conf = {}

        for conffile in self.configuration_files:
            self.conf = dict_deep_merge(self.conf,
                                        self.file_configuration(conffile))

        (self.args, kwargs) = self.command_line_configuration(argv)
        self.conf = dict_deep_merge(self.conf, kwargs)

    def file_configuration(self, name):
        """
        Parse settings from a configuration file.
        """
        try:
            with open(name) as conffile:
                return yaml.load(conffile)
        except IOError:
            return {}

    def command_line_configuration(self, argv):
        """
        Parse settings from the command line.
        """

        args = []
        kwargs = {}

        command_line = argv[1:]
        parsing_kwargs = True
        while command_line:
            arg = command_line.pop(0)
            if parsing_kwargs:
                if arg == '--':
                    parsing_kwargs = False
                elif arg.startswith('--'):
                    setting = arg[2:]
                    if not command_line or command_line[0].startswith('--'):
                        conf = True
                    else:
                        conf = command_line.pop(0)
                    for part in reversed(setting.split('.')):
                        conf = {part: conf}
                    kwargs = dict_deep_merge(kwargs, conf)
                else:
                    args.append(arg)
            else:
                args.append(arg)

        return (args, kwargs)

    def help(self):
        """
        Render the help file.
        """

        from pkg_resources import resource_stream
        readme = resource_stream(__name__, 'README.md')

        # Try to format the README nicely if Pandoc is installed
        try:
            subprocess.check_call(['pandoc', '-v'],
                                  stdout=DEVNULL, stderr=DEVNULL)
            pager = 'pandoc -s -f markdown -t man | man -l -'
        except OSError:
            pager = os.environ.get('PAGER', 'more')

        subprocess.check_call(pager, shell=True, stdin=readme)

    def main(self):
        """
        Run the specified application command.
        """

        if 'help' in self.conf or len(self.args) == 0:
            self.help()
            return 0

        (target, *command) = self.args

        if 'driver' in self.conf:
            driver_class = self.drivers[self.conf['driver']]
        else:
            for driver_class in self.drivers.values():
                if driver_class.valid_target(target):
                    break
            else:
                driver_class = self.drivers['docker']

        try:
            required_services = self.conf.get('services', [])
            services = [
                self.services[service].provide(self.conf.get(service))
                for service in required_services
            ]

            driver = driver_class(
                target=target,
                services=services,
                environment=self.conf.get('environment', {}),
                conf=self.conf,
            )

        except ImproperlyConfigured as ex:
            print(ex)
            return 1

        return driver.run(*command)


def main():
    """
    Main entry point.
    """

    return Forklift(sys.argv).main()


if __name__ == '__main__':
    main()
