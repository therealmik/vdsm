#
# Copyright 2008-2011 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

SUBDIRS = protect imageRepository

include $(top_srcdir)/build-aux/Makefile.subs

vdsmstoragedir = $(vdsmdir)/storage
dist_vdsmstorage_PYTHON = \
	__init__.py \
	blockSD.py \
	blockVolume.py \
	clusterlock.py \
	curlImgWrap.py \
	devicemapper.py \
	dispatcher.py \
	domainMonitor.py \
	fileSD.py \
	fileUtils.py \
	fileVolume.py \
	fuser.py \
	glusterSD.py \
	glusterVolume.py \
	hba.py \
	hsm.py \
	image.py \
	imageSharing.py \
	iscsiadm.py \
	iscsi.py \
	localFsSD.py \
	lvm.py \
	misc.py \
	mount.py \
	multipath.py \
	nfsSD.py \
	outOfProcess.py \
	persistentDict.py \
	remoteFileHandler.py \
	resourceFactories.py \
	resourceManager.py \
	sdc.py \
	sd.py \
	securable.py \
	sp.py \
	spbackends.py \
	storageConstants.py \
	storage_exception.py \
	storage_mailbox.py \
        storageServer.py \
	sync.py \
	taskManager.py \
	task.py \
	threadLocal.py \
	threadPool.py \
	volume.py

dist_vdsmexec_SCRIPTS = \
	curl-img-wrap

nodist_vdsmstorage_DATA = \
	lvm.env \
	$(NULL)

EXTRA_DIST = \
	lvm.env.in \
	$(NULL)
