RPMBUILDPATH="${WORKDIR}/rpm"

RPMOPTS="--rcfile=${WORKDIR}/rpmrc"
RPMOPTS="--rcfile=${WORKDIR}/rpmrc --target ${TARGET_SYS}"
RPM="rpm ${RPMOPTS}"
RPMBUILD="rpmbuild --buildroot ${D} --short-circuit ${RPMOPTS}"

rpm_core_do_preprpm() {
	mkdir -p ${RPMBUILDPATH}/{SPECS,RPMS/{i386,i586,i686,noarch,ppc,mips,mipsel,arm},SRPMS,SOURCES,BUILD}
	echo 'macrofiles:/usr/lib/rpm/macros:${WORKDIR}/macros' > ${WORKDIR}/rpmrc
	echo '%_topdir ${RPMBUILDPATH}' > ${WORKDIR}/macros
	echo '%_repackage_dir ${WORKDIR}' >> ${WORKDIR}/macros
}

EXPORT_FUNCTIONS do_preprpm
addtask preprpm before do_fetch
