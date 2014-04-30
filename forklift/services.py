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
Services that can be provided to running applications.
"""

import json
import os
import socket
import subprocess
import urllib.request

from forklift.base import free_port, ImproperlyConfigured
from forklift.registry import Registry


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


def split_host_port(host_port, default_port):
    """
    Split host:port into host and port, using the default port in case
    it's not given.
    """

    host_port = host_port.split(':')
    if len(host_port) == 2:
        host, port = host_port
        return host, port
    else:
        return host_port[0], default_port


register = Registry()  # pylint:disable=invalid-name


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
    def add_arguments(cls, add_argument):
        """
        Add service configuration arguments to the parser.
        """

        # TODO: refactor for types other than string (port numbers) and
        # list (Elasticsearch host).

        for param in cls.allow_override:
            add_argument('--{0}'.format(param))

    @classmethod
    def provide(cls, application_id, overrides=None):
        """
        Choose the first available service from the list of providers.
        """

        overrides = overrides or {}

        for provider in cls.providers:
            service = getattr(cls, provider)(application_id)

            for key, value in vars(overrides).items():
                if value is not None:
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


@register('postgres')
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
    def localhost(cls, application_id):
        """
        The PostgreSQL environment on the local machine.
        """
        return cls(
            host='localhost',
            name=application_id,
            user=application_id,
        )

    providers = ('localhost',)


@register('postgis')
class PostGISService(PostgreSQLService):
    """
    PostgreSQL database with PostGIS support.
    """

    URL_SCHEME = 'postgis'

    CHECK_COMMAND = 'select PostGIS_full_version()'


def pipe_split(string):
    """
    Split a pipe-separated string into an array.

    Do nothing if an array already.
    """

    return string.split('|') if isinstance(string, str) else string


@register('memcache')
class MemcacheService(Service):
    """
    Memcache service for the application.
    """

    allow_override = ('key_prefix', 'host', 'hosts')
    providers = ('localhost',)

    DEFAULT_PORT = 11211

    def __init__(self,
                 key_prefix='',
                 hosts=None):

        self.key_prefix = key_prefix
        self.hosts = hosts or []

    def environment(self):
        """
        The environment to access Memcache
        """

        return {
            'MEMCACHE_HOSTS': '|'.join(self.hosts),
            'MEMCACHE_PREFIX': self.key_prefix,
        }

    def available(self):
        """
        Check whether memcache is available

        Do this by connecting to the socket. At least one host must be up
        """

        if not self.hosts:
            return False

        for host in self.hosts:
            if port_open(*split_host_port(host, self.DEFAULT_PORT)):
                return True

        return False

    @property
    def host(self):
        """
        The (pipe separated) hosts for the Memcache service.
        """

        return '|'.join(
            split_host_port(host, self.DEFAULT_PORT)[0]
            for host in self.hosts
        )

    @host.setter
    def host(self, host):
        """
        Set the host to access Memcache at.
        """

        self.hosts = [
            h if ':' in h else '{0}:{1}'.format(h, self.DEFAULT_PORT)
            for h in host.split('|')
        ]

    @classmethod
    def localhost(cls, application_id):
        """
        The default memcached provider
        """

        return cls(key_prefix=application_id,
                   hosts=['localhost:{0}'.format(cls.DEFAULT_PORT)])


@register('elasticsearch')
class ElasticsearchService(Service):
    """
    Elasticsearch service for the application.
    """

    allow_override = ('index_name', 'host', 'urls')

    def __init__(self, index_name, urls):
        self.index_name = index_name
        self._url_array = []
        self.urls = urls

    def environment(self):
        """
        The environment to access Elasticsearch.
        """

        return {
            'ELASTICSEARCH_INDEX_NAME': self.index_name,
            'ELASTICSEARCH_URLS': self.url_string(),
        }

    def url_string(self):
        """
        All URLs joined as a string.
        """
        return '|'.join(url.geturl() for url in self.urls)

    @property
    def urls(self):
        """
        The (pipe separated) URLs to access Elasticsearch at.
        """

        return self._url_array

    @urls.setter
    def urls(self, urls):
        """
        Set the URLs to access Elasticsearch at.
        """

        self._url_array = [
            urllib.parse.urlparse(url) if isinstance(url, str) else url
            for url in pipe_split(urls)
        ]

    @property
    def host(self):
        """
        The (pipe separated) hosts for the Elasticsearch service.
        """

        return '|'.join(url.hostname for url in self._url_array)

    @host.setter
    def host(self, host):
        """
        Set the host to access Elasticsearch at.
        """

        self.urls = [
            # pylint:disable=protected-access
            url._replace(
                netloc='{host}:{port}'.format(host=host, port=url.port))
            for url in self.urls
        ]

    def available(self):
        """
        Check whether Elasticsearch is available at a given URL.
        """

        if not self.urls:
            return False

        for url in self.urls:
            try:
                es_response = urllib.request.urlopen(url.geturl())
                es_status = json.loads(es_response.read().decode())
                if es_status['status'] != 200:
                    return False
            except (urllib.request.URLError, ValueError):
                return False

        return True

    @classmethod
    def localhost(cls, application_id):
        """
        The Elasticsearch environment on the local machine.
        """
        return cls(index_name=application_id,
                   urls='http://localhost:9200')

    providers = ('localhost',)


@register('proxy')
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

    # pylint:disable=unused-argument
    @classmethod
    def manual(cls, application_id):
        """
        Manually-configured proxy. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    providers = ('manual',)


@register('email')
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

    # pylint:disable=unused-argument
    @classmethod
    def localhost(cls, application_id):
        """
        The MTA on the local machine.
        """
        return cls(host='localhost')

    providers = ('localhost',)


@register('syslog')
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

    # pylint:disable=unused-argument
    @classmethod
    def manual(cls, application_id):
        """
        Manually-configured syslog. Will not be available unless parameters
        are overridden in configuration.
        """

        return cls()

    # pylint:disable=unused-argument
    @classmethod
    def stdout(cls, application_id):
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
