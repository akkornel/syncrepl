#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 et

# syncrepl_client installer code.
#
# Refer to the AUTHORS file for copyright statements.
#
# This file contains only factual information.
# Therefore, this file is likely not copyrightable.
# As such, this file is in the public domain.
# For locations where public domain does not exist, this file is licensed
# under the Creative Commons CC0 Public Domain Dedication, the text of which
# may be found in the file `LICENSE_others.md` that was included with this
# distribution, and also at
# https://github.com/akkornel/syncrepl/blob/master/LICENSE_others.md


import re
import setuptools
from setuptools import setup, find_packages
from sys import argv, version_info


# Thanks to https://hynek.me/articles/conditional-python-dependencies/
# for helping me understand the mess that is requirements specifications.

setuptools_under_18 = False
if int(setuptools.__version__.split('.', 1)[0]) < 18:
    setuptools_under_18 = True
install_requirements = list()
extra_requirements = dict()

# Block wheel creation on old setuptools
if ((setuptools_under_18 is True) and
    ('bdist_wheel' in argv)
):
    raise OSError('setuptools is too old to create good wheel files.')

# Make sure we have Python 2.7, or 3.1+
# This is covered again later in the 'python_requires' option, but let's be
# safe.
if ((version_info[0] == 2) and
    (version_info[1] < 7)
):
    raise OSError('With Python 2, Python 2.7 is required.')
if ((version_info[0] == 3) and
    (version_info[1] == 0)
):
    raise OSError('With Python 3, Python 3.1 or later is required.')

# Pythons 3.4 and lower require enum34
if setuptools_under_18 is True:
    if ((version_info[0] == 2) or
        ((version_info[0] == 3) and
         (version_info[1] < 4)
        )
    ):
        install_requirements.append('enum34')
else:
    extra_requirements[":python_version<'3.4'"] = ['enum34']

# Python 2 requires python-ldap; Python 3 requires pyldap
if setuptools_under_18 is True:
    if version_info[0] == 2:
        install_requirements.append('python-ldap')
    else:
        install_requirements.append('pyldap')
else:
    extra_requirements[":python_version<='2.7'"] = ['python-ldap>=2.4.40']
    extra_requirements[":python_version>='3.1'"] = ['pyldap>=2.4.35.1']



# Have code pull the version number from _version.py
def version():
    with open('syncrepl_client/_version.py') as file:
        regex = r"^__version__ = '(.+)'$"
        matches = re.search(regex, file.read(), re.M)
        if matches:
            return matches.group(1)
        else:
            raise LookupError('Unable to find version number')


# Have code pull the long description from our README
def readme():
    with open('README.rst') as file:
        return file.read()


# Let setuptools handle the rest
setup(
    name = 'syncrepl-client',
    version = version(),
    description = 'An easier-to-use LDAP syncrepl client',
    long_description = readme(),

    keywords = 'ldap syncrepl',

    author = 'A. Karl Kornel',
    author_email = 'karl@kornel.us',

    url = 'http://github.com/akkornel/syncrepl',

    packages = find_packages(),
    zip_safe = True,
    include_package_data = True,

    python_requires = '>=2.7,!=3.0.*',
    install_requires = install_requirements,
    extras_require = extra_requirements,
    provides = ['syncrepl_client'],

    license = 'BSD 3-Clause',

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: System :: Systems Administration :: Authentication/Directory :: LDAP'
    ]
)
