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


from setuptools import setup, find_packages
from syncrepl_client import __version__
from sys import version_info


# Our requirements depend on the Python version
if ((version_info[0] == 2) and
    (version_info[1] == 7)
):
    install_requires = [
        'enum34',
        'python-ldap(>2.4.40)'
    ]
elif ((version_info[0] == 3) and
      (version_info[1] >= 4)
):
    install_requires = [
        'pyldap(>2.4.40)'
    ]
elif ((version_info[0] == 3) and
      (version_info[1] >= 1)
):
    install_requires = [
        'enum34',
        'pyldap(>2.4.40)'
    ]
else:
    raise OSError('Python 2.7, 3.1, or later is required!')


# Let setup handle the rest

setup(
    version = __version__,

    name = 'syncrepl-client',
    description = 'An easier-to-use LDAP syncrepl client',

    author = 'A. Karl Kornel',
    author_email = 'karl@kornel.us',

    url = 'http://github.com/akkornel/syncrepl',

    packages = find_packages(),

    install_requires = install_requires,

    license = 'BSD 3-Clause',

    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: System :: Systems Administration :: Authentication/Directory :: LDAP'
    ]
)
