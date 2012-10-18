#
# Copyright 2012 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import logging

from vdsm import qemuImg

from storage import sd
from storage import blockSD
from storage import image
from storage import safelease
from storage import volume


def __convertDomainMetadataToTags(domain, targetVersion):
    log = logging.getLogger('Storage.DomainMetadataToTags')

    newMetadata = blockSD.TagBasedSDMetadata(domain.sdUUID)
    oldMetadata = domain._metadata

    # We use _dict to bypass the validators in order to copy all metadata
    metadata = oldMetadata._dict.copy()
    metadata[sd.DMDK_VERSION] = str(targetVersion)  # Must be a string

    log.debug("Converting domain %s to tag based metadata", domain.sdUUID)
    newMetadata._dict.update(metadata)

    try:
        # If we can't clear the old metadata we don't have any clue on what
        # actually happened. We prepare the convertError exception to raise
        # later on if we discover that the upgrade didn't take place.
        oldMetadata._dict.clear()
    except Exception, convertError:
        log.error("Could not clear the old metadata", exc_info=True)
    else:
        # We don't have any valuable information to add here
        convertError = RuntimeError("Unknown metadata conversion error")

    # If this fails, there's nothing we can do, let's bubble the exception
    chkMetadata = blockSD.selectMetadata(domain.sdUUID)

    if chkMetadata[sd.DMDK_VERSION] == int(targetVersion):
        # Switching to the newMetadata (successful upgrade), the oldMetadata
        # was cleared after all.
        domain._metadata = chkMetadata
        log.debug("Conversion of domain %s to tag based metadata completed, "
                  "target version = %s", domain.sdUUID, targetVersion)
    else:
        # The upgrade failed, cleaning up the new metadata
        log.error("Could not convert domain %s to tag based metadata, "
                  "target version = %s", domain.sdUUID, targetVersion)
        newMetadata._dict.clear()
        # Raising the oldMetadata_dict.clear() exception or the default one
        raise convertError


def v2DomainConverter(repoPath, hostId, domain, isMsd):
    log = logging.getLogger('Storage.v2DomainConverter')
    targetVersion = 2

    if domain.getStorageType() in sd.BLOCK_DOMAIN_TYPES:
        log.debug("Trying to upgrade domain %s to tag based metadata "
                  "version %s", domain.sdUUID, targetVersion)

        __convertDomainMetadataToTags(domain, targetVersion)

    else:
        log.debug("Skipping the upgrade to tag based metadata version %s "
                  "for the domain %s", targetVersion, domain.sdUUID)


def v3DomainConverter(repoPath, hostId, domain, isMsd):
    log = logging.getLogger('Storage.v3DomainConverter')
    log.debug("Starting conversion for domain %s", domain.sdUUID)

    log.debug("Initializing the new cluster lock for domain %s", domain.sdUUID)
    newClusterLock = safelease.SANLock(domain.sdUUID, domain.getIdsFilePath(),
                                       domain.getLeasesFilePath())
    newClusterLock.initLock()

    log.debug("Acquiring the host id %s for domain %s", hostId, domain.sdUUID)
    newClusterLock.acquireHostId(hostId, async=False)

    V2META_SECTORSIZE = 512

    def v3ResetMetaVolSize(vol):
        # BZ811880 Verifiying that the volume size is the same size advertised
        # by the metadata
        log.debug("Checking the volume size for the volume %s", vol.volUUID)

        metaVolSize = int(vol.getMetaParam(volume.SIZE))

        if vol.getFormat() == volume.COW_FORMAT:
            qemuVolInfo = qemuImg.info(vol.getVolumePath(),
                                       qemuImg.FORMAT.QCOW2)
            virtVolSize = qemuVolInfo["virtualsize"] / V2META_SECTORSIZE
        else:
            virtVolSize = vol.getVolumeSize()

        if metaVolSize != virtVolSize:
            log.warn("Fixing the mismatch between the metadata volume size "
                     "(%s) and the volume virtual size (%s) for the volume "
                     "%s", vol.volUUID, metaVolSize, virtVolSize)
            vol.setMetaParam(volume.SIZE, str(virtVolSize))

    def v3UpdateVolume(vol):
        log.debug("Changing permissions (read-write) for the "
                  "volume %s", vol.volUUID)

        # Using the internal call to skip the domain V3 validation,
        # see volume.setrw for more details.
        vol._setrw(True)

        log.debug("Creating the volume lease for %s", vol.volUUID)
        metaId = vol.getMetadataId()
        type(vol).newVolumeLease(metaId, vol.sdUUID, vol.volUUID)

    try:
        if isMsd:
            log.debug("Acquiring the cluster lock for domain %s with "
                      "host id: %s", domain.sdUUID, hostId)
            newClusterLock.acquire(hostId)

        img = image.Image(repoPath)

        for imgUUID in domain.getAllImages():
            log.debug("Converting domain image: %s", imgUUID)

            # XXX: The only reason to prepare the image is to verify the volume
            # virtual size configured in the qcow2 header (BZ#811880).
            # The activation and deactivation of the LVs might lead to a race
            # with the creation or destruction of a VM on the SPM.
            #
            # The analyzed scenarios are:
            #  1. A VM is currently running on the image we are preparing.
            #     This is safe because the prepare is superfluous and the
            #     teardown is going to fail (the LVs are in use by the VM)
            #  2. A VM using this image is started after the prepare.
            #     This is safe because the prepare issued by the VM is
            #     superfluous and our teardown is going to fail (the LVs are
            #     in use by the VM).
            #  3. A VM using this image is started and the teardown is
            #     executed before that the actual QEMU process is started.
            #     This is safe because the VM is going to fail (the engine
            #     should retry later) but there is no risk of corruption.
            #  4. A VM using this image is destroyed after the prepare and
            #     before reading the image size.
            #     This is safe because the upgrade process will fail (unable
            #     to read the image virtual size) and it can be restarted
            #     later.
            volChain = img.prepare(domain.sdUUID, imgUUID)

            try:
                for vol in volChain:
                    v3UpdateVolume(vol)
                    v3ResetMetaVolSize(vol)  # BZ#811880
            finally:
                try:
                    img.teardown(domain.sdUUID, imgUUID)
                except:
                    log.debug("Unable to teardown the image: %s", imgUUID,
                              exc_info=True)

        targetVersion = 3
        currentVersion = domain.getVersion()
        log.debug("Finalizing the storage domain upgrade from version %s to "
                  "version %s for domain %s", currentVersion, targetVersion,
                  domain.sdUUID)

        if (currentVersion not in blockSD.VERS_METADATA_TAG
                        and domain.getStorageType() in sd.BLOCK_DOMAIN_TYPES):
            __convertDomainMetadataToTags(domain, targetVersion)
        else:
            domain.setMetaParam(sd.DMDK_VERSION, targetVersion)

    except:
        if isMsd:
            try:
                log.error("Releasing the cluster lock for domain %s with "
                          "host id: %s", domain.sdUUID, hostId)
                newClusterLock.release()
            except:
                log.error("Unable to release the cluster lock for domain "
                          "%s with host id: %s", domain.sdUUID, hostId,
                          exc_info=True)

        try:
            log.error("Releasing the host id %s for domain %s", hostId,
                      domain.sdUUID)
            newClusterLock.releaseHostId(hostId, async=False, unused=True)
        except:
            log.error("Unable to release the host id %s for domain %s",
                      hostId, domain.sdUUID, exc_info=True)

        raise

    # Releasing the old cluster lock (safelease). This lock was acquired
    # by the regular startSpm flow and now must be replaced by the new one
    # (sanlock). Since we are already at the end of the process (no way to
    # safely rollback to version 0 or 2) we should ignore the cluster lock
    # release errors.
    if isMsd:
        try:
            domain._clusterLock.release()
        except:
            log.error("Unable to release the old cluster lock for domain "
                      "%s ", domain.sdUUID, exc_info=True)

    # This is not strictly required since the domain object is destroyed right
    # after the upgrade but let's not make assumptions about future behaviors
    log.debug("Switching the cluster lock for domain %s", domain.sdUUID)
    domain._clusterLock = newClusterLock


_IMAGE_REPOSITORY_CONVERSION_TABLE = {
    ('0', '2'): v2DomainConverter,
    ('0', '3'): v3DomainConverter,
    ('2', '3'): v3DomainConverter,
}


class FormatConverter(object):
    def __init__(self, conversionTable):
        self._convTable = conversionTable

    def _getConverter(self, sourceFormat, targetFormat):
        return self._convTable[(sourceFormat, targetFormat)]

    def convert(self, repoPath, hostId, imageRepo, isMsd, targetFormat):
        sourceFormat = imageRepo.getFormat()
        if sourceFormat == targetFormat:
            return

        converter = self._getConverter(sourceFormat, targetFormat)
        converter(repoPath, hostId, imageRepo, isMsd)


def DefaultFormatConverter():
    return FormatConverter(_IMAGE_REPOSITORY_CONVERSION_TABLE)