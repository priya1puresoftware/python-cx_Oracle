#------------------------------------------------------------------------------
# Copyright (c) 2016, 2020, Oracle and/or its affiliates. All rights reserved.
#
# Portions Copyright 2007-2015, Anthony Tuininga. All rights reserved.
#
# Portions Copyright 2001-2007, Computronix (Canada) Ltd., Edmonton, Alberta,
# Canada. All rights reserved.
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Sets the environment used by the cx_Oracle test suite. Production
# applications should consider using External Authentication to
# avoid hard coded credentials.
#
# You can set values in environment variables to bypass having the test suite
# request the information it requires.
#
#     CX_ORACLE_TEST_MAIN_USER: user used for most test cases
#     CX_ORACLE_TEST_MAIN_PASSWORD: password of user used for most test cases
#     CX_ORACLE_TEST_PROXY_USER: user for testing proxying
#     CX_ORACLE_TEST_PROXY_PASSWORD: password of user for testing proxying
#     CX_ORACLE_TEST_CONNECT_STRING: connect string for test suite
#     CX_ORACLE_TEST_ADMIN_USER: administrative user for test suite
#     CX_ORACLE_TEST_ADMIN_PASSWORD: administrative password for test suite
#
# CX_ORACLE_TEST_CONNECT_STRING can be set to an Easy Connect string, or a
# Net Service Name from a tnsnames.ora file or external naming service,
# or it can be the name of a local Oracle database instance.
#
# If cx_Oracle is using Instant Client, then an Easy Connect string is
# generally appropriate. The syntax is:
#
#   [//]host_name[:port][/service_name][:server_type][/instance_name]
#
# Commonly just the host_name and service_name are needed
# e.g. "localhost/orclpdb1" or "localhost/XEPDB1"
#
# If using a tnsnames.ora file, the file can be in a default
# location such as $ORACLE_HOME/network/admin/tnsnames.ora or
# /etc/tnsnames.ora.  Alternatively set the TNS_ADMIN environment
# variable and put the file in $TNS_ADMIN/tnsnames.ora.
#
# The administrative user for cloud databases is ADMIN and the administrative
# user for on premises databases is SYSTEM.
#------------------------------------------------------------------------------

import cx_Oracle
import getpass
import os
import sys
import unittest

# default values
DEFAULT_MAIN_USER = "pythontest"
DEFAULT_PROXY_USER = "pythontestproxy"
DEFAULT_CONNECT_STRING = "localhost/orclpdb1"

# dictionary containing all parameters; these are acquired as needed by the
# methods below (which should be used instead of consulting this dictionary
# directly) and then stored so that a value is not requested more than once
PARAMETERS = {}

def GetValue(name, label, defaultValue=""):
    value = PARAMETERS.get(name)
    if value is not None:
        return value
    envName = "CX_ORACLE_TEST_" + name
    value = os.environ.get(envName)
    if value is None:
        if defaultValue:
            label += " [%s]" % defaultValue
        label += ": "
        if defaultValue:
            value = input(label).strip()
        else:
            value = getpass.getpass(label)
        if not value:
            value = defaultValue
    PARAMETERS[name] = value
    return value

def GetMainUser():
    return GetValue("MAIN_USER", "Main User Name", DEFAULT_MAIN_USER)

def GetMainPassword():
    return GetValue("MAIN_PASSWORD", "Password for %s" % GetMainUser())

def GetProxyUser():
    return GetValue("PROXY_USER", "Proxy User Name", DEFAULT_PROXY_USER)

def GetProxyPassword():
    return GetValue("PROXY_PASSWORD", "Password for %s" % GetProxyUser())

def GetConnectString():
    return GetValue("CONNECT_STRING", "Connect String", DEFAULT_CONNECT_STRING)

def GetCharSetRatio():
    value = PARAMETERS.get("CS_RATIO")
    if value is None:
        connection = GetConnection()
        cursor = connection.cursor()
        cursor.execute("select 'X' from dual")
        col, = cursor.description
        value = col[3]
        PARAMETERS["CS_RATIO"] = value
    return value

def GetAdminConnectString():
    adminUser = GetValue("ADMIN_USER", "Administrative user", "admin")
    adminPassword = GetValue("ADMIN_PASSWORD", "Password for %s" % adminUser)
    return "%s/%s@%s" % (adminUser, adminPassword, GetConnectString())

def RunSqlScript(conn, scriptName, **kwargs):
    statementParts = []
    cursor = conn.cursor()
    replaceValues = [("&" + k + ".", v) for k, v in kwargs.items()] + \
            [("&" + k, v) for k, v in kwargs.items()]
    scriptDir = os.path.dirname(os.path.abspath(sys.argv[0]))
    fileName = os.path.join(scriptDir, "sql", scriptName + "Exec.sql")
    for line in open(fileName):
        if line.strip() == "/":
            statement = "".join(statementParts).strip()
            if statement:
                for searchValue, replaceValue in replaceValues:
                    statement = statement.replace(searchValue, replaceValue)
                try:
                    cursor.execute(statement)
                except:
                    print("Failed to execute SQL:", statement)
                    raise
            statementParts = []
        else:
            statementParts.append(line)
    cursor.execute("""
            select name, type, line, position, text
            from dba_errors
            where owner = upper(:owner)
            order by name, type, line, position""",
            owner = GetMainUser())
    prevName = prevObjType = None
    for name, objType, lineNum, position, text in cursor:
        if name != prevName or objType != prevObjType:
            print("%s (%s)" % (name, objType))
            prevName = name
            prevObjType = objType
        print("    %s/%s %s" % (lineNum, position, text))

def RunTestCases():
    print("Running tests for cx_Oracle version", cx_Oracle.version,
            "built at", cx_Oracle.buildtime)
    print("File:", cx_Oracle.__file__)
    print("Client Version:",
            ".".join(str(i) for i in cx_Oracle.clientversion()))
    with GetConnection() as connection:
        print("Server Version:", connection.version)
        print()
    unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))

def GetConnection(**kwargs):
    return cx_Oracle.connect(GetMainUser(), GetMainPassword(),
            GetConnectString(), encoding="UTF-8", nencoding="UTF-8", **kwargs)

def GetPool(user=None, password=None, **kwargs):
    if user is None:
        user = GetMainUser()
    if password is None:
        password = GetMainPassword()
    return cx_Oracle.SessionPool(user, password, GetConnectString(),
            encoding="UTF-8", nencoding="UTF-8", **kwargs)

def GetClientVersion():
    name = "CLIENT_VERSION"
    value = PARAMETERS.get(name)
    if value is None:
        value = cx_Oracle.clientversion()[:2]
        PARAMETERS[name] = value
    return value

def GetServerVersion():
    name = "SERVER_VERSION"
    value = PARAMETERS.get(name)
    if value is None:
        conn = GetConnection()
        value = tuple(int(s) for s in conn.version.split("."))[:2]
        PARAMETERS[name] = value
    return value

def SkipSodaTests():
    client = GetClientVersion()
    if client < (18, 3):
        return True
    server = GetServerVersion()
    if server < (18, 0):
        return True
    if server > (20, 1) and client < (20, 1):
        return True
    return False

class RoundTripInfo:

    def __init__(self, connection):
        self.prevRoundTrips = 0
        self.adminConn = cx_Oracle.connect(GetAdminConnectString())
        with connection.cursor() as cursor:
            cursor.execute("select sys_context('userenv', 'sid') from dual")
            self.sid, = cursor.fetchone()
        self.getRoundTrips()

    def getRoundTrips(self):
        with self.adminConn.cursor() as cursor:
            cursor.execute("""
                    select ss.value
                    from v$sesstat ss, v$statname sn
                    where ss.sid = :sid
                      and ss.statistic# = sn.statistic#
                      and sn.name like '%roundtrip%client%'""", sid=self.sid)
            currentRoundTrips, = cursor.fetchone()
            diffRoundTrips = currentRoundTrips - self.prevRoundTrips
            self.prevRoundTrips = currentRoundTrips
            return diffRoundTrips

class BaseTestCase(unittest.TestCase):

    def assertRoundTrips(self, n):
        self.assertEqual(self.roundTripInfo.getRoundTrips(), n)

    def getSodaDatabase(self, minclient=(18, 3), minserver=(18, 0),
            message="not supported with this client/server combination"):
        client = cx_Oracle.clientversion()[:2]
        if client < minclient:
            self.skipTest(message)
        server = tuple(int(s) for s in self.connection.version.split("."))[:2]
        if server < minserver:
            self.skipTest(message)
        if server > (20, 1) and client < (20, 1):
            self.skipTest(message)
        return self.connection.getSodaDatabase()

    def isOnOracleCloud(self, connection=None):
        if connection is None:
            connection = self.connection
        cursor = connection.cursor()
        cursor.execute("""
                select sys_context('userenv', 'service_name')
                from dual""")
        serviceName, = cursor.fetchone()
        return serviceName.endswith("oraclecloud.com")

    def setUp(self):
        self.connection = GetConnection()
        self.cursor = self.connection.cursor()

    def setUpRoundTripChecker(self):
        self.roundTripInfo = RoundTripInfo(self.connection)

    def tearDown(self):
        self.connection.close()
        del self.cursor
        del self.connection


def load_tests(loader, standard_tests, pattern):
    return loader.discover(os.path.dirname(__file__))

if __name__ == "__main__":
    RunTestCases()
