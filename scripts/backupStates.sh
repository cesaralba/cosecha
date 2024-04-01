#!/bin/bash

set -eu

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/Cosecha}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ ${CS_DEBUGSCRIPTS:-0} = 1 ]
then
  set -vx
fi

BASEDIR=$(cd "$(dirname $(readlink -e $0))/../" && pwd )

if [ -n "${CS_DATADIR}" ] ; then
  ROOTDATA=${CS_DATADIR}
else
  ROOTDATA=${BASEDIR}
fi


if [ -n "${CS_ROOTWRK}" ] ; then
  ROOTWRK=${CS_ROOTWRK}
else
  ROOTWRK=${BASEDIR}
fi

YEAR=$(date +%Y)
TODAY=$(date '+%Y%m%d%H%M')
BACKUPDIR="${ROOTWRK}/backup.State/${YEAR}"
STATEDIR="${ROOTDATA}/state"


if [ ! -d  ${STATEDIR} ]
then
  echo "Unable to find State dir ${STATEDIR}"
  exit 1
fi

mkdir -pv ${BACKUPDIR}
tar cz -f ${BACKUPDIR}/state.${TODAY}.tgz -C ${STATEDIR} .    &> /dev/null
