#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PYTHON3_SITELIB=$(/usr/bin/python3 -Ic "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm langtable
        rlAssertRpm python3-langtable
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
    rlPhaseEnd

    rlPhaseStartTest
        for i in keyboards languages territories timezoneidparts timezones
        do
            rlRun "xmllint --noout --relaxng \
                ${PYTHON3_SITELIB}/langtable/schemas/${i}.rng \
                ${PYTHON3_SITELIB}/langtable/data/${i}.xml.gz \
                " 0 "testing ${i}.xml"
        done
        rlRun "/usr/bin/python3 /usr/share/doc/langtable/test_cases.py" \
            0 "Running test cases"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
