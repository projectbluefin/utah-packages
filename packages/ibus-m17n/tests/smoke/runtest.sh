#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartSetup
        rlShowPackageVersion ibus-m17n
        rlRun -t -l "VERSION=$(rpm -q ibus-m17n --queryformat='%{version}')" 0 "Get VERSION"
        FEDORA_VERSION=$(rlGetDistroRelease)
        rlLog "FEDORA_VERSION=${DISTRO_RELEASE}"
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
        rlFetchSrcForInstalled "ibus-m17n"
        rlRun "rpm --define '_topdir $tmp' -i *src.rpm"
        rlRun -t -l "mkdir BUILD" 0 "Creating BUILD directory"
        rlRun -t -l "rpmbuild --noclean --nodeps --define '_topdir $tmp' -bp $tmp/SPECS/*spec"
        if [ -d BUILD/ibus-m17n-${VERSION}-build ]; then
            rlRun -t -l "pushd BUILD/ibus-m17n-${VERSION}-build/ibus-m17n-${VERSION}"
        else
            rlRun -t -l "pushd BUILD/ibus-m17n-${VERSION}"
        fi
        rlRun "set -o pipefail"
        rlRun -t -l "NOCONFIGURE=1 ./autogen.sh"
        rlRun -t -l "./configure --disable-static --with-gtk=3.0"
        rlRun -t -l "make check"
        rlAssertRpm "ibus"
        rlAssertRpm "m17n-db"
    rlPhaseEnd

    rlPhaseStartTest
        # The -s option and & is important, when using the -d option
        # in this test environment the error “Can't connect to IBus.” occurs.
        rlRun -t -l "ibus-daemon -v -r -s &"
        rlRun "sleep 5" 0 "Give ibus-daemon some time to start properly."
        for name in \
            am:sera \
            ar:kbd \
            ar:translit \
            as:inscript \
            as:inscript2 \
            as:itrans \
            as:phonetic \
            ath:phonetic \
            bla:phonetic \
            bn:disha \
            bn:inscript \
            bn:inscript2 \
            bn:itrans \
            bn:probhat \
            bo:ewts \
            bo:tcrc \
            bo:wylie \
            brx:inscript2-deva \
            cr:western \
            da:post \
            doi:inscript2-deva \
            dv:phonetic \
            eo:h-fundamente \
            eo:h-sistemo \
            eo:plena \
            eo:q-sistemo \
            eo:vi-sistemo \
            eo:x-sistemo \
            fa:isiri \
            fr:azerty \
            grc:mizuochi \
            gu:inscript \
            gu:inscript2 \
            gu:itrans \
            gu:phonetic \
            hi:inscript \
            hi:inscript2 \
            hi:itrans \
            hi:optitransv2 \
            hi:phonetic \
            hi:remington \
            hi:typewriter \
            hi:vedmata \
            hu:rovas-post \
            ii:phonetic \
            iu:phonetic \
            kk:arabic \
            km:yannis \
            kn:inscript \
            kn:inscript2 \
            kn:itrans \
            kn:kgp \
            kn:optitransv2 \
            kn:typewriter \
            kok:inscript2-deva \
            ks:inscript \
            ks:inscript2-deva \
            ks:kbd \
            lo:lrt \
            mai:inscript \
            mai:inscript2 \
            ml:enhanced-inscript \
            ml:inscript \
            ml:inscript2 \
            ml:itrans \
            ml:mozhi \
            ml:remington \
            ml:swanalekha \
            mni:inscript2-beng \
            mni:inscript2-mtei \
            mr:inscript \
            mr:inscript2 \
            mr:itrans \
            mr:phonetic \
            mr:remington \
            mr:typewriter \
            ne:inscript2-deva \
            ne:rom \
            ne:rom-translit \
            ne:trad \
            ne:trad-ttf \
            nsk:phonetic \
            oj:phonetic \
            or:inscript \
            or:inscript2 \
            or:itrans \
            or:phonetic \
            pa:anmollipi \
            pa:inscript \
            pa:inscript2-guru \
            pa:itrans \
            pa:jhelum \
            pa:phonetic \
            ps:phonetic \
            ru:phonetic \
            ru:translit \
            ru:yawerty \
            sa:IAST \
            sa:harvard-kyoto \
            sa:inscript2 \
            sa:itrans \
            sat:inscript2-deva \
            sat:inscript2-olck \
            sd:inscript \
            sd:inscript2-deva \
            si:phonetic-dynamic \
            si:samanala \
            si:sayura \
            si:singlish \
            si:sumihiri \
            si:transliteration \
            si:wijesekera \
            sv:post \
            t:latn-post \
            t:latn-pre \
            t:latn1-pre \
            t:lsymbol \
            t:math-latex \
            t:rfc1345 \
            t:ssymbol \
            t:syrc-phonetic \
            t:unicode \
            ta:inscript \
            ta:inscript2 \
            ta:itrans \
            ta:lk-renganathan \
            ta:phonetic \
            ta:tamil99 \
            ta:typewriter \
            ta:vutam \
            tai:sonla-kbd \
            te:apple \
            te:inscript \
            te:inscript2 \
            te:itrans \
            te:pothana \
            te:rts \
            te:sarala \
            th:kesmanee \
            th:pattachote \
            th:tis820 \
            ur:phonetic \
            vi:han \
            vi:nomtelex \
            vi:nomvni \
            vi:tcvn \
            vi:telex \
            vi:viqr \
            vi:vni \
            yi:yivo
        do
            rlRun -t -l "/usr/libexec/ibus-engine-m17n --xml 2>/dev/null | grep '<name>m17n:${name}</name>'" \
                0 "checking whether 'ibus-engine-m17n --xml' can list m17n:${name}:"
            rlRun -t -l "ibus list-engine --name-only | grep 'm17n:${name}$'" \
                0 "checking whether ibus can list m17n:${name}:"
        done
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd; popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
