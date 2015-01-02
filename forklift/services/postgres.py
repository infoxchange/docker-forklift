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
import subprocess

from forklift.base import DEVNULL
from .base import (ProviderNotAvailable,
                   URLNameDescriptor,
                   URLService,
                   register)


LOGGER = logging.getLogger(__name__)


@register('postgres')
class PostgreSQL(URLService):
    """
    PostgreSQL service provided by the host machine.
    """

    CHECK_COMMAND = 'select version()'
    CONTAINER_IMAGE = 'paintedfox/postgresql'
    DATABASE_NAME = 'DEFAULT'
    DEFAULT_PORT = 5432
    URL_SCHEME = 'postgres'

    PERMANENT_AVAILABILITY_ERRORS = (subprocess.CalledProcessError,
                                     OSError)

    allow_override = URLService.allow_override + ('name',)

    name = URLNameDescriptor()

    # pylint:disable=too-many-arguments
    def __init__(self,
                 name,
                 host='localhost',
                 port=DEFAULT_PORT,
                 user=None,
                 password=None):
        super().__init__((
            '{scheme}://{user}{password}@{host}:{port}/{name}'.format(
                scheme=self.URL_SCHEME,
                user=user,
                password=':' + password if password else '',
                host=host,
                port=port,
                name=name,
            ),
        ))

    def environment(self):
        """
        The environment needed for the application to connect to PostgreSQL.
        """

        env_name = 'DB_{0}_URL'.format(self.DATABASE_NAME)
        return {env_name: self.urls[0].geturl()}

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
    def ensure_container(cls, application_id, **kwargs):
        """
        Pass custom environment to a PostgreSQL container.
        """

        db_name = re.sub(r'[^a-zA-Z0-9_]', '_', application_id)

        kwargs.setdefault('environment', {}).update({
            'DB': db_name,
            'PASS': 'forklift',
        })

        return super().ensure_container(application_id, **kwargs)

    @classmethod
    def from_container(cls, application_id, container):
        """
        PostgreSQL provided by a container.
        """

        db_name = re.sub(r'[^a-zA-Z0-9_]', '_', application_id)

        return cls(
            host=container.host,
            port=container.port,
            name=db_name,
            user='super',
            password='forklift',
        )

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
