# Download page

The page at **https://bayan-android.vercel.app** (Vercel project `bayan-app`): Arabic and English with a toggle, the
install steps, what's new, and every APK of the current release with its SHA-256.

The APKs themselves are on Hugging Face, `Congi-libya/Bayan-App/releases/<version>/` (the GitHub repo is private).

## A new release
1. Bump `versionCode` and `versionName` in `app/app/build.gradle.kts`, and add the release to `app/CHANGELOG.md`.
2. `ANDROID_HOME=~/Android/Sdk sh app/tools/release.sh` builds the signed APKs into `app/build/dist/<version>/` with
   `SHA256SUMS.txt` (the signing key is in `~/.android/`, linked as `app/keystore.properties`; never commit it).
3. Upload that folder and the changelog to `Congi-libya/Bayan-App` under `releases/<version>/`.
4. Update the version, sizes and links in `index.html`, then `npx vercel deploy --prod` from this folder.
