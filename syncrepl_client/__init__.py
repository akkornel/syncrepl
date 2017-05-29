#!/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# syncrepl_client main code.
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

# For Python 2 support
from __future__ import print_function

import ldap
from ldap.ldapobject import SimpleLDAPObject
from ldap.syncrepl import SyncreplConsumer
import ldapurl
import shelve
import signal
from sys import argv, exit
import threading

from . import exceptions

__version__ = '0.75'

class Syncrepl(SyncreplConsumer, SimpleLDAPObject):
    '''
    This class implements the Syncrepl client.  You should have one instance of
    this class for each syncrepl connection.

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
      software version changes.

    * **A callback class**
      
      The callback class is an object (a class, or an instance).  The callback
      class' methods are called when the Syncrepl client receives updates.

      The complete list of callback methods is documented in
      :class:`~syncrepl_client.callbacks.BaseCallback`.  That class is designed
      for subclassing, because it defines each callback method, but doesn't
      actually do anything.  So, you can subclass
      :class:`~syncrepl_client.callbacks.BaseCallback`, and let it handle the
      callbacks that you don't care about.

      For a simple example of a callback in action, see the
      :class:`~syncrepl_client.callbacks.LoggingCallback` class.

    * **An LDAP URL**
      
      The LDAP URL contains all information about how the Syncrepl client
      should connect, what credentials should be used to connect, and how the
      search should be performed.

      The :class:`~ldapurl.LDAPUrl` class is used to parse the LDAP URL.  Refer
      to that class' documentation for information on the fields available.

      If a valid data store exists, this field is *optional*; the URL will be
      stored in the data store.  If you provide both an LDAP URL *and* a valid
      data store, your LDAP URL will be used, *as long as* the search
      parameters have not changed (the LDAP host and authentication information
      can be changed).

      The Callback class supports the following bind methods:

      * *Anonymous bind*: Do not set a bind DN or password.
      
      * *Simple bind*: Set the bind DN and password as part of the URL.
        
        For security, it is suggested that you store the LDAP URL without
        password, convert the URL into an object at runtime, add the password,
        and pass the password-laden object to the constructor.
      
      * *GSSAPI bind*: Set the bind DN to `GSSAPI`, and do not set a password.
        You are responsible for ensuring that you have valid Kerberos
        credentials.
        
        As an extra safety mechanism, when you receive the `bind_complete`
        callback, consider doing a "Who am I?" check against the LDAP server,
        to make sure the bind DN is what you expected.  That will help guard
        against expired or unexpected credentials.

    Methods are defined below.  Almost all methods are documented, including
    internal methods: Methods whose names start with `syncrepl_` are internal
    methods, which clients **must not call**.  That being said, the methods are
    documented here, for educational purposes.
    '''

    def __init__(self, data_path, callback, ldap_url=None, **kwargs):
        """Instantiate, connect, and bind.

        :param str data_path: A path to where data files will be stored.

        :param object callback: An object that receives callbacks.

        :param ldap_url: A complete LDAP URL string, or an LDAPUrl object, or None.

        :type ldap_url: str or ldapurl.LDAPUrl or None

        :returns: A Syncrepl instance.

        This is the :class:`Syncrepl` class's constructor.  In addition to
        basic initialization, it is also responsible for making the initial
        connection to the LDAP server, binding, and starting the syncrepl
        search.

        .. note::

            Many parts of this documentation refers to syncrepl as a "search".
            That is because a syncrepl is initiated using an LDAP search
            operation, to which a syncrepl "control" is attached.

        `data_path` is used to specify the prefix for the path to data storage.
        :class:`Syncrepl` will open multiple files, whose names will be
        appended to :obj:`data_path`.  You are responsible for making sure that
        :obj:`data_path` is appropriate for your OS.

        .. note::

            Some basic checks may be performed on the data files.  If you use a
            different version of software, those checks will fail, and the
            contents will be wiped.

        The `bind_complete()` callback will be called at some point during the
        constructor's execution.

        Returns a ready-to-use instance.  The next call you should make to the
        instance is :obj:`poll()`.  Continue calling :obj:`poll()` until it
        returns `False`; then you should call :obj:`unbind()`.  To request safe
        teardown of the connection, call :obj:`please_stop()`.
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

        # Open our shelves
        self.__data = shelve.open(data_path + 'data')
        self.__uuid_dn_map = shelve.open(data_path + 'uuid_map')
        self.__uuid_attrs = shelve.open(data_path + 'attrs')

        # Check the data file version for a mismatch.  If we find one, then
        # prepare to wipe everything.
        if (('version' in self.__data) and
                (self.__data['version'] != __version__)):
            del self.__data['version']

        # If no version is defined, set it and clear everything else.
        if 'version' not in self.__data:
            self.__data.clear
            self.__data['version'] = __version__
            self.__uuid_dn_map.clear
            self.__uuid_attrs.clear

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
#            mode='refreshOnly',
             mode='refreshAndPersist',
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

          If you are using the Context Manager protocol, do *not* call `unbind`;
          it will be called for you at the appropriate time.

        .. warning::

          Not all Python implementations delete objects at the same point in
          their code.  PyPy, in particular, is very different.  Do not rely on
          assumptions about garbage collection!

        Once unbound, this instance is no longer usable, even if it hasn't been
        deleted yet.  To start a new Syncrepl client, make a new instance of
        this object.
        """
        self.__uuid_dn_map.close()
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

        1. Continue calling `poll()` until it returns `False`.

        2. Call `unbind()` (unless you're using the Context Management protocol).

        3. Stop using this instance.

        When running in refresh-only mode, this does nothing: Interrupting a
        refresh is dangerous, because there is no guarantee that the updates
        from the LDAP server are being received in any particular order.  The
        refresh will be allowed to complete, and then it is safe to stop. 

        When running in refresh-and-persist mode, if the refresh phase is still
        in progress, it will be completed.  If in the persist phase, a Cancel
        request will be sent to the LDAP server.  Operations will then continue
        until the LDAP server confirms the operation is cancelled.

        This is the *only* method which is thread-safe.
        """

        self.__please_stop_lock.acquire()
        self.__please_stop = True
        self.__please_stop_lock.release()
        return None


    def poll(self):
        """Poll the LDAP server for changes.

        :returns: True or False.

        In refresh-only mode, returning True indicates that the refresh is
        still in progress.  You must continue calling `poll()` until `False` is
        returned.  Once `False` is returned, the refresh is complete, and it is
        safe to call `unbind()`.

        In refresh-and-persist mode, returning `True` only indicates that the
        connection is still active: Work might or might not be taking place.
        The `refresh_done()` callback is used to indicate the completion of the
        refresh phase and the start of the persist phase.  During the refresh
        phase, when the connection is idle, `poll()` will return `True` every ~3
        seconds.  This is for single-process applications.

        Most callbacks will be made during the execution of `poll()`.

        .. warning::

          Just because `poll()` has returned, does not mean that you are in
          sync with the LDAP server.  You must continue calling `poll()` until
          it returns `False`.

          To request safe, consistent teardown of the connection, call
          `please_stop()`.
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
                return False

        # All other exceptions are real, and aren't caught.

        # If poll_output was False, then we're done, so return
        if poll_output is False:
            return poll_output

        # Check if we have been asked to stop.  If we have, send a cancellation.
        self.__please_stop_lock.acquire()
        if self.__please_stop:
            self.cancel(self.ldap_object_search)
        self.__please_stop_lock.release()

        # Return.  The client will have to continue polling until the LDAP
        # server is done with us.
        return poll_output


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


    def syncrepl_refreshdone(self):
        """Mark the transition from the refresh phase to the persist phase.

        :returns: None.

        .. note::

            This is an internal Syncrepl operation.  It is documented here for
            educational purposes, but should **not** be called by clients.

        This is called when we moving from the Refresh mode into the Persist
        mode of refresh-and-persist.  This is not called in refresh-only mode.
        """

        # Besides doing a callback, we update an internal tracking variable, and
        # we delete our list of present items (that's only used in the Refresh mode).
        self.callback.refresh_done()
        self.__in_refresh = False
        del self.__present_uuids


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

        Triggers a deletion callback for each UUID.
        """
        for uuid in uuids:
            if not uuid in self.__uuid_dn_map:
                raise RuntimeError('WARNING: Trying to delete uuid', uuid, 'not in map!')
                continue
            self.callback.record_delete(self.__uuid_dn_map[uuid])
            del self.__uuid_dn_map[uuid]
            del self.__uuid_attrs[uuid]


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
        :obj:`syncrepl_entry()`, below).  The first time a sync takes place
        (when there is no valid cookie), you are able to assume that every
        mapping entry received is present in the directory; but in subsequent
        syncs (using a valid cookie) you can't be sure which entries are
        present and which have been deleted.  In addition, if you have a cookie
        that is now too old, there is no way to know which entries in your data
        store still exist in the directory.
        
        The "Present" messages, and the resulting calls, are used to bring us
        back in sync with the Directory, regardless of our local state.

        `uuids` is either a list of UUIDs, or `None`.  `refreshDeletes` is a
        boolean.  To understand how the two parameters are related, it's better
        to look at the latter parameter first.

        * If `refreshDeletes` is `False`, and `uuids` is a list, then `uuids`
          contains a list of entries that are currently in the directory.

        * If `refreshDeletes` is `False`, but `uuids` is `None`, then we are
          almost synced.  We now need to go into our mapping, and remove all
          entries that were not previously mentioned as being in the directory.

        * If `refreshDeletes` is `True`, and we have a list, then `uuids`
          contains entries that used to be in the directory, but are now gone.

        * If `refreshDeletes` is `True`, but `uuids` is `None`, then we are
          synced: Our current mapping of UUIDs, minus those previously deleted,
          represents the current state of the directory.

        Here is another way to think about it: The LDAP server needs to work out
        the most efficient way of relaying changes to us.  There are three ways
        of telling us what has changed:

        * "The following entries are in the directory; everything else you knew
          about has been deleted."

          This is the easiest way of informing us of changes and deletions.

          In this mode, you will receive:

          - Calls where `uuids` is a list and `refreshDeletes` is `False`.

          - A call where `uuids` is `None` and `refreshDeletes` is `False`.

        * "The following entries are new, and these other entries have been
          deleted, but everything else you know about is still in the directory."

          This is the mode that is used when, since your last checkin, there have
          been alot of additions and deletions.

          In this mode, you will receive:

          - Calls where `uuids` is a list and `refreshDeletes` is `False`.

          - Calls where `uuids` is a list and `refreshDeletes` is `True`.

          - A call where uuids` is `None` and `refreshDeletes` is `True`.

        * "Everything is up-to-date and there are no changes."

          When things are quiet, this is the mode that is used.

          In this mode, you wil receive:

          - A call where `uuids` is `None` and `refreshDeletes` is `True`.

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
        to :obj:`syncrepl_present()`.  If a valid cookie was provided, the
        server will only send new/changed entries since our last checkin;
        otherwise, we'll get a big list of entries—all of which will be
        present—to seed our mapping.

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
                # Besides updating our records, we need to do a callback.
                self.callback.record_rename(self.__uuid_dn_map[uuid], dn)
                self.__uuid_dn_map[uuid] = dn

            # Besides the DN change, other attributes may also have changed.
            # In fact, since the DN is basically (key attr) + (base DN), we
            # know that at least the key attribute changed!

            # Do a callback, then update our record.
            self.callback.record_change(dn, self.__uuid_attrs[uuid], attrs)
            self.__uuid_attrs[uuid] = attrs
        else:
            # The UUID is new, so add it!
            self.__uuid_dn_map[uuid] = dn
            self.__uuid_attrs[uuid] = attrs
            self.callback.record_add(dn, attrs)
