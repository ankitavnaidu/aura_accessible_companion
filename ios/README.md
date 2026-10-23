# Apple Watch and iPhone HealthKit bridge

`AURAHealthBridge/HealthLocationBridge.swift` is a source starter, not a complete iOS app. Apple Watch measurements reach this code through Apple's HealthKit APIs on the paired iPhone. A browser cannot directly read the Apple Watch health database.

To turn the starter into an app, an iOS developer must:

1. Create an iOS app target in Xcode and add `AURAHealthBridge/HealthLocationBridge.swift` to it.
2. Enable the HealthKit capability and add the HealthKit usage description to the app's `Info.plist`. Add the appropriate location usage description and capability if location sharing is offered.
3. Build a sign-in flow for the same Cognito user pool as `aws-sharing/template.yaml`. Supply the bridge with a short-lived Cognito access token containing `aura/circle.share` and the circle ID.
4. Present the circle, approved guardian email list, and individual data-field choices before calling `startSharing`.
5. Test authorization denial, no sensor values, stale values, location denial, loss of connectivity, sign-out, and stop-sharing on physical devices.

The bridge requests permission to read heart rate, oxygen saturation, and step count. Heart rate and SpO₂ samples older than two minutes are omitted instead of being presented as fresh. Step count is the day's cumulative HealthKit total; movement state comes from Core Motion. Location and health data are sent to the configured AURA API only while the bridge is sharing. On stop it asks the API to clear remote sharing and stops the location and motion updates.

HealthKit does not guarantee second-by-second watch measurements or background updates. The current starter polls every 15 seconds while its host app is active. Production background delivery, account recovery, token refresh, app signing, privacy disclosures, accessibility, and safety review remain to be implemented. It does not detect emergencies or contact emergency services.
