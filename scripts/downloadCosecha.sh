#!/bin/bash

set -eu

function soLong {
  MSG=${1:-No msg}
  echo ${MSG}
  exit 1
}

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/Cosecha}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ ${CS_DEBUGSCRIPTS:-0} = 1 ]
then
  set -vx
fi

ME="$(readlink -e $0)"
HEREDIR=$(cd "$(dirname ${ME})" && pwd )
BASEDIR=$(cd "${HEREDIR}/../" && pwd )
TODAY=$(date '+%Y%m%d%H%M')

if [ -n "${CS_ROOTWRK}" ] ; then
  ROOTDATA=${CS_ROOTWRK}
else
  ROOTDATA=${BASEDIR}
fi

[ "x${CS_REPO}" = "x" ] && soLong "ORROR: No se ha suministrado valor para CS_REPO. Adios."

WRKDIR="${ROOTDATA}/wrk"
[ -d ${WRKDIR} ] || soLong "ORROR: No se encuentra código descargado. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."

VENV=${VENVHOME:-"${BASEDIR}/venv"}
ACTIVATIONSCR="${VENV}/bin/activate"

if [ -f "${ACTIVATIONSCR}" ] ; then
  source "${ACTIVATIONSCR}"
else
  soLong "ORROR: Incapaz de encontrar activador de virtualenv. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."
fi

python ${WRKDIR}/bin/DescargaCosecha.py $*
