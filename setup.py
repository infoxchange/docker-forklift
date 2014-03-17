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
Setup script.
"""

from setuptools import setup, find_packages

setup(
    name='forklift',
    version='0.2',
    description='Utility for running a container',
    author='Infoxchange Australia development team',
    author_email='devs@infoxchange.net.au',
    url='https://github.com/infoxchange/docker-forklift',
    license='MIT',
    long_description=open('README.md').read(),
    packages=find_packages(),
    scripts=['forklift'],
    install_requires=[
        'pyxdg',
        'pyyaml',
    ],
    test_suite='tests',
    tests_require=[
        'pep8',
        'pylint',
        'pylint-mccabe',
    ],
)
