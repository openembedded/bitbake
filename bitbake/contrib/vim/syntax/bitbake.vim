" Vim syntax file
"
" Copyright (C) 2004  Chris Larson <kergoth@handhelds.org>
" This file is licensed under the MIT license, see COPYING.MIT in
" this source distribution for the terms.
"
" Language:	BitBake
" Maintainer:	Chris Larson <kergoth@handhelds.org>
" Filenames:	*.bb, *.bbclass

if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

syn case match


" Catch incorrect syntax (only matches if nothing else does)
"
syn match bbUnmatched		"."


" Other

syn match bbComment		"^#.*$" display contains=bbTodo
syn keyword bbTodo		TODO FIXME XXX contained
syn match bbDelimiter		"[(){}=]" contained
syn match bbQuote		/['"]/ contained
syn match bbArrayBrackets	"[\[\]]" contained


" BitBake strings

syn match bbContinue		"\\$"
syn region bbString		matchgroup=bbQuote start=/"/ skip=/\\$/ excludenl end=/"/ contained keepend contains=bbTodo,bbContinue,bbVarDeref
syn region bbString		matchgroup=bbQuote start=/'/ skip=/\\$/ excludenl end=/'/ contained keepend contains=bbTodo,bbContinue,bbVarDeref


" BitBake variable metadata

syn keyword bbExportFlag	export contained nextgroup=bbIdentifier skipwhite
syn match bbVarDeref	"${[a-zA-Z0-9\-_\.]\+}" contained
syn match bbVarDef		"^\(export\s*\)\?\([a-zA-Z0-9\-_\.]\+\(_[${}a-zA-Z0-9\-_\.]\+\)\?\)\s*\(\(:=\)\|\(+=\)\|\(=+\)\|\(?=\)\|=\)\@=" contains=bbExportFlag,bbIdentifier,bbVarDeref nextgroup=bbVarEq

syn match bbIdentifier		"[a-zA-Z0-9\-_\.]\+" display contained
"syn keyword bbVarEq	= display contained nextgroup=bbVarValue
syn match bbVarEq		"\(:=\)\|\(+=\)\|\(=+\)\|\(?=\)\|=" contained nextgroup=bbVarValue
syn match bbVarValue		".*$" contained contains=bbString,bbVarDeref


" BitBake variable metadata flags
syn match bbVarFlagDef		"^\([a-zA-Z0-9\-_\.]\+\)\(\[[a-zA-Z0-9\-_\.]\+\]\)\@=" contains=bbIdentifier nextgroup=bbVarFlagFlag
syn region bbVarFlagFlag	matchgroup=bbArrayBrackets start="\[" end="\]\s*\(=\)\@=" keepend excludenl contained contains=bbIdentifier nextgroup=bbVarEq
"syn match bbVarFlagFlag		"\[\([a-zA-Z0-9\-_\.]\+\)\]\s*\(=\)\@=" contains=bbIdentifier nextgroup=bbVarEq


" Functions!
syn match bbFunction	"\h\w*" display contained


" BitBake python metadata
syn include @python syntax/python.vim
if exists("b:current_syntax")
  unlet b:current_syntax
endif

syn keyword bbPythonFlag	python contained nextgroup=bbFunction
syn match bbPythonFuncDef	"^\(python\s\+\)\(\w\+\)\?\(\s*()\s*\)\({\)\@=" contains=bbPythonFlag,bbFunction,bbDelimiter nextgroup=bbPythonFuncRegion skipwhite
syn region bbPythonFuncRegion	matchgroup=bbDelimiter start="{\s*$" end="^}\s*$" keepend contained contains=@python
"hi def link bbPythonFuncRegion	Comment


" BitBake shell metadata
syn include @shell syntax/sh.vim
if exists("b:current_syntax")
  unlet b:current_syntax
endif

syn keyword bbFakerootFlag	fakeroot contained nextgroup=bbFunction
syn match bbShellFuncDef	"^\(fakeroot\s*\)\?\(\w\+\)\(python\)\@<!\(\s*()\s*\)\({\)\@=" contains=bbFakerootFlag,bbFunction,bbDelimiter nextgroup=bbShellFuncRegion skipwhite
syn region bbShellFuncRegion	matchgroup=bbDelimiter start="{\s*$" end="^}\s*$" keepend contained contains=@shell
"hi def link bbShellFuncRegion	Comment


" BitBake 'def'd python functions
syn keyword bbDef	def	contained
syn region bbDefRegion		start='^def\s\+\w\+\s*([^)]*)\s*:\s*$' end='^\(\s\|$\)\@!' contains=@python


" BitBake statements
syn keyword bbStatement		include inherit addtask addhandler EXPORT_FUNCTIONS display contained
syn match bbStatementLine	"^\(include\|inherit\|addtask\|addhandler\|EXPORT_FUNCTIONS\)\s\+" contains=bbStatement nextgroup=bbStatementRest
syn match bbStatementRest		".*$" contained contains=bbString,bbVarDeref

" Highlight
"
hi def link bbArrayBrackets	Statement
hi def link bbUnmatched		Error
hi def link bbVarDeref		String
hi def link bbContinue		Special
hi def link bbDef		Statement
hi def link bbPythonFlag	Type
hi def link bbExportFlag	Type
hi def link bbFakerootFlag	Type
hi def link bbStatement		Statement
hi def link bbString		String
hi def link bbTodo		Todo
hi def link bbComment		Comment
hi def link bbOperator		Operator
hi def link bbError		Error
hi def link bbFunction		Function
hi def link bbDelimiter		Delimiter
hi def link bbIdentifier	Identifier
hi def link bbVarEq		Operator
hi def link bbQuote		String
hi def link bbVarValue		String

let b:current_syntax = "bb"
