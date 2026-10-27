%option noyywrap
%{
#include <stdio.h>

int chars = 0;
int lines = 0;
%}

%%

\n { lines++; chars++; }
.  { chars++; }

%%

int main(int argc, char ** argv) {
	yylex();
	printf("chars: %d\n", chars);
	printf("lines: %d\n", lines);
	return 0;
}
