# Prevent aliases from causing us to act inappropriately.
# Make sure it's before everything so we don't mess aliases that follow.
unalias -a

# We need this next line for "die" and "assert". It expands
# It _must_ preceed all the calls to die and assert.
shopt -s expand_aliases
alias die='diefunc "$FUNCNAME" "$LINENO" "$?"'



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



#has_version() {
#        # return shell-true/shell-false if exists.
#        # Takes single depend-type atoms.
#        if /usr/lib/portage/bin/portageq 'has_version' ${ROOT} $1; then
#                return 0
#        else
#                return 1
#        fi
#}


#best_version() {
#        # returns the best/most-current match.
#        # Takes single depend-type atoms.
#        /usr/lib/portage/bin/portageq 'best_version' ${ROOT} $1
#}


use_with() {
        if [ -z "$1" ]; then
                die "use_with() called without parameter"
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
                die "use_with() called without parameter"
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
        echo "ERROR: $CATEGORY/$PF failed" >&2
        echo "NOTE: Function $funcname, Line $lineno, Exitcode $exitcode" >&2
        echo "NOTE: ${*:-(no error message)}" >&2
        echo >&2
        exit 1
}


#if no perms are specified, dirs/files will have decent defaults
#(not secretive, but not stupid)
umask 022
export DESTTREE=/usr
export INSDESTTREE=""
export EXEDESTTREE=""
export DOCDESTTREE=""
export INSOPTIONS="-m0644"
export EXEOPTIONS="-m0755"
export LIBOPTIONS="-m0644"
export DIROPTIONS="-m0755"
export MOPREFIX=${PN}


unpack() {
	local x
	local y
	local myfail
	
	for x in $@
	do
		myfail="failure unpacking ${x}"
		echo "NOTE: Unpacking ${x} to $(pwd)"
		y="$(echo $x | sed 's:.*\.\(tar\)\.[a-zA-Z0-9]*:\1:')"
		case "${x##*.}" in
		tar) 
			tar x --no-same-owner -f ${DISTDIR}/${x} || die "$myfail"
			;;
		tgz) 
			tar xz --no-same-owner -f ${DISTDIR}/${x} || die "$myfail"
			;;
		tbz2) 
			tar xj --no-same-owner -f ${DISTDIR}/${x} || die "$myfail"
			;;
		ZIP|zip) 
			unzip -qo ${DISTDIR}/${x} || die "$myfail"
			;;
		gz|Z|z) 
			if [ "${y}" == "tar" ]; then
				tar xz --no-same-owner -f ${DISTDIR}/${x} || die "$myfail"
			else
				gzip -dc ${DISTDIR}/${x} > ${x%.*} || die "$myfail"
			fi
			;;
		bz2) 
			if [ "${y}" == "tar" ]; then
				tar xj --no-same-owner -f ${DISTDIR}/${x} || die "$myfail"
			else
				bzip2 -dc ${DISTDIR}/${x} > ${x%.*} || die "$myfail"
			fi
			;;
		*)
			echo "unpack ${x}: file format not recognized. Ignoring."
			;;
		esac
	done
}


oeconf() {
	if [ -x ./configure ] ; then
		if [ ! -z "${CBUILD}" ]; then
			EXTRA_ECONF="--build=${CBUILD} ${EXTRA_ECONF}"
		fi
		./configure \
		    --prefix=/usr \
		    --host=${CHOST} \
		    --mandir=/usr/share/man \
		    --infodir=/usr/share/info \
		    --datadir=/usr/share \
		    --sysconfdir=/etc \
		    --localstatedir=/var/lib \
				${EXTRA_ECONF} \
		    "$@" || die "econf failed" 
	else
		die "no configure script found"
	fi
}


oeinstall() {
	if [ -f ./[mM]akefile -o -f ./GNUmakefile ] ; then
		make prefix=${D}/usr \
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


pkg_setup()
{
	return 
}


pkg_nofetch()
{
	[ -z "${SRC_URI}" ] && return

	echo "!!! The following are listed in SRC_URI for ${PN}:"
	for MYFILE in `echo ${SRC_URI}`; do
		echo "!!!   $MYFILE"
	done
	return 
}


src_unpack() { 
	if [ "${A}" != "" ]
	then
		unpack ${A}
	fi	
}


src_compile() { 
	if [ -x ./configure ] ; then
		econf 
		emake || die "emake failed"
	fi
	return 
}

src_install() 
{ 
	return 
}

