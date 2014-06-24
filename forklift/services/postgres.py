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
PostgreSQL database service.
"""

import os
import re
import subprocess

from .base import (ensure_container,
                   ProviderNotAvailable,
                   Service,
                   register,
                   wait_for)


@register('postgres')
class PostgreSQL(Service):
    """
    PostgreSQL service provided by the host machine.
    """

    CHECK_COMMAND = 'select version()'
    CONTAINER_IMAGE = 'paintedfox/postgseql'
    DATABASE_NAME = 'DEFAULT'
    DEFAULT_PORT = 5432
    URL_SCHEME = 'postgres'

    allow_override = ('name', 'host', 'port', 'user', 'password')

    # pylint:disable=too-many-arguments
    def __init__(self,
                 name,
                 host='localhost',
                 port=DEFAULT_PORT,
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

    def wait_until_available(self, timeout=60):
        """
        Wait for the Postgres container to be available (or timeout) before
        returning
        """
        if not wait_for(self.available, timeout=timeout):
            raise ProviderNotAvailable(
                "Provider '{}'' unavailable after {} seconds".format(
                    self.__class__.__name__, timeout
                )
            )

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

    @classmethod
    def container(cls, application_id):
        """
        PostgreSQL provided by a container.
        """

        user = re.sub('[^a-z]', '_', application_id)
        container = ensure_container(
            image=cls.CONTAINER_IMAGE,
            port=cls.DEFAULT_PORT,
            application_id=application_id,
            data_dir='/data',
            environment={
                'USER': user,
                'DB': user,
                'PASS': user,
            }
        )

        instance = cls(
            host='localhost',
            name=user,
            user=user,
            password=user,
            port=container.port,
        )
        instance.wait_until_available()
        return instance

    providers = ('localhost', 'container')


@register('postgis')
class PostGIS(PostgreSQL):
    """
    PostgreSQL database with PostGIS support.
    """

    CHECK_COMMAND = """CREATE EXTENSION IF NOT EXISTS postgis;
                       SELECT PostGIS_full_version()"""
    CONTAINER_IMAGE = 'thatpanda/postgis'
    URL_SCHEME = 'postgis'

    providers = ('localhost', 'container')
