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
#define YYNOCODE 42
#define YYACTIONTYPE unsigned char
#define bbparseTOKENTYPE token_t
typedef union {
  bbparseTOKENTYPE yy0;
  int yy83;
} YYMINORTYPE;
#define YYSTACKDEPTH 100
#define bbparseARG_SDECL lex_t* lex;
#define bbparseARG_PDECL ,lex_t* lex
#define bbparseARG_FETCH lex_t* lex = yypParser->lex
#define bbparseARG_STORE yypParser->lex = lex
#define YYNSTATE 74
#define YYNRULE 41
#define YYERRORSYMBOL 28
#define YYERRSYMDT yy83
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
 /*     0 */    28,   47,    5,   57,   33,   58,   30,   25,   24,   37,
 /*    10 */    45,   14,    2,   29,   41,    3,   16,    4,   23,   39,
 /*    20 */    69,    8,   11,   17,   26,   48,   47,   32,   21,   42,
 /*    30 */    31,   57,   57,   73,   44,   10,   66,    7,   34,   38,
 /*    40 */    57,   51,   72,  116,    1,   62,    6,   49,   52,   35,
 /*    50 */    36,   59,   54,    9,   20,   64,   43,   22,   40,   50,
 /*    60 */    46,   71,   67,   60,   15,   65,   61,   70,   53,   56,
 /*    70 */    27,   12,   68,   63,   84,   55,   18,   84,   13,   84,
 /*    80 */    84,   84,   84,   84,   84,   84,   84,   84,   84,   84,
 /*    90 */    84,   19,
};
static const YYCODETYPE yy_lookahead[] = {
 /*     0 */     1,    2,    3,   21,    4,   23,    6,    7,    8,    9,
 /*    10 */    31,   32,   13,   14,    1,   16,   39,   18,   19,   20,
 /*    20 */    37,   38,   22,   24,   25,    1,    2,    4,   10,    6,
 /*    30 */     7,   21,   21,   23,   23,   22,   35,   36,   11,   12,
 /*    40 */    21,    5,   23,   29,   30,   33,   34,    5,    5,   10,
 /*    50 */    12,   10,    5,   22,   39,   15,   40,   11,   10,    5,
 /*    60 */    26,   17,   17,   10,   32,   35,   33,   17,    5,    5,
 /*    70 */     1,   22,   37,    1,   41,    5,   39,   41,   27,   41,
 /*    80 */    41,   41,   41,   41,   41,   41,   41,   41,   41,   41,
 /*    90 */    41,   39,
};
#define YY_SHIFT_USE_DFLT (-19)
#define YY_SHIFT_MAX 43
static const signed char yy_shift_ofst[] = {
 /*     0 */   -19,   -1,   18,   40,   45,   24,   18,   40,   45,  -19,
 /*    10 */   -19,  -19,  -19,  -19,    0,   23,  -18,   13,   19,   10,
 /*    20 */    11,   27,   53,   50,   63,   64,   69,   49,   51,   72,
 /*    30 */    70,   36,   42,   43,   39,   38,   41,   47,   48,   44,
 /*    40 */    46,   31,   54,   34,
};
#define YY_REDUCE_USE_DFLT (-24)
#define YY_REDUCE_MAX 13
static const signed char yy_reduce_ofst[] = {
 /*     0 */    14,  -21,   12,    1,  -17,   32,   33,   30,   35,   37,
 /*    10 */    52,  -23,   15,   16,
};
static const YYACTIONTYPE yy_default[] = {
 /*     0 */    76,   74,  115,  115,  115,  115,   94,   99,  103,  107,
 /*    10 */   107,  107,  107,  113,  115,  115,  115,  115,  115,  115,
 /*    20 */   115,   89,  115,  115,  115,  115,  115,  115,   77,  115,
 /*    30 */   115,  115,  115,  115,  115,   90,  115,  115,  115,  115,
 /*    40 */    91,  115,  115,  114,  111,   75,  112,   78,   77,   79,
 /*    50 */    80,   81,   82,   83,   84,   85,   86,  106,  108,   87,
 /*    60 */    88,   92,   93,   95,   96,   97,   98,  100,  101,  102,
 /*    70 */   104,  105,  109,  110,
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
  "OP_ASSIGN",     "STRING",        "OP_IMMEDIATE",  "OP_COND",     
  "OP_PREPEND",    "OP_APPEND",     "TSYMBOL",       "BEFORE",      
  "AFTER",         "ADDTASK",       "ADDHANDLER",    "FSYMBOL",     
  "EXPORT_FUNC",   "ISYMBOL",       "INHERIT",       "INCLUDE",     
  "REQUIRE",       "PROC_BODY",     "PROC_OPEN",     "PROC_CLOSE",  
  "PYTHON",        "FAKEROOT",      "DEF_BODY",      "DEF_ARGS",    
  "error",         "program",       "statements",    "statement",   
  "variable",      "task",          "tasks",         "func",        
  "funcs",         "inherit",       "inherits",      "proc_body",   
  "def_body",    
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
 /*   6 */ "statement ::= EXPORT variable OP_IMMEDIATE STRING",
 /*   7 */ "statement ::= EXPORT variable OP_COND STRING",
 /*   8 */ "statement ::= variable OP_ASSIGN STRING",
 /*   9 */ "statement ::= variable OP_PREPEND STRING",
 /*  10 */ "statement ::= variable OP_APPEND STRING",
 /*  11 */ "statement ::= variable OP_IMMEDIATE STRING",
 /*  12 */ "statement ::= variable OP_COND STRING",
 /*  13 */ "task ::= TSYMBOL BEFORE TSYMBOL AFTER TSYMBOL",
 /*  14 */ "task ::= TSYMBOL AFTER TSYMBOL BEFORE TSYMBOL",
 /*  15 */ "task ::= TSYMBOL",
 /*  16 */ "task ::= TSYMBOL BEFORE TSYMBOL",
 /*  17 */ "task ::= TSYMBOL AFTER TSYMBOL",
 /*  18 */ "tasks ::= tasks task",
 /*  19 */ "tasks ::= task",
 /*  20 */ "statement ::= ADDTASK tasks",
 /*  21 */ "statement ::= ADDHANDLER SYMBOL",
 /*  22 */ "func ::= FSYMBOL",
 /*  23 */ "funcs ::= funcs func",
 /*  24 */ "funcs ::= func",
 /*  25 */ "statement ::= EXPORT_FUNC funcs",
 /*  26 */ "inherit ::= ISYMBOL",
 /*  27 */ "inherits ::= inherits inherit",
 /*  28 */ "inherits ::= inherit",
 /*  29 */ "statement ::= INHERIT inherits",
 /*  30 */ "statement ::= INCLUDE ISYMBOL",
 /*  31 */ "statement ::= REQUIRE ISYMBOL",
 /*  32 */ "proc_body ::= proc_body PROC_BODY",
 /*  33 */ "proc_body ::=",
 /*  34 */ "statement ::= variable PROC_OPEN proc_body PROC_CLOSE",
 /*  35 */ "statement ::= PYTHON SYMBOL PROC_OPEN proc_body PROC_CLOSE",
 /*  36 */ "statement ::= PYTHON PROC_OPEN proc_body PROC_CLOSE",
 /*  37 */ "statement ::= FAKEROOT SYMBOL PROC_OPEN proc_body PROC_CLOSE",
 /*  38 */ "def_body ::= def_body DEF_BODY",
 /*  39 */ "def_body ::=",
 /*  40 */ "statement ::= SYMBOL DEF_ARGS def_body",
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
#line 50 "bitbakeparser.y"
{ (yypminor->yy0).release_this (); }
#line 409 "bitbakeparser.c"
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
 
  if( stateno>YY_SHIFT_MAX || (i = yy_shift_ofst[stateno])==YY_SHIFT_USE_DFLT ){
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
 
  if( stateno>YY_REDUCE_MAX ||
      (i = yy_reduce_ofst[stateno])==YY_REDUCE_USE_DFLT ){
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
  { 29, 1 },
  { 30, 2 },
  { 30, 0 },
  { 32, 1 },
  { 32, 1 },
  { 31, 4 },
  { 31, 4 },
  { 31, 4 },
  { 31, 3 },
  { 31, 3 },
  { 31, 3 },
  { 31, 3 },
  { 31, 3 },
  { 33, 5 },
  { 33, 5 },
  { 33, 1 },
  { 33, 3 },
  { 33, 3 },
  { 34, 2 },
  { 34, 1 },
  { 31, 2 },
  { 31, 2 },
  { 35, 1 },
  { 36, 2 },
  { 36, 1 },
  { 31, 2 },
  { 37, 1 },
  { 38, 2 },
  { 38, 1 },
  { 31, 2 },
  { 31, 2 },
  { 31, 2 },
  { 39, 2 },
  { 39, 0 },
  { 31, 4 },
  { 31, 5 },
  { 31, 4 },
  { 31, 5 },
  { 40, 2 },
  { 40, 0 },
  { 31, 3 },
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
#line 677 "bitbakeparser.c"
        break;
      case 4:
#line 64 "bitbakeparser.y"
{
          yygotominor.yy0.assignString( (char*)yymsp[0].minor.yy0.string() );
          yymsp[0].minor.yy0.assignString( 0 );
          yymsp[0].minor.yy0.release_this(); }
#line 685 "bitbakeparser.c"
        break;
      case 5:
#line 70 "bitbakeparser.y"
{ e_assign( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(4,&yymsp[-1].minor);
}
#line 694 "bitbakeparser.c"
        break;
      case 6:
#line 74 "bitbakeparser.y"
{ e_immediate ( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          e_export( lex, yymsp[-2].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(6,&yymsp[-1].minor);
}
#line 703 "bitbakeparser.c"
        break;
      case 7:
#line 78 "bitbakeparser.y"
{ e_cond( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(3,&yymsp[-3].minor);
  yy_destructor(7,&yymsp[-1].minor);
}
#line 711 "bitbakeparser.c"
        break;
      case 8:
#line 82 "bitbakeparser.y"
{ e_assign( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(4,&yymsp[-1].minor);
}
#line 718 "bitbakeparser.c"
        break;
      case 9:
#line 85 "bitbakeparser.y"
{ e_prepend( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(8,&yymsp[-1].minor);
}
#line 725 "bitbakeparser.c"
        break;
      case 10:
#line 88 "bitbakeparser.y"
{ e_append( lex, yymsp[-2].minor.yy0.string() , yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(9,&yymsp[-1].minor);
}
#line 732 "bitbakeparser.c"
        break;
      case 11:
#line 91 "bitbakeparser.y"
{ e_immediate( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(6,&yymsp[-1].minor);
}
#line 739 "bitbakeparser.c"
        break;
      case 12:
#line 94 "bitbakeparser.y"
{ e_cond( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(7,&yymsp[-1].minor);
}
#line 746 "bitbakeparser.c"
        break;
      case 13:
#line 98 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-4].minor.yy0.string(), yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string() );
          yymsp[-4].minor.yy0.release_this(); yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(11,&yymsp[-3].minor);
  yy_destructor(12,&yymsp[-1].minor);
}
#line 754 "bitbakeparser.c"
        break;
      case 14:
#line 101 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-4].minor.yy0.string(), yymsp[0].minor.yy0.string(), yymsp[-2].minor.yy0.string());
          yymsp[-4].minor.yy0.release_this(); yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(12,&yymsp[-3].minor);
  yy_destructor(11,&yymsp[-1].minor);
}
#line 762 "bitbakeparser.c"
        break;
      case 15:
#line 104 "bitbakeparser.y"
{ e_addtask( lex, yymsp[0].minor.yy0.string(), NULL, NULL);
          yymsp[0].minor.yy0.release_this();}
#line 768 "bitbakeparser.c"
        break;
      case 16:
#line 107 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-2].minor.yy0.string(), yymsp[0].minor.yy0.string(), NULL);
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(11,&yymsp[-1].minor);
}
#line 775 "bitbakeparser.c"
        break;
      case 17:
#line 110 "bitbakeparser.y"
{ e_addtask( lex, yymsp[-2].minor.yy0.string(), NULL, yymsp[0].minor.yy0.string());
          yymsp[-2].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this();   yy_destructor(12,&yymsp[-1].minor);
}
#line 782 "bitbakeparser.c"
        break;
      case 21:
#line 117 "bitbakeparser.y"
{ e_addhandler( lex, yymsp[0].minor.yy0.string()); yymsp[0].minor.yy0.release_this ();   yy_destructor(14,&yymsp[-1].minor);
}
#line 788 "bitbakeparser.c"
        break;
      case 22:
#line 119 "bitbakeparser.y"
{ e_export_func( lex, yymsp[0].minor.yy0.string()); yymsp[0].minor.yy0.release_this(); }
#line 793 "bitbakeparser.c"
        break;
      case 26:
#line 124 "bitbakeparser.y"
{ e_inherit( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this (); }
#line 798 "bitbakeparser.c"
        break;
      case 30:
#line 130 "bitbakeparser.y"
{ e_include( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this();   yy_destructor(19,&yymsp[-1].minor);
}
#line 804 "bitbakeparser.c"
        break;
      case 31:
#line 133 "bitbakeparser.y"
{ e_require( lex, yymsp[0].minor.yy0.string() ); yymsp[0].minor.yy0.release_this();   yy_destructor(20,&yymsp[-1].minor);
}
#line 810 "bitbakeparser.c"
        break;
      case 32:
#line 136 "bitbakeparser.y"
{ /* concatenate body lines */
          yygotominor.yy0.assignString( token_t::concatString(yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string()) );
          yymsp[-1].minor.yy0.release_this ();
          yymsp[0].minor.yy0.release_this ();
        }
#line 819 "bitbakeparser.c"
        break;
      case 33:
#line 141 "bitbakeparser.y"
{ yygotominor.yy0.assignString(0); }
#line 824 "bitbakeparser.c"
        break;
      case 34:
#line 143 "bitbakeparser.y"
{ e_proc( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this();   yy_destructor(22,&yymsp[-2].minor);
  yy_destructor(23,&yymsp[0].minor);
}
#line 832 "bitbakeparser.c"
        break;
      case 35:
#line 146 "bitbakeparser.y"
{ e_proc_python ( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this();   yy_destructor(24,&yymsp[-4].minor);
  yy_destructor(22,&yymsp[-2].minor);
  yy_destructor(23,&yymsp[0].minor);
}
#line 841 "bitbakeparser.c"
        break;
      case 36:
#line 149 "bitbakeparser.y"
{ e_proc_python( lex, NULL, yymsp[-1].minor.yy0.string());
          yymsp[-1].minor.yy0.release_this ();   yy_destructor(24,&yymsp[-3].minor);
  yy_destructor(22,&yymsp[-2].minor);
  yy_destructor(23,&yymsp[0].minor);
}
#line 850 "bitbakeparser.c"
        break;
      case 37:
#line 153 "bitbakeparser.y"
{ e_proc_fakeroot( lex, yymsp[-3].minor.yy0.string(), yymsp[-1].minor.yy0.string() );
          yymsp[-3].minor.yy0.release_this (); yymsp[-1].minor.yy0.release_this ();   yy_destructor(25,&yymsp[-4].minor);
  yy_destructor(22,&yymsp[-2].minor);
  yy_destructor(23,&yymsp[0].minor);
}
#line 859 "bitbakeparser.c"
        break;
      case 38:
#line 157 "bitbakeparser.y"
{ /* concatenate body lines */
          yygotominor.yy0.assignString( token_t::concatString(yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string()) );
          yymsp[-1].minor.yy0.release_this (); yymsp[0].minor.yy0.release_this ();
        }
#line 867 "bitbakeparser.c"
        break;
      case 39:
#line 161 "bitbakeparser.y"
{ yygotominor.yy0.assignString( 0 ); }
#line 872 "bitbakeparser.c"
        break;
      case 40:
#line 163 "bitbakeparser.y"
{ e_def( lex, yymsp[-2].minor.yy0.string(), yymsp[-1].minor.yy0.string(), yymsp[0].minor.yy0.string());
          yymsp[-2].minor.yy0.release_this(); yymsp[-1].minor.yy0.release_this(); yymsp[0].minor.yy0.release_this(); }
#line 878 "bitbakeparser.c"
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
#line 938 "bitbakeparser.c"
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
    /* if( yymajor==0 ) return; // not sure why this was here... */
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
