#!/usr/bin/env python
# vim: ts=4 sw=4 et

# syncrepl_client demo code.
#
# Refer to the AUTHORS file for copyright statements.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
