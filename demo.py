#!/usr/bin/env python

# Python 3.2 or later, because of tempfile.TemporaryDirectory
from sys import exit, version_info
if ((version_info[0] < 3) or
    ((version_info[0] == 3) and (version_info[1] < 2))
):
    print('This script requires Python 3.2 or later!')
    exit(1)


from syncrepl_client import Syncrepl
from syncrepl_client.callbacks import LoggingCallback
from sys import argv
from tempfile import TemporaryDirectory


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
         )
client.debug = True
print('CLIENT SETUP COMPLETE!')

while True:
    print('CLIENT LOOP START')
    loop_result = client.loop()
    print('CLIENT LOOP END')
    print("\tLoop Result:", loop_result)
    if loop_result is False:
        print('CLIENT LOOP COMPLETE!')
        break

print('CLIENT EXIT START')
client.unbind()
print('CLIENT EXIT COMPLETE!')
