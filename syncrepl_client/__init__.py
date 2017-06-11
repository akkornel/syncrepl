#!/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# syncrepl_client main code.
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


# For Python 2 support
from __future__ import print_function

from enum import Enum
import ldap
from ldap.ldapobject import SimpleLDAPObject
from ldap.syncrepl import SyncreplConsumer
import ldapurl
import shelve
import signal
from sys import argv, exit, version_info
import threading

from . import exceptions

__version__ = '0.81'

class SyncreplMode(Enum):
    """
    This enumeration is used to specify the operating mode for the Syncrepl
    client.  Once a mode is set it can not be changed.  To change the mode, you
    will have to (safely) shut down your existing search, unbind and destroy
    the existing instance, and start a new instance in the new mode.
    """

    REFRESH_ONLY = 'refreshOnly'
    """
    In this mode, the syncrepl search will last long enough to bring you in
    sync with the server.  Once you are in sync,
    :meth:`~syncrepl_client.Syncrepl.poll()` will return :obj:`False`.
    """
    
    REFRESH_AND_PERSIST = 'refreshAndPersist'
    """
    In this mode, you start out doing a refresh.  Once the refresh is complete,
    subsequent calls to :meth:`~syncrepl_client.Syncrepl.poll` will be used to
    receive changes as they happen on the LDAP server.  All calls to
    :meth:`~syncrepl_client.Syncrepl.poll()` will return :obj:`True`, unless a
    timeout takes place (that will throw :class:`ldap.TIMEOUT`), you cancel the
    search (that will throw :class:`ldap.CANCELLED`), or something else goes
    wrong.
    """


class Syncrepl(SyncreplConsumer, SimpleLDAPObject, threading.Thread):
    '''
    This class implements the Syncrepl client.  You should have one instance of
    this class for each syncrepl search.

    Each class requires several items, which will be discussed here:

    * **A data store**
      
      The Syncrepl client stores a copy of all LDAP records returned by the
      LDAP server.  This data is stored on disk to speed up synchronization if
      the client loses connection to the LDAP server (either intentionally or
      not).
      
      The Syncrepl class writes to several files, so the class will be given a
      `data_path`.  To come up with the actual file paths, we concatenate
      `data_path` and our file name.  For that reason, `data_path` should
      normally end with a slash (forward or back, depending on OS), to keep our
      data files in its own directory.
    
      The data store files should be deleted any time you want a completely
      fresh start.  The data store files will also be wiped any time the
      syncrepl_client software version changes.

      .. warning::

        Data store files are also not compatible between Python 2 and Python 3.
        Attempting to use a data store from Python 2 with Python 3—or vice
        versa—will likely trigger an exception during instantiation.

    * **A callback class**
      
      The callback class is an object (a class, or an instance).  The callback
      class' methods are called when the Syncrepl client receives updates.

      The complete list of callback methods is documented in
      :class:`~syncrepl_client.callbacks.BaseCallback`.  That class is designed
      for subclassing, because it defines each callback method but doesn't
      actually do anything.  You can have your class inherit from
      :class:`~syncrepl_client.callbacks.BaseCallback`, and let it handle the
      callbacks that you don't care about.

      For a simple example of a callback in action, see the code for the
      :class:`~syncrepl_client.callbacks.LoggingCallback` class.

    * **An LDAP URL**
      
      The LDAP URL contains all information about how the Syncrepl client
      should connect, what credentials should be used to connect, and how the
      search should be performed.

      The :class:`~ldapurl.LDAPUrl` class is used to parse the LDAP URL.  You
      can also use :manpage:`ldapurl` (part of the ldap-utils) to construct a
      URL.  Refer to the class' documentation for information on the fields
      available.

      If a valid data store exists, this field is optional: the URL your
      provide will be stored in the data store, which will be used in
      subsequent connections.  If you provide both an LDAP URL *and* a valid
      data store, your LDAP URL will be used, *as long as* the search
      parameters have not changed (the LDAP host and authentication information
      are OK to change).

      syncrepl_client supports the following bind methods, which you control by
      using particular LDAP URL extensions:

      * *Anonymous bind*: Do not set a bind DN or password.
      
      * *Simple bind*: Set the bind DN and password as part of the URL.

        The `bindname` LDAP URL extension is used to hold the bind DN, and the
        `X-BINDPW` extension is used to hold the bind password.

        .. note::
          For security, it is suggested that you store the LDAP URL without a
          password, convert the URL into an :class:`ldapurl.LDAPUrl` object at
          runtime, add the password, and pass the password-laden object to the
          :class:`~syncrepl_client.Syncrepl` constructor.

      * *GSSAPI bind*: Set the bind DN to `GSSAPI`, and do not set a password.

        .. note::
          You are responsible for ensuring that you have valid Kerberos
          credentials.

        As an extra safety mechanism, when you receive the
        :meth:`~syncrepl_client.callbacks.BaseCallback.bind_complete`
        callback, consider doing a "Who am I?" check against the LDAP server,
        to make sure the bind DN is what you expected.  That will help guard
        against expired or unexpected credentials.

    Methods are defined below.  Almost all methods are documented, including
    internal methods.
    
    .. warning::
      Methods whose names start with `syncrepl_` are internal
      methods, which clients **must not call**.  That being said, the methods
      are still being documented here, for educational purposes.
    '''

    def __init__(self, data_path, callback, mode, ldap_url=None, **kwargs):
        """Instantiate, connect to an LDAP server, and bind.

        :param str data_path: A path to where data files will be stored.

        :param object callback: An object that receives callbacks.

        :param mode: The syncrepl search mode to use.

        :type mode: A member of the :class:`~syncrepl_client.SyncreplMode` enumeration.

        :param ldap_url: A complete LDAP URL string, or an LDAPUrl instance, or None.

        :type ldap_url: str or ldapurl.LDAPUrl or None

        :returns: A Syncrepl instance.

        This is the :class:`~syncrepl_client.Syncrepl` class's constructor.  In
        addition to basic initialization, it is also responsible for making the
        initial connection to the LDAP server, binding, and starting the
        syncrepl search.

        .. note::

            Many parts of this documentation refers to syncrepl as a "search".
            That is because a syncrepl is initiated using an LDAP search
            operation, to which a syncrepl control is attached.

        - `data_path` is used to specify the prefix for the path to data
          storage.  :class:`~syncrepl_client.Syncrepl` will open multiple
          files, whose names will be appended to :obj:`data_path`.  You are
          responsible for making sure that :obj:`data_path` is appropriate for
          your OS.

          .. note::

              Some basic checks may be performed on the data files.  If you use
              a different version of software, those checks will fail, and the
              contents will be wiped.

        - :obj:`callback` can be anything which can receive method calls, and
          which is specifically able to handle the calls defined in
          :class:`~syncrepl_client.callbacks.BaseCallback`.

        - :obj:`mode` should be one of the values from
          :class:`~syncrepl_client.SyncreplMode`.
          :attr:`~syncrepl_client.SyncreplMode.REFRESH_ONLY` means that you
          want the syncrepl search to end once your have been brought in sync
          with the LDAP server.
          :attr:`~syncrepl_client.SyncreplMode.REFRESH_AND_PERSIST` means that,
          after being refreshed, you will receive notice whenever a change is
          made on the LDAP server.

        - :obj:`ldap_url` is an LDAP URL, containing at least the following
          information:

          - The LDAP protocol (`ldap`, `ldaps`, or `ldapi`).

          - The base DN to search, and the search scope.

          All other LDAP URL fields are recognized.  The `bindname` LDAP URL
          extension may be used to specify a bind DN (or "GSSAPI" for GSSAPI
          bind).  When using simple bind, the `X-BINDPW` extension must hold
          the bind password.

        The `bind_complete()` callback will be called at some point during the
        constructor's execution.

        Returns a ready-to-use instance.  The next call you should make to the
        instance is :meth:`~syncrepl_client.Syncrepl.poll`.  Continue calling
        :meth:`~syncrepl_client.Syncrepl.poll` until it returns :obj:`False`;
        then you should call :meth:`~syncrepl_client.Syncrepl.unbind`.  To
        request safe teardown of the connection, call
        :meth:`~syncrepl_client.Syncrepl.please_stop`.
        """

        # Set up the thread
        threading.Thread.__init__(self)

        # Set some instanace veriables.
        self.__in_refresh = True
        self.__present_uuids = []
        self.deleted = False

        # Set up please_stop with a lock
        self.__please_stop = False
        self.__please_stop_lock = threading.Lock()

        # TODO: Make sure callback is a subclass or subclass instance.
        self.callback = callback

        # Check that we have a valid mode
        assert(isinstance(mode, SyncreplMode))

        # Open our shelves
        try:
            self.__data = shelve.open(data_path + 'data', writeback=True)
            self.__uuid_dn_map = shelve.open(data_path + 'uuid_map', writeback=True)
            self.__dn_uuid_map = shelve.open(data_path + 'dn_map', writeback=True)
            self.__uuid_attrs = shelve.open(data_path + 'attrs', writeback=True)
        except:
            # It's likely a shelf had a problem opening, so recreate them all.
            self.__data = shelve.open(data_path + 'data',
                flag='n',
                writeback=True
            )
            self.__uuid_dn_map = shelve.open(data_path + 'uuid_map',
                flag='n',
                writeback=True
            )
            self.__dn_uuid_map = shelve.open(data_path + 'dn_map',
                flag='n',
                writeback=True
            )
            self.__uuid_attrs = shelve.open(data_path + 'attrs',
                flag='n',
                writeback=True
            )

        # Check the Python version for a mismatch.
        # If the major or minor numbers differ, then prepare to wipe
        # everything.
        if (('version' in self.__data) and
            ('pyversion' not in self.__data)
        ):
            del self.__data['version']

        if (('version' in self.__data) and
            ('pyversion' in self.__data) and
            ((self.__data['pyversion'][0] != version_info.major) or
             (self.__data['pyversion'][1] != version_info.minor)
            )
        ):
            del self.__data['version']

        # Check the data file version for a mismatch.  If we find one, then
        # prepare to wipe everything.
        if (('version' in self.__data) and
                (self.__data['version'] != __version__)):
            del self.__data['version']

        # If no version is defined, set it and clear everything else.
        if 'version' not in self.__data:
            # Try to grab the URL, if it exists.
            if (('url' in self.__data) and
                (ldap_url is None)
            ):
                # This fetch might fail, which is OK.
                try:
                    ldap_url = self.__data['url']
                except:
                    pass

            # Calling .clear() might not work, because of version changes.
            # It might be amazing that we even got this far.
            # So, close and re-create all shelves.
            self.__data.close()
            self.__data = shelve.open(data_path + 'data',
                flag='n',
                writeback=True
            )
            self.__uuid_dn_map.close()
            self.__uuid_dn_map = shelve.open(data_path + 'uuid_map',
                flag='n',
                writeback=True
            )
            self.__dn_uuid_map.close()
            self.__dn_uuid_map = shelve.open(data_path + 'dn_map',
                flag='n',
                writeback=True
            )
            self.__uuid_attrs.close()
            self.__uuid_attrs = shelve.open(data_path + 'attrs',
                flag='n',
                writeback=True
            )

            # Set version and sync
            self.__data['version'] = __version__
            self.__data['pyversion'] = tuple(version_info)
            self.sync()

        # If ldap_url exists, and isn't an object, then convert it
        if ((ldap_url is not None) and (type(ldap_url) is not ldapurl.LDAPUrl)):
            try:
                ldap_url = ldapurl.LDAPUrl(ldap_url)
            except:
                raise ValueError

        # If no ldap_url was provided, pull from state.
        if ldap_url is None:
            if 'url' not in self.__data:
                raise ValueError
            ldap_url = self.__data['url']

        # Check if someone's trying to change the existing LDAP URL.
        if (('url' in self.__data) and
            (self.__data['url'] != ldap_url)
        ):
            current_url = self.__data['url']
            new_url = ldap_url

            # If the stored URL doesn't match the passed URL,
            # _and_ one of our invariant attributes is different, fail.
            if ((current_url.dn != new_url.dn) or
                (current_url.attrs != new_url.attrs) or
                (current_url.scope != new_url.scope) or
                (current_url.filterstr != new_url.filterstr)
               ):
                raise LDAPUrlError

            # We allow changes to other attributes (like host, who, and cred)
            # even though they may cause weird search result changes (for
            # example, due to differing ACLs between accounts).

            # Since we haven't thrown, allow the new URL.
            self.__data['url'] = new_url

        # Finally, we can set up our LDAP client!
        SimpleLDAPObject.__init__(self, ldap_url.unparse(), **kwargs)

        # Bind to the server (this also triggers connection setup)
        if ldap_url.who is None:
            print('Doing anonymous bind...')
            self.simple_bind_s()
        elif ldap_url.who == 'GSSAPI':
            import ldap.sasl
            sasl_bind = ldap.sasl.gssapi()
            self.sasl_interactive_bind_s('',sasl_bind)
        else:
            print('Doing simple bind...')
            self.simple_bind_s(who=ldap_url.who, cred=ldap_url.cred)

        # Callback to mark a successful bind.
        self.callback.bind_complete(self)

        # Before we start, we have to check if a filter was set.  If not, set the
        # default that the LDAP module uses.
        if ldap_url.filterstr is None:
            ldap_url.filterstr = '(objectClass=*)'

        # Prepare the search
        self.ldap_object_search = self.syncrepl_search(ldap_url.dn, ldap_url.scope,
            mode=mode.value,
            filterstr=ldap_url.filterstr,
            attrlist=ldap_url.attrs
        )

        # All done!
        return None


    def __enter__(self):
        # Required for the context-manager protocol, but we don't do anything
        # that the constructor doesn't do already.
        pass


    def __exit__(self, exception_type, value, traceback):
        # If we got an exception, let it raise.
        if exception_type is not None:
            return False

        # Otherwise, unbind
        return self.unbind()


    def unbind(self):
        """Safely save state and disconnect from the LDAP server.

        :returns: None

        If you have instantiated this object on your own, call `unbind` to
        ensure that all data files are flushed to disk, and the LDAP server
        connection is properly closed.

        .. warning::

          If you are using the Context Manager protocol, *do not call `unbind`*;
          it will be called for you at the appropriate time.

        .. warning::

          Not all Python implementations delete objects at the same point in
          their code.  PyPy, in particular, is very different.  Do not rely on
          assumptions about garbage collection!

        Once unbound, this instance is no longer usable, even if it hasn't been
        deleted yet.  To start a new client, make a new instance of
        :class:`~syncrepl_client.Syncrepl`.
        """
        self.__uuid_dn_map.close()
        self.__dn_uuid_map.close()
        self.__uuid_attrs.close()
        self.__data.close()
        self.deleted = True
        return SimpleLDAPObject.unbind(self)


    def __del__(self):
        # Last-resort attempt to make sure things are cleaned up.
        if self.deleted is not True:
            return self.unbind()


    def please_stop(self):
        """Requests the safe termination of a Syncrepl search.

        :returns: None.

        After calling this method, there is a set list of steps your code
        should take:

        1. Continue calling :meth:`~syncrepl_client.Syncrepl.poll` until it
           returns :obj:`False`.

        2. Call :meth:`~syncrepl_client.Syncrepl.unbind` (unless you're using
           the Context Management protocol).

        3. Stop using this instance.

        When running in refresh-only mode, this does nothing: Interrupting a
        refresh is dangerous, because there is no guarantee that the updates
        from the LDAP server are being received in any particular order.  The
        refresh will be allowed to complete, and then it is safe to stop. 

        When running in refresh-and-persist mode, if the refresh phase is still
        in progress, it will be completed.  If in the persist phase, a Cancel
        request will be sent to the LDAP server.  Operations will then continue
        until the LDAP server confirms the search is cancelled.

        This is the *only* method which is thread-safe.
        """

        self.__please_stop_lock.acquire()
        self.__please_stop = True
        self.__please_stop_lock.release()
        return None


    def poll(self):
        """Poll the LDAP server for changes.

        :returns: True or False.

        In refresh-only mode, returning :obj:`True` indicates that the refresh
        is still in progress.  You must continue calling
        :meth:`~syncrepl_client.Syncrepl.poll` until :obj:`False` is returned.
        Once :obj:`False` is returned, the refresh is complete, and it is safe
        to call :meth:`~syncrepl_client.Syncrepl.unbind`.

        In refresh-and-persist mode, returning :obj:`True` only indicates that
        the connection is still active: Work might or might not be taking
        place.  The
        :meth:`~syncrepl_client.callbacks.BaseCallback.refresh_done` callback
        is used to indicate the completion of the refresh phase and the start
        of the persist phase.  During the refresh phase, when the connection is
        idle, :meth:`~syncrepl_client.Syncrepl.poll` will return :obj:`True`
        every ~3 seconds.  This is for single-process applications.

        Most callbacks will be made during the execution of
        :meth:`~syncrepl_client.Syncrepl.poll`.

        .. warning::

          Just because :meth:`~syncrepl_client.Syncrepl.poll` has returned,
          does not mean that you are in sync with the LDAP server.  You must
          continue calling :meth:`~syncrepl_client.Syncrepl.poll` until it
          returns :obj:`False`.

          To request safe, consistent teardown of the connection, call
          :meth:`~syncrepl_client.Syncrepl.please_stop`.
        """

        # Make sure we aren't running on a closed object.
        if self.deleted:
            raise ReferenceError

        # We default poll_output to True because, if the poll times out, that
        # causes an exception (so the variable doesn't get set).
        poll_output = True
        try:
            poll_output = self.syncrepl_poll(msgid=self.ldap_object_search,
                    all=1, timeout=3)
        # Timeout exceptions are totally OK, and should be ignored.
        except ldap.TIMEOUT:
            pass

        # Cancelled exceptions _should_ be OK, as long as `please_stop()` has
        # previously been called.
        except ldap.CANCELLED:
            self.__please_stop_lock.acquire()
            please_stop_value = self.__please_stop
            self.__please_stop_lock.release()
            if please_stop_value is False:
                raise ldap.CANCELLED
            else:
                # Before returning, do a forced sync
                self.sync(force=True)
                return False

        # All other exceptions are real, and aren't caught.

        # If poll_output was False, then we're done, but done with what?
        # If we're in refresh-only mode, call syncrepl_refreshdone()
        # (That will also sync for us.)
        # If we're in refresh-and-persist mode, then just sync.
        if poll_output is False:
            if self.__in_refresh is True:
                self.syncrepl_refreshdone()
            else:
                self.sync(force=True)
            return poll_output

        # Check if we have been asked to stop.  If we have, send a cancellation.
        self.__please_stop_lock.acquire()
        if self.__please_stop:
            self.cancel(self.ldap_object_search)
        self.__please_stop_lock.release()

        # Return.  The client will have to continue polling until the LDAP
        # server is done with us.
        return poll_output


    def sync(self, force=False):
        """Sync the data store to storage.

        :param bool force: Force sync even in refresh mode.

        :returns: None

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        For performance, the data store is kept in memory, and is only synced
        to disk in certain cases.  Those cases are:

        * When an instance is unbound.

        * When a change happens in the persist phase of refresh-and-persist
          mode.

        In refresh mode, the data store is not synced to disk until the refresh
        is complete.  This is done because consistency is not guaranteed in the
        middle of a refresh phase.

        You normally never need to call this yourself; it is called for you,
        typically as soon as your callback completes.
        """
        if ((force is True) or
            (self.__in_refresh is False)
        ):
            self.__data.sync()
            self.__uuid_dn_map.sync()
            self.__dn_uuid_map.sync()
            self.__uuid_attrs.sync()


    def syncrepl_get_cookie(self):
        """Get Syncrepl cookie from data store.

        :returns: bytes or None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        Called at the start of the syncrepl operation, to load a cookie from
        state.  If present and valid, the LDAP server will know how far behind
        we are.

        If not present, or invalid (typically because it's too old), the LDAP
        server will start us over, as if we were a new client.


        """
        if 'cookie' in self.__data:
            return self.__data['cookie']
        else:
            return None


    def syncrepl_set_cookie(self, cookie):
        """Store Syncrepl cookie in data store.

        :param bytes cookie: An opaque string.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        Called regularly during syncrepl operations, to store a "cookie" from
        the LDAP server.  This cookie is presented to the LDAP server when we
        reconnect, so that it knows how far behind we are.
        """
        self.__data['cookie'] = cookie
        self.sync()


    def syncrepl_refreshdone(self):
        """Mark the transition from the refresh phase to the persist phase.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        This is called when we moving from the Refresh mode into the Persist
        mode of refresh-and-persist.  This is not called in refresh-only mode.

        Triggers a :meth:`~syncrepl_client.callbacks.BaseCallback.refresh_done`
        callback.
        """

        # Besides doing a callback, we update an internal tracking variable,
        # and we delete our list of present items (that's only used in the
        # Refresh mode).
        self.callback.refresh_done()
        self.__in_refresh = False
        del self.__present_uuids
        self.sync()


    def syncrepl_delete(self, uuids):
        """Report deletion of an LDAP entry.

        :param uuids: List of UUIDs to delete.

        :type uuids: List of binary.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        Called when one or more entries have been deleted, *or* have changed
        such that they are no longer in our search results.

        The one parameter is a list of UUIDs, which we should already know
        about.

        Triggers a
        :meth:`~syncrepl_client.callbacks.BaseCallback.record_delete` callback
        for each UUID.
        """
        for uuid in uuids:
            if not uuid in self.__uuid_dn_map:
                raise RuntimeError('WARNING: Trying to delete uuid', uuid, 'not in map!')
            self.callback.record_delete(self.__uuid_dn_map[uuid])
            del self.__dn_uuid_map[self.__uuid_dn_map[uuid]]
            del self.__uuid_dn_map[uuid]
            del self.__uuid_attrs[uuid]
            self.sync()


    def syncrepl_present(self, uuids, refreshDeletes=False):
        """Indicate the presence or absence of an LDAP entry.

        :param uuids: List of UUIDs present or absent.

        :type uuids: List of bytes, or None.

        :param boolean refreshDeletes: Indicates presence or absence.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        This function is used in refresh-only syncrepl, and in the refresh
        phase of refresh-and-persist syncrepl.  It is *not* used in the persist
        phase.

        As part of the syncrepl process, we get a big list of UUIDs and their
        DNs (plus attributes), from which we build a mapping (see
        :meth:`~syncrepl_client.Syncrepl.syncrepl_entry`, below).  The first
        time a sync takes place (when there is no valid cookie), you are able
        to assume that every mapping entry received is present in the
        directory; but in subsequent syncs (using a valid cookie) you can't be
        sure which entries are present and which have been deleted.  In
        addition, if you have a cookie that is now too old, there is no way to
        know which entries in your data store still exist in the directory.
        
        The "Present" messages, and the resulting calls, are used to bring us
        back in sync with the Directory, regardless of our local state.

        `uuids` is either a list of UUIDs, or :obj:`None`.  `refreshDeletes` is
        a boolean.  To understand how the two parameters are related, it's
        better to look at the latter parameter first.

        * If `refreshDeletes` is :obj:`False`, and `uuids` is a list, then
          `uuids` contains a list of entries that are currently in the
          directory.

        * If `refreshDeletes` is :obj:`False`, but `uuids` is :obj:`None`, then
          we are almost synced.  We now need to go into our mapping, and remove
          all entries that were not previously mentioned as being in the
          directory.

        * If `refreshDeletes` is :obj:`True`, and we have a list, then `uuids`
          contains entries that used to be in the directory, but are now gone.

        * If `refreshDeletes` is :obj:`True`, but `uuids` is :obj:`None`, then
          we are synced: Our current mapping of UUIDs, minus those previously
          deleted, represents the current state of the directory.

        Here is another way to think about it: The LDAP server needs to work out
        the most efficient way of relaying changes to us.  There are three ways
        of telling us what has changed:

        * "The following entries are in the directory; everything else you knew
          about has been deleted."

          This is the easiest way of informing us of changes and deletions.

          In this mode, you will receive:

          - Calls where `uuids` is a list and `refreshDeletes` is :obj:`False`.

          - A call where `uuids` is :obj:`None` and `refreshDeletes` is
            :obj:`False`.

        * "The following entries are new, and these other entries have been
          deleted, but everything else you know about is still in the
          directory."

          This is the mode that is used when, since your last checkin, there
          have been alot of additions and deletions.

          In this mode, you will receive:

          - Calls where `uuids` is a list and `refreshDeletes` is :obj:`False`.

          - Calls where `uuids` is a list and `refreshDeletes` is :obj:`True`.

          - A call where uuids` is :obj:`None` and `refreshDeletes` is
            :obj:`True`.

        * "Everything is up-to-date and there are no changes."

          When things are quiet, this is the mode that is used.

          In this mode, you wil receive:

          - A call where `uuids` is :obj:`None` and `refreshDeletes` is
            :obj:`True`.

        The LDAP server chooses which mode to use when we connect and present a
        valid cookie.  If we don't have a valid cookie, then the LDAP server
        falls back to mode A.
        """

        if ((uuids is not None) and (refreshDeletes is False)):
            # We have a list of items which are present in the directory.
            # Update our tracking list.
            self.__present_uuids.extend(uuids)

            # No need for a callback, because we already did that for each
            # entry received.

        elif ((uuids is None) and (refreshDeletes is False)):
            # We're almost at the end of the refresh.  Every entry that we have in
            # state, but that didn't get a "present" message, has been deleted!
            deleted_uuids = []
            for uuid in self.__uuid_dn_map.keys():
                if uuid in self.__present_uuids:
                    next
                else:
                    deleted_uuids.append(uuid)

            # We've built up a list of things to delete.
            # If there's anything in the list, then call the code to delete stuff.
            # `syncrepl_delete` will handle the callbacks.
            if len(deleted_uuids) > 0:
                self.syncrepl_delete(deleted_uuids)

        elif ((uuids is not None) and (refreshDeletes is True)):
            # We have a list of items to delete.
            # `syncrepl_delete` will handle the callbacks.
            self.syncrepl_delete(uuids)

        elif ((uuids is None) and (refreshDeletes is True)):
            # We're almsot at the end of the refresh.  There's nothing else to
            # do!
            pass


    def syncrepl_entry(self, dn, attrs, uuid):
        """Report addition or modification of an LDAP entry.

        :param str dn: The DN of the entry.

        :param attrs: The entry's attributes.

        :type attrs: Dict of List of bytes.

        :param bytes uuid: The entry's UUID.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        This function is called to add entries to a map of UUIDs to
        DN/attribute-list pairs.  It is also used to change an existing DN: In
        that case, the UUID matches an existing entry, but the DN is different.

        DNs are not static - they can change.  That's a problem when you are
        trying to track changes over time.  To deal with that, the LDAP server
        assigns each entry a UUID.  We then maintain a mapping of UUIDs to DNs,
        because all future syncrepl-related calls will refernce UUIDs instead
        of DNs.

        In refresh-only sync, and in the refresh phase of refresh-and-persist
        syncrepl, this method is called multiple times, interspersed with calls
        to :meth:`~syncrepl_client.Syncrepl.syncrepl_present`.  If a valid
        cookie was provided, the server will only send new/changed entries
        since our last checkin; otherwise, we'll get a big list of entries—all
        of which will be present—to seed our mapping.

        In refresh-and-persist mode, everything from the previous paragraph is
        true, but when in the persist phase (once the refresh phase has
        completed) we should expect to be called at random times as the server
        sends us updates to our mapping.

        The set of attributes is the intersection of three sets:

        * The populated attributes of a particular entry.

        * The attributes you are allowed to see.

        * The attributes you requested in your search.

        All attribute entries are lists of binary strings.  Lists are used
        throughout because the LDAP client does not know which attributes are
        multi-valued, and binary strings are used because the LDAP client does
        not know each attribute's syntax.  The client is responsible for
        knowing the directory's schema, and casting/converting values
        appropriately.
        """

        # Check if the UUID is in our map.
        if uuid in self.__uuid_dn_map:
            # We already have this UUID, so the DN and/or attributes have changed.

            # Check first for DN change.
            if self.__uuid_dn_map[uuid] != dn:
                # Is there already a DN in the map???
                if dn in self.__dn_uuid_map:
                    # Our new DN is already in the map!  That means a deletion
                    # happened at some point in the past, but we missed it.
                    # We need to completely delete the "old" entry;
                    # only then can we continue with the rename.
                    self.syncrepl_delete(self.__dn_uuid_map[dn])

                # At this point, the new DN is clear to occupy.
                # Let the client know about the rename.
                self.callback.record_rename(self.__uuid_dn_map[uuid], dn)

                # Now delete the old DN-UUID map entry, and update both maps.
                del self.__dn_uuid_map[__uuid_dn_map[uuid]]
                self.__dn_uuid_map[dn] = uuid
                self.__uuid_dn_map[uuid] = dn

            # Besides the DN change, other attributes may also have changed.
            # In fact, since the DN is basically (key attr) + (base DN), we
            # know that at least the key attribute changed!

            # Do a callback, then update our record.
            self.callback.record_change(dn, self.__uuid_attrs[uuid], attrs)
            self.__uuid_attrs[uuid] = attrs
        else:
            # The UUID is new, so add it!

            # But first, is the DN already in the map???
            if dn in self.__dn_uuid_map:
                # Our new DN is already in the map!  That means a deletion
                # happened at some point in the past, and this is a totally new
                # entry, but we missed that happening.
                # We need to completely delete the old entry, using the old UUID.
                self.syncrepl_delete(self.__dn_uuid_map[dn])

            # Our maps are clear!  Update the map and do the callback.
            self.__uuid_dn_map[uuid] = dn
            self.__dn_uuid_map[dn] = uuid
            self.__uuid_attrs[uuid] = attrs
            self.callback.record_add(dn, attrs)

        # Sync changes
        self.sync()
