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

import socket

from forklift.base import ImproperlyConfigured
from forklift.registry import Registry

register = Registry()  # pylint:disable=invalid-name


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


def pipe_split(value):
    """
    Split a pipe-separated string if it's the only value in an array.
    """

    if len(value) == 1 and '|' in value[0]:
        return value[0].split('|')
    else:
        return value


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
    def provide(cls, application_id, overrides=None):
        """
        Choose the first available service from the list of providers.
        """

        overrides = overrides or {}
        allowed_overrides = cls.allow_override + cls.allow_override_list

        for provider in cls.providers:
            service = getattr(cls, provider)(application_id)

            for key, value in vars(overrides).items():
                if value is not None:
                    if key in allowed_overrides:
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
