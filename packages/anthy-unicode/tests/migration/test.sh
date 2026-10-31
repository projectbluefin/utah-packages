#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
. /usr/share/beakerlib/beakerlib.sh || exit 1

[ -d $HOME/.anthy ] || mkdir $HOME/.anthy

rlJournalStart
    rlPhaseStartTest
        rlRun -t "anthy-dic-tool-unicode --load /usr/share/anthy-unicode/dic-tool-input"
        rlRun -t "diff $HOME/.config/anthy/private_words_default /usr/share/anthy-unicode/dic-tool-result"
        rlRun -t "anthy-dic-tool-unicode --dump"
        rlRun -t "mv $HOME/.config/anthy/private_words_default $HOME/.anthy"
        rlRun -t "anthy-dic-tool-unicode --migrate"
        rlRun -t "diff $HOME/.config/anthy/private_words_default /usr/share/anthy-unicode/dic-tool-result"
    rlPhaseEnd
rlJournalEnd
