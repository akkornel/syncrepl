#!/usr/bin/env python

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
