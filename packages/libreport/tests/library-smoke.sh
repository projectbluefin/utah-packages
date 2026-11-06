#!/usr/bin/bash

gcc -x c -o smoke_test -lreport -Wno-implicit-function-declaration - <<EOF
#include <stdio.h>
int main(void) {
    libreport_init();
    printf("libreport initialized OK\n");
    return 0;
}
EOF
./smoke_test
