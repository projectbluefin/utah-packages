#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
. /usr/share/beakerlib/beakerlib.sh || exit 1

FAILED=0
for dir in annotations annotationsDerived; do
    for xml in /usr/share/unicode/cldr/common/$dir/*.xml; do
        echo xmllint --noout --valid --postvalid $xml
        if ! xmllint --noout --valid --postvalid $xml; then
            FAILED=1
            break
        fi
        # CWE-93: Improper Neutralization of CRLF Sequences
        # https://cwe.mitre.org/data/definitions/93.html
        echo "file $xml | grep CRLF"
        if file $xml | grep CRLF; then
            FAILED=1
            break
        fi
        # Avoid 3 byte unauthenticated attacker;
        # sequence a tab, a vertical tab, and a newline
        echo grep -U '$\x09\x0b\0x0a' $xml
        if grep -U $'\x09\x0b\0x0a' $xml; then
            FAILED=1
            break
        fi
    done
    if test $FAILED -ne 0 ; then
        break
    fi
done

rlJournalStart
    rlPhaseStartTest
        rlAssertEquals "lint result" $FAILED 0
    rlPhaseEnd
rlJournalEnd
