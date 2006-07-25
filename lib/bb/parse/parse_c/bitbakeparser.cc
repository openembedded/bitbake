/* Driver template for the LEMON parser generator.
** The author disclaims copyright to this source code.
*/
/* First off, code is include which follows the "include" declaration
** in the input file. */
#include <stdio.h>
#line 43 "bitbakeparser.y"

#include "token.h"
#include "lexer.h"
#include "python_output.h"
#line 14 "bitbakeparser.c"
/* Next is all token values, in a form suitable for use by makeheaders.
** This section will be null unless lemon is run with the -m switch.
*/
/* 
** These constants (all generated automatically by the parser generator)
** specify the various kinds of tokens (terminals) that the parser
** understands. 
**
** Each symbol here is a terminal symbol in the grammar.
*/
/* Make sure the INTERFACE macro is defined.
*/
#ifndef INTERFACE
# define INTERFACE 1
#endif
/* The next thing included is series of defines which control
** various aspects of the generated parser.
**    YYCODETYPE         is the data type used for storing terminal
**                       and nonterminal numbers.  "unsigned char" is
**                       used if there are fewer than 250 terminals
**                       and nonterminals.  "int" is used otherwise.
**    YYNOCODE           is a number of type YYCODETYPE which corresponds
**                       to no legal terminal or nonterminal number.  This
**                       number is used to fill in empty slots of the hash 
**                       table.
**    YYFALLBACK         If defined, this indicates that one or more tokens
**                       have fall-back values which should be used if the
**                       original value of the token will not parse.
**    YYACTIONTYPE       is the data type used for storing terminal
**                       and nonterminal numbers.  "unsigned char" is
**                       used if there are fewer than 250 rules and
**                       states combined.  "int" is used otherwise.
**    bbparseTOKENTYPE     is the data type used for minor tokens given 
**                       directly to the parser from the tokenizer.
**    YYMINORTYPE        is the data type used for all minor tokens.
**                       This is typically a union of many types, one of
**                       which is bbparseTOKENTYPE.  The entry in the union
**                       for base tokens is called "yy0".
**    YYSTACKDEPTH       is the maximum depth of the parser's stack.
**    bbparseARG_SDECL     A static variable declaration for the %extra_argument
**    bbparseARG_PDECL     A parameter declaration for the %extra_argument
**    bbparseARG_STORE     Code to store %extra_argument into yypParser
**    bbparseARG_FETCH     Code to extract %extra_argument from yypParser
**    YYNSTATE           the combined number of states.
**    YYNRULE            the number of rules in the grammar
**    YYERRORSYMBOL      is the code number of the error symbol.  If not
**                       defined, then do no error processing.
*/
#define YYCODETYPE unsigned char
#define YYNOCODE 44
#define YYACTIONTYPE unsigned char
#define bbparseTOKENTYPE token_t
typedef union {
  bbparseTOKENTYPE yy0;
  int yy87;
} YYMINORTYPE;
#define YYSTACKDEPTH 100
#define bbparseARG_SDECL lex_t* lex;
#define bbparseARG_PDECL ,lex_t* lex
#define bbparseARG_FETCH lex_t* lex = yypParser->lex
#define bbparseARG_STORE yypParser->lex = lex
#define YYNSTATE 82
#define YYNRULE 45
#define YYERRORSYMBOL 30
#define YYERRSYMDT yy87
#define YY_NO_ACTION      (YYNSTATE+YYNRULE+2)
#define YY_ACCEPT_ACTION  (YYNSTATE+YYNRULE+1)
#define YY_ERROR_ACTION   (YYNSTATE+YYNRULE)

/* Next are that tables used to determine what action to take based on the
** current state and lookahead token.  These tables are used to implement
** functions that take a state number and lookahead value and return an
** action integer.  
**
** Suppose the action integer is N.  Then the action is determined as
** follows
**
**   0 <= N < YYNSTATE                  Shift N.  That is, push the lookahead
**                                      token onto the stack and goto state N.
**
**   YYNSTATE <= N < YYNSTATE+YYNRULE   Reduce by rule N-YYNSTATE.
**
**   N == YYNSTATE+YYNRULE              A syntax error has occurred.
**
**   N == YYNSTATE+YYNRULE+1            The parser accepts its input.
**
**   N == YYNSTATE+YYNRULE+2            No such action.  Denotes unused
**                                      slots in the yy_action[] table.
**
** The action table is constructed as a single large table named yy_action[].
** Given state S and lookahead X, the action is computed as
**
**      yy_action[ yy_shift_ofst[S] + X ]
**
** If the index value yy_shift_ofst[S]+X is out of range or if the value
** yy_lookahead[yy_shift_ofst[S]+X] is not equal to X or if yy_shift_ofst[S]
** is equal to YY_SHIFT_USE_DFLT, it means that the action is not in the table
** and that yy_default[S] should be used instead.  
**
** The formula above is for computing the action when the lookahead is
** a terminal symbol.  If the lookahead is a non-terminal (as occurs after
** a reduce action) then the yy_reduce_ofst[] array is used in place of
** the yy_shift_ofst[] array and YY_REDUCE_USE_DFLT is used in place of
** YY_SHIFT_USE_DFLT.
**
** The following are the tables generated in this section:
**
**  yy_action[]        A single table containing all actions.
**  yy_lookahead[]     A table containing the lookahead for each entry in
**                     yy_action.  Used to detect hash collisions.
**  yy_shift_ofst[]    For each state, the offset into yy_action for
**                     shifting terminals.
**  yy_reduce_ofst[]   For each state, the offset into yy_action for
**                     shifting non-terminals after a reduce.
**  yy_default[]       Default action for each state.
*/
static const YYACTIONTYPE yy_action[] = {
 /*     0 */    82,    3,    7,    8,   38,   22,   39,   24,   26,   32,
 /*    10 */    34,   28,   30,    2,   21,   40,   53,   70,   55,   44,
 /*    20 */    60,   65,   67,  128,    1,   36,   69,   77,   42,   46,
 /*    30 */    11,   66,   13,   15,   17,   19,   64,   62,    9,    7,
 /*    40 */    74,   38,   45,   81,   59,   57,   38,   38,   73,   76,
 /*    50 */     5,   68,   52,   50,   14,   31,   47,   71,   48,   10,
 /*    60 */    72,   33,   23,   49,    6,   41,   51,   78,   75,   16,
 /*    70 */     4,   54,   35,   25,   18,   80,   79,   56,   27,   37,
 /*    80 */    58,   12,   61,   29,   43,   63,   20,
};
static const YYCODETYPE yy_lookahead[] = {
 /*     0 */     0,    1,    2,    3,   23,    4,   25,    6,    7,    8,
 /*    10 */     9,   10,   11,   33,   34,   15,   16,    1,   18,   14,
 /*    20 */    20,   21,   22,   31,   32,   24,   26,   27,   13,   14,
 /*    30 */     4,   19,    6,    7,    8,    9,   39,   40,    1,    2,
 /*    40 */    24,   23,   12,   25,   37,   38,   23,   23,   25,   25,
 /*    50 */    42,   19,   35,   36,    5,    5,   12,   24,   13,   34,
 /*    60 */    41,    5,    5,   12,   28,   12,   35,    1,   41,    5,
 /*    70 */    29,    1,    5,    5,    5,   41,   24,   17,    5,   41,
 /*    80 */    37,    5,   19,    5,   12,   39,    5,
};
#define YY_SHIFT_USE_DFLT (-20)
static const signed char yy_shift_ofst[] = {
 /*     0 */   -20,    0,  -20,   41,  -20,   36,  -20,  -20,   37,  -20,
 /*    10 */    26,   76,  -20,   49,  -20,   64,  -20,   69,  -20,   81,
 /*    20 */   -20,    1,   57,  -20,   68,  -20,   73,  -20,   78,  -20,
 /*    30 */    50,  -20,   56,  -20,   67,  -20,  -20,  -19,  -20,  -20,
 /*    40 */    53,   15,   72,    5,   30,  -20,   44,   45,   51,  -20,
 /*    50 */    53,  -20,  -20,   70,  -20,   60,  -20,   60,  -20,  -20,
 /*    60 */    63,  -20,   63,  -20,  -20,   12,  -20,   32,  -20,   16,
 /*    70 */    33,  -20,   23,  -20,  -20,   24,  -20,   66,   52,  -20,
 /*    80 */    18,  -20,
};
#define YY_REDUCE_USE_DFLT (-21)
static const signed char yy_reduce_ofst[] = {
 /*     0 */    -8,  -20,  -21,  -21,    8,  -21,  -21,  -21,   25,  -21,
 /*    10 */   -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,
 /*    20 */   -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,
 /*    30 */   -21,  -21,  -21,  -21,  -21,  -21,   38,  -21,  -21,  -21,
 /*    40 */    17,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,  -21,
 /*    50 */    31,  -21,  -21,  -21,  -21,    7,  -21,   43,  -21,  -21,
 /*    60 */    -3,  -21,   46,  -21,  -21,  -21,  -21,  -21,  -21,  -21,
 /*    70 */   -21,   19,  -21,  -21,   27,  -21,  -21,  -21,  -21,   34,
 /*    80 */   -21,  -21,
};
static const YYACTIONTYPE yy_default[] = {
 /*     0 */    84,  127,   83,   85,  125,  126,  124,   86,  127,   85,
 /*    10 */   127,  127,   87,  127,   88,  127,   89,  127,   90,  127,
 /*    20 */    91,  127,  127,   92,  127,   93,  127,   94,  127,   95,
 /*    30 */   127,   96,  127,   97,  127,   98,  119,  127,  118,  120,
 /*    40 */   127,  101,  127,  102,  127,   99,  127,  103,  127,  100,
 /*    50 */   106,  104,  105,  127,  107,  127,  108,  111,  109,  110,
 /*    60 */   127,  112,  115,  113,  114,  127,  116,  127,  117,  127,
 /*    70 */   127,  119,  127,  121,  119,  127,  122,  127,  127,  119,
 /*    80 */   127,  123,
};
#define YY_SZ_ACTTAB (sizeof(yy_action)/sizeof(yy_action[0]))

/* The next table maps tokens into fallback tokens.  If a construct
** like the following:
** 
**      %fallback ID X Y Z.
**
** appears in the grammer, then ID becomes a fallback token for X, Y,
** and Z.  Whenever one of the tokens X, Y, or Z is input to the parser
** but it does not parse, the type of the token is changed to ID and
** the parse is retried before an error is thrown.
*/
#ifdef YYFALLBACK
static const YYCODETYPE yyFallback[] = {
};
#endif /* YYFALLBACK */

/* The following structure represents a single element of the
** parser's stack.  Information stored includes:
**
**   +  The state number for the parser at this level of the stack.
**
**   +  The value of the token stored at this level of the stack.
**      (In other words, the "major" token.)
**
**   +  The semantic value stored at this level of the stack.  This is
**      the information used by the action routines in the grammar.
**      It is sometimes called the "minor" token.
*/
struct yyStackEntry {
  int stateno;       /* The state-number */
  int major;         /* The major token value.  This is the code
                     ** number for the token at this stack level */
  YYMINORTYPE minor; /* The user-supplied minor token value.  This
                     ** is the value of the token  */
};
typedef struct yyStackEntry yyStackEntry;

/* The state of the parser is completely contained in an instance of
** the following structure */
struct yyParser {
  int yyidx;                    /* Index of top element in stack */
  int yyerrcnt;                 /* Shifts left before out of the error */
  bbparseARG_SDECL                /* A place to hold %extra_argument */
  yyStackEntry yystack[YYSTACKDEPTH];  /* The parser's stack */
};
typedef struct yyParser yyParser;

#ifndef NDEBUG
#include <stdio.h>
static FILE *yyTraceFILE = 0;
static char *yyTracePrompt = 0;
#endif /* NDEBUG */

#ifndef NDEBUG
/* 
** Turn parser tracing on by giving a stream to which to write the trace
** and a prompt to preface each trace message.  Tracing is turned off
** by making either argument NULL 
**
** Inputs:
** <ul>
** <li> A FILE* to which trace output should be written.
**      If NULL, then tracing is turned off.
** <li> A prefix string written at the beginning of every
**      line of trace output.  If NULL, then tracing is
**      turned off.
** </ul>
**
** Outputs:
** None.
*/
void bbparseTrace(FILE *TraceFILE, char *zTracePrompt){
  yyTraceFILE = TraceFILE;
  yyTracePrompt = zTracePrompt;
  if( yyTraceFILE==0 ) yyTracePrompt = 0;
  else if( yyTracePrompt==0 ) yyTraceFILE = 0;
}
#endif /* NDEBUG */

#ifndef NDEBUG
/* For tracing shifts, the names of all terminals and nonterminals
** are required.  The following table supplies these names */
static const char *const yyTokenName[] = { 
  "$",             "SYMBOL",        "VARIABLE",      "EXPORT",      
  "OP_ASSIGN",     "STRING",        "OP_PREDOT",     "OP_POSTDOT",  
  "OP_IMMEDIATE",  "OP_COND",       "OP_PREPEND",    "OP_APPEND",   
  "TSYMBOL",       "BEFORE",        "AFTER",         "ADDTASK",     
  "ADDHANDLER",    "FSYMBOL",       "EXPORT_FUNC",   "ISYMBOL",     
  "INHERIT",       "INCLUDE",       "REQUIRE",       "PROC_BODY",   
  "PROC_OPEN",     "PROC_CLOSE",    "PYTHON",        "FAKEROOT",    
  "DEF_BODY",      "DEF_ARGS",      "error",         "program",     
  "statements",    "statement",     "variable",      "task",        
  "tasks",         "func",          "funcs",         "inherit",     
  "inherits",      "proc_body",     "def_body",    
};
#endif /* NDEBUG */

#ifndef NDEBUG
/* For tracing reduce actions, the names of all rules are required.
*/
static const char *const yyRuleName[] = {
 /*   0 */ "program ::= statements",
 /*   1 */ "statements ::= statements statement",
 /*   2 */ "statements ::=",
 /*   3 */ "variable ::= SYMBOL",
 /*   4 */ "variable ::= VARIABLE",
 /*   5 */ "statement ::= EXPORT variable OP_ASSIGN STRING",
 /*   6 */ "statement ::= EXPORT variable OP_PREDOT STRING",
 /*   7 */ "statement ::= EXPORT variable OP_POSTDOT STRING",
 /*   8 */ "statement ::= EXPORT variable OP_IMMEDIATE STRING",
 /*   9 */ "statement ::= EXPORT variable OP_COND STRING",
 /*  10 */ "statement ::= variable OP_ASSIGN STRING",
 /*  11 */ "statement ::= variable OP_PREDOT STRING",
 /*  12 */ "statement ::= variable OP_POSTDOT STRING",
 /*  13 */ "statement ::= variable OP_PREPEND STRING",
 /*  14 */ "statement ::= variable OP_APPEND STRING",
 /*  15 */ "statement ::= variable OP_IMMEDIATE STRING",
 /*  16 */ "statement ::= variable OP_COND STRING",
 /*  17 */ "task ::= TSYMBOL BEFORE TSYMBOL AFTER TSYMBOL",
 /*  18 */ "task ::= TSYMBOL AFTER TSYMBOL BEFORE TSYMBOL",
 /*  19 */ "task ::= TSYMBOL",
 /*  20 */ "task ::= TSYMBOL BEFORE TSYMBOL",
 /*  21 */ "task ::= TSYMBOL AFTER TSYMBOL",
 /*  22 */ "tasks ::= tasks task",
 /*  23 */ "tasks ::= task",
 /*  24 */ "statement ::= ADDTASK tasks",
 /*  25 */ "statement ::= ADDHANDLER SYMBOL",
 /*  26 */ "func ::= FSYMBOL",
 /*  27 */ "funcs ::= funcs func",
 /*  28 */ "funcs ::= func",
 /*  29 */ "statement ::= EXPORT_FUNC funcs",
 /*  30 */ "inherit ::= ISYMBOL",
 /*  31 */ "inherits ::= inherits inherit",
 /*  32 */ "inherits ::= inherit",
 /*  33 */ "statement ::= INHERIT inherits",
 /*  34 */ "statement ::= INCLUDE ISYMBOL",
 /*  35 */ "statement ::= REQUIRE ISYMBOL",
 /*  36 */ "proc_body ::= proc_body PROC_BODY",
 /*  37 */ "proc_body ::=",
 /*  38 */ "statement ::= variable PROC_OPEN proc_body PROC_CLOSE",
 /*  39 */ "statement ::= PYTHON SYMBOL PROC_OPEN proc_body PROC_CLOSE",
 /*  40 */ "statement ::= PYTHON PROC_OPEN proc_body PROC_CLOSE",
 /*  41 */ "statement ::= FAKEROOT SYMBOL PROC_OPEN proc_body PROC_CLOSE",
 /*  42 */ "def_body ::= def_body DEF_BODY",
 /*  43 */ "def_body ::=",
 /*  44 */ "statement ::= SYMBOL DEF_ARGS def_body",
};
#endif /* NDEBUG */

/*
** This function returns the symbolic name associated with a token
** value.
*/
const char *bbparseTokenName(int tokenType){
#ifndef NDEBUG
  if( tokenType>0 && tokenType<(sizeof(yyTokenName)/sizeof(yyTokenName[0])) ){
    return yyTokenName[tokenType];
  }else{
    return "Unknown";
  }
#else
  return "";
#endif
}

/* 
** This function allocates a new parser.
** The only argument is a pointer to a function which works like
** malloc.
**
** Inputs:
** A pointer to the function used to allocate memory.
**
** Outputs:
** A pointer to a parser.  This pointer is used in subsequent calls
** to bbparse and bbparseFree.
*/
void *bbparseAlloc(void *(*mallocProc)(size_t)){
  yyParser *pParser;
  pParser = (yyParser*)(*mallocProc)( (size_t)sizeof(yyParser) );
  if( pParser ){
    pParser->yyidx = -1;
  }
  return pParser;
}

/* The following function deletes the value associated with a
** symbol.  The symbol can be either a terminal or nonterminal.
** "yymajor" is the symbol code, and "yypminor" is a pointer to
** the value.
*/
static void yy_destructor(YYCODETYPE yymajor, YYMINORTYPE *yypminor){
  switch( yymajor ){
    /* Here is inserted the actions which take place when a
    ** terminal or non-terminal is destroyed.  This can happen
    ** when the symbol is popped from the stack during a
    ** reduce or during error processing or when a parser is 
    ** being destroyed before it is finished parsing.
    **
    ** Note: during a reduce, the only symbols destroyed are those
    ** which appear on the RHS of the rule, but which are not used
    ** inside the C code.
    */
    case 1:
    case 2:
    case 3:
    case 4:
    case 5:
    case 6:
    case 7:
    case 8:
    case 9:
    case 10:
    case 11:
    case 12:
    case 13:
    case 14:
    case 15:
    case 16:
    case 17:
    case 18:
    case 19:
    case 20:
    case 21:
    case 22:
    case 23:
    case 24:
    case 25:
    case 26:
    case 27:
    case 28:
    case 29:
#line 50 "bitbakeparser.y"
{ (yypminor->yy0).release_this (); }
#line 423 "bitbakeparser.c"
      break;
    default:  break;   /* If no destructor action specified: do nothing */
  }
}

/*
** Pop the parser's stack once.
**
** If there is a destructor routine associated with the token which
** is popped from the stack, then call it.
**
** Return the major token number for the symbol popped.
*/
static int yy_pop_parser_stack(yyParser *pParser){
  YYCODETYPE yymajor;
  yyStackEntry *yytos = &pParser->yystack[pParser->yyidx];

  if( pParser->yyidx<0 ) return 0;
#ifndef NDEBUG
  if( yyTraceFILE && pParser->yyidx>=0 ){
    fprintf(yyTraceFILE,"%sPopping %s\n",
      yyTracePrompt,
      yyTokenName[yytos->major]);
  }
#endif
  yymajor = yytos->major;
  yy_destructor( yymajor, &yytos->minor);
  pParser->yyidx--;
  return yymajor;
}

/* 
** Deallocate and destroy a parser.  Destructors are all called for
** all stack elements before shutting the parser down.
**
** Inputs:
** <ul>
** <li>  A pointer to the parser.  This should be a pointer
**       obtained from bbparseAlloc.
** <li>  A pointer to a function used to reclaim memory obtained
**       from malloc.
** </ul>
*/
void bbparseFree(
  void *p,                    /* The parser to be deleted */
  void (*freeProc)(void*)     /* Function used to reclaim memory */
){
  yyParser *pParser = (yyParser*)p;
  if( pParser==0 ) return;
  while( pParser->yyidx>=0 ) yy_pop_parser_stack(pParser);
  (*freeProc)((void*)pParser);
}

/*
** Find the appropriate action for a parser given the terminal
** look-ahead token iLookAhead.
**
** If the look-ahead token is YYNOCODE, then check to see if the action is
** independent of the look-ahead.  If it is, return the action, otherwise
** return YY_NO_ACTION.
*/
static int yy_find_shift_action(
  yyParser *pParser,        /* The parser */
  int iLookAhead            /* The look-ahead token */
){
  int i;
  int stateno = pParser->yystack[pParser->yyidx].stateno;
 
  /* if( pParser->yyidx<0 ) return YY_NO_ACTION;  */
  i = yy_shift_ofst[stateno];
  if( i==YY_SHIFT_USE_DFLT ){
    return yy_default[stateno];
  }
  if( iLookAhead==YYNOCODE ){
    return YY_NO_ACTION;
  }
  i += iLookAhead;
  if( i<0 || i>=YY_SZ_ACTTAB || yy_lookahead[i]!=iLookAhead ){
#ifdef YYFALLBACK
    int iFallback;            /* Fallback token */
    if( iLookAhead<sizeof(yyFallback)/sizeof(yyFallback[0])
           && (iFallback = yyFallback[iLookAhead])!=0 ){
#ifndef NDEBUG
      if( yyTraceFILE ){
        fprintf(yyTraceFILE, "%sFALLBACK %s => %s\n",
           yyTracePrompt, yyTokenName[iLookAhead], yyTokenName[iFallback]);
      }
#endif
      return yy_find_shift_action(pParser, iFallback);
    }
#endif
    return yy_default[stateno];
  }else{
    return yy_action[i];
  }
}

/*
** Find the appropriate action for a parser given the non-terminal
** look-ahead token iLookAhead.
**
** If the look-ahead token is YYNOCODE, then check to see if the action is
** independent of the look-ahead.  If it is, return the action, otherwise
** return YY_NO_ACTION.
*/
static int yy_find_reduce_action(
  int stateno,              /* Current state number */
  int iLookAhead            /* The look-ahead token */
){
  int i;
  /* int stateno = pParser->yystack[pParser->yyidx].stateno; */
 
  i = yy_reduce_ofst[stateno];
  if( i==YY_REDUCE_USE_DFLT ){
    return yy_default[stateno];
  }
  if( iLookAhead==YYNOCODE ){
    return YY_NO_ACTION;
  }
  i += iLookAhead;
  if( i<0 || i>=YY_SZ_ACTTAB || yy_lookahead[i]!=iLookAhead ){
    return yy_default[stateno];
  }else{
    return yy_action[i];
  }
}

/*
** Perform a shift action.
*/
static void yy_shift(
  yyParser *yypParser,          /* The parser to be shifted */
  int yyNewState,               /* The new state to shift in */
  int yyMajor,                  /* The major token to shift in */
  YYMINORTYPE *yypMinor         /* Pointer ot the minor token to shift in */
){
  yyStackEntry *yytos;
  yypParser->yyidx++;
  if( yypParser->yyidx>=YYSTACKDEPTH ){
     bbparseARG_FETCH;
     yypParser->yyidx--;
#ifndef NDEBUG
     if( yyTraceFILE ){
       fprintf(yyTraceFILE,"%sStack Overflow!\n",yyTracePrompt);
     }
#endif
     while( yypParser->yyidx>=0 ) yy_pop_parser_stack(yypParser);
     /* Here code is inserted which will execute if the parser
     ** stack every overflows */
     bbparseARG_STORE; /* Suppress warning about unused %extra_argument var */
     return;
  }
  yytos = &yypParser->yystack[yypParser->yyidx];
  yytos->stateno = yyNewState;
  yytos->major = yyMajor;
  yytos->minor = *yypMinor;
#ifndef NDEBUG
  if( yyTraceFILE && yypParser->yyidx>0 ){
    int i;
    fprintf(yyTraceFILE,"%sShift %d\n",yyTracePrompt,yyNewState);
    fprintf(yyTraceFILE,"%sStack:",yyTracePrompt);
    for(i=1; i<=yypParser->yyidx; i++)
      fprintf(yyTraceFILE," %s",yyTokenName[yypParser->yystack[i].major]);
    fprintf(yyTraceFILE,"\n");
  }
#endif
}

/* The following table contains information about every rule that
** is used during the reduce.
*/
static const struct {
  YYCODETYPE lhs;         /* Symbol on the left-hand side of the rule */
  unsigned char nrhs;     /* Number of right-hand side symbols in the rule */
} yyRuleInfo[] = {
  { 31, 1 },
  { 32, 2 },
  { 32, 0 },
  { 34, 1 },
  { 34, 1 },
  { 33, 4 },
  { 33, 4 },
  { 33, 4 },
  { 33, 4 },
  { 33, 4 },
  { 33, 3 },
  { 33, 3 },
  { 33, 3 },
  { 33, 3 },
  { 33, 3 },
  { 33, 3 },
  { 33, 3 },
  { 35, 5 },
  { 35, 5 },
  { 35, 1 },
  { 35, 3 },
  { 35, 3 },
  { 36, 2 },
  { 36, 1 },
  { 33, 2 },
  { 33, 2 },
  { 37, 1 },
  { 38, 2 },
  { 38, 1 },
  { 33, 2 },
  { 39, 1 },
  { 40, 2 },
  { 40, 1 },
  { 33, 2 },
  { 33, 2 },
  { 33, 2 },
  { 41, 2 },
  { 41, 0 },
  { 33, 4 },
  { 33, 5 },
  { 33, 4 },
  { 33, 5 },
  { 42, 2 },
  { 42, 0 },
  { 33, 3 },
};

static void yy_accept(yyParser*);  /* Forward Declaration */

/*
** Perform a reduce action and the shift that must immediately
** follow the reduce.
*/
static void yy_reduce(
  yyParser *yypParser,         /* The parser */
  int yyruleno                 /* Number of the rule by which to reduce */
){
  int yygoto;                     /* The next state */
  int yyact;                      /* The next action */
  YYMINORTYPE yygotominor;        /* The LHS of the rule reduced */
  yyStackEntry *yymsp;            /* The top of the parser's stack */
  int yysize;                     /* Amount to pop the stack */
  bbparseARG_FETCH;
  yymsp = &yypParser->yystack[yypParser->yyidx];
#ifndef NDEBUG
  if( yyTraceFILE && yyruleno>=0 
        && yyruleno<sizeof(yyRuleName)/sizeof(yyRuleName[0]) ){
    fprintf(yyTraceFILE, "%sReduce [%s].\n", yyTracePrompt,
      yyRuleName[yyruleno]);
  }
#endif /* NDEBUG */

#ifndef NDEBUG
  /* Silence complaints from purify about yygotominor being uninitialized
  ** in some cases when it is copied into the stack after the following
  ** switch.  yygotominor is uninitialized when a rule reduces that does
  ** not set the value of its left-hand side nonterminal.  Leaving the
  ** value of the nonterminal uninitialized is utterly harmless as long
  ** as the value is never used.  So really the only thing this code
  ** accomplishes is to quieten purify.  
  */
  memset(&yygotominor, 0, sizeof(yygotominor));
#endif

  switch( yyruleno ){
  /* Beginning here are the reduction cases.  A typical example
  ** follows:
  **   case 0:
  **  #line <lineno> <grammarfile>
  **     { ... }           // User supplied code
  **  #line <lineno> <thisfile>
  **     break;
  */
      case 3:
#line 60 "bitbakeparser.y"
{ yygotominor.yy0.assignString( (char*)yymsp[0].minor.yy0.string() );
          yymsp[0].minor.yy0.assignString( 0 );
          yymsp[0].minor.yy0.release_this(); }
#line 697 "bitbakeparser.c"
        break;
      case 4:
#line 64 "bitbakeparser.y"
{
          yygotominor.yy0.assignString( (char*)yymsp[0].minor.yy0.string() );
          yymsp[0].minor.yy0.assignString( 0 );
          yymsp[0].minor.yy0.release_this(); }
#line 705 "bitbakeparser.c"
        break;
      case 5:
#line 70 "bitbakeparser.y"
{ e_assign( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(4,&yymsp[-1].minor);
}
#line 714 "bitbakeparser.c"
        break;
      case 6:
#line 74 "bitbakeparser.y"
{ e_precat( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(6,&yymsp[-1].minor);
}
#line 723 "bitbakeparser.c"
        break;
      case 7:
#line 78 "bitbakeparser.y"
{ e_postcat( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(7,&yymsp[-1].minor);
}
#line 732 "bitbakeparser.c"
        break;
      case 8:
#line 82 "bitbakeparser.y"
{ e_immediate ( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(8,&yymsp[-1].minor);
}
#line 741 "bitbakeparser.c"
        break;
      case 9:
#line 86 "bitbakeparser.y"
{ e_cond( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(9,&yymsp[-1].minor);
}
#line 749 "bitbakeparser.c"
        break;
      case 10:
#line 90 "bitbakeparser.y"
{ e_assign( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(4,&yymsp[-1].minor);
}
#line 756 "bitbakeparser.c"
        break;
      case 11:
#line 93 "bitbakeparser.y"
{ e_precat( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(6,&yymsp[-1].minor);
}
#line 763 "bitbakeparser.c"
        break;
      case 12:
#line 96 "bitbakeparser.y"
{ e_postcat( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(7,&yymsp[-1].minor);
}
#line 770 "bitbakeparser.c"
        break;
      case 13:
#line 99 "bitbakeparser.y"
{ e_prepend( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(10,&yymsp[-1].minor);
}
#line 777 "bitbakeparser.c"
        break;
      case 14:
#line 102 "bitbakeparser.y"
{ e_append( lex, yymsp[-2].minor.yy0.string() , yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(11,&yymsp[-1].minor);
}
#line 784 "bitbakeparser.c"
        break;
      case 15:
#line 105 "bitbakeparser.y"
{ e_immediate( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(8,&yymsp[-1].minor);
}
#line 791 "bitbakeparser.c"
        break;
      case 16:
#line 108 "bitbakeparser.y"
{ e_cond( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(9,&yymsp[-1].minor);
}
#line 798 "bitbakeparser.c"
        break;
      case 17:
#line 112 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-4].minor.yy0.string(), yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-4].minor.yy0.release_this(); yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(13,&yymsp[-3].minor);
  yy_destructor(14,&yymsp[-1].minor);
}
#line 806 "bitbakeparser.c"
        break;
      case 18:
#line 115 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-4].minor.yy0.string(), yymsp[0].minor.yy0.string(), yymsp[-2].minor.yy0.string());
          yymsp[-4].minor.yy0.release_this(); yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(14,&yymsp[-3].minor);
  yy_destructor(13,&yymsp[-1].minor);
}
#line 814 "bitbakeparser.c"
        break;
      case 19:
#line 118 "bitbakeparser.y"
{ e_addtask( lex, yymsp[0].minor.yy0.string(), NULL, NULL);
          yymsp[0].minor.yy0.release_this();}
#line 820 "bitbakeparser.c"
        break;
      case 20:
#line 121 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string(), NULL);
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(13,&yymsp[-1].minor);
}
#line 827 "bitbakeparser.c"
        break;
      case 21:
#line 124 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-2].minor.yy0.string(), NULL, yymsp[0].minor.yy0.string());
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(14,&yymsp[-1].minor);
}
#line 834 "bitbakeparser.c"
        break;
      case 25:
#line 131 "bitbakeparser.y"
{ e_addhandler( lex, yymsp[0].minor.yy0.string()); yymsp[0].minor.yy0.release_this ();   yy_destructor(16,&yymsp[-1].minor);
}
#line 840 "bitbakeparser.c"
        break;
      case 26:
#line 133 "bitbakeparser.y"
{ e_export_func( lex, yymsp[0].minor.yy0.string()); yymsp[0].minor.yy0.release_this(); }
#line 845 "bitbakeparser.c"
        break;
      case 30:
#line 138 "bitbakeparser.y"
{ e_inherit( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this (); }
#line 850 "bitbakeparser.c"
        break;
      case 34:
#line 144 "bitbakeparser.y"
{ e_include( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this();   yy_destructor(21,&yymsp[-1].minor);
}
#line 856 "bitbakeparser.c"
        break;
      case 35:
#line 147 "bitbakeparser.y"
{ e_require( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this();   yy_destructor(22,&yymsp[-1].minor);
}
#line 862 "bitbakeparser.c"
        break;
      case 36:
#line 150 "bitbakeparser.y"
{ /* concatenate body lines */
          yygotominor.yy0.assignString( token_t::concatString(yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string()) );
          yymsp[-1].minor.yy0.release_this ();
          yymsp[0].minor.yy0.release_this ();
        }
#line 871 "bitbakeparser.c"
        break;
      case 37:
#line 155 "bitbakeparser.y"
{ yygotominor.yy0.assignString(0); }
#line 876 "bitbakeparser.c"
        break;
      case 38:
#line 157 "bitbakeparser.y"
{ e_proc( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this();   yy_destructor(24,&yymsp[-2].minor);
  yy_destructor(25,&yymsp[0].minor);
}
#line 884 "bitbakeparser.c"
        break;
      case 39:
#line 160 "bitbakeparser.y"
{ e_proc_python ( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this();   yy_destructor(26,&yymsp[-4].minor);
  yy_destructor(24,&yymsp[-2].minor);
  yy_destructor(25,&yymsp[0].minor);
}
#line 893 "bitbakeparser.c"
        break;
      case 40:
#line 163 "bitbakeparser.y"
{ e_proc_python( lex, NULL, yymsp[-1].minor.yy0.string());
          yymsp[-1].minor.yy0.release_this ();   yy_destructor(26,&yymsp[-3].minor);
  yy_destructor(24,&yymsp[-2].minor);
  yy_destructor(25,&yymsp[0].minor);
}
#line 902 "bitbakeparser.c"
        break;
      case 41:
#line 167 "bitbakeparser.y"
{ e_proc_fakeroot( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this (); yymsp[-1].minor.yy0.release_this ();   yy_destructor(27,&yymsp[-4].minor);
  yy_destructor(24,&yymsp[-2].minor);
  yy_destructor(25,&yymsp[0].minor);
}
#line 911 "bitbakeparser.c"
        break;
      case 42:
#line 171 "bitbakeparser.y"
{ /* concatenate body lines */
          yygotominor.yy0.assignString( token_t::concatString(yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string()) );
          yymsp[-1].minor.yy0.release_this (); yymsp[0].minor.yy0.release_this ();
        }
#line 919 "bitbakeparser.c"
        break;
      case 43:
#line 175 "bitbakeparser.y"
{ yygotominor.yy0.assignString( 0 ); }
#line 924 "bitbakeparser.c"
        break;
      case 44:
#line 177 "bitbakeparser.y"
{ e_def( lex, yymsp[-2].minor.yy0.string(), yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string());
          yymsp[-2].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this(); }
#line 930 "bitbakeparser.c"
        break;
  };
  yygoto = yyRuleInfo[yyruleno].lhs;
  yysize = yyRuleInfo[yyruleno].nrhs;
  yypParser->yyidx -= yysize;
  yyact = yy_find_reduce_action(yymsp[-yysize].stateno,yygoto);
  if( yyact < YYNSTATE ){
#ifdef NDEBUG
    /* If we are not debugging and the reduce action popped at least
    ** one element off the stack, then we can push the new element back
    ** onto the stack here, and skip the stack overflow test in yy_shift().
    ** That gives a significant speed improvement. */
    if( yysize ){
      yypParser->yyidx++;
      yymsp -= yysize-1;
      yymsp->stateno = yyact;
      yymsp->major = yygoto;
      yymsp->minor = yygotominor;
    }else
#endif
    {
      yy_shift(yypParser,yyact,yygoto,&yygotominor);
    }
  }else if( yyact == YYNSTATE + YYNRULE + 1 ){
    yy_accept(yypParser);
  }
}

/*
** The following code executes when the parse fails
*/
static void yy_parse_failed(
  yyParser *yypParser           /* The parser */
){
  bbparseARG_FETCH;
#ifndef NDEBUG
  if( yyTraceFILE ){
    fprintf(yyTraceFILE,"%sFail!\n",yyTracePrompt);
  }
#endif
  while( yypParser->yyidx>=0 ) yy_pop_parser_stack(yypParser);
  /* Here code is inserted which will be executed whenever the
  ** parser fails */
  bbparseARG_STORE; /* Suppress warning about unused %extra_argument variable */
}

/*
** The following code executes when a syntax error first occurs.
*/
static void yy_syntax_error(
  yyParser *yypParser,           /* The parser */
  int yymajor,                   /* The major type of the error token */
  YYMINORTYPE yyminor            /* The minor type of the error token */
){
  bbparseARG_FETCH;
#define TOKEN (yyminor.yy0)
#line 52 "bitbakeparser.y"
 e_parse_error( lex ); 
#line 990 "bitbakeparser.c"
  bbparseARG_STORE; /* Suppress warning about unused %extra_argument variable */
}

/*
** The following is executed when the parser accepts
*/
static void yy_accept(
  yyParser *yypParser           /* The parser */
){
  bbparseARG_FETCH;
#ifndef NDEBUG
  if( yyTraceFILE ){
    fprintf(yyTraceFILE,"%sAccept!\n",yyTracePrompt);
  }
#endif
  while( yypParser->yyidx>=0 ) yy_pop_parser_stack(yypParser);
  /* Here code is inserted which will be executed whenever the
  ** parser accepts */
  bbparseARG_STORE; /* Suppress warning about unused %extra_argument variable */
}

/* The main parser program.
** The first argument is a pointer to a structure obtained from
** "bbparseAlloc" which describes the current state of the parser.
** The second argument is the major token number.  The third is
** the minor token.  The fourth optional argument is whatever the
** user wants (and specified in the grammar) and is available for
** use by the action routines.
**
** Inputs:
** <ul>
** <li> A pointer to the parser (an opaque structure.)
** <li> The major token number.
** <li> The minor token number.
** <li> An option argument of a grammar-specified type.
** </ul>
**
** Outputs:
** None.
*/
void bbparse(
  void *yyp,                   /* The parser */
  int yymajor,                 /* The major token code number */
  bbparseTOKENTYPE yyminor       /* The value for the token */
  bbparseARG_PDECL               /* Optional %extra_argument parameter */
){
  YYMINORTYPE yyminorunion;
  int yyact;            /* The parser action. */
  int yyendofinput;     /* True if we are at the end of input */
  int yyerrorhit = 0;   /* True if yymajor has invoked an error */
  yyParser *yypParser;  /* The parser */

  /* (re)initialize the parser, if necessary */
  yypParser = (yyParser*)yyp;
  if( yypParser->yyidx<0 ){
    if( yymajor==0 ) return;
    yypParser->yyidx = 0;
    yypParser->yyerrcnt = -1;
    yypParser->yystack[0].stateno = 0;
    yypParser->yystack[0].major = 0;
  }
  yyminorunion.yy0 = yyminor;
  yyendofinput = (yymajor==0);
  bbparseARG_STORE;

#ifndef NDEBUG
  if( yyTraceFILE ){
    fprintf(yyTraceFILE,"%sInput %s\n",yyTracePrompt,yyTokenName[yymajor]);
  }
#endif

  do{
    yyact = yy_find_shift_action(yypParser,yymajor);
    if( yyact<YYNSTATE ){
      yy_shift(yypParser,yyact,yymajor,&yyminorunion);
      yypParser->yyerrcnt--;
      if( yyendofinput && yypParser->yyidx>=0 ){
        yymajor = 0;
      }else{
        yymajor = YYNOCODE;
      }
    }else if( yyact < YYNSTATE + YYNRULE ){
      yy_reduce(yypParser,yyact-YYNSTATE);
    }else if( yyact == YY_ERROR_ACTION ){
      int yymx;
#ifndef NDEBUG
      if( yyTraceFILE ){
        fprintf(yyTraceFILE,"%sSyntax Error!\n",yyTracePrompt);
      }
#endif
#ifdef YYERRORSYMBOL
      /* A syntax error has occurred.
      ** The response to an error depends upon whether or not the
      ** grammar defines an error token "ERROR".  
      **
      ** This is what we do if the grammar does define ERROR:
      **
      **  * Call the %syntax_error function.
      **
      **  * Begin popping the stack until we enter a state where
      **    it is legal to shift the error symbol, then shift
      **    the error symbol.
      **
      **  * Set the error count to three.
      **
      **  * Begin accepting and shifting new tokens.  No new error
      **    processing will occur until three tokens have been
      **    shifted successfully.
      **
      */
      if( yypParser->yyerrcnt<0 ){
        yy_syntax_error(yypParser,yymajor,yyminorunion);
      }
      yymx = yypParser->yystack[yypParser->yyidx].major;
      if( yymx==YYERRORSYMBOL || yyerrorhit ){
#ifndef NDEBUG
        if( yyTraceFILE ){
          fprintf(yyTraceFILE,"%sDiscard input token %s\n",
             yyTracePrompt,yyTokenName[yymajor]);
        }
#endif
        yy_destructor(yymajor,&yyminorunion);
        yymajor = YYNOCODE;
      }else{
         while(
          yypParser->yyidx >= 0 &&
          yymx != YYERRORSYMBOL &&
          (yyact = yy_find_shift_action(yypParser,YYERRORSYMBOL)) >= YYNSTATE
        ){
          yy_pop_parser_stack(yypParser);
        }
        if( yypParser->yyidx < 0 || yymajor==0 ){
          yy_destructor(yymajor,&yyminorunion);
          yy_parse_failed(yypParser);
          yymajor = YYNOCODE;
        }else if( yymx!=YYERRORSYMBOL ){
          YYMINORTYPE u2;
          u2.YYERRSYMDT = 0;
          yy_shift(yypParser,yyact,YYERRORSYMBOL,&u2);
        }
      }
      yypParser->yyerrcnt = 3;
      yyerrorhit = 1;
#else  /* YYERRORSYMBOL is not defined */
      /* This is what we do if the grammar does not define ERROR:
      **
      **  * Report an error message, and throw away the input token.
      **
      **  * If the input token is $, then fail the parse.
      **
      ** As before, subsequent error messages are suppressed until
      ** three input tokens have been successfully shifted.
      */
      if( yypParser->yyerrcnt<=0 ){
        yy_syntax_error(yypParser,yymajor,yyminorunion);
      }
      yypParser->yyerrcnt = 3;
      yy_destructor(yymajor,&yyminorunion);
      if( yyendofinput ){
        yy_parse_failed(yypParser);
      }
      yymajor = YYNOCODE;
#endif
    }else{
      yy_accept(yypParser);
      yymajor = YYNOCODE;
    }
  }while( yymajor!=YYNOCODE && yypParser->yyidx>=0 );
  return;
}
