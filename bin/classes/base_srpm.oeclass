inherit base package rpm_core

SPECFILE="${RPMBUILDPATH}/SPECS/${PN}.spec"

base_srpm_do_unpack() {
	test -e ${SRPMFILE} || die "Source rpm \"${SRPMFILE}\"does not exist"
	if ! test -e ${SPECFILE}; then
		${RPM} -i ${SRPMFILE}
	fi
	test -e ${SPECFILE} || die "Spec file \"${SPECFILE}\" does not exist"
	${RPMBUILD} -bp ${SPECFILE}
}

base_srpm_do_compile() {
	${RPMBUILD} -bc ${SPECFILE}
}

base_srpm_do_install() {
	${RPMBUILD} -bi ${SPECFILE}
}
