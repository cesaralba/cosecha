#!/bin/bash

set -eu

BASEDIR=$(cd "$(dirname $(readlink -e $0))" && pwd )

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/Cosecha}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

bash ${BASEDIR}/buildDataTree.sh
bash ${BASEDIR}/buildVENV.sh
bash ${BASEDIR}/checkScripts.sh || true

bash ${BASEDIR}/downloadCosecha.sh
