"""Provides the KB class.
"""
__version__ = "$Revision$"
# $Id$

import re

import LX
import LX.rdf
import sniff
import urllib
import LX.language
import pluggable

class UnsupportedDatatype(RuntimeError):
    pass

defaultScope = {
    ("legal",): re.compile(r"^[a-zA-Z0-9_]+$"),
    ("hint",): re.compile(r"(?:\/|#)([a-zA-Z0-9_]*)/?$")
    }

def stdValuesFilter(obj):
    if isinstance(obj, type("")): return 1
    if isinstance(obj, type(1)): return 1
    if isinstance(obj, type(0.1)): return 1
    # we'd like this to only be acceptable as a predicate/function...
    if obj == LX.ns.lx.uri: return 1
    return 0

class KB(list, pluggable.Store):
    """A Knowledge Base, a list of implicitely conjoined sentences.

    This is comparable to an RDF Graph if the Sentences here are all
    plain triples.

    Actually it's more complicated: we have a list of top level
    quantifications, too, so the elements can be open formulas iff
    their open variables are quantified by the kb. So the kb is a
    sentence of the form

       exists e1 e2 e3 ... (
          all x1 x2 x3 ... (
             formula1 & formula2 & formula3 ...
          )
       )

    (aka a sentence in "prenex" form.)

    """

    def __init__(self):
        self.exivars = []
        self.univars = []
        self.exIndex = 0
        self.__datatypeValuesChecked = { }

    def clear(self):
        self.__init__()
        self[:] = []

    def __str__(self):
        scope = defaultScope.copy()
        result = "\nKB Contents:"
        result+= "\n  exivars: "+", ".join(map(LX.expr.getNameInScope, self.exivars, [scope] * len(self.exivars)))
        result+= "\n  univars: "+", ".join(map(LX.expr.getNameInScope, self.univars, [scope] * len(self.univars)))
        result+= "\n  interpretation: "
        for (key,valueList) in self.__interpretation.iteritems():
            result+="\n     %s -->  %s"%(key.getNameInScope(scope), ", ".join(map(str, valueList)))
        result+= "\n  formulas: "
        result+= "\n     "
        result+= "\n     ".join(map(LX.expr.getNameInScope, self, [scope] * len(self)))
        result+= "\n"
        #result+= "\n  asFormulaString: "+self.asFormulaString()+"\n"
        #result+= "\n  asFormula:       "+str(self.asFormula())+"\n"
        return result
    
    def asFormulaString(self):
        scope = defaultScope.copy()
        result = ""
        if self.exivars: result += "exists "+" ".join(map(LX.expr.getNameInScope, self.exivars, [scope] * len(self.exivars)))
        if self.univars: result += "all "   +" ".join(map(LX.expr.getNameInScope, self.univars, [scope] * len(self.univars)))
        result += " (" + " &\n    ".join(map(LX.expr.getNameInScope, self, [scope] * len(self))) + ")"
        return result

    def asFormula(self):
        result = self[0]
        for s in self[1:]:
            result = LX.logic.AND(result, s)
        for v in self.univars:
            result = LX.logic.FORALL(v, result)
        for v in self.exivars:
            result = LX.logic.EXISTS(v, result)
        return result
       
    def prep(kb):
        """return a KB if possible, perhaps just the argument; throw
        an error we can't make a KB out of this thing"""
        if isinstance(kb, KB): return kb
        if isinstance(kb, list): return KB(kb)
        # nothing else for now
        raise RuntimeError, "Not convertable to a KB"
    prep = staticmethod(prep)

    def addSupportingTheory(self, term):
        """
        If the term, or elements of the term (as an Expr) are datatype
        value constants (as in LX.logic.ConstantForDatatypeValue),
        then we should make sure this KB has a datatype theory to
        support it.
        """
        if not term.isAtomic():
            for e in term.all:
                # print 
                assert(e != term)
                #self.addSupportingTheory(e)
            return
        try:
            pair = LX.logic.valuesForConstants[term]
        except KeyError:
            return

        (lexrep, dturi) = pair

        if pair in self.__datatypeValuesChecked: return

        #print "DTURI", dturi
        if dturi == "::native":
            # ignore for now....
            return
        
        if dturi == "http://www.w3.org/2001/XMLSchema#nonNegativeInteger":
            val = int(lexrep)
            assert(val != 0)   # would have been handled in LX.logic
            assert(val > 0)
            if val > 50:
                raise UnsupportedDatatype, "Int %s too big" % val
            for n in range(1, val+1):
                # print "Describing",n,"via:", n-1, "succ", n
                lesser = LX.logic.ConstantForDatatypeValue(str(n-1), dturi)
                succ = LX.logic.ConstantForURI('foo:succ')
                greater = LX.logic.ConstantForDatatypeValue(str(n), dturi)
                self.append(LX.logic.RDF(lesser,succ,greater))
                self.__datatypeValuesChecked[pair] = 1
            return

        #raise UnsupportedDatatype, ("unsupported datatype: "+lexrep+ ", type "+dturi)
        
        
    def add(self, formula, p=None, o=None):
        """
        Possibility: call Constant, ConstantForURI, ConstantForDTV,
        if you don't pass in constants...?  Nah.
        """
        if (p):
            s = formula
            self.append(LX.logic.RDF(s,p,o))
            self.addSupportingTheory(s)
            self.addSupportingTheory(p)
            self.addSupportingTheory(o)
            return

        #print "KB adding: ",
        #formula.dump()
        #print
        
        ##assert(isinstance(formula, LX.Formula))
        ##assert(LX.fol.isFirstOrderFormula(formula))
        # could check that all its openVars are in are vars
        self.append(formula)
        self.addSupportingTheory(formula)

    def addFrom(self, kb):
        for formula in kb:
            self.add(formula)
        self.exivars.extend(kb.exivars)
        self.univars.extend(kb.univars)
        self.exIndex = self.exIndex + kb.exIndex

    def newExistential(self, name=None):
        if name is None: name = "g"
        v = LX.logic.ExiVar(name)
        self.exivars.append(v)
        return v

    def reifyAsTrue(self):
        flat = KB()
        LX.rdf.flatten(self, flat, indirect=1)
        self.clear()
        self.addFrom(flat)

    def dereifyTrue(self):
        LX.rdf.dereify(self)

    def reifyAsTrueNonRDF(self):
        flat = KB()
        LX.rdf.flatten(self, flat, indirect=0)
        self.clear()
        self.addFrom(flat)

    def serializeWithOperators(self, scope, ops):
        result = ""
        for f in self:
            result = result + f.serializeWithOperators(scope, ops) + ".\n"
        result = result[0:-1]
        return result

        
    def isSelfConsistent(self):
        # should also try mace, icgns, etc...
        try:
            proof = LX.engine.otter.run(self)
            return 0
        except LX.engine.otter.SOSEmpty:
            return 1
        # ... just let other exceptions bubble up, for now

    def gather(self, prefixMap={}):
        """Fetch more knowledge associated with each term in the KB.

        Basically do a web retrieval on each URI term and incorporate
        the result.   This can be repeated if you want a broader
        inclusion.

        The prefixMap is used to override certain URI terms and point
        them somewhere else, such as when the published content for
        OWL doesn't contain the OWL axioms, you might use
          { 'http://www.w3.org/2002/07/owl#':
            'file:web-override/owl/' }

        Mapping to None means no gathering should be done on that prefix.
            
        The actual retrieval and parsing is done by .load(...)
        """
        uris = { }
        for formula in self:
            LX.logic.gatherURIs(formula, uris)
            #print "Did Formula", "Got", uris
        loadable = { }
        for uri in uris.keys():
            #print "Do with: ", uri
            for (key, value) in prefixMap.iteritems():
                if uri.startswith(key):
                    if value is None:
                        uri = None
                        #print " ... Dropped"
                    else:
                        uri = value + uri[len(key):]
                        #print " ... prefix", value
                    break
            if uri is None: continue
            try:
                uri=uri[0:uri.index("#")]
                #print "  ... chopped"
            except ValueError:
                pass
            loadable[uri] = 1
            #print "  ... done, as ", uri
        for uri in loadable.keys():
            self.load(uri)
            

    def load(self, uri, allowedLanguages=["*"]):
        """Add the formal meaning of identified document.

        ONLY BARELY IMPLEMENTED.   Intended to work in a
        blindfold-like manner; just works for hard coded languages
        right now.

        @@@   languageOverrides={}
           a mapping from string->string, overriding self-identificat.

        In the simplest case, this might mean opening a local file,
        which we know to contain n3, read the contents, and parse them
        directly to the kb.

        In a more complex case, we do an HTTP GET to obtain the
        document, using allowedLanguages to help guide our content
        negotiation, get some content, figure out what language is
        actually used, [recursively] load that language's definition,
        use that definition to build a parser for the original content,
        and parse it.

        We end up with a logical formula which might or might not be
        RDF (depending on how the language definition is written), but
        we can convert it, of course.  If we want to load from an
        untrusted source, load to a temporary kb first, reify it to
        the main KB, then apply your trust rules.

        See Blindfold.

        Does something like:

           1.  Identify the language
                 from content-type, other headers, embedded emacs magic strings,
                 suffixes, 
                 and perhaps a pre-arranged list of allowed languages.
           2.  Look up its definition
                 from an allowed set of language definitions, and/or the web
           3.  Parse it, collecting the semantics
                 perhaps by compiling a parser for it
           4.  return the logic sentence it claims
                 with some latitude as to form; the sentence only guarantees
                 to be inconsistent (T=F) or to entail only the intended
                 expression's meaning and separable metadata. 

        """
        #print "LOADING",uri
        stream=urllib.urlopen(uri)
        language=sniff.sniffLanguage(stream)
        #print "LANGUAGE",language

        # generalize this!   first one which can handle this lang!
        
        if language=="http://www.w3.org/1999/02/22-rdf-syntax-ns#RDF":
            language="rdflib"
        
        parser=LX.language.getParser(language=language)
        parser.parse(stream, self) 

if __name__ == "__main__":
    import doctest, sys
    doctest.testmod(sys.modules[__name__])
 
# $Log$
# Revision 1.16  2003-08-25 16:10:41  sandro
# removed all the leftover 'interpretation' stuff
#
# Revision 1.15  2003/08/22 20:49:41  sandro
# midway on getting load() and parser abstraction to work better
#
# Revision 1.14  2003/08/20 11:50:58  sandro
# --dereify implemented (linear time algorithm)
#
# Revision 1.13  2003/08/20 09:26:48  sandro
# update --flatten code path to work again, using newer URI strategy
#
# Revision 1.12  2003/08/01 15:27:21  sandro
# kind of vaguely working datatype support (for xsd unsigned ints)
#
# Revision 1.11  2003/07/31 18:25:15  sandro
# some unknown earlier changes...
# PLUS increasing support for datatype values
#
# Revision 1.10  2003/02/14 17:21:59  sandro
# Switched to import-as-needed for LX languages and engines
#
# Revision 1.9  2003/02/14 00:36:37  sandro
# added constantFor() method
#
# Revision 1.8  2003/02/13 19:48:31  sandro
# a little more thinking/comment about interpretations
#
# Revision 1.7  2003/02/01 05:58:10  sandro
# intermediate lbase support; getting there but buggy; commented out
# some fol checks 
#
# Revision 1.6  2003/01/29 20:59:34  sandro
# Moved otter language support back from engine/otter to language/otter
# Changed cwm.py to use this, and [ --engine=otter --think ] instead of
# --check.
#
# Revision 1.5  2003/01/29 06:09:18  sandro
# Major shift in style of LX towards using expr.py.  Added some access
# to otter, via --check.  Works as described in
# http://lists.w3.org/Archives/Public/www-archive/2003Jan/0024
# I don't like this UI; I imagine something more like --engine=otter
# --think, and --language=otter (instead of --otterDump).
# No tests for any of this.
#
# Revision 1.4  2002/10/03 16:13:02  sandro
# some minor changes to LX-formula stuff, but it's still broken in ways
# that don't show up on the regression test.
#
# mostly: moved llyn-LX conversion stuff out of llyn.py, into
# LX.engine.llynInterface.py
#
# Revision 1.3  2002/10/02 23:32:20  sandro
# not sure
#
# Revision 1.2  2002/08/29 16:39:55  sandro
# fixed various early typos and ommissions; working on logic bug which
# is manifesting in description loops  
#
# Revision 1.1  2002/08/29 11:00:46  sandro
# initial version, mostly written or heavily rewritten over the past
# week (not thoroughly tested)
#

  
