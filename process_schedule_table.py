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


"""
from StringIO import StringIO
import ldap # local lib to simplify LDAP work

from com.ziclix.python.sql import zxJDBC
from java.io import ObjectInputStream, ByteArrayInputStream, StringReader
from javax.xml.parsers import DocumentBuilderFactory
from org.xml.sax import InputSource, SAXParseException

import java
import sys
import base64
import gzip
import time
import com # lazy way to link all the ISIM libs

from com.ibm.itim.remoteservices.ejb.mediation import ServiceProviderReconciliationMessageObject
from com.ibm.itim.orchestration.lifecycle import LifecycleRuleMessageObject
#from com.ibm.itim.scheduling import ScheduledMessage

# get the DB connection properties
pm=com.ibm.itim.common.properties.PropertiesManager.gInstance() # we could use straght java, but this is easier. java.util.Properties().load(java.io.FileInputStream(java.lang.System.getProperty("isim.path")+"/enrole.properties"))
isimdburl=pm.getProperty("enrole.database","database.jdbc.driverUrl")
isimdbuser=pm.getProperty("enrole.database","database.db.user")
# decrypt password if needed
em=com.ibm.itim.util.EncryptionManager.getInstance()
isimdbpwd=pm.getProperty("enrole.database","database.db.password")
if pm.getProperty("enrole","enrole.password.database.encrypted") == "true":
    isimdbpwd=em.decrypt(isimdbpwd)

print "Connecting to "+isimdburl+" as "+isimdbuser+"..."
try:
    db=zxJDBC.connect(isimdburl,isimdbuser,isimdbpwd,pm.getProperty("enrole.database","database.jdbc.driver"))
    cur=db.cursor()
    cur.execute("select * from SCHEDULED_MESSAGE")
    if cur.rowcount == 0:
        print "The table is empty!"
        sys.exit(4)
except:
    print "DB connection failure %s, %s" % (sys.exc_info()[0],sys.exc_info()[1])
    sys.exit(5)

# get LDAP connection properties
isimldapurl=pm.getProperty("enrole.ldap.connection","java.naming.provider.url")
isimldapuser=pm.getProperty("enrole.ldap.connection","java.naming.security.principal")
isimldapproto=pm.getProperty("enrole.ldap.connection","java.naming.security.protocol")
isimldappwd=pm.getProperty("enrole.ldap.connection","java.naming.security.credentials")
if pm.getProperty("enrole", "enrole.password.ldap.encrypted") == "true":
    isimldappwd=em.decrypt(isimldappwd)

print "Connecting to "+isimldapurl+" as "+isimldapuser+"..."
isimldap=ldap.Directory(isimldapurl,isimldapuser,isimldappwd,isimldapproto)

#data=csv.DictReader(open(sys.argv[1],'r'),fieldnames=("SCHEDULED_TIME","SCHEDULED_MESSAGE_ID","MESSAGE","SERVER","CHECKPOINT_TIME","REFERENCE_ID","REFERENCE2_ID","SMALL_MESSAGE"))
fdump=open("scheduled_message.dump",'wb')
fout=open("scheduled_message_digest.csv",'w')
fscript=open("scheduled_message_cleanup.sql",'w')


count=0
for line in cur.fetchall():
    count+=1
    percent = int(count*100/cur.rowcount)
    sys.stdout.write("\rProcessing...%d%%" % percent)
    sys.stdout.flush()
    # the following message assignment is a bruteforce guess - may not be the right field. Enable the following line to see the full string 
    #print line
    if line[2] is not None:
        message=line[2]
    else:
        message=line[3] #was 7
    #message=re.sub(r'[\r\n]','',message) # swallow non-ascii stuff
    print>>fout,time.strftime("%m/%d/%Y %H:%M:%S,", time.localtime(line[0]/1000)), "%s," % line[1],
    print>>fdump,time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(line[0]/1000)), "%s," % line[1],
    try:
        zipmessage=base64.b64decode(message)
        zipstore=StringIO(zipmessage)
    except:
        print "Base64 decode failure %s, %s: %s" % (sys.exc_info()[0],sys.exc_info()[1],message)
        sys.exit(2)
    try:
        #message=zlib.decompress(zipmessage,8)
        fmessage=gzip.GzipFile(fileobj=zipstore,mode='rb') # the way to gunzip in jython
        message=fmessage.read()
        fmessage.close()
    except:
        print "Unzip failure %s, %s" % (sys.exc_info()[0],sys.exc_info()[1])
        #print>>fout, message
        fout.write(zipmessage)
        sys.exit(3)
    print>>fdump,message

    try:
        # process the content
        # first discern the serialization method
        if message[0:5] == "<?xml": # XML serialization.
            xmldoc=(DocumentBuilderFactory.newInstance()).newDocumentBuilder()
            doc=xmldoc.parse(InputSource(StringReader(message)))
            main=doc.getElementsByTagName("object"); # firstChild did not work since it returns #text
            print>>fout,"old,",
            msgbody=main.item(0).getElementsByTagName("class").item(0).childNodes#getElementsByTagName("object")
            #msgbody=doc.firstChild.firstChild.childNodes
            for obj in [msgbody.item(i) for i in range(msgbody.length) if msgbody.item(i).nodeName == "object"]: #msgbody.item(i).nodeType == msgbody.item(i).ELEMENT_NODE]:
                if obj.getAttribute("class") == "com.ibm.itim.remoteservices.ejb.mediation.ServiceProviderReconciliationMessageObject":
                    header="Recon"
                    so=obj.getElementsByTagName("special-object")
                    serviceDN=[so.item(i).getAttribute("value").strip() for i in range(so.length) if so.item(i).getAttribute("name") == "serviceDN"]
                    serviceName=isimldap.locate(serviceDN[0])["erservicename"][0].encode('ascii')
                    if serviceName == None:
                        print>>fscript,"DELETE FROM SCHEDULED_MESSAGE WHERE SCHEDULED_MESSAGE_ID = %s " % line[1]
                        header = "Bad recon"
                        serviceName = serviceDN[0]
                    print>>fout,"%s for %s" % (header, serviceName),
                    # <primitive name="dayOfWeek" class="int" value="0"/>
                    # <primitive name="month" class="int" value="0"/>
                    # <primitive name="dayOfMonth" class="int" value="-1"/>
                    # <primitive name="hour" class="int" value="2"/>
                    # <primitive name="minute" class="int" value="15"/>
                else:
                    print>>fout,"%s(%s):" % (obj.getAttribute("name"),obj.getAttribute("class")),
                    #if obj.getAttribute("name") == "ServiceDN"
                    #variables=[]
                    #specials=obj.getElementsByTagName("special-object")
                    #if specials.length > 0:
                    #    variables.extend([specials.item(i) for i in range(specials.length)])
                    #primitives=obj.getElementsByTagName("primitive")
                    #if primitives.length > 0:
                    #    variables.extend([primitives.item(i) for i in range(primitives.length)])
                # tag along subitems
                objclasses=obj.childNodes
                for objclass in [objclasses.item(i) for i in range(objclasses.length) if objclasses.item(i).nodeName == "class"]:
                    subnodes=objclass.childNodes
                    for variable in [subnodes.item(i) for i in range(subnodes.length) if subnodes.item(i).nodeName == "special-object" or subnodes.item(i).nodeName == "primitive"]:
                        #for variable in variables:
                        print>>fout,"%s=%s" % (variable.getAttribute("name"),variable.getAttribute("value")),
            print>>fout
        else: # native java serialization
            # deserialize that object
            obj=ObjectInputStream(ByteArrayInputStream(message)).readObject()
            print>>fout,"new,",
            msgbody=obj.getMessage()
            if type(msgbody) == ServiceProviderReconciliationMessageObject:
                header = "Recon"
                service=isimldap.locate(msgbody.getServiceDN())
                if service== None:
                    print>>fscript,"DELETE FROM SCHEDULED_MESSAGE WHERE SCHEDULED_MESSAGE_ID = %s " % line[1]
                    header = "Bad recon"
                    serviceName= msgbody.getServiceDN()
                else:
                    serviceName=service["erservicename"][0].encode('ascii')
                # really a com\ibm\itim\remoteservices\ejb\reconciliation\ReconciliationMessageObject
                print>>fout,"%s for %s every %s" % (header, serviceName,msgbody.getReconUnit()) #,msgbody.getRequester(),msgbody.getReconCallback()
            elif type(msgbody) == LifecycleRuleMessageObject:
                if msgbody.getRuleType()==LifecycleRuleMessageObject.RECERT_POLICY_TYPE:
                    header = isimldap.locate(msgbody.getPolicyDN())
                    if header is None:
                        header = "Recertification"
                elif msgbody.getRuleType()==LifecycleRuleMessageObject.CATEGORY_TYPE:
                    header = msgbody.getCategoryName()
                elif msgbody.getRuleType()==LifecycleRuleMessageObject.PROFILE_TYPE:
                    header = msgbody.getProfileName()
                else:
                    header = "Unknown"
                print>>fout,"%s lifecycle rule #%s" % (header, msgbody.getLifecycleRuleID()) # DistinguishedName
            else:
                print>>fout,msgbody
        # class contains object and primitives and special-object that contains classes
        # all have names and class. latter two have values
    except SAXParseException:
        print "sax parsing of %s %s, %s" % (sys.exc_info()[0],sys.exc_info()[1],message)
        sys.exit(6)
    #except:
    #    print "General SNAFU %s %s %s"% (sys.exc_info()[0],sys.exc_info()[1],message)
    #    sys.exit(6)
print " done."
