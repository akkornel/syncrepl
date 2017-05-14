#!/bin/env python3

from __future__ import print_function

import ldap, ldap.sasl
import ldap.ldapobject
import ldap.syncrepl
import ldapurl
import shelve
from sys import argv, exit

# When looking up group members via the 'members' attribute, we get a list of 
# DNs.  We need to convert those DNs into things that we care about.
# username_uid_attr maps to a (possibly non-human-readable) permanent ID.
# username_uname_attribute maps to a human-readable ID, which can change.
username_uid_attr = 'suRegID'
username_uname_attr = 'uid'

# member_cache: A dictionary of DNs to (username_uid_attr,username_uname_attr) tuples.
# resolve_member: Takes a key & LDAP connection; returns a tuple.
member_cache = dict()
def resolve_member(key, ldap_conn):
    if key not in member_cache:
        ldap_result = ldap_conn.search_s(key, ldap.SCOPE_BASE)
        for dn,attr in ldap_result:
            # Make sure our keys are present
            for key in (username_uid_attr, username_uname_attr):
                if key not in attr:
                    print('Found DN', dn, 'but missing key', key, '!')
            # Construct our value tuple, containing Unique ID, and username
            value_tuple = (attr[username_uid_attr][0].decode('UTF-8'),
                    attr[username_uname_attr][0].decode('UTF-8'))
            member_cache[key] = value_tuple
    return member_cache[key]


class WorkgroupSyncRepl(ldap.syncrepl.SyncreplConsumer, ldap.ldapobject.SimpleLDAPObject):
    '''
    WorkgroupSyncRepl is an LDAP syncrepl consumer object, focused on 
    workgroups.  Although, TBH, this can focus on pretty much any type of LDAP 
    group.
    '''

    # attr_group_name: The attribute containing the workgroup's name.
    attr_group_name = 'cn'
    attr_members = 'member'

    def __init__(self, db_path, ldap_uri, **kwargs):
        '''
        db_path: A path to store a shelve file.

        ldap_uri: This is an LDAPUrl-compatible URI.  It is passed to the ldap 
        module to prepare for a connection.

        Other keyword args may be passed, and will be passed along to the ldap class.
        '''

        # Set up our parent class
        ldap.ldapobject.SimpleLDAPObject.__init__(self, ldap_uri, **kwargs)

        # Open our shelves
        self.__uuid_dn_map = shelve.open(db_path + 'uuid_map')
        self.__uuid_cn_member = shelve.open(db_path + 'attrs')
        self.__data = shelve.open(db_path + 'data')

        # Set some flags
        self.__refresh_done = False


    def unbind(self):
        self.__uuid_dn_map.close()
        self.__uuid_cn_member.close()
        self.__data.close()
        return ldap.ldapobject.SimpleLDAPObject.unbind(self)

    def unbind_s(self):
        self.__uuid_dn_map.close()
        self.__uuid_cn_member.close()
        self.__data.close()
        return ldap.ldapobject.SimpleLDAPObject.unbind_s(self)

    def unbind_ext(self, *args, **kwargs):
        self.__uuid_dn_map.close()
        self.__uuid_cn_member.close()
        self.__data.close()
        return ldap.ldapobject.SimpleLDAPObject.unbind_ext(self, *args, **kwargs)

    def unbind_ext_s(self, *args, **kwargs):
        self.__uuid_dn_map.close()
        self.__uuid_cn_member.close()
        self.__data.close()
        return ldap.ldapobject.SimpleLDAPObject.unbind_ext_s(self, *args, **kwargs)

    def syncrepl_get_cookie(self):
        if 'cookie' in self.__data:
            return self.__data['cookie']
        else:
            return None

    def syncrepl_set_cookie(self, cookie):
        self.__data['cookie'] = cookie

    def syncrepl_refreshdone(self):
        '''
        This is called when we moving from the Refresh mode into the Persist 
        mode of refresh-and-persist.
        '''
        print('Refresh is complete!  Now in persist mode.')
        self.__refresh_done = True

    def syncrepl_delete(self, uuids):
        '''
        Called when one or more DNs are deleted.

        The one parameter is a list of DNs, which we SHOULD have in our map.

        For each DN, we trigger a deletion callback, and then remove the UUID 
        from our mapping.
        '''

        for uuid in uuids:
            if not uuid in self.__uuid_dn_map:
                print('WARNING: Trying to delete uuid', uuid, 'not in map!')
                continue
            print('Deleting dn', self.__uuid_dn_map[uuid])
            # TODO: Callback
            del self.__uuid_dn_map[uuid]

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

        # The UUID list is being reset, which means our map is about to 
        # disappear.  But, should we also delete stuff?
        if uuids is None:
            print('Present called without UUIDs.  refreshDeletes is', refreshDeletes)
        else:
            print('Present called with', len(uuids), 'UUIDs.',
                    'refreshDeletes is', refreshDeletes)
            for uuid in uuids:
                if uuid in self.__uuid_dn_map:
                    print("\t", self.__uuid_dn_map[uuid])
                else:
                    print("\tUUID", uuid, '(DN not present)')

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
                # Our DN has changed!
                print('UUID', uuid, 'DN changed from', self.__uuid_dn_map[uuid], 'to', dn)
                self.__uuid_dn_map[uuid] = dn

            # Besides the DN change, other attributes may also have changed.
            print('Modification of existing dn', dn, 'with uuid', uuid,
                    '; new attrlist', attrs.keys())
            if (WorkgroupSyncRepl.attr_group_name not in attrs):
                self.__uuid_cn_member[uuid] = (None, None)
            elif (WorkgroupSyncRepl.attr_members in attrs):
                self.__uuid_cn_member[uuid] = (
                        WorkgroupSyncRepl.attr_group_name,
                        WorkgroupSyncRepl.attr_members)
            else:
                self.__uuid_cn_member[uuid] = (
                        WorkgroupSyncRepl.attr_group_name, None)
            # TODO: Callback to update attrlist
        else:
            # The UUID is new, so add it!
            print('Adding DN', dn, 'with uuid', uuid, 'and attrlist', attrs.keys())
            self.__uuid_dn_map[uuid] = dn
            if (WorkgroupSyncRepl.attr_group_name not in attrs):
                self.__uuid_cn_member[uuid] = (None, None)
            elif (WorkgroupSyncRepl.attr_members in attrs):
                self.__uuid_cn_member[uuid] = (
                        WorkgroupSyncRepl.attr_group_name,
                        WorkgroupSyncRepl.attr_members)
            else:
                self.__uuid_cn_member[uuid] = (
                        WorkgroupSyncRepl.attr_group_name,
                        None)
            # TODO: Callback to refresh workgroup



# PROGRAM START!

# Parse LDAP URL
ldap_url = ldapurl.LDAPUrl(argv[2])

# Connect to LDAP server and bind
# NOTE: We use the LDAP URL for *everything*, including who to bind as.
# If the "bind DN" is "GSSAPI", we trigger a GSSAPI bind.
ldap_conn = WorkgroupSyncRepl(argv[1], argv[2])
if ldap_url.who is None:
    print('Doing anonymous bind...')
    ldap_conn.simple_bind_s()
elif ldap_url.who == 'GSSAPI':
    print('Doing GSSAPI bind...')
    sasl_bind = ldap.sasl.gssapi()
    ldap_conn.sasl_interactive_bind_s('',sasl_bind)
else:
    print('Doing simple bind...')
    ldap_conn.simple_bind_s(who=ldap_url.who, cred=ldap_url.cred)
print('Bind complete!')
print('I am', ldap_conn.whoami_s())

# Do an LDAP search, pulling parameters from the LDAP URL
# Before we start, we have to check if a filter was set.  If not, set the 
# default that the LDAP module uses.
if ldap_url.filterstr is None:
    ldap_url.filterstr = '(objectClass=*)'

# Prepare the search
ldap_search = ldap_conn.syncrepl_search(ldap_url.dn, ldap_url.scope,
#        mode='refreshOnly',
        mode='refreshAndPersist',
        filterstr=ldap_url.filterstr
        )

# Actually, do the search!
try:
    print('Starting poll...')
    while True:
        poll_result = ldap_conn.syncrepl_poll(msgid=ldap_search)
        if poll_result is False:
            print('Poll complete; no more updates!')
            break;
except KeyboardInterrupt:
    pass

print('All done!')
ldap_conn.unbind_s()
exit(0)
