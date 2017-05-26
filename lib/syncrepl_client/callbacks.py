#!/usr/bin/env python
# vim: ts=4 sw=4 et

# syncrepl_client callback code.
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

# Python 2 support
from __future__ import print_function

from sys import stdout


class BaseCallback(object):

    @classmethod
    def refresh_done(cls):
        pass

    @classmethod
    def record_add(cls, dn, attrs):
        pass

    @classmethod
    def record_delete(cls, dn):
        pass

    @classmethod
    def record_rename(cls, old_dn, new_dn):
        pass

    @classmethod
    def record_change(cls, dn, old_attrs, new_attrs):
        pass

    @classmethod
    def debug(cls, message):
        pass


class LoggingCallback(BaseCallback):

    dest = stdout

    @classmethod
    def refresh_done(cls):
        print('REFRESH COMPLETE!', file=cls.dest)

    @classmethod
    def record_add(cls, dn, attrs):
        print('NEW RECORD:', dn, file=cls.dest)
        for attr in attrs.keys():
            print("\t", attr, sep='', file=cls.dest)
            for value in attrs[attr]:
                print("\t\t", value, sep='', file=cls.dest)


    @classmethod
    def record_delete(cls, dn):
        print('DELETED RECORD:', dn, file=cls.dest)

    @classmethod
    def record_rename(cls, old_dn, new_dn):
        print('RENAMED RECORD:', file=cls.dest)
        print("\tOld:", old_dn, file=cls.dest)
        print("\tNew:", new_dn, file=cls.dest)

    @classmethod
    def record_change(cls, dn, old_attrs, new_attrs):
        print('RECORD CHANGED:', dn, file=cls.dest)
        for attr in new_attrs.keys():
            print("\t", attr, sep='', file=cls.dest)
            for value in new_attrs[attr]:
                print("\t\t", value, sep='', file=cls.dest)

    @classmethod
    def debug(cls, message):
        print('[DEBUG]', message, file=cls.dest)
