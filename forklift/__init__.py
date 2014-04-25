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

import argparse
import os
import pwd
import socket
import subprocess
import sys
import time
import yaml
# pylint:disable=no-name-in-module,import-error
from distutils.spawn import find_executable
# pylint:enable=no-name-in-module,import-error

from xdg.BaseDirectory import xdg_config_home


from forklift.arguments import argument_factory, convert_to_args, project_args
from forklift.base import DEVNULL, ImproperlyConfigured
import forklift.drivers
import forklift.services


def create_parser(services, drivers):
    """
    Collect all options from services and drivers in an argparse format.
    """

    parser = argparse.ArgumentParser(
        usage="%(prog)s [options]",
    )
    add_argument = parser.add_argument

    add_argument('--application_id')
    add_argument('--driver', default=None, choices=drivers.keys())
    add_argument('--services', default=[], nargs='*', choices=services.keys())
    add_argument('--environment', default=[], nargs='*',
                 type=lambda pair: pair.split('=', 1))

    for name, service in services.items():
        service.add_arguments(argument_factory(add_argument, name))

    add_argument('command', nargs='+')

    # Drivers inherit all the common options from their base class, so
    # allow conflicts for this group of options
    driver_options = parser.add_argument_group('Driver options')
    driver_options.conflict_handler = 'resolve'
    for name, driver in drivers.items():
        driver.add_arguments(driver_options.add_argument)

    return parser


class Forklift(object):
    """
    The main class.
    """

    services = forklift.services.register
    drivers = forklift.drivers.register

    CONFIG_DIR = os.path.join(xdg_config_home, 'forklift')

    def __init__(self, argv):
        """
        Parse the command line and set up the class.
        """

        # Parse the configuration from:
        # - implicit defaults
        # - project configuration file
        # - user configuration file
        # - user per-project configuration file
        # - command line

        options = self.implicit_configuration()

        for conffile in self.configuration_files():
            options.extend(self.file_configuration(conffile))

        options.extend(argv[1:])

        parser = create_parser(self.services, self.drivers)

        self.conf = parser.parse_args(options)

    def implicit_configuration(self):
        """
        Implicit configuration based on the current directory.
        """

        application_id = os.path.basename(os.path.abspath(os.curdir))
        return [
            '--application_id', application_id,
        ]

    def configuration_files(self):
        """
        A list of configuration files to look for settings in.
        """

        application_id = self.conf.application_id
        return (
            'forklift.yaml',
            os.path.join(self.CONFIG_DIR, '_default.yaml'),
            os.path.join(self.CONFIG_DIR, '{0}.yaml'.format(application_id)),
        )

    def file_configuration(self, name):
        """
        Parse settings from a configuration file.
        """
        try:
            with open(name) as conffile:
                return convert_to_args(yaml.load(conffile))
        except IOError:
            return []

    @staticmethod
    def _readme_stream():
        """
        Get the README file as a stream.
        """

        from pkg_resources import resource_stream
        return resource_stream(__name__, 'README.md')

    def help(self):
        """
        Render the help file.
        """

        readme = self._readme_stream()

        # Try to format the README nicely if Pandoc is installed
        pagers = [
            'pandoc -s -f markdown -t man | man -l -',
            os.environ.get('PAGER', ''),
            'less',
            'more',
        ]

        pager = None

        for pager in pagers:
            if find_executable(pager.split(' ')[0]):
                break

        process = subprocess.Popen(pager, shell=True, stdin=subprocess.PIPE)
        process.communicate(input=readme.read())
        readme.close()
        process.wait()

    def main(self):
        """
        Run the specified application command.
        """

        if self.conf.command == ['help']:
            self.help()
            return 0

        (target, *command) = self.conf.command

        if self.conf.driver:
            driver_name = self.conf.driver
        else:
            for driver_name, driver_class in self.drivers.items():
                if driver_class.valid_target(target):
                    break
            else:
                driver_name = 'docker'
        driver_class = self.drivers[driver_name]

        try:
            services = [
                self.services[service].provide(
                    self.conf.application_id,
                    project_args(self.conf, service)
                )
                for service in self.conf.services
            ]

            environment = dict(self.conf.environment)

            driver = driver_class(
                target=target,
                services=services,
                environment=environment,
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
