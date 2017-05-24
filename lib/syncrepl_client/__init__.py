#!/bin/env python

# For Python 2 support
from __future__ import print_function

import ldap
from ldap.ldapobject import SimpleLDAPObject
from ldap.syncrepl import SyncreplConsumer
import ldapurl
import shelve
import signal
from sys import argv, exit

from . import exceptions

__version__ = 1

class Syncrepl(SyncreplConsumer, SimpleLDAPObject):
    '''
    WorkgroupSyncRepl is an LDAP syncrepl consumer object, focused on
    workgroups.  Although, TBH, this can focus on pretty much any type of LDAP
    group.
    '''

    def __init__(self, data_path, callback, ldap_url=None, **kwargs):
        """A LDAP syncrepl client.

        :param data: A path to where data files will be stored.  Data file
        names and extensions will be appended to this value.
        :type data: str

        :param callback: A class or instance which will receive callbacks when
        things change.
        :type callback: A subclass of, or instance of a subclass of,
        SyncreplClient.

        :param ldap_url: A complete LDAP URL string, or an LDAPUrl object.
        Only required when no data files exist.
        :type ldap_url: str|LDAPUrl

        :returns: Client

        The constructor does all of the syncrepl client preparation.

        First, a set of shelves are opened, which are used to store state.
        These shelves are stored at the path specified by the data parameter.

        If you would like to ensure that all state is cleared, delete all files
        & directories who's path starts with path.  Also, if this class's
        version number changes, shelves created by older code will be wiped
        when used by newer code.

        If no valid state is present, then ldap_url is mandatory.  This is an
        LDAP URL string, or an LDAPUrl instance.

        If using simple bind, the bind DN is expected to be found in the
        `bindname` URL extension, and the bind password is expected to be found
        in the `X-BINDPW` URL extension.  These are easily accessed using
        `LDAPURL.who` and `LDAPURL.cred`, respectively.

        If using GSSAPI bind, set `bindname` to the string "GSSAPI".
        `ldap.sasl` must be available, and it is the client's responsibility to
        ensure that a valid Kerberos ticket exists.

        If state already exists, and `ldap_url` does not match the LDAP URL
        previously provided, some checks are performed.  If the LDAP search base,
        scope, filter, or attribute list are different, a ValueError is raised.
        Otherwise, the new `ldap_url` is stored for future use.

        If state already exists, and `ldap_url` is `None`, then the LDAP URL
        stored in state is used.

        Returns a Syncrepl instance.  Call `unbund` when done, or use the
        context manager protocol instead.
        """

        # Set some instanace veriables.
        self.__in_refresh = True
        self.__present_uuids = []
        self.__please_stop = False

        # TODO: Make sure callback is a subclass or subclass instance.
        self.callback = callback

        # Put our signal handler in place
        signal.signal(signal.SIGINT, signal.SIG_IGN)

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
        pass


    def __exit__(self, exception_type, value, traceback):
        # If we got an exception, let it raise.
        if exception_type is not None:
            return False

        # Otherwise, unbind
        return self.unbind()


    def unbind(self):
        '''
        unbind safely saves state and disconnects from the LDAP server.

        If you are using the Context Manager protocol, do *not* call `unbind`;
        it will be called for you at tha appropriate time.

        Otherwise, you will need to call `unbind` before your program exits, or
        state will not be safed safely.
        '''
        self.__uuid_dn_map.close()
        self.__uuid_attrs.close()
        self.__data.close()
        return SimpleLDAPObject.unbind(self)


    def loop(self):
        '''
        Loop through 
        '''
        if self.__please_stop:
            return
        poll_output = True
        try:
            poll_output = self.syncrepl_poll(msgid=self.ldap_object_search,
                    all=1, timeout=3)
        except ldap.TIMEOUT:
            pass
        return poll_output


    def syncrepl_get_cookie(self):
        '''
        Internal Syncrepl operation.  Not for client use.

        Called at the start of the syncrepl operation, to load a cookie from
        state.  If present and valid, the LDAP server will know how far behind
        we are.

        If not present, or invalid (typically because it's too old), the LDAP
        server will start us over, as if we were a new client.
        '''
        if 'cookie' in self.__data:
            return self.__data['cookie']
        else:
            return None


    def syncrepl_set_cookie(self, cookie):
        '''
        Internal Syncrepl operation.  Not for client use.

        Called regularly during syncrepl operations, to store a "cookie" from
        the LDAP server.
        '''
        self.__data['cookie'] = cookie


    def syncrepl_refreshdone(self):
        '''
        Internal Syncrepl operation.  Not for client use.

        This is called when we moving from the Refresh mode into the Persist
        mode of refresh-and-persist.

        Besides doing a callback, we update an internal tracking variable, and
        we delete our list of present items (that's only used in the Refresh mode).
        '''
        self.callback.refresh_done()
        self.__in_refresh = False
        del self.__present_uuids


    def syncrepl_delete(self, uuids):
        '''
        Internal Syncrepl operation.  Not for client use.

        Called when one or more DNs are deleted.

        The one parameter is a list of DNs, which we SHOULD have in our map.

        For each DN, we trigger a deletion callback, and then remove the UUID
        from our mapping.
        '''
        for uuid in uuids:
            if not uuid in self.__uuid_dn_map:
                print('WARNING: Trying to delete uuid', uuid, 'not in map!')
                continue
            self.callback.record_delete(self.__uuid_dn_map[uuid])
            del self.__uuid_dn_map[uuid]
            del self.__uuid_attrs[uuid]


    def syncrepl_present(self, uuids, refreshDeletes=False):
        '''
        This function is used in refresh-only syncrepl, and in the refresh
        phase of refresh-and-persist syncrepl.

        As part of the syncrepl process, we get a big list of UUIDs and their
        DNs (plus attributes), from which we build a mapping (see
        syncrepl_entry).  The first time a sync takes place (when there is no
        valid cookie), you may be able to assume that every mapping entry
        received is present in the directory, but that's not actually true; and
        of course in subsequent syncs (using a valid cookie) you can't be sure
        which entries are present and which have been deleted.

        uuids is either a list of UUIDs or None.  refreshDeletes is a boolean.
        To understand how the two parameters are related, it's better to look
        at the latter parameter first.

        * If refreshDeletes is False, and uuids is a list, then uuids contains
        a list of entries that are currently in the directory.

        * If refreshDeletes is False, but uuids is None, then we are almost
        synced.  We now need to go into our mapping, and remove all entries
        that were not previously mentioned as being in the directory.

        * If refreshDeletes is True, and we have a list, then uuids contains
        entries that used to be in the directory, but are now gone.

        * If refreshDeletes is True, but uuids is None, then we are synced: Our
        current mapping of UUIDs, minus those previously deleted, represents
        the current state of the directory.

        Here is another way to think about it: The LDAP server needs to work out
        the most efficient way of relaying changes to us.  There are three ways
        of telling us what has changed:

        A) "The following entries are in the directory; everything else you knew
        about has been deleted."

        This is the easiest way of informing us of changes and deletions.

        In this mode, you will receive:

        * Calls where uuids is a list and refreshDeletes is False.

        * A call where uuids is None and refreshDeletes is False.

        B) "The following entries are new, and these other entries have been
        deleted, but everything else you know about is still in the directory."

        This is the mode that is used when, since your last checkin, there have
        been alot of additions and deletions.

        In this mode, you will receive:

        * Calls where uuids is a list and refreshDeletes is False.

        * Calls where uuids is a list and refreshDeletes is True.

        * A call where uuids is None and refreshDeletes is True.

        C) "Everything is up-to-date and there are no changes."

        When things are quiet, this is the mode that is used.

        In this mode, you wil receive:

        * A call where uuids is None and refreshDeletes is True.

        The LDAP server chooses which mode to use (A, B, or C) when we connect
        and present a valid cookie.  If we don't have a valid cookie, then the
        LDAP server falls back to mode A.
        '''

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
        '''
        DNs are not static - they can change.  That's a problem when you are
        trying to track changes over time.  To deal with that, the LDAP server
        assigns each entry a UUID.  We then maintain a mapping of UUIDs to DNs,
        because all future syncrepl-related calls will refernce UUIDs instead
        of DNs.

        This function is called to add entries to a map of UUIDs to
        DN/attribute-list pairs.  It is also used to change an existing DN: In
        that case, the UUID matches an existing entry, but the DN is different.

        In refresh-only sync, and in the refresh phase of refresh-and-persist
        syncrepl, this function is called multiple times, interspersed with
        calls to syncrepl_present.  If a valid cookie was provided, the server will
        only send new/changed entries since our last checkin; otherwise, we'll
        get a big list of entries--all of which will be present--to seed our mapping.

        In refresh-and-persist mode, everything from the previous paragraph is
        true, but when in persist mode, we should expect to be called at random
        times after the refresh phase completes, as the server sends us updates
        to our mapping.

        NOTE: This list is *not* the list of entries present in the directory.
        This is just a list of UUIDs and DNs.  syncrepl_present and syncrepl_delete are
        used to specify which entries are present in the directory at any given
        time.

        The list of attributes is the intersection of three sets:

        * The attributes of a particular entry.
        * The attributes you are allowed to see.
        * The attributes you requested in your search.
        '''

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
