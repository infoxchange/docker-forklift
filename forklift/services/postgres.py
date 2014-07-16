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

import logging
import os
import re
import string
import subprocess

from forklift.base import DEVNULL
from .base import (ensure_container,
                   log_service_settings,
                   ProviderNotAvailable,
                   Service,
                   register,
                   transient_provider)


LOGGER = logging.getLogger(__name__)


@register('postgres')
class PostgreSQL(Service):
    """
    PostgreSQL service provided by the host machine.
    """

    CHECK_COMMAND = 'select version()'
    CONTAINER_IMAGE = 'paintedfox/postgresql'
    DATABASE_NAME = 'DEFAULT'
    DEFAULT_PORT = 5432
    URL_SCHEME = 'postgres'

    TEMPORARY_AVAILABILITY_ERRORS = (ProviderNotAvailable,)
    PERMANENT_AVAILABILITY_ERRORS = (ProviderNotAvailable,
                                     subprocess.CalledProcessError,
                                     OSError)

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

        log_service_settings(
            LOGGER, self,
            'name', 'host', 'port', 'name', 'user', 'password'
        )

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

    def check_available(self):
        """
        Check whether PostgreSQL is installed on the host and accessible. Will
        raise ProviderNotAvailable or subprocess.CalledProcessError when
        unavailable
        """

        stderr = ""
        subprocess_kwargs = {
            'stdin': DEVNULL,
            'stdout': DEVNULL,
            'stderr': subprocess.PIPE,
        }

        def get_proc_stderr(proc):
            """
            Safely read data from stderr into a string and return it
            """
            proc_stderr = ""
            for stderr_data in proc.communicate():
                proc_stderr += str(stderr_data)
            proc.wait()
            return proc_stderr

        psql_check_command = ['psql', '--version']
        proc = subprocess.Popen(psql_check_command, **subprocess_kwargs)
        stderr = get_proc_stderr(proc)

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=proc.returncode,
                cmd=' '.join(psql_check_command),
                output=stderr
            )

        if self.password:
            os.environ['PGPASSWORD'] = self.password

        proc = subprocess.Popen([
            'psql',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-w',
            self.name,
            '-c', self.CHECK_COMMAND,
        ], **subprocess_kwargs)
        stderr += get_proc_stderr(proc)

        if proc.returncode != 0:
            raise ProviderNotAvailable(
                ("Provider '{}' is not yet available: psql exited with status "
                 "{}\n{}").format(self.__class__.__name__,
                                  proc.returncode,
                                  stderr)
            )

        return True

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
    @transient_provider
    def container(cls, application_id):
        """
        PostgreSQL provided by a container.
        """

        user = re.sub('[^a-z0-9]', '_', application_id)

        # Postgres DB names can't start with a digit
        if user[0] in string.digits:
            user[0] = ('zero', 'one', 'two', 'three', 'four', 'five', 'six',
                       'seven', 'eight', 'nine')[int(user[0])]

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
        # pylint:disable=attribute-defined-outside-init
        instance.container_info = container
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
