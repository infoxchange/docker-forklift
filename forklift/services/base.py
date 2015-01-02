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
Services that can be provided to running applications - base definitions.
"""

import logging
import os
import socket
import subprocess
import sys
import urllib.parse

from collections import namedtuple
from operator import attrgetter

import docker

import requests.exceptions

from xdg.BaseDirectory import save_cache_path

from forklift.base import ImproperlyConfigured, wait_for, rm_tree_root_owned
from forklift.registry import Registry

LOGGER = logging.getLogger(__name__)
register = Registry()  # pylint:disable=invalid-name


def try_port(host, port):
    """
    Try to connect to a given TCP port.
    """

    with socket.socket() as sock:
        sock.connect((host, int(port)))
        return True


def port_open(host, port):
    """
    Check whether the specified TCP port is open.
    """

    try:
        return try_port(host, port)
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


def pipe_split(value):
    """
    Split a pipe-separated string if it's the only value in an array.
    """

    if isinstance(value, str):
        value = (value,)

    try:
        value = tuple(value)
    except TypeError:
        value = (value,)

    if len(value) == 1 and isinstance(value[0], str) and '|' in value[0]:
        return value[0].split('|')
    else:
        return value


def transient_provider(func):
    """
    Decorator to mark a provider as transient
    """
    func.transient = True
    return func


class ProviderNotAvailable(Exception):
    """
    A service provider is not available.
    """

    pass


class DependencyRequired(ProviderNotAvailable):
    """
    A dependency is required to make a provider available.
    """

    def __init__(self, message, command=None):
        super().__init__(message)
        self.command = command


class DockerImageRequired(DependencyRequired):
    """
    A Docker image is required to make a provider available.
    """

    def __init__(self, image):
        super().__init__(
            message="Docker image {0} is required.".format(image),
            command='docker pull {0}'.format(image),
        )


class ContainerRefusingConnection(ProviderNotAvailable):
    """
    A Docker container that was started is not connectable after a period of
    time.
    """

    def __init__(self, image, port):
        super().__init__(
            message=("Docker container {0} was started but couldn't connect on"
                     "port {1}").format(image, port)
        )


class Service(object):
    """
    Base class for services required by the application.
    """

    # A list of class methods to try to find an available service provider.
    providers = ()

    # A list of attributes which can be overridden from a configuration file
    # or the command line.
    allow_override = ()

    # A list of attributes which can be overridden as a list of arguments
    # (i.e. hosts, urls)
    allow_override_list = ()

    TEMPORARY_AVAILABILITY_ERRORS = (
        ProviderNotAvailable,
        socket.error,
    )
    PERMANENT_AVAILABILITY_ERRORS = ()

    CONTAINER_IMAGE = None
    DEFAULT_PORT = None

    @classmethod
    def add_arguments(cls, add_argument):
        """
        Add service configuration arguments to the parser.
        """

        # TODO: refactor for types other than string (port numbers) and
        # list (Elasticsearch host).

        for param in cls.allow_override:
            add_argument('--{0}'.format(param))

        for param in cls.allow_override_list:
            add_argument('--{0}'.format(param), nargs='+')

    @classmethod
    def provide(cls, application_id, overrides=None, transient=False):
        """
        Choose the first available service from the list of providers.
        """
        for provider in cls.providers:
            provider_func = getattr(cls, provider)
            if transient and not getattr(provider_func, 'transient', False):
                LOGGER.debug("Skipping %s provider for %s service because "
                             "it's not transient", provider, cls.__name__)
                continue

            LOGGER.debug("Trying %s provider for %s service",
                         provider, cls.__name__)
            try:
                service = provider_func(application_id)
                setattr(service, 'provided_by', provider)
            except ProviderNotAvailable as exc:
                print((
                    "While trying '{provider}' provider for {service}: {exc}"
                ).format(
                    provider=provider,
                    service=cls.__name__,
                    exc=exc,
                ), file=sys.stderr)
                continue

            cls._set_overrides(service, overrides)

            try:
                if service.available():
                    return service
            except:
                service.cleanup()
                raise

        raise ImproperlyConfigured(
            "No available providers for service {0}.".format(cls.__name__))

    @classmethod
    def _set_overrides(cls, service, overrides=None):
        """
        Setup override values on a service
        """
        overrides = vars(overrides) if overrides else {}
        allowed_overrides = cls.allow_override + cls.allow_override_list

        for key, value in overrides.items():
            if value is not None:
                if key in allowed_overrides:
                    setattr(service, key, value)
                    LOGGER.debug("Config for %s: %s = %s",
                                 cls.__name__, key, value)
                else:
                    raise ImproperlyConfigured(
                        "Invalid parameter {0} for service {1}.".format(
                            key, cls.__name__))

    def available(self):
        """
        Wrap check_available so that "expected" exceptions are not raised
        """
        try:
            return self.check_available()
        except self.TEMPORARY_AVAILABILITY_ERRORS:
            return False
        except self.PERMANENT_AVAILABILITY_ERRORS:
            return False

    def check_available(self):
        """
        Check whether the service is available. Override to implement
        availability checks to warn the user instead of let the application
        fail.
        """
        return True

    def wait_until_available(self, retries=60):
        """
        Wait for the container to be available before returning. If the retry
        limit is exceeded, ProviderNotAvailable is raised

        Parameters:
            retries - number of times to retry before giving up
        """
        try:
            LOGGER.info("Waiting for %s to become available",
                        self.__class__.__name__)
            available = wait_for(
                self.check_available,
                expected_exceptions=self.TEMPORARY_AVAILABILITY_ERRORS,
                retries=retries,
            )
            return available

        except self.PERMANENT_AVAILABILITY_ERRORS as ex:
            print("Error checking for {}: {}".format(
                self.__class__.__name__, ex
            ))
            return False

    def environment(self):
        """
        The environment, as a dictionary, to let the application know
        the service configuration.
        """

        raise NotImplementedError("Please override environment().")

    def cleanup(self):
        """
        Do any clean up required to undo anything that was done in the provide
        method
        """

        # pylint:disable=no-member
        if self.provided_by != 'container':
            LOGGER.debug("Don't know how to clean up %s service provided "
                         "by %s",
                         self.__class__.__name__,
                         self.provided_by)
            return False

        if self.container_info.new:
            LOGGER.debug("Cleaning up container '%s' for %s service",
                         self.container_info.name,
                         self.__class__.__name__)
            destroy_container(self.container_info.name)
        else:
            LOGGER.debug("Not cleaning up container '%s' for service %s "
                         "because it was not created by this invocation",
                         self.container_info.name,
                         self.__class__.__name__)

        return True

    @classmethod
    def ensure_container(cls, application_id, **kwargs):
        """
        Ensure a container for this service is running.
        """

        return _ensure_container(
            image=cls.CONTAINER_IMAGE,
            port=cls.DEFAULT_PORT,
            application_id=application_id,
            **kwargs
        )

    @classmethod
    def from_container(cls, application_id, container):
        """
        The service instance connecting to the specified Docker container.
        """

        raise NotImplementedError("Please override from_container.")

    @classmethod
    @transient_provider
    def container(cls, application_id):
        """
        A generic container provider for a service. Needs to be specified in
        'providers' to activate.
        """

        container = cls.ensure_container(application_id)

        instance = cls.from_container(application_id, container)
        instance.wait_until_available()

        # pylint:disable=attribute-defined-outside-init
        instance.container_info = container
        return instance


def replace_part(url, **kwargs):
    """
    Replace a part of the URL with a new value.

    Keyword arguments can be any properties of urllib.parse.ParseResult.
    """

    netloc_parts = ('username', 'password', 'hostname', 'port')

    for part, value in kwargs.items():
        if part in netloc_parts:
            # Reassemble netloc
            netloc = {
                p: getattr(url, p)
                for p in netloc_parts
            }

            netloc[part] = value

            netloc_str = netloc['hostname']

            if netloc['port']:
                netloc_str += ':' + str(netloc['port'])
            if netloc['username'] or netloc['password']:
                userinfo = netloc['username'] or ''
                if netloc['password']:
                    userinfo += ':' + netloc['password']
                netloc_str = userinfo + '@' + netloc_str

            kwargs = {'netloc': netloc_str}
        else:
            kwargs = {part: value}

        # pylint:disable=protected-access
        url = url._replace(**kwargs)

    return url


class URLDescriptor(object):
    """
    A descriptor to get or set an URL part for all the URLs of the class.
    """

    def __init__(self, part, default='', joiner='|'.join):
        """
        Initialise a descriptor to get or set an URL part.

        Parameters:
            part - the part to get, can be a string or a tuple of (get, set)
            default - filler for missing parts of the URL, defaults to ''
            joiner - how to join the parts from the URL array together;
            defaults to concatenating with '|' in between
        """

        if isinstance(part, str):
            self.getter = attrgetter(part)
            self.setter = lambda url, value: replace_part(url, **{part: value})
        else:
            (self.getter, self.setter) = part

        self.default = default
        self.joiner = joiner

    def __get__(self, instance, owner):
        """
        Get the URL part for all URLs in the instance.
        """

        if instance is None:
            return self

        return self.joiner(
            self.getter(url) or self.default
            for url in instance.urls
        )

    def __set__(self, instance, value):
        """
        Set the URL part for all URLs in the instance.
        """

        instance.urls = tuple(
            self.setter(url, value)
            for url in instance.urls
        )


class URLNameDescriptor(URLDescriptor):
    """
    A descriptor to get or set the URL path without a leading slash,
    commonly used when mapping an alphanumeric namespace (e.g. database names)
    onto URLs.
    """

    def __init__(self):
        super().__init__((
            lambda url: url.path.lstrip('/'),
            lambda url, value: replace_part(url, path='/' + value),
        ))


class URLMultiValueDescriptor(URLDescriptor):
    """
    A descriptor to get or set part of the URLs to an array of values.
    """

    def __init__(self, part, default='', joiner=lambda xs: next(iter(xs))):
        super().__init__(part, default, joiner)

    def __set__(self, instance, value):
        """
        Set the URL part to an array of values.

        After setting this, all the URLs will be identical except for hostinfo
        taken from the (iterable) value assigned. The rest of the URL
        parameters will be copied from the first one.
        """

        url = instance.urls[0]
        instance.urls = tuple(
            self.setter(url, v)
            for v in pipe_split(value)
        )


class URLHostInfoDescriptor(URLMultiValueDescriptor):
    """
    A descriptor to get or set hostinfo pairs (hostname:port), accounting for
    default port.
    """

    def get_hostinfo(self, url):
        """
        Get the hostname:port pair of the URL.
        """

        port = url.port
        if port == self.default_port or port is None:
            return url.hostname
        else:
            return ':'.join((url.hostname, str(port)))

    def set_hostinfo(self, url, value):
        """
        Set the hostname:port pair of the URL.
        """

        hostname, port = split_host_port(value, self.default_port)
        return replace_part(url, hostname=hostname, port=port)

    def __init__(self, default_port, joiner=lambda xs: next(iter(xs))):
        self.default_port = default_port
        super().__init__(
            (
                self.get_hostinfo,
                self.set_hostinfo,
            ),
            joiner=joiner,
        )


class URLService(Service):
    """
    A service specified by a set of URLs.

    This is a common 12 factor pattern and should be used instead of inheriting
    Service directly as much as possible.
    """

    # These set respective attributes on all the URLs.
    allow_override = ('user', 'password', 'host', 'port', 'path')

    allow_override_list = ('urls',)

    def __init__(self, urls):
        self._urls = ()
        self.urls = urls

        log_service_settings(LOGGER, self, 'urls')

    def url_string(self):
        """
        All URLs joined as a string.
        """
        return '|'.join(url.geturl() for url in self.urls)

    @property
    def urls(self):
        """
        The array of the URLs the service can be accessed at.
        """

        return self._urls

    @urls.setter
    def urls(self, urls):
        """
        Set the URLs to access the service at.
        """

        self._urls = tuple(
            urllib.parse.urlparse(url) if isinstance(url, str) else url
            for url in pipe_split(urls)
        )

    user = URLDescriptor('username')
    password = URLDescriptor('password')
    host = hostname = URLMultiValueDescriptor('hostname')
    port = URLMultiValueDescriptor('port', default=None)
    path = URLDescriptor('path')


ContainerInfo = namedtuple('ContainerInfo', ['host',
                                             'port',
                                             'data_dir',
                                             'name',
                                             'new'])


def cache_directory(container_name):
    """
    A directory to cache the container data in.
    """

    return os.path.join(save_cache_path('forklift'), container_name)


def container_name_for(image, application_id):
    """
    Get a name for a service container based on image and application ID

    Parameters:
        image - image that the container is for
        application_id - application id that the container is for

    Return value:
        A string
    """
    return image.replace('/', '_') + '__' + application_id


def _ensure_container(image,
                      port,
                      application_id,
                      data_dir=None,
                      **kwargs):
    """
    Ensure that a container for an application is running and wait for the port
    to be connectable.

    Parameters:
        image - the image to run a container from
        port - the port to forward from the container
        application_id - the application ID, for naming the container
        data_dir - the directory to persistently mount inside the container

    Return value:
        An object with the following attributes:
            port - the forwarded port number
            data_dir - if asked for, path for the persistently mounted
            directory inside the container
            name - the container name
            new - True/False to show if the container was created or not
    """

    with docker.Client() as docker_client:

        # TODO: better container name
        container_name = container_name_for(image, application_id)
        LOGGER.info("Ensuring container for '%s' is started with name '%s'",
                    image, container_name)

        if data_dir is not None:
            cached_dir = cache_directory(container_name)
        else:
            cached_dir = None

        try:
            created, container_status = get_or_create_container(
                docker_client,
                container_name,
                image,
                port,
                data_dir,
                cached_dir,
                **kwargs
            )

            if not container_status['State']['Running']:
                _start_container(docker_client,
                                 container_name,
                                 port,
                                 data_dir,
                                 cached_dir)

            host = docker_client.inspect_container(
                container_name)['NetworkSettings']['IPAddress']
            host_port = docker_client.port(container_name, port)[0]['HostPort']

            try:
                _wait_for_port(image, host_port)
            except:
                if created:
                    LOGGER.debug("Could not connect to '%s' container, so "
                                 "destroying it", image)
                    destroy_container(container_name)
                raise

            return ContainerInfo(host=host,
                                 port=port,
                                 data_dir=cached_dir,
                                 name=container_name,
                                 new=created)
        except requests.exceptions.ConnectionError:
            raise ProviderNotAvailable("Cannot connect to Docker daemon.")


# pylint:disable=too-many-arguments
def get_or_create_container(docker_client,
                            container_name,
                            image,
                            port,
                            data_dir=None,
                            cached_dir=None,
                            **kwargs):
    """
    Get info for an existing container by name, or create a new one

    Parameters:
        docker_client - a docker.Client object for the Docker daemon
        container_name - name to check/start
        image - the image to run a container from
        port - the port to forward from the container
        data_dir - the directory to persistently mount inside the container
        cached_dir - the directory to mount from the host to data_dir

    Return value:
        A tuple of:
            - True if the container started as a result of this call
            - Output from Docker inspect
    """
    try:
        return False, docker_client.inspect_container(container_name)
    except docker.errors.APIError:
        try:
            docker_client.inspect_image(image)
        except docker.errors.APIError:
            raise DockerImageRequired(image)

        if data_dir is not None:
            # Ensure the data volume is mounted
            kwargs.setdefault('volumes', {})[data_dir] = cached_dir

        docker_client.create_container(
            image,
            name=container_name,
            ports=(port,),
            **kwargs
        )
        container_status = docker_client.inspect_container(container_name)

    return True, container_status


def destroy_container(container_name):
    """
    Stop and remove a container by name
    """
    cache_dir = cache_directory(container_name)
    with docker.Client() as docker_client:
        docker_client.stop(container_name)
        docker_client.remove_container(container_name)

    try:
        rm_tree_root_owned(cache_dir)
    except subprocess.CalledProcessError:
        pass


def _wait_for_port(image, port, retries=30):
    """
    Wait for a port to become available, or raise ContainerRefusingConnection
    error

    Parameters:
        image - the image that the container is run from
        port - the port to wait for
        retries - number of times to retry before giving up
    """
    LOGGER.debug("Waiting for '%s' port %s to be reachable", image, port)
    if not wait_for(lambda: port_open('127.0.0.1', port), retries=retries):
        raise ContainerRefusingConnection(image, port)


def _start_container(docker_client, image, port, data_dir, cached_dir):
    """
    Start a container, binding ports and data dirs

    Parameters:
        docker_client - client for the Docker API
        image - the image to run a container from
        port - the port to forward from the container
        data_dir - the directory to persistently mount inside the container
        cached_dir - the directory to mount from the host to data_dir
    """
    LOGGER.info("Starting '%s' container", image)
    LOGGER.debug("Container port: %s", port)
    LOGGER.debug("Container data dir (in container): %s", data_dir)
    LOGGER.debug("Container cached dir (on host): %s", cached_dir)
    start_args = {
        'port_bindings': {port: None},
    }
    if data_dir is not None:
        start_args['binds'] = {
            cached_dir: data_dir,
        }
    docker_client.start(image, **start_args)


def log_service_settings(logger, service, *attrs):
    """
    Format and log a service settings.

    Parameters:
        logger - a logger object to log to
        service - the service object that the settings are for
        attrs - a list of attrs to get from the service. If the attr is
                callable, it will be called with no arguments. It may return
                just a value, or a tuple of a new attr name and a value
    """
    if logger.isEnabledFor(logging.DEBUG):
        for attr in attrs:
            val = getattr(service, attr)
            if callable(val):
                val = val()

            logger.debug("%s %s: %s", service.__class__.__name__, attr, val)
