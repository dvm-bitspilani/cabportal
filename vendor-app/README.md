# Ridezy Vendor

Ionic React + TypeScript Android client for the Ridezy vendor API.

## Local development

```sh
cp .env.development.example .env.development
npm install
npm run dev
```

For an Android emulator, `10.0.2.2` reaches Django on the host. A physical
device needs a reachable development HTTPS URL (or an explicit debug-only
network configuration). Production builds reject cleartext traffic.

Authentication tokens are held in Android encrypted storage by
`@aparajita/capacitor-secure-storage`. Access tokens refresh automatically;
failed refresh clears the session. Mutations are never cached or retried.

## Android builds

Install Android SDK 35 and a JDK that supports Java 21 source (JDK 21+), then:

```sh
npm run android:sync
cd android
./gradlew assembleDebug
```

For a signed Play App Bundle, keep the keystore outside the repository and set:

```sh
export RIDEZY_KEYSTORE_PATH=/secure/location/ridezy-upload.jks
export RIDEZY_KEYSTORE_PASSWORD='...'
export RIDEZY_KEY_ALIAS='ridezy-upload'
export RIDEZY_KEY_PASSWORD='...'
export RIDEZY_VERSION_CODE=1
export RIDEZY_VERSION_NAME=1.0.0
./gradlew bundleRelease
```

The AAB is written to `android/app/build/outputs/bundle/release/`. Increment
`RIDEZY_VERSION_CODE` for every Play upload. Never commit the keystore,
passwords, `.env` files, or `local.properties`.

## Play internal testing

1. Create the app as **Ridezy Vendor**, package `com.ridezy.vendor`.
2. Complete App content and Data safety using the deployment owner's details.
3. Use the existing privacy URL: `https://cab.bits-oasis.org/privacy-policy/`.
4. Upload the signed AAB under Testing → Internal testing and add testers.
5. Verify fresh install, login persistence after relaunch, expired-token refresh,
   offline recovery, Android back behavior, keyboards/date inputs, and phone and
   tablet layouts before promoting the release.

The production API origin is controlled by `.env.production`; copy the example
and review it before `npm run android:sync`.
