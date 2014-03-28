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

import os
import pwd
import socket
import subprocess
import sys
import time
import yaml

from xdg.BaseDirectory import xdg_config_home


from forklift.base import application_id, DEVNULL, ImproperlyConfigured
import forklift.drivers
import forklift.services


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
        'postgres': forklift.services.PostgreSQLService,
        'postgis': forklift.services.PostGISService,
        'elasticsearch': forklift.services.ElasticsearchService,
        'proxy': forklift.services.ProxyService,
        'email': forklift.services.EmailService,
        'syslog': forklift.services.SyslogService,
    }

    drivers = {
        'direct': forklift.drivers.Direct,
        'docker': forklift.drivers.Docker,
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
        try:
            subprocess.check_call(['pandoc', '-v'],
                                  stdout=DEVNULL, stderr=DEVNULL)
            pager = 'pandoc -s -f markdown -t man | man -l -'
        except OSError:
            pager = os.environ.get('PAGER', 'more')

        process = subprocess.Popen(pager, shell=True, stdin=subprocess.PIPE)
        process.communicate(input=readme.read())
        readme.close()
        process.wait()

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
