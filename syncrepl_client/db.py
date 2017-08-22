#!/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# syncrepl_client database code.
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


import pyasn1.codec.ber.encoder
import pyasn1.type.char, pyasn1.type.namedtype, pyasn1.type.univ
import sqlite3
import uuid

# We use threading for a lock
try:
    import threading
except ImportError:
    import dummy_threading as threading


# We want to store a UUID directly into the database.
# To do that, define two conversion functions.

def uuid_to_bytes(uuid):
    """Convert a UUID to a string of bytes, for database storage.

    :param UUID uuid: The :class:`~uuid.UUID` instance.

    :returns: A bytes object.
    """
    return uuid.bytes

def bytes_to_uuid(uuid_bytes):a
    """Convert a string of bytes into a UUID.

    :param bytes uuid_bytes: A string of bytes.

    :returns: A UUID object.
    """
    return uuid.UUID(bytes=uuid_bytes)


# We want to store an attribute list into the database.
# That's more complicated, because the attribute list is variable, 
# So, we'll ASN.1-encode it!!!!!

'''
Attribute-List DEFINITIONS AUTOMATIC TAGS ::= 
BEGIN
'''
'''
  AttributeListValue ::= CHOICE {
     string UTF8String,
     binary OCTET STRING
  }
'''
class AttributeListValue(pyasn1.type.univ.Choice):
    componentType = pyasn1.type.namedtype.NamedTypes(
        pyasn1.type.namedtype.NamedType(
            'string',
            pyasn1.type.char.UTF8String()
        ),
        pyasn1.type.namedtype.NamedType(
            'binary',
            pyasn1.type.univ.OctetString()
        )
    )
'''
  AttributeListEntry ::= SEQUENCE {
     name AttributeListValue,
     value CHOICE {
         single-valued AttributeListValue,
         multi-valued SET OF AttributeListValue
     } OPTIONAL
  }
'''
class AttributeListEntry(pyasn1.type.univ.Sequence):
    componentType = pyasn1.type.namedtype.NamedTypes(
        # name AttributeListValue,
        pyasn1.type.namedtype.NamedType(
            'name',
            AttributeListValue()
        ),
        # value CHOICE {
        pyasn1.type.namedtype.OptionalNamedType(
            'value',
            pyasn1.type.univ.Choice(
                # (two different possibilities:)
                componentType=(pyasn1.type.namedtype.NamedTypes(
                    # single-valued AttributeListValue,
                    pyasn1.type.namedtype.NamedType(
                        'single-valued',
                        AttributeListValue()
                    ),
                    # multi-valued SET OF AttributeListValue
                    pyasn1.type.namedtype.NamedType(
                        'multi-valued',
                        pyasn1.type.univ.SetOf(
                            componentType=AttributeListValue()
                        )
                    ),
                ))
            )
        )
    )
'''
  AttributeList ::= SEQUENCE OF AttributeListEntry
'''
class AttributeList(pyasn1.type.univ.SequenceOf):
    componentType=AttributeListEntry()
'''
END
'''

def attributes_to_bytes(attrlist):
    asn1_sequence = AttributeList()

    # Iterate through all our "list" (actually, dict) items.
    for attr_name, attr_values in attrlist.items():
        # First, convert our attribute name
        attr_name_asn1 = AttributeListValue()
        if type(key) is str:
            attr_name_asn1.setComponentByName('string',
                key=attr_name
            )
        else:
            attr_name_asn1.setComponentByName('binary',
                key=attr_name
            )

        # Next, convert our values into AttributeListValue entries
        attr_value_asn1_list = list()
        for attr_value in attr_values:
            attr_value_asn1 = AttributeListValue()
            if type(value) is str:
                attr_value_asn1.setComponentByName('string',
                    value=attr_value
                )
            else:
                attr_value_asn1.setComponentByName('binary',
                    value=attr_value
                )
            attr_value_asn1_list.append(attr_value_asn1)

        # Now, convert our list into an object
        if len(attr_value_asn1_list) == 0:
            attr_value_asn1 = None
        # For a single item, list the AttributeListValue directly.
        elif len(attr_value_asn1_list) == 1:
            single_valued_item = pyasn1.type.namedtype.NamedType(
                'single-valued',
                attr_value_asn1_list[0]
            )
            attr_value_asn1_list = single_valued_item
        # For a multi-item list, construct a set of AttributeListValue
        else:
            # Construct our set.
            multi_valued_set = pyasn1.type.univ.SetOf(
                componentType=AttributeListValue()
            )
            for set_item in attr_value_asn1_list:
                multi_valued_set.setComponentByPosition(
                    len(multi_valued_set),
                    value=set_item
                )

            # Construct our multi-valued named type.
            multi_valued_item = pyasn1.type.namedtype.NamedType(
                'multi-valued',
                multi_valued_item
            )
            attr_value_asn1_list = multi_valued_item            

        # Now we create our AttributeListEntry!
        list_entry_asn1 = AttributeListEntry()
        list_entry_asn1.setComponentByName('name',
            value=attr_name_asn1
        )
        if attr_value_asn1_list is not None:
            list_entry_asn1.setComponentByName('value',
                value=pyasn1.type.univ.Choice(
                    componentType=attr_value_asn1_list
                )
            )

        # Add the entry to our list!
        # NOTE: Positions are zero-indexed.
        asn1_sequence.setComponentByPosition(
            len(asn1_sequence),
            value=list_entry_asn1

    # Now that the sequence is built, encode and return it!
    return pyasn1.codec.ber.encoder.encode(asn1_sequence)


def bytes_to_attributes(attrlist_bytes):
    asn1_struct = pyasn1.codec.ber.encoder.decode(
        attrlist_bytes,
        asn1Spec=AttributeList()
    )





# This is the current schema version number.
# To rev the version number...
# * Increment this number!
# * Extend upgrade_schema, so that it can do the upgrade from the
#   now-most-recent schema version, to the new schema version.
# * Extend validate_schema, so that it can validate the new schema version.
CURRENT_SCHEMA_VERSION = 1


class DBInterface(object):
    """A connection to the syncrepl state database.

    The purpose of the Syncrepl protocol is for the LDAP client to have, by the
    end of the refresh phase, a view of the directory which is in sync with
    that of the LDAP server.  For this to be possible, the client needs to have
    a place to put the directory.  For that, we use a SQLite database.

    This class acts as a front-end to that database: It handles opening the
    database, checking it, and ensuring that the schema is up-to-date.  If
    present and valid, the LDAP server will be told that we already have a
    (old) view of the directory.  If our view is not too old, then the LDAP
    server will not have to take as much time to bring us up-to-date when a new
    connection is made.

    The other purpose of this database is so that the client may be presented
    with a view of an entry's old attributes, so that the client can determine
    which attributes have changed.

    .. note::

        This database is not going to be performant as an LDAP server's native
        database, which has been designed/chosen and tuned specifically for its
        purpose.  This is meant more as a cache.

    Some clients may be interested in using this database to store some of
    their information.  That is possible.  Clients should obtain their own
    :class:`~syncrepl_client.db.DBInterface` instance by calling
    :meth:`syncrepl_client.Syncrepl.db`.

    .. note::

        Instances are tied to the thread where they were created.  If you spawn
        a new thread, you should call :meth:`~syncrepl_client.db.clone` to get
        an instance that you can use in the new thread.

    .. warning::

        All tables, views, indexes, and triggers whose names start with
        `synrepl` are rerved for this code's use.  Please use a different name.

    .. warning::

        Do not change any of the database pragmas.

    .. note::

        Please do not `VACUUM`.  A vacuum is automatically run the first time a
        database is opened, and the optimize pragma is automatically called
        right before each instance is deleted.  The same is also done at the
        end of the refresh phase.

    Failure to observe the notes and warnings above may cause data corruption.
    If you are unable to observe the notes and warnings above, please use your
    own database.
    """


    # Track if a vacuum has been run yet on a file.
    vacuum_run = dict()


    def __init__(self, data_path):
        """Connect to our database, creating/upgrading it if necessary.

        :param str data_path: The path to the database file.

        :returns: A sqlite3 instance.

        Create a new instance.  This opens the SQLite database, creating a new
        one if needed.  Once open, the schema is checked.  If necessary, it is
        upgraded or created.

        .. warning::

            Do not use this instance, or cursors generated by this instance,
            outside of the instance's original thread.  If you spawn a new
            thread, call :meth:`~syncrepl_client.DBInterface.clone` to get an
            instance which is safe to use in this thread.
        """

        # Open our database file
        self.__data_path = data_path
        self.__db = sqlite3.connect(data_path,
            detect_types = sqlite3.PARSE_DECLTYPES
        )

        # Register our custom types
        self.__db.register_adapter(uuid.UUID, uuid_to_bytes)
        self.__db.register_converter('UUID', bytes_to_uuid)

        # Check (and, if necessary, upgrade) our schema.
        self._check_and_upgrade_schema()

        # If this is the first time we've opened the file, do a vacuum.
        if data_path not in self.vacuum_run:
            self.__db.execute('VACUUM')
            self.vacuum_run[data_path] = True

        # We are ready to go!
        return None


    def clone(self):
        """Clones an existing DBInterface, making an additional connection.

        :returns: A DBInterface instance.

        This method is used to clone a DBInterface instance (the "parent
        instance"), without modifying the parent instance.

        This is used in two cases:

        * A client wants their own database object, because they want to
          manage their own transactions.
        * A new thread has just been spawned.  SQLite will complain if a
          connection is used not in its original thread.

        This method is preferable to the constructor, because it skips all of
        the validation that is done by the constructor.
        """

        # We make an empty instance, set attributes, open the database, and
        # register our custom types.  That's it!
        newbie = DBInterface.__new__(DBInterface)
        newbie.__data_path = data_path
        newbie.__db = sqlite3.connect(self.__data_path,
            detect_types = sqlite3.PARSE_DECLTYPES
        )
        return newbie


    def __del__(self):
        # Do a local optimize before disconnecting.
        self.__db.execute('PRAGMA optimize')


    def cursor(self):
        """Returns a sqlite3 cursor connected to this database.

        :returns: A sqlite3.cursor instance.

        .. warning::

            Do not use the returned cursor outside of this thread!
        """
        return self._db.cursor()

    
    def _check_and_upgrade_schema(self):
        """Check (and, if needed, upgrade) a database's schema.

        :returns: None.

        .. note::

            This method is run automatically as part of instance initialization.
            It need not be run directly.

        This method takes an already-open database, and checks to see if it is
        using the latest schema.  If it is not, then the schema is either
        created (if it is missing), or it is upgraded (if it is out of date).

        .. note::

            For compatibility, only tables who's name starts with `syncrepl_`
            are examined.  If you are subclassing this class, then you should
            take care of your own tables, but remember to call this method as
            well!
        """

        # Let's see what tables we have.
        # We search for all table names that we've ever used.
        c = self.__db.execute('''
            SELECT name
              FROM sqlite_master
             WHERE (type='table') AND (name IN (
                       'syncrepl_schema',
                       'syncrepl_records',
                       'syncrepl_settings'
                       )
                   )
        ''')
        discovered_tables = c.fetchall()

        # If we don't have any tables, then we're at "schema version zero".
        # Go ahead and upgrade to the current version.
        if len(discovered_tables) == 0:
            c.close()
            return self._upgrade_schema(0)

        # Grab the list of tables, and make sure our version-number-containing
        # table is present.
        if 'syncrepl_schema' is not in discovered_tables:
            raise OSError

        # Grab the schema version number from the table
        c.execute('SELECT version FROM syncrepl_schema')
        schema_version = c.fetchall()
        if len(schema_version) != 1:
            raise OSError
        schema_version = schema_version[0][0]

        # Error out if the DB schema is too new.
        # Check our schema is valid for the specified version.
        # Then, if not the latest, upgrade!
        if schema_version > CURRENT_SCHEMA_VERSION:
            raise OSError
        self._validate_schema(schema_version)
        if schema_version < CURRENT_SCHEMA_VERSION:
            self._upgrade_schema(schema_version)

        # Woooo, schema check complete!


    def _validate_schema(self, version):


    def _upgrade_schema(self, old_version):
        # To enable recursion, support being asked to upgrade from the current
        # schema version to the current schema version.
        if old_version == CURRENT_SCHEMA_VERSION:
            return None

        # Start by upgrading us from version 0 to version 1.
        if old_version == 0:
            c = self.__db.execute('''
                CREATE TABLE syncrepl_schema (
                    version    UNSIGNED INT PRIMARY KEY
                )
            ''')
            c.execute('''
                CREATE TABLE syncrepl_records (
                    uuid       UUID         PRIMARY KEY,
                    dn         TEXT         UNIQUE,
                    attributes ATTRLIST
                )
            ''')
            c.execute('''
                CREATE TABLE syncrepl_settings (
                    name       TEXT         PRIMARY KEY,
                    value      BLOB
                )                
            ''')
            c.execute('INSERT INTO syncrepl_schema (version) VALUES (1)')
            c.commit()
            
            # Hand us off to upgrade us from version 1 to whatever we're at now.
            return self._upgrade_schema(1)


