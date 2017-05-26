#!/usr/bin/env python
# vim: sw=4 ts=4 et

# syncrepl_client installer code.
#
# Refer to the AUTHORS file for copyright statements.
#
# This file contains only factual information.
# Therefore, this file is likely not copyrightable.
# As such, this file is in the public domain.
# For locations where public domain does not exist, this file is licensed
# under the Creative Commons CC0 Public Domain Dedication.

from setuptools import setup, find_packages

setup(
    version = '0.75',

    name = 'syncrepl-client',
    description = 'An easier-to-use LDAP syncrepl client',

    author = 'A. Karl Kornel',
    author_email = 'karl@kornel.us',

    url = 'http://github.com/akkornel/syncrepl',

    packages = find_packages(),

    install_requires = [
        'python-ldap(>2.4.38)',
    ],

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
