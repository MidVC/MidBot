#!/bin/bash
# 在 user namespace 里 chroot 进 rootfs，root 身份；cwd 固定为 /
# 用途：宿主机没有 xkbcomp，借 rootfs 里的 /usr/bin/xkbcomp 跑 Xvfb
exec unshare -Urmp --fork --mount-proc /usr/sbin/chroot "${XVFB_ROOTFS:-$HOME/napcat-qq/rootfs}" /bin/bash -c "cd /; $*"
