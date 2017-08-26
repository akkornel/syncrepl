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


import pickle
import sqlite3
import uuid

from . import exceptions


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
sqlite3.register_adapter(uuid.UUID, uuid_to_bytes)

def bytes_to_uuid(uuid_bytes):
    """Convert a string of bytes into a UUID.

    :param bytes uuid_bytes: A string of bytes.

    :returns: A UUID object.
    """
    return uuid.UUID(bytes=uuid_bytes)
sqlite3.register_converter('UUID', bytes_to_uuid)


# We want to store an object into the database.
# Luckily, pickle is forward-compatible, so we're OK as long as the client
# keeps track of the Python version used (so we don't go back).

def object_to_bytes(object_in):
    """Convert an object to bytes.

    :param object object_in: The object.

    :returns: A bytes object.
    """
    # The parameters depend on Python version.
    if version_info >= 3:
        return pickle.dumps(object_in,
            protocol=pickle.HIGHEST_PROTOCOL
        )
    else:
        return pickle.dumps(object_in, pickle.HIGHEST_PROTOCOL)
sqlite3.register_adapter(object, object_to_bytes)


def bytes_to_object(object_bytes):
    """Decode a bytes-string-encoded object.

    :param bytes object_bytes: The bytes string-encoded object.

    :returns: The object.
    """
    # The parameters depend on Python version.
    if version_info[0] >= 3:
        return pickle.loads(object_bytes,
            fix_imports=False,
            encoding='bytes'
        )
    else:
        return pickle.loads(object_bytes)
        # Register our custom types
sqlite3.register_adapter('OBJECT', bytes_to_object)


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

        :raises: sqlite3.OperationalError

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
        self.__db = None
        self.__db = sqlite3.connect(data_path,
            detect_types = sqlite3.PARSE_DECLTYPES
        )

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
        newbie.__db = None
        newbie.__db = sqlite3.connect(self.__data_path,
            detect_types = sqlite3.PARSE_DECLTYPES
        )
        return newbie


    def __del__(self):
        # Do a local optimize before disconnecting.
        if self.__db is not None:
            self.__db.execute('PRAGMA optimize')
            self.__db.close()


    def cursor(self):
        """Returns a sqlite3 cursor connected to this database.

        :returns: A sqlite3.cursor instance.

        .. warning::

            Do not use the returned cursor outside of this thread!
        """
        return self._db.cursor()

    
    def commit(self):
        """Commit the current transaction.
        """
        self.__db.commit()


    def rollback(self):
        """Roll back the current transaction.
        """
        self.__db.rollback()

    
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
            return self._upgrade_schema(self.__db, 0)

        # Grab the list of tables, and make sure our version-number-containing
        # table is present.
        if 'syncrepl_schema' not in discovered_tables:
            raise exceptions.DBSchemaError('No schema table found')

        # Grab the schema version number from the table
        c.execute('SELECT version FROM syncrepl_schema')
        schema_version = c.fetchall()
        if len(schema_version) != 1:
            raise exceptions.DBSchemaError('Too many version entries')
        schema_version = schema_version[0][0]

        # Error out if the DB schema is too new.
        # Check our schema is valid for the specified version.
        # Then, if not the latest, upgrade!
        if schema_version > CURRENT_SCHEMA_VERSION:
            raise exceptions.SchemaVersionError()
        self._validate_schema(self.__db, schema_version)
        if schema_version < CURRENT_SCHEMA_VERSION:
            self._upgrade_schema(self.__db, schema_version)

        # Woooo, schema check/upgrade complete!


    @classmethod
    def _validate_schema(cls, db, version):
        # If the schema version is higher than we know, error out.
        if version > CURRENT_SCHEMA_VERSION:
            raise exceptions.SchemaVersionError('Schema too new')

        # Schema version zero should not be coming to us.
        if version == 0:
            raise exceptions.DBSchemaError('Schema version zero is implicit.')

        # Now we can validate the schema against the stated version.

        elif version == 1:
            pass


    @classmethod
    def _upgrade_schema(cls, db, old_version):
        # To enable recursion, support being asked to upgrade from the current
        # schema version to the current schema version.  This also tells us
        # that, since we're done making changes, it's a good time to commit!
        if old_version == CURRENT_SCHEMA_VERSION:
            return None

        # Start by upgrading us from version 0 to version 1.
        elif old_version == 0:
            db.executescript('''
                CREATE TABLE syncrepl_schema (
                    version    UNSIGNED INT PRIMARY KEY
                );

                CREATE TABLE syncrepl_records (
                    uuid       UUID         PRIMARY KEY,
                    dn         TEXT         UNIQUE,
                    attributes OBJECT
                );

                CREATE TABLE syncrepl_settings (
                    name       TEXT         PRIMARY KEY,
                    value      OBJECT
                );

                INSERT INTO syncrepl_schema (version) VALUES (1);
            ''')
            db.commit()
            
            # Hand us off to upgrade us from version 1 to whatever we're at now.
            return cls._upgrade_schema(db, 1)

        # The next upgrade would be here.

        # Finally, catch cases where the schema is too new.
        elif old_version > CURRENT_SCHEMA_VERSION:
            raise exceptions.SchemaVersionError('Schema too new')


    def get_setting(self, setting):
        """Get a setting from the syncrepl_settings table

        :param str setting: The name of a setting to fetch.

        :returns: An object, or None if the object is not stored.

        Returns a setting from the `syncrepl_settings` table, converted back
        into the object it previously was.
        """
        c = self.__db.execute('''
            SELECT value
              FROM syncrepl_settings
             WHERE name = ?
        ''', (setting,)
        )

        # We either get one result, or none, since we searched on the key.
        r = c.fetchone()
        if r is None:
            return None
        else:
            return r[0]


    def set_setting(self, setting, value):
        """Store a setting into the syncrepl_settings table.

        :param str setting: The name of the setting to store.

        :param object value: The object to store.

        :returns: None

        :throws:syncrepl_client.exceptions.DBSettingError

        This can be used to store a string, bytes, simple object, etc..
        Basically, anything that is a subclass of :class:`object`.

        .. note::
        
            Be careful storing integers, since they might not be a subclass at
            the time you try to store the setting.

        .. warning::

            Setting names starting with "syncrepl" are reserved.

        .. warning::

            This method does not commit!  You are responsible for committing at
            the appropriate time.
        """
        if not isinstance(setting, str):
            raise exceptions.DBSettingError(
                'Setting name is not a string.' % (setting,)
            )
        if not isinstance(value, object):
            raise exceptions.DBSettingError(
                'Value for setting "%s" is not an object.' % (setting,)
            )

        self.__db.execute('''
            INSERT OR REPLACE
                         INTO syncrepl_settings
                              (name, value)
                       VALUES (?, ?)
        ''', (setting, value)
        )
