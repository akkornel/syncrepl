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
import signal
import sqlite3
from sys import argv, exit, version_info
try:
    import threading
except ImportError:
    import dummy_threading as threading

# From Python 3.3+, Mapping is in collections.abc.
# In Python 2, and Python ≤ 3.2, Mapping is in collections.
if ((version_info[0] == 3) and (version_info[1] >= 3)):
    from collections.abc import Iterator, Mapping
else:
    from collections import Iterator, Mapping

# Bring in some stuff from this package.
from . import db
from . import exceptions
from . import _version

__version__ = _version.__version__


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

    .. note::
        When running a Syncrepl search in refresh-and-persist mode, it is
        **strongly** recommended that you run the actual search operation in a
        thread, so that you can catch signals which would otherwise cause an
        unclean termination of the Syncrepl search.

        For more information, see the :meth:`~syncrepl_client.Syncrepl.run`
        method, which is what you should use as the thread's target.
    """


class Syncrepl(SyncreplConsumer, SimpleLDAPObject):
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

        :param str data_path: A path to the database file.

        :param object callback: An object that receives callbacks.

        :param mode: The syncrepl search mode to use.

        :type mode: A member of the :class:`~syncrepl_client.SyncreplMode` enumeration.

        :param ldap_url: A complete LDAP URL string, or an LDAPUrl instance, or :obj:`None`.

        :type ldap_url: str or ldapurl.LDAPUrl or None

        :returns: A Syncrepl instance.

        :raises: syncrepl_client.exceptions.VersionError,
        syncrepl_client.exceptions.LDAPUrlError,
        syncrepl_client.exceptions.LDAPUrlConflict,
        sqlite3.OperationalError

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

        The :meth:`~syncrepl_client.callbacks.BaseCallback.bind_complete`
        callback will be called at some point during the constructor's
        execution.

        Returns a ready-to-use instance.  The next call you should make to the
        instance is :meth:`~syncrepl_client.Syncrepl.poll`.  Continue calling
        :meth:`~syncrepl_client.Syncrepl.poll` until it returns :obj:`False`;
        then you should call :meth:`~syncrepl_client.Syncrepl.unbind`.  To
        request safe teardown of the connection, call
        :meth:`~syncrepl_client.Syncrepl.please_stop`.
        """

        # Set some instanace veriables.
        self.__ldap_setup_complete = False
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

        # Connect to (and, if necessary, initialize) our database.
        # We pre-set each variable, so we know what's been done if we have to
        # clean up after an exception.
        self.__db = None
        self.__db = db.DBInterface(data_path)

        # If the versions are missing, then set them now.
        if (    (self.__db.get_setting('syncrepl_version') is None)
            and (self.__db.get_setting('syncrepl_pyversion') is None)
        ):
            self.__db.set_setting('syncrepl_version',
                _version.__version_tuple__
            )
            self.__db.set_setting('syncrepl_pyversion',
                tuple(version_info)
            )

        # Make a small function to compare version tuples.
        def compare_versions(a, b):
            """Compare two version tuples.

            :param tuple a: The left side.

            :param tuple b: The right side.

            :returns: -1 if a<b, zero if a==b, or 1 if a>b.

            .. note::
                Only the first three components are compared.
            """
            # A simple loop over each component
            for i in (0,1,2):
                # Check for difference, fall through to next if the same.
                if a[i]<b[i]:
                    return -1
                elif a[i]>b[i]:
                    return 1
            return 0

        # Check our pyversion, and throw if we're too new.
        db_pyversion = self.__db.get_setting('syncrepl_pyversion')
        db_version = self.__db.get_setting('syncrepl_version')
        if compare_versions(db_pyversion, tuple(version_info)) == 1:
            raise exceptions.VersionError(
                which='python',
                ours=tuple(version_info),
                db=db_pyversion,

            )
        if compare_versions(db_version, _version.__version_tuple__) == 1:
            raise exceptions.VersionError(
                which='syncrepl_client',
                ours=_version.__version_tuple_,
                db=db_version
            )

        # If ldap_url exists, and isn't an object, then convert it
        if ((ldap_url is not None) and (type(ldap_url) is not ldapurl.LDAPUrl)):
            try:
                ldap_url = ldapurl.LDAPUrl(ldap_url)
            except:
                raise exceptions.LDAPURLParseError(ldap_url)

        # Grab the DB-stored URL.  If found, parse.
        db_url = self.__db.get_setting('syncrepl_url')
        if db_url is not None:
            db_url = ldapurl.LDAPUrl(db_url)

        # If we don't have a URL in the database, then store what we were given.
        # If we don't have any URL at all, then throw.
        if db_url is None:
            if ldap_url is None:
                raise exceptions.LDAPUrlError
            self.__db.set_setting('syncrepl_url', str(ldap_url))

        # Check if someone's trying to change the existing LDAP URL.
        if db_url is not None and ldap_url != db_url:
            # Temporary names, for clarity.
            current_url = db_url
            new_url = ldap_url

            # If the stored URL doesn't match the passed URL,
            # _and_ one of our invariant attributes is different, fail.
            if ((current_url.dn != new_url.dn) or
                (current_url.attrs != new_url.attrs) or
                (current_url.scope != new_url.scope) or
                (current_url.filterstr != new_url.filterstr)
               ):
                raise exceptions.LDAPUrlConflict(current_url, new_url)

            # We allow changes to other attributes (like host, who, and cred)
            # even though they may cause weird search result changes (for
            # example, due to differing ACLs between accounts).

            # Since we haven't thrown, allow the new URL.
            self.__db.set_setting('syncrepl_url', str(new_url))

        # Finally, we can set up our LDAP client!
        SimpleLDAPObject.__init__(self, ldap_url.initializeUrl(), **kwargs)

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

        # Commit any settings changes, then do a vacuum.
        self.__db.commit()
        self.__db.execute('PRAGMA optimize')

        # Callback to mark a successful bind.
        self.callback.bind_complete(self, self.__db.cursor())
        self.__ldap_setup_complete = True

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

        # All done!  Commit any client-changed stuff, and return.
        self.__db.commit()
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


    @staticmethod
    def throw_closederror(*args, **kwargs):
        # Special Monkey-Patching method!
        raise exceptions.ClosedError()


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

        # We can't be totally sure that all external stuff is good, so first
        # we make sure that something exists before we close/unbind it.
        if self.__db is not None:
            del(self.__db)
        if self.__ldap_setup_complete is True:
            unbind_result = SimpleLDAPObject.unbind(self)
        else:
            unbind_result = True
        self.deleted = True

        # Monkey-patch most of our methods away
        self.__init__ = self.throw_closederror
        self.__exit__ = self.throw_closederror
        self.please_stop = self.throw_closederror
        self.poll = self.throw_closederror
        self.sync = self.throw_closederror
        self.syncrepl_get_cookie = self.throw_closederror
        self.syncrepl_set_cookie = self.throw_closederror
        self.syncrepl_refreshdone = self.throw_closederror
        self.syncrepl_delete = self.throw_closederror
        self.syncrepl_present = self.throw_closederror
        self.syncrepl_entry = self.throw_closederror

        # Return the result from SimpleLDAPObject (or just True)
        return unbind_result


    def __del__(self):
        # Last-resort attempt to make sure things are cleaned up.
        # NOTE: If there was a problem in initialization, unbind will catch it.
        if self.deleted is not True:
            return self.unbind()


    def db(self):
        """Return a sqlite3 database instance for client use.

        :returns: A DBInterface instance.

        Returns an instance of :class:`~syncrepl_client.db.DBInterface`, which
        you can use.

        .. warning::

            Please read, understand, and observe all of the notes and warnings
            in the :class:`~syncrepl_client.db.DBInterface` class!
        """
        return self.__db.clone()


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
                return False

        # All other exceptions are real, and aren't caught.

        # If poll_output was False, then we're done, but done with what?
        # If we're in refresh-only mode, call syncrepl_refreshdone()
        if poll_output is False:
            if self.__in_refresh is True:
                self.syncrepl_refreshdone()
            return poll_output

        # Check if we have been asked to stop.  If we have, send a cancellation.
        self.__please_stop_lock.acquire()
        if self.__please_stop:
            self.cancel(self.ldap_object_search)
        self.__please_stop_lock.release()

        # Return.  The client will have to continue polling until the LDAP
        # server is done with us.
        return poll_output


    def run(self):
        """Run :meth:`~syncrepl_client.Syncrepl.poll` until it returns :obj:`False`.

        :returns: None

        Runs the :meth:`~syncrepl_client.Syncrepl.poll` method continuously,
        until it returns :obj:`False`.  This is a :obj:`callable`.

        In refresh-only mode, this method is good to use, as it saves you from
        having to write a `while` loop.  Once this method returns, you
        know that the refresh has completed, and you are clear to call
        :meth:`~syncrepl_client.Syncrepl.unbind` to clean up the instance.

        In refresh-and-persist mode, this method should only be called when you
        are running this instance in its own thread.  It will call
        :meth:`~syncrepl_client.Syncrepl.poll` effectively forever, until the
        LDAP server goes away.  For that reason, you should use this method as
        the target to pass to the :class:`threading.Thread` constructor.  Doing
        so allows the Syncrepl search to run while your main thread can get on
        with other work.  In particular, your main thread should catch signals
        like `SIGHUP`, `SIGINT`, and `SIGTERM`.

        .. note::

            When a Syncrepl search is actively running, most of the execution
            time is spent inside OpenLDAP client code, waiting for updates from
            the LDAP server.  If OpenLDAP client code receives a signal, it
            normally responds by abruptly closing the LDAP connection and
            raising an exception.  That will cause the Syncrepl search to
            stop in an unsafe manner.

            You *really* should run refresh-and-persist Syncrepl searches in a
            thread.

        When you are running this method in a thread, use
        :meth:`~syncrepl_client.Syncrepl.please_stop` to request the safe
        shutdown of the Syncrepl search.  Once the thread has been
        :meth:`~threading.Thread.join`-ed, remember to call
        :meth:`~syncrepl_client.Syncrepl.unbind` to clean up the instance.

        .. warning::

            :meth:`~syncrepl_client.Syncrepl.please_stop` is the **only**
            thread-safe method!  Once you have spawned your Syncrepl search
            thread, no other methods (except for
            :meth:`~syncrepl_client.Syncrepl.please_stop`) may be called until
            the thread has been :meth:`~threading.Thread.join`-ed.
        """
        poll_result = True
        while poll_result:
            poll_result = self.poll()


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
        return self.__db.get_setting('syncrepl_cookie')


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
        self.callback.cookie_change(cookie)
        self.__db.set_setting('syncrepl_cookie', cookie)


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

        # Let's make a class to represent our LDAP items!
        # We implement the methods needed for a Dictionary.
        # The keys are DNs; the values are attribute dicts.
        class ItemList(Mapping):
            # The only thing we need is a database cursor.
            def __init__(self, cursor):
                # Let the superclass set itself up.
                Mapping.__init__(self)

                # Store our cursor
                self.__syncrepl_cursor = cursor

                # Define attributes for our list of DNs, and the number of DNs.
                # These are lazily-populated by checking __syncrepl_count.
                self.__syncrepl_count = None
                self.__syncrepl_list = None

                # We also make a place to cache entries we've pulled.
                self.__syncrepl_attrlist = dict()

            def __del__(self):
                try:
                    self.__syncrepl_cursor.close()
                except sqlite3.ProgrammingError:
                    pass

            def __syncrepl_populate(self):
                rowlist = list()
                self.__syncrepl_cursor.execute('''
                    SELECT dn
                      FROM syncrepl_records
                ''')
                for row in self.__syncrepl_cursor.fetchall():
                    rowlist.append(row[0])
                self.__syncrepl_list = rowlist
                self.__syncrepl_count = len(rowlist)

            def __getitem__(self, dn):
                # Populate, and check cache.
                if self.__syncrepl_count is None:
                    self.__syncrepl_populate()
                elif dn in self.__syncrepl_attrlist:
                    return self.__syncrepl_attrlist[dn]

                # Check for the DN in the DB.
                # Cache the result for later use.
                self.__syncrepl_cursor.execute('''
                    SELECT attributes
                      FROM syncrepl_records
                     WHERE dn = ?
                ''', (dn,))
                row = self.__syncrepl_cursor.fetchone()
                if row is not None:
                    self.__syncrepl_attrlist[dn] = row[0]
                    return row[0]
                else:
                    raise KeyError(dn)

            def __iter__(self):
                # Populate the DNs first.
                if self.__syncrepl_count is None:
                    self.__syncrepl_populate()

                # Make a small iterator class.
                # NOTE: The only reason we just need a local index, is because
                # this object is read-only.
                class ItemIter(Iterator):
                    def __init__(iterself, item_list):
                        iterself.i = 0
                        iterself.item_list = item_list
                    def __next__(iterself):
                        # Remember, i is zero-indexed
                        if iterself.i >= len(iterself.item_list):
                            raise StopIteration
                        dn = iterself.item_list[iterself.i]
                        iterself.i += 1
                        return dn

                # Give the iterator to the client, along with a list ref.
                return ItemIter(self.__syncrepl_list)

            def __len__(self):
                # Populate, and then return length.
                if self.__syncrepl_count is None:
                    self.__syncrepl_populate()
                return self.__syncrepl_count

        # Get a cursor, then do the callback to the client.
        c = self.__db.cursor()
        self.callback.refresh_done(ItemList(c), c)

        # Update our internal tracking variable, delete the present UUID list,
        # and (finally!) commit.  We also trigger an optimize run.
        self.__in_refresh = False
        self.__db.commit()
        self.__db.execute('PRAGMA optimize')
        del self.__present_uuids


    def syncrepl_delete(self, uuids):
        """Report deletion of an LDAP entry.

        :param uuids: List of UUIDs to delete.

        :type uuids: List of binary.

        :returns: None.

        :raises: syncrepl_client.exceptions.DBConsistencyWarning

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
        c = self.__db.cursor()
        for uuid in uuids:
            # First, get our DN
            c.execute('''
                SELECT dn
                  FROM syncrepl_records
                 WHERE uuid = ?
            ''', (uuid,))
            dn = c.fetchone()

            # If the DN doesn't exist, then that's a problem, because the LDAP
            # server things we have it!  This is only a warning, because it's
            # possible we are replaying an operation.
            if dn is None:
                raise exceptions.DBConsistencyWarning(
                    'Attempted to delete UUID %d from the database, but it '
                    'does not exist!' % (uuid,)
                )
                return

            # Go ahead and delete (but don't commit yet!)
            c.execute('''
                DELETE
                  FROM syncrepl_records
                 WHERE uuid = ?
            ''', (uuid,))

            # Do our callback.
            self.callback.record_delete(dn[0], c)

        # Now that the deletes & callbacks are done, commit and close cursor.
        # (Only commit if we are not in the refresh phase.)
        if self.__in_refresh is False:
            self.__db.commit()
        c.close()


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
            # We're almost at the end of the refresh.  Every entry that we have
            # in state, but that didn't get a "present" message, has been
            # deleted!

            # Look through each UUID in the database.
            c = self.__db.execute('''
                SELECT uuid
                  FROM syncrepl_records
            ''')
            for db_uuid in c.fetchall():
                # If the DB has a UUID _not_ in the present list, note it.
                if db_uuid[0] not in self.__present_uuids:
                    deleted_uuids.append(db_uuid[0])

            # Close this cursor, since we're done with it.
            c.close()

            # We've built up a list of things to delete.
            # If there's anything in the list, then call the code to delete
            # stuff.  `syncrepl_delete` will handle the callbacks, and the
            # database transaction.
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

        # We're need a cursor early for this one!
        c = self.__db.cursor()

        # First, we need to grab any existing entry from the DB.
        c.execute('''
            SELECT dn, attributes
              FROM syncrepl_records
             WHERE uuid = ?
        ''', (uuid,))
        db_record = c.fetchone()

        # If a DB record already exists, then we have a change of some sort.
        if db_record is not None:
            # Either the DN changed, or the attributes, or both.
            db_dn = db_record[0]
            db_attrs = db_record[1]

            # First, check if the DN changed.
            if dn != db_dn:
                # OK, we have a DN change.

                # But first, might the new DN already be in the map?
                # Especially if we're being refreshed, we might have a small
                # inconsistency.  So, check for the new DN.
                c.execute('''
                    SELECT uuid
                      FROM syncrepl_records
                     WHERE dn = ?
                ''', (dn,))
                possible_db_record = c.fetchone()
                if possible_db_record is not None:
                    # We have an old record in the way.  Act like we got an
                    # "item deleted" message from the LDAP server.
                    old_uuid = possible_db_record[0]
                    self.syncrepl_delete(old_uuid)

                # Now we can update the DB with the new DN, and do the callback.
                c.execute('''
                    UPDATE syncrepl_records
                       SET dn = ?
                     WHERE uuid = ?
                ''', (dn, uuid))
                self.callback.record_rename(db_dn, dn, c)

            # Now we've checked the DN, update the DB and do the callback.
            c.execute('''
                UPDATE syncrepl_records
                   SET attributes = ?
                 WHERE uuid = ?
            ''', (attrs, uuid))
            self.callback.record_change(dn, db_attrs, attrs, c)


        # If we're here, then this UUID is new to us!
        else:
            # Just like before, we have to make sure our DN isn't already in
            # the database.
            c.execute('''
                SELECT uuid
                  FROM syncrepl_records
                 WHERE dn = ?
            ''', (dn,))
            possible_db_record = c.fetchone()
            if possible_db_record is not None:
                # We have an old record in the way.  Act like we got an "item
                # deleted" message from the LDAP server.
                old_uuid = possible_db_record[0]
                syncrepl_delete(old_uuid)

            # Now we can insert the record and do the add callback.
            c.execute('''
                INSERT
                  INTO syncrepl_records
                       (uuid, dn, attributes)
                VALUES (?, ?, ?)
            ''', (uuid, dn, attrs))
            self.callback.record_add(dn, attrs, c)
