''' LDAP management class
2015 (c) Alex Ivkin
v1.1
'''
from java.lang import System
from java.util import Hashtable
from javax.naming import Context
from javax.naming.directory import InitialDirContext, BasicAttributes, DirContext, SearchControls, BasicAttribute
from types import ListType

class Directory:
    def __init__(self,url,user,pwd,proto):
        env=Hashtable()
        env.put(Context.INITIAL_CONTEXT_FACTORY,"com.sun.jndi.ldap.LdapCtxFactory")
        env.put(Context.SECURITY_AUTHENTICATION,"simple")
        env.put(Context.PROVIDER_URL,url)
        env.put(Context.SECURITY_PRINCIPAL,user)
        env.put(Context.SECURITY_CREDENTIALS,pwd)
        if proto is not None:
            env.put(Context.SECURITY_PROTOCOL,proto)
        ctx=InitialDirContext(env)
        self.url=url
        self.ctx=ctx

    def __str__(self):
        return self.url

    def pythonize(self,results):
        # convert the namingenumeration into a list of enties that are hashes of attributes that contain lists of attributes
        pyresults=[]
        for result in results:
            pyresult={'dn':result.nameInNamespace.lower()} # force case insensitivity on the DN
            for attribute in result.attributes.all:
                pyresult[attribute.getID().lower()]=[value for value in attribute.all] #convert namingenumeration
            pyresults.append(pyresult)
        return pyresults

    def add(self,loc,entry):
        ''' Add a new entry to the LDAP based on the provided hash that contains entry attributes and corresponding values '''
        ldapentry=BasicAttributes()
        for (attr,values) in entry.items(): # add hashed attributes one by one
            attribute=BasicAttribute(attr)
            if type(values) is ListType: # add list items one by one
                for value in values:
                    attribute.add(value)
            else:
                attribute.add(values)
            #print str(attribute)
            ldapentry.put(attribute)
        self.ctx.createSubcontext(loc,ldapentry)

    def find(self,filter):
        srch=SearchControls()
        srch.setSearchScope(SearchControls.SUBTREE_SCOPE)
        results=self.ctx.search("",filter,srch)
        return self.pythonize(results)

    def locate(self,dn):
        ''' locate a specific entry in a tree by dn
            returns the located item
        '''
        if dn is None:
            return None
        try:
            attributes=self.ctx.getAttributes(dn) # without this call the lookup would return a new (blank) object
            pyresult={}
            for attribute in attributes.all:
                pyresult[attribute.getID().lower()]=[value for value in attribute.all] #convert namingenumeration
            return pyresult
        except:
            #print "%s, %s" % (sys.exc_info()[0],sys.exc_info()[1])
            return None

    def poke(self,dn,attr):
        ''' locate a specific entry in a tree by dn
            returns a specific attribute on that entry
        '''
        try:
            return self.ctx.getAttributes(dn).get(attr).get() # a bit elaborate due to java's nastyness
        except:
            #print "%s, %s" % (sys.exc_info()[0],sys.exc_info()[1])
            return None

    def modify(self,entry,attr,values):
        newAttrs=BasicAttributes(1)
        newattr=BasicAttribute(attr)
        for value in values:
            newattr.add(value)
        newAttrs.put(newattr)
        self.ctx.modifyAttributes(entry,DirContext.REPLACE_ATTRIBUTE,newAttrs)
