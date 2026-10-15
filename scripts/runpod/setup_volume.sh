#!/usr/bin/env bash
# One-off setup of the RunPod network volume for render offload (render-pod-lifecycle).
#
# Run it yourself in the RunPod web terminal of a temporary pod that uses the SAME image
# as RENDER_OFFLOAD_RUNPOD_IMAGE and has the network volume mounted at /workspace.
# The app never runs this script. See docs/runpod-setup.md.
#
#   bash setup_volume.sh "ssh-ed25519 AAAA... you@laptop"
#
# It is safe to run again: what is already on the volume is checked and kept.
set -euo pipefail

BLENDER_VERSION="5.2.1"
BLENDER_SERIES="5.2"
BLENDER_DIR="/workspace/blender-${BLENDER_VERSION}-linux-x64"
TARBALL="blender-${BLENDER_VERSION}-linux-x64.tar.xz"
RELEASE_URL="https://download.blender.org/release/Blender${BLENDER_SERIES}"
HRA="/workspace/hra"
SSH_DIR="${HRA}/ssh"
DEB_DIR="${HRA}/debs"
# What Blender needs to run headless, and the SSH server the app connects to. Only the
# ones this image lacks are downloaded (with their own missing dependencies).
PACKAGES=(openssh-server libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 xz-utils)

fail() { echo "setup: $*" >&2; exit 1; }

[[ $# -eq 1 ]] || fail "give your public key as the one argument, in quotes"
PUBLIC_KEY="$1"
[[ "$PUBLIC_KEY" =~ ^(ssh-ed25519|ecdsa-sha2-nistp(256|384|521)|ssh-rsa)\ [A-Za-z0-9+/=]+(\ .*)?$ ]] \
  || fail "that does not look like a single OpenSSH public key line"
[[ "$PUBLIC_KEY" != *$'\n'* ]] || fail "give exactly one key line"
mountpoint -q /workspace || [[ -d /workspace ]] || fail "/workspace is not mounted; attach the network volume"
[[ $EUID -eq 0 ]] || fail "run as root (the RunPod web terminal is root)"

mkdir -p "$SSH_DIR" "${DEB_DIR}/partial"

echo "== System packages for Blender and sshd"
apt-get update -qq
apt-get install -y -qq --download-only -o "Dir::Cache::archives=${DEB_DIR}" "${PACKAGES[@]}"
rm -f "${DEB_DIR}/lock"
rm -rf "${DEB_DIR}/partial"
if compgen -G "${DEB_DIR}/*.deb" >/dev/null; then
  dpkg -i "${DEB_DIR}"/*.deb >/dev/null
  echo "   kept $(find "$DEB_DIR" -name '*.deb' | wc -l) package(s) on the volume"
else
  echo "   the image already has them all"
fi

echo "== Blender ${BLENDER_VERSION}"
if [[ -x "${BLENDER_DIR}/blender" ]] && "${BLENDER_DIR}/blender" --version 2>/dev/null | head -n 1 | grep -q "Blender ${BLENDER_VERSION}"; then
  echo "   already on the volume"
else
  work="$(mktemp -d /workspace/hra-download.XXXXXX)"
  trap 'rm -rf "$work"' EXIT
  curl -fsSL --proto '=https' -o "${work}/${TARBALL}" "${RELEASE_URL}/${TARBALL}"
  curl -fsSL --proto '=https' -o "${work}/checksums" "${RELEASE_URL}/blender-${BLENDER_VERSION}.sha256" \
    || fail "blender.org has no checksum file for ${BLENDER_VERSION}; not installing an unchecked download"
  expected="$(grep " ${TARBALL}\$" "${work}/checksums" | cut -d ' ' -f 1)"
  [[ -n "$expected" ]] || fail "the checksum file does not list ${TARBALL}"
  actual="$(sha256sum "${work}/${TARBALL}" | cut -d ' ' -f 1)"
  [[ "$expected" == "$actual" ]] || fail "SHA-256 mismatch for ${TARBALL}; nothing was installed"
  echo "   SHA-256 matches blender.org"
  rm -rf "$BLENDER_DIR"
  tar -xJf "${work}/${TARBALL}" -C /workspace
fi
"${BLENDER_DIR}/blender" --background --factory-startup --python-expr "import bpy; print('HRA-OK', bpy.app.version_string)" 2>/dev/null \
  | grep -q "HRA-OK ${BLENDER_VERSION}" || fail "Blender does not start headless on this image"
echo "   starts headless"

echo "== SSH keys"
if [[ ! -f "${SSH_DIR}/ssh_host_ed25519_key" ]]; then
  ssh-keygen -q -t ed25519 -N "" -C hra-render-pod -f "${SSH_DIR}/ssh_host_ed25519_key"
  echo "   new host key made"
else
  echo "   host key kept"
fi
chmod 600 "${SSH_DIR}/ssh_host_ed25519_key"
printf '%s\n' "$PUBLIC_KEY" > "${SSH_DIR}/authorized_keys"
chmod 600 "${SSH_DIR}/authorized_keys"
echo "   your public key is the only authorised key"

echo
echo "Done. Add this line to the file RENDER_OFFLOAD_KNOWN_HOSTS_PATH names on your laptop:"
echo
echo "hra-render-pod $(cut -d ' ' -f 1,2 "${SSH_DIR}/ssh_host_ed25519_key.pub")"
echo
echo "Set RENDER_OFFLOAD_BLENDER=${BLENDER_DIR}/blender and RENDER_OFFLOAD_USER=root, then delete this setup pod."
