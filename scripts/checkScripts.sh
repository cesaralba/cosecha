#!/bin/bash

set -eu

BASEDIR=$(cd "$(dirname $(readlink -e $0))" && pwd )

CONFIGFILE=${DEVSMCONFIGFILE:-/etc/sysconfig/Cosecha}
[ -f ${CONFIGFILE} ] && source ${CONFIGFILE}

if [ -n "${CS_ROOTWRK}" ] ; then
  ROOTDATA=${CS_ROOTWRK}
else
  ROOTDATA=${BASEDIR}
fi

WRKDIR="${ROOTDATA}/wrk"
[ -d ${WRKDIR} ] || soLong "ORROR: No se encuentra código descargado. Pruebe a ejecutar ${HEREDIR}/buildVENV.sh . Adios."

LOC="${WRKDIR}/scripts/*"
ECHOLOC=$(echo ${LOC})


if [ ${#LOC} = ${#ECHOLOC} ]
then
  echo "Scripts not found in ${WRKDIR}"
  exit 1
fi

for MYFILE in ${WRKDIR}/scripts/*
do
  FILEHERE=$(basename ${MYFILE} )
  if [ -f ${FILEHERE} ]
  then
    MD5HERE=$(md5sum ${FILEHERE})
    MD5WRK=$(md5sum ${MYFILE})

    if [ ${MD5HERE} != ${MD5WRK} ]
    then
      echo "$(readlink -e ${FILEHERE}) and $(readlink -e ${MYFILE}) differ"
      diff ${MD5HERE}  ${MD5WRK}
    fi
  else
    echo "$(readlink -e ${MYFILE}) does not exist in ${BASEDIR}"
  fi
done