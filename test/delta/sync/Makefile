# Sync calendars
#

P=python2.3  # Must be 2. python is still 1 by default on tux
W=../../../../../..
C=$W/2000/10/swap/cwm.py
PIM=$W/2000/10/swap/pim
CAL=$W/2002/12/cal
SWAP=$W/2000/10/swap
D=$(SWAP)/delta.py
TOICAL=PYTHONPATH=$(SWAP):$(CAL) $P $(SWAP)/pim/toIcal.py

.SUFFIXES: .ics3 .icsx .ics .cal
.ics.icsx:
	$P $(CAL)/fromIcal.py --noprotocol  $< > $@
.icsx.ics3:
	$P $C --rdf $< --n3 > $@
.cal.ics:
	PYTHONPATH=$(SWAP):$(CAL) $P $(PIM)/toIcal.py $<  > $@


all : check t2.n3

check:  s1a.n3 s1b.n3
	$P $(SWAP)/cant.py --from=s1a.n3 --diff=s1b.n3

# Generate both differnces:

d1a.n3 : t1a.ics3 t1.ics3
	$P $D --from=t1.ics3 --to=t1a.ics3 > $@

d1b.n3 : t1b.ics3 t1.ics3
	$P $D --from=t1.ics3 --to=t1b.ics3 > $@

# Generate both sums

s1a.cal : t1b.ics3 d1a.n3
	$P $C t1b.ics3 --patch=d1a.n3 --ntriples > $@
	
s1b.cal : t1a.ics3 d1b.n3
	$P $C t1a.ics3 --patch=d1b.n3 --ntriples > $@
	

#t2.ics : s1b.cal
#	$(TOICAL) s1b.n3  > $@



