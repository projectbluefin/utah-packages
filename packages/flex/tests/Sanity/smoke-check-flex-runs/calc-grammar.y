%{
#include <stdio.h>
int yylex(void);
void yyerror(const char *);
%}

%token NUMBER
%token ADD SUB MUL DIV
%token EOL

%%

input:
	| input EOL { }
	| input expression EOL { printf("%d\n", $2); }
	;

expression:
	factor
	| expression ADD factor { $$ = $1 + $3; }
	| expression SUB factor { $$ = $1 - $3; }
	;

factor:
	NUMBER
	| factor MUL NUMBER { $$ = $1 * $3; }
	| factor DIV NUMBER { $$ = $1 / $3; }
	;

%%

int main(int argc, char ** argv) {
	yyparse();
}

void yyerror(const char *s) {
	fprintf(stderr, "ERROR: %s\n", s);
}
