#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# syncrepl_client demo code.
#
# Refer to the AUTHORS file for copyright statements.
#
# This file is made available under the terms of the BSD 3-Clause License,
# the text of which may be found in the file `LICENSE.md` that was included
# with this distribution, and also at
# https://github.com/akkornel/syncrepl/blob/master/LICENSE.md 
#
# The Python docstrings contained in this file are also made available under the terms
# of the Creative Commons Attribution-ShareAlike 4.0 International Public License,
# the text of which may be found in the file `LICENSE_others.md` that was included
# with this distribution, and also at
# https://github.com/akkornel/syncrepl/blob/master/LICENSE_others.md
#


from syncrepl_client import Syncrepl, SyncreplMode
from syncrepl_client.callbacks import LoggingCallback
from sys import argv, exit


if len(argv) == 1:
    print('You must provide an LDAP URL as an argument!')
    exit(1)

if len(argv) == 2:
    print('You must provide a temporary path prefix!')
    exit(1)

tempdir = argv[2]
print('Temporary Directory:', tempdir)

print('CLIENT SETUP START')
client = Syncrepl(data_path=tempdir,
                  callback=LoggingCallback,
                  ldap_url=argv[1],
                  mode=SyncreplMode.REFRESH_ONLY
         )
client.debug = True
print('CLIENT SETUP COMPLETE!')

count = 1
while True:
    print('CLIENT LOOP START')
    loop_result = client.poll()
    print('CLIENT LOOP END')
    print("\tLoop Result:", loop_result)
    if loop_result is False:
        print('CLIENT LOOP COMPLETE!')
        break
    count += 1
    if count >= 5:
        print('CALLING PLEASE_STOP')
        client.please_stop()

print('CLIENT EXIT START')
client.unbind()
print('CLIENT EXIT COMPLETE!')
