# Prevent aliases from causing us to act inappropriately.
# Make sure it's before everything so we don't mess aliases that follow.
unalias -a

# We need this next line for "die" and "assert". It expands
# It _must_ preceed all the calls to die and assert.
shopt -s expand_aliases
alias die='diefunc "$FUNCNAME" "$LINENO" "$?"'
alias assert='_retval=$?; [ $_retval = 0 ] || diefunc "$FUNCNAME" "$LINENO" "$_retval"'

PATH="${OEDIR}/bin/build:${PATH}"
test -z "$PREROOTPATH" || PATH="${PREROOTPATH%%:}:$PATH"


# filter-flags <flag> ####
#	Remove particular flags from C[XX]FLAGS

filter-flags () {
	for x in $1; do
		export CFLAGS="${CFLAGS/${x}}"
		export CXXFLAGS="${CXXFLAGS/${x}}"
	done
}


# append-flags <flag>
#	Add extra flags to your current C[XX]FLAGS

append-flags () {
	CFLAGS="${CFLAGS} $1"
	CXXFLAGS="${CXXFLAGS} $1"
}


# replace-flags <orig.flag> <new.flag>
#	Replace a flag by another one

replace-flags () {
	CFLAGS="${CFLAGS/${1}/${2} }"
	CXXFLAGS="${CXXFLAGS/${1}/${2} }"
}


# is-flag <flag> ####
#	Returns "true" if flag is set in C[XX]FLAGS
#	Matches only complete flag

is-flag() {
	for x in ${CFLAGS} ${CXXFLAGS};	do
		if [ "${x}" = "$1" ]; then
			echo true
			return 0
		fi
	done
	return 1
}


# strip-flags
#	Strip C[XX]FLAGS of everything except known good options.

strip-flags() {
	local NEW_CFLAGS=""
	local NEW_CXXFLAGS=""

	set -f
	for x in ${CFLAGS}; do
		for y in ${ALLOWED_FLAGS}; do
			if [ "${x/${y}}" != "${x}" ]; then
				if [ -z "${NEW_CFLAGS}" ]; then
					NEW_CFLAGS="${x}"
				else
					NEW_CFLAGS="${NEW_CFLAGS} ${x}"
				fi
			fi
		done
	done

	for x in ${CXXFLAGS}; do
		for y in ${ALLOWED_FLAGS}; do
			if [ "${x/${y}}" != "${x}" ]; then
				if [ -z "${NEW_CXXFLAGS}" ]; then
					NEW_CXXFLAGS="${x}"
				else
					NEW_CXXFLAGS="${NEW_CXXFLAGS} ${x}"
				fi
			fi
		done
	done

	set +f

	export CFLAGS="${NEW_CFLAGS}"
	export CXXFLAGS="${NEW_CXXFLAGS}"
}


# get-flag <flag>
#	Find and echo the value for a particular flag

get-flag() {
	local findflag="$1"

	for f in ${CFLAGS} ${CXXFLAGS}; do
		if [ "${f/${findflag}}" != "${f}" ]; then
			echo "${f/-${findflag}=}"
			return
		fi
	done
}


# TODO: oepatch
# TODO?: drawline, oenewuser, oenewgroup, oedos2unix

# return 0 when argument is in ${USE}

use() {
        local x
        for x in ${USE}
        do
                if [ "${x}" = "${1}" ]
                then
                        echo "${x}"
                        return 0
                fi
        done
        return 1
}



# find out if the first argument is one of the rest of the arguments
#
#	if ! has test $FEATURES ; then
#		...
#	fi

has() {
        local x

        local me
        me=$1
        shift

        for x in $@
        do
                if [ "${x}" = "${me}" ]
                then
                        echo "${x}"
                        return 0
                fi
        done
        return 1
}



use_with() {
        if [ -z "$1" ]; then
                oefatal "use_with() called without parameter"
		return
        fi

        local UWORD="$2"
        if [ -z "${UWORD}" ]; then
                UWORD="$1"
        fi

        if use $1 &>/dev/null; then
                echo "--with-${UWORD}"
                return 0
        else
                echo "--without-${UWORD}"
                return 1
        fi
}


use_enable() {
        if [ -z "$1" ]; then
                oefatal "use_with() called without parameter"
		return
        fi

        local UWORD="$2"
        if [ -z "${UWORD}" ]; then
                UWORD="$1"
        fi

        if use $1 &>/dev/null; then
                echo "--enable-${UWORD}"
                return 0
        else
                echo "--disable-${UWORD}"
                return 1
        fi
}


diefunc() {
        local funcname="$1" lineno="$2" exitcode="$3"
        shift 3
        echo >&2
        oefatal "$CATEGORY/$PF failed"
        oenote "Function $funcname, Line $lineno, Exitcode $exitcode"
        oenote "${*:-(no error message)}"
        exit 1
}


unpack() {
	local x
	local y
	local myfail
	
	for x in $@
	do
		myfail="failure unpacking ${x}"
		oenote "Unpacking ${x} to $(pwd)"
		y="$(echo $x | sed 's:.*\.\(tar\)\.[a-zA-Z0-9]*:\1:')"
		case "${x##*.}" in
		tar) 
			tar x --no-same-owner -f ${DL_DIR}/${x} || die "$myfail"
			;;
		tgz) 
			tar xz --no-same-owner -f ${DL_DIR}/${x} || die "$myfail"
			;;
		tbz2) 
			tar xj --no-same-owner -f ${DL_DIR}/${x} || die "$myfail"
			;;
		ZIP|zip) 
			unzip -qo ${DL_DIR}/${x} || die "$myfail"
			;;
		gz|Z|z) 
			if [ "${y}" == "tar" ]; then
				tar xz --no-same-owner -f ${DL_DIR}/${x} || die "$myfail"
			else
				gzip -dc ${DL_DIR}/${x} > ${x%.*} || die "$myfail"
			fi
			;;
		bz2) 
			if [ "${y}" == "tar" ]; then
				tar xj --no-same-owner -f ${DL_DIR}/${x} || die "$myfail"
			else
				bzip2 -dc ${DL_DIR}/${x} > ${x%.*} || die "$myfail"
			fi
			;;
		*)
			if [ -d "${x}" ]; then
				if [ -e ${S} ]; oefatal "unpack: ${S} already exists!"; return; fi
				cp -a ${x} ${S}
			else
				oefatal "unpack ${x}: file format not recognized"
			fi
			;;
		esac
	done
}


#TODO: add crosscompile support
oeconf() {
	if [ -x ./configure ] ; then
		test -z "${BUILD_SYS}" || EXTRA_OECONF="--build=${BUILD_SYS} ${EXTRA_OECONF}"
		test -z "${TARGET_SYS}" || EXTRA_OECONF="--target=${TARGET_SYS} ${EXTRA_OECONF}"
		set -x
		./configure \
		    --prefix=/usr \
		    --host=${SYS} \
		    --mandir=/usr/share/man \
		    --infodir=/usr/share/info \
		    --datadir=/usr/share \
		    --sysconfdir=/etc \
		    --localstatedir=/var/lib \
			${EXTRA_OECONF} \
		    "$@" || die "oeconf failed" 
	else
		die "no configure script found"
	fi
}

oemake() {
	if [ -f ./[mM]akefile -o -f ./GNUmakefile ] ; then
		if [ x"$MAKE" = x ]; then MAKE=make; fi
		${MAKE} ${EXTRA_OEMAKE} "$@" || die "oemake failed"
	else
		die "no Makefile found"
	fi
}


oeinstall() {
	if [ -f ./[mM]akefile -o -f ./GNUmakefile ] ; then
		${MAKE} prefix=${D}/usr \
		    datadir=${D}/usr/share \
		    infodir=${D}/usr/share/info \
		    localstatedir=${D}/var/lib \
		    mandir=${D}/usr/share/man \
		    sysconfdir=${D}/etc \
		    "$@" install || die "einstall failed" 
	else
		die "no Makefile found"
	fi
}


do_nofetch()
{
	test -z "${SRC_URI}" && return

	oenote "The following files are listed in SRC_URI for ${PN}:"
	for MYFILE in `echo ${SRC_URI}`; do
		oenote "  $MYFILE"
	done
}



do_unpack()
{
	test "${A}" != "" && unpack "${A}" || oenote "nothing to extract"
}




do_compile()
{ 
	if [ -x ./configure ] ; then
		oeconf 
		oemake || die "oemake failed"
	else
		oenote "nothing to compile"
	fi
}


do_stage()
{ 
	oenote "nothing to install into stage area"
}


do_install()
{ 
	oenote "nothing to install"
}


try() {
	env "$@"
	if [ "$?" != "0" ]; then
		oefatal "ERROR: the $1 command did not complete successfully."
		oefatal "(\"$*\")"
		oefatal "Since this is a critical task, ebuild will be stopped."
		exit 1
	fi
}


# debug-print() gets called from many places with verbose status information useful
# for tracking down problems. The output is in $T/eclass-debug.log.
# You can set OECLASS_DEBUG_OUTPUT to redirect the output somewhere else as well.
# The special "on" setting echoes the information, mixing it with the rest of the
# emerge output.
# You can override the setting by exporting a new one from the console, or you can
# set a new default in oe.conf. Here the default is "" or unset.

debug-print() {
	while [ "$1" ]; do
	
		# extra user-configurable targets
		if [ "$OECLASS_DEBUG_OUTPUT" == "on" ]; then
			echo "debug: $1"
		elif [ -n "$OECLASS_DEBUG_OUTPUT" ]; then
			echo "debug: $1" >> $OECLASS_DEBUG_OUTPUT
		fi
		
		# default target
		echo $1 >> ${T}/oeclass-debug.log
		
		shift
	done
}

# The following 2 functions are debug-print() wrappers

debug-print-function() {
	str="$1: entering function" 
	shift
	debug-print "$str, parameters: $*"
}

debug-print-section() {
	debug-print "now in section $*"
}

# Sources all eclasses in parameters
inherit() {
	unset INHERITED
	local location
	while [ "$1" ]
	do
		location="${OEDIR}/bin/build/${1}.oeclass"
		POECLASS="$OECLASS"
		export OECLASS="$1"

		# TODO: work throught OEPATH
		#if [ -n "$PORTDIR_OVERLAY" ]
		#then
		#	olocation="${PORTDIR_OVERLAY}/eclass/${1}.eclass"
		#	if [ -e "$olocation" ]; then
		#		location="${olocation}"
		#	fi
		#fi

		debug-print "inherit: $1 -> $location"
		source "$location" || die "died sourcing $location in inherit()"
		OECLASS="$POECLASS"
		unset POECLASS

		if ! has $1 $INHERITED &>/dev/null; then
			export INHERITED="$INHERITED $1"
		fi

		shift
	done
}


# Exports stub functions that call the oeclass's functions, thereby making them default.
# For example, if OECLASS="base" and you call "EXPORT_FUNCTIONS do_unpack", the following
# code will be eval'd:
# do_unpack() { base_do_unpack; }
EXPORT_FUNCTIONS() {
	if [ -z "$OECLASS" ]; then
		oefatal "EXPORT_FUNCTIONS without a defined OECLASS"
		exit 1
	fi
	while [ "$1" ]; do
		debug-print "EXPORT_FUNCTIONS: ${1} -> ${OECLASS}_${1}" 
		eval "$1() { ${OECLASS}_$1 ; }" >/dev/null
		shift
	done
}


# adds all parameters to DEPEND and RDEPEND
newdepend() {
	debug-print-function newdepend $*
	debug-print "newdepend: DEPEND=$DEPEND RDEPEND=$RDEPEND"

	while [ -n "$1" ]; do
		case $1 in
		"/autotools")
			DEPEND="${DEPEND} sys-devel/autoconf sys-devel/automake sys-devel/make"
			;;
		"/c")
			DEPEND="${DEPEND} sys-devel/gcc virtual/glibc"
			RDEPEND="${RDEPEND} virtual/glibc"
			;;
		*)
			DEPEND="$DEPEND $1"
			if [ -z "$RDEPEND" ] && [ "${RDEPEND-unset}" == "unset" ]; then
				export RDEPEND="$DEPEND"
			fi
			RDEPEND="$RDEPEND $1"
			;;
		esac
		shift
	done
}
