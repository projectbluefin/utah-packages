#!/bin/bash

check_pkg() {
    local pkg=$1
    if rpm -q $pkg
    then
        echo "PASS"
    else
        echo "FAIL"
    fi
}

check_dict() {
    if [ -f "/usr/share/hunspell/de_DE.dic" ]
    then
        echo "PASS"
    else
        echo "FAIL"
    fi
}

check_misspelled_word() {
    VAR1="Fedoraaa"
    VAR2=$(hunspell -l data.txt)
    if [ "$VAR1" = "$VAR2" ]; then
        echo "PASS"
    else
        echo "FAIL"
    fi
}

check_misspelled_line() {
    VAR1="Fedoraaa"
    VAR2=$(hunspell -L data.txt)
    if [ "$VAR1" = "$VAR2" ]; then
        echo "PASS"
    else
        echo "FAIL"
    fi
}

check_correct_word() {
    VAR1="Cloud\nLinux\nFedora"
    VAR1=$(echo -e "$VAR1")
    VAR2=$(hunspell -G data.txt)
    if [ "$VAR1" = "$VAR2" ]; then
        echo "PASS"
    else
        echo "FAIL"
    fi
}

check_pkg "hunspell"
check_pkg "hunspell-de"
check_dict
check_misspelled_word
check_misspelled_line
check_correct_word
