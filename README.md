""" Scheduled table review script
2015 (c) Alex Ivkin
v1.2

This script answers the questions "what will ISIM do and when". It does so by intelligently decoding the scheduled events table in ISIM.
Useful for a mass export of the recon schedules, finding out next steps for in-flight workflows, inconsistencies in the table etc.

The events in the scheduled_message are processed by an ISIM spooler periodically. More documentation of the table is in the ISIM 6.0 Database and Directory Server Schema Reference document

The scripts creates a table digest, a cleanup SQL script and and a full binary dump
* scheduled_message_digest.csv - a readable, CSV formatted digest of the scheduled_message table
* scheduled_message_cleanup.csv - SQL script to remove invalid references and obsolete entries
* scheduled_message.dump - raw, but decoded and unzipped dump of the messages from the table, for indepth investigations.

## Setup
Create sub folders under the current folder: isim/data, isim/data/keystore and isim/lib

Copy the following property files from the isim\data folder to the local isim\data folder
* Properties.properties - anchor properties, hardcoded and points to all other properties
* enRole.properties - core ISIM properties, control password encryption and storage
* enRoleDatabase.properties - DB connection properties
* enRoleLDAPConnection.properties - LDAP connection properties
* tmsMessages.properties - necessary for ISIM to 'translate' messages to the default locale
* enRoleLogging.properties - optional, tells where to save logging and at what level. Change handler.file.fileDir and logger.trace.level
* encryptionKey.properties - access key to the keystore

If your DB/LDAP creds are encrypted and stored in a keystore copy the appropriate isim keystore from isim\data\keystore to the new keystore folder

Copy the following libraries from isim\lib and jre\jre\lib to the local isim\lib folder
* itim_common.jar - common ITIM functions (EncryptionManager and PropertiesManager)
* itim_server.jar - java reflector for com.ibm.itim.scheduling, com.ibm.itim.remoteservices.ejb.mediation and other ISIM server classes,
* jlog.jar- logger for itim_server and others  com.ibm.log
* j2ee.jar- javax.ejb, used by the itim server classes
* aspectjrt.jar - org.aspectj, used by the itim server classes
* enroleagent.jar - com.ibm.daml, used by the itim server classes
* ibmjceprovider.jar (from IBM JVM jvm/lib/ext) - com.ibm.crypto.provider
* ibmpkcs.jar (from IBM JVM jvm/lib/) - com.ibm.misc/BASE64Decoder
* db2jcc.jar or other appropriate jar - your JDBC driver

## Usage:
`jython -J-cp "isim/data;isim/lib/*" process_schedule_table.py`

Tested on Win7
