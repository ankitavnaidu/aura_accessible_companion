import CoreLocation
import CoreMotion
import Foundation
import HealthKit

/// iPhone-side bridge for Apple Watch/HealthKit data. The containing iOS app must
/// provide a Cognito sign-in token and call start only after the patient chooses
/// the circle and fields to share.
@MainActor
final class HealthLocationBridge: NSObject, CLLocationManagerDelegate {
    struct Selection {
        var location = true
        var heartRate = true
        var oxygenSaturation = true
        var dailySteps = true
        var movement = true
    }

    typealias TokenProvider = () async throws -> String

    private let healthStore = HKHealthStore()
    private let locationManager = CLLocationManager()
    private let activityManager = CMMotionActivityManager()
    private let apiBase: URL
    private var circleId = ""
    private var tokenProvider: TokenProvider?
    private var selection = Selection()
    private var latestLocation: CLLocation?
    private var movementState = "unknown"
    private var timer: Timer?
    private var isSharing = false

    init(apiBase: URL) {
        self.apiBase = apiBase
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        locationManager.distanceFilter = 5
    }

    func requestHealthPermissions() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw BridgeError.message("HealthKit is not available on this device.")
        }
        let readTypes: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .oxygenSaturation)!,
            HKObjectType.quantityType(forIdentifier: .stepCount)!
        ]
        try await healthStore.requestAuthorization(toShare: [], read: readTypes)
    }

    /// Call after the signed-in patient selected a circle, selected fields, and
    /// reviewed the approved guardian email addresses. Sharing stops on logout.
    func startSharing(circleId: String, selection: Selection, tokenProvider: @escaping TokenProvider) async throws {
        guard !circleId.isEmpty else { throw BridgeError.message("Choose a guardian circle first.") }
        self.circleId = circleId
        self.selection = selection
        self.tokenProvider = tokenProvider
        if selection.location {
            locationManager.requestWhenInUseAuthorization()
            guard CLLocationManager.locationServicesEnabled() else {
                throw BridgeError.message("Location Services are off. Enable them or turn off location sharing.")
            }
        }
        try await requestHealthPermissions()
        try await setRemoteSharing(true)
        isSharing = true
        if selection.location { locationManager.startUpdatingLocation() }
        if selection.movement && CMMotionActivityManager.isActivityAvailable() {
            activityManager.startActivityUpdates(to: .main) { [weak self] activity in
                guard let self, let activity else { return }
                if activity.walking { self.movementState = "walking" }
                else if activity.running { self.movementState = "running" }
                else if activity.stationary { self.movementState = "still" }
                else { self.movementState = "unknown" }
            }
        }
        await publishLatest()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.publishLatest() }
        }
    }

    func stopSharing() async throws {
        timer?.invalidate()
        timer = nil
        locationManager.stopUpdatingLocation()
        activityManager.stopActivityUpdates()
        isSharing = false
        latestLocation = nil
        try await setRemoteSharing(false)
        tokenProvider = nil
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        latestLocation = locations.last
        guard isSharing else { return }
        Task { await publishLatest() }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // Keep the last valid fix in memory; the dashboard marks it stale by age.
    }

    private func quantity(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit) async -> Double? {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { return nil }
        return await withCheckedContinuation { continuation in
            let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
            // Do not relabel an old HealthKit sample as a fresh live reading.
            let recent = Date().addingTimeInterval(-120)
            let predicate = HKQuery.predicateForSamples(withStart: recent, end: Date(), options: .strictStartDate)
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: 1, sortDescriptors: [sort]) { _, samples, _ in
                guard let sample = samples?.first as? HKQuantitySample else { continuation.resume(returning: nil); return }
                continuation.resume(returning: sample.quantity.doubleValue(for: unit))
            }
            healthStore.execute(query)
        }
    }

    private func todayStepCount() async -> Int? {
        guard let type = HKObjectType.quantityType(forIdentifier: .stepCount) else { return nil }
        let start = Calendar.current.startOfDay(for: Date())
        let predicate = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)
        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, stats, _ in
                guard let quantity = stats?.sumQuantity() else { continuation.resume(returning: nil); return }
                continuation.resume(returning: Int(quantity.doubleValue(for: .count())))
            }
            healthStore.execute(query)
        }
    }

    private func publishLatest() async {
        guard isSharing, let tokenProvider else { return }
        var payload: [String: Any] = ["collectedAt": ISO8601DateFormatter().string(from: Date())]
        if selection.location, let loc = latestLocation {
            payload["location"] = ["latitude": loc.coordinate.latitude, "longitude": loc.coordinate.longitude, "accuracy": loc.horizontalAccuracy]
        }
        if selection.heartRate, let bpm = await quantity(.heartRate, unit: HKUnit.count().unitDivided(by: .minute())) {
            payload["heartRate"] = Int(bpm.rounded())
        }
        if selection.oxygenSaturation, let oxygen = await quantity(.oxygenSaturation, unit: .percent()) {
            payload["spo2"] = (oxygen * 100).rounded(toPlaces: 1)
        }
        if selection.dailySteps, let steps = await todayStepCount() { payload["stepCount"] = steps }
        if selection.movement { payload["movement"] = movementState }
        guard payload.count > 1 else { return }
        do {
            var request = URLRequest(url: apiBase.appending(path: "/v1/circles/\(circleId)/readings"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer \(try await tokenProvider())", forHTTPHeaderField: "Authorization")
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            request.timeoutInterval = 10
            let (_, response) = try await URLSession.shared.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return }
        } catch {
            // Do not persist or queue readings after network failure.
        }
    }

    private func setRemoteSharing(_ enabled: Bool) async throws {
        guard let tokenProvider else { throw BridgeError.message("Sign in to the AURA AWS circle first.") }
        var request = URLRequest(url: apiBase.appending(path: "/v1/circles/\(circleId)/sharing"))
        request.httpMethod = enabled ? "POST" : "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(try await tokenProvider())", forHTTPHeaderField: "Authorization")
        if enabled {
            var fields: [String] = []
            if selection.location { fields.append("location") }
            if selection.heartRate { fields.append("heartRate") }
            if selection.oxygenSaturation { fields.append("spo2") }
            if selection.dailySteps { fields.append("stepCount") }
            if selection.movement { fields.append("movement") }
            let body: [String: Any] = ["consent": true, "fields": fields]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let status = (response as? HTTPURLResponse)?.statusCode, (200..<300).contains(status) else {
            throw BridgeError.message("AWS could not start or stop the circle. Check guardian approval and sign-in.")
        }
    }

    enum BridgeError: Error, LocalizedError {
        case message(String)
        var errorDescription: String? { if case let .message(text) = self { return text }; return nil }
    }
}

private extension Double {
    func rounded(toPlaces places: Int) -> Double {
        let factor = pow(10, Double(places))
        return (self * factor).rounded() / factor
    }
}
