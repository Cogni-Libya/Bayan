#!/bin/sh
# Builds the release APKs and puts them in app/build/dist/ as Bayan-<version>-<abi>.apk, with SHA256SUMS.txt.
#   ANDROID_HOME=~/Android/Sdk sh app/tools/release.sh
# Signing: app/keystore.properties (see app/app/build.gradle.kts). Without it the APKs are debug-signed.
set -e
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/.*versionName = "\(.*\)".*/\1/p' app/build.gradle.kts)
[ -f keystore.properties ] || echo "warning: no keystore.properties, so the APKs are signed with the debug key" >&2
./gradlew -q :app:assembleRelease
OUT=build/dist/$VERSION
rm -rf "$OUT"; mkdir -p "$OUT"
for f in app/build/outputs/apk/release/app-*-release.apk; do
  abi=$(basename "$f" | sed 's/^app-\(.*\)-release\.apk$/\1/')
  cp "$f" "$OUT/Bayan-$VERSION-$abi.apk"
done
(cd "$OUT" && sha256sum Bayan-*.apk > SHA256SUMS.txt)
ls -l "$OUT"; cat "$OUT/SHA256SUMS.txt"
