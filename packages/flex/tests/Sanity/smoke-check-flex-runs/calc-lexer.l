%option noyywrap
%{
#include "calc-grammar.tab.h"
void yyerror(const char *);
%}

%%
"+"     { return ADD; }
"-"     { return SUB; }
"*"     { return MUL; }
"/"     { return DIV; }
[0-9]+  { yylval = atoi(yytext); return NUMBER; }
\n      { return EOL; }
[ \t]   { /* ignore whitespaces */ }
.       { yyerror("unexpected character"); }
%%
