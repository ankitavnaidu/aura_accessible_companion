/* Cognito Hosted UI + consented AWS latest-reading sharing. No data is sent until the
   signed-in patient approves a guardian and explicitly starts selected data streams. */
(() => {
  const $ = (id) => document.getElementById(id);
  const cfg = window.AURA_REMOTE_CONFIG || {};
  const configured = /^https:\/\//.test(cfg.apiBase || "") && /^https:\/\//.test(cfg.cognitoDomain || "") && !!cfg.clientId;
  let accessToken = sessionStorage.getItem("aura.aws.accessToken") || "";
  let circleId = sessionStorage.getItem("aura.aws.circleId") || "";
  let role = "";
  let activeMembers = [];
  let shareTimer = null;
  let guardianPoll = null;
  let locationWatch = null;
  let currentLocation = null;
  let shareChoices = null;

  const status = (message, state = "") => {
    if ($("cloudStatus")) $("cloudStatus").textContent = message;
    if ($("cloudBadge")) {
      $("cloudBadge").textContent = state || (configured ? (accessToken ? "SIGNED IN" : "READY TO SIGN IN") : "NOT SET UP");
      $("cloudBadge").classList.toggle("cloudBadgeReady", Boolean(accessToken && configured));
    }
  };
  const visible = (id, show) => { if ($(id)) $(id).classList.toggle("hidden", !show); };
  const random = (length = 32) => {
    const bytes = crypto.getRandomValues(new Uint8Array(length));
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  };
  const base64url = (buffer) => btoa(String.fromCharCode(...new Uint8Array(buffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  const redirectUri = () => { const url = new URL(location.href); url.search = ""; url.hash = ""; return url.toString(); };
  async function login() {
    const verifier = random(48), stateValue = random(24);
    const challenge = base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
    sessionStorage.setItem("aura.aws.pkce", verifier);
    sessionStorage.setItem("aura.aws.state", stateValue);
    const url = new URL("/oauth2/authorize", cfg.cognitoDomain);
    url.search = new URLSearchParams({
      response_type: "code", client_id: cfg.clientId, redirect_uri: redirectUri(),
      scope: cfg.scope || "openid email profile", state: stateValue, code_challenge: challenge, code_challenge_method: "S256"
    });
    location.assign(url.toString());
  }
  async function handleCallback() {
    const query = new URLSearchParams(location.search), code = query.get("code");
    if (!code) return;
    const stateValue = query.get("state"), expectedState = sessionStorage.getItem("aura.aws.state");
    const verifier = sessionStorage.getItem("aura.aws.pkce");
    history.replaceState({}, document.title, location.pathname);
    sessionStorage.removeItem("aura.aws.state"); sessionStorage.removeItem("aura.aws.pkce");
    if (!stateValue || stateValue !== expectedState || !verifier) throw new Error("Sign-in validation failed. Please sign in again.");
    const form = new URLSearchParams({ grant_type: "authorization_code", client_id: cfg.clientId, code, redirect_uri: redirectUri(), code_verifier: verifier });
    const result = await fetch(new URL("/oauth2/token", cfg.cognitoDomain), { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: form });
    if (!result.ok) throw new Error("AWS sign-in could not be completed. Try signing in again.");
    const tokens = await result.json();
    if (!tokens.access_token) throw new Error("AWS did not return an access token.");
    accessToken = tokens.access_token;
    sessionStorage.setItem("aura.aws.accessToken", accessToken);
  }
  async function api(path, method = "GET", body = undefined) {
    if (!accessToken) throw new Error("Sign in before using the AWS circle.");
    const opts = { method, headers: { authorization: `Bearer ${accessToken}` } };
    if (body !== undefined) { opts.headers["content-type"] = "application/json"; opts.body = JSON.stringify(body); }
    const result = await fetch(`${cfg.apiBase.replace(/\/$/, "")}/v1${path}`, opts);
    let data = {};
    try { data = await result.json(); } catch (_) { /* no body */ }
    if (!result.ok) throw new Error(data.error || `AWS request failed (${result.status}).`);
    return data;
  }
  function addMemberRow(host, person) {
    const row = document.createElement("div"); row.className = "cloudMemberRow";
    const label = document.createElement("span"); label.textContent = `${person.email || "Verified account"} · ${person.role} · ${person.status}`; row.append(label);
    if (role === "patient" && person.role === "guardian" && person.status === "pending") {
      const approve = document.createElement("button"); approve.type = "button"; approve.className = "voiceTest"; approve.textContent = "Approve";
      approve.addEventListener("click", async () => { try { await api(`/circles/${encodeURIComponent(circleId)}/members/${encodeURIComponent(person.userId)}/approve`, "POST", {}); await refreshMembers(); } catch (e) { status(e.message, "ACTION NEEDED"); } });
      row.append(approve);
    }
    if (role === "patient" && person.role === "guardian" && person.status === "active") {
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "voiceTest"; remove.textContent = "Remove access";
      remove.addEventListener("click", async () => { try { await api(`/circles/${encodeURIComponent(circleId)}/members/${encodeURIComponent(person.userId)}`, "DELETE"); await refreshMembers(); status("Guardian access removed.", "ACCESS REMOVED"); } catch (e) { status(e.message, "ACTION NEEDED"); } });
      row.append(remove);
    }
    host.append(row);
  }
  async function refreshCircles() {
    const data = await api("/circles");
    let circles = data.circles || [];
    if (circleId && !circles.some((c) => c.circleId === circleId)) circleId = "";
    if (!circleId && circles.length) circleId = circles[0].circleId;
    if (circleId) sessionStorage.setItem("aura.aws.circleId", circleId); else sessionStorage.removeItem("aura.aws.circleId");
    const current = circles.find((c) => c.circleId === circleId);
    role = current?.role || "";
    visible("cloudCreateCircle", !current);
    visible("cloudMakeInvite", role === "patient");
    visible("cloudRefresh", Boolean(current));
    visible("cloudJoinLabel", true);
    visible("cloudJoin", true);
    visible("cloudConsentBox", role === "patient");
    visible("cloudLogout", true);
    if (!current) status("You are signed in. Create a patient circle or enter a one-time invite code.");
    else if (current.status === "pending") status("Your guardian request is waiting for the patient to approve your verified account.", "PENDING APPROVAL");
    else if (role === "guardian") status("Connected to the circle. Readings are visible only while the patient has sharing turned on.", "GUARDIAN CONNECTED");
    else status("Your patient circle is ready. Create an invite, review each guardian email, then choose the data fields to share.", "PATIENT CIRCLE");
    if (current && (role === "patient" || current.status === "active")) await refreshMembers();
    if (role === "guardian" && current?.status === "active") { visible("cloudLive", true); await refreshLatest(); guardianPoll ||= setInterval(() => void refreshLatest(), 5000); }
    else { visible("cloudLive", false); clearInterval(guardianPoll); guardianPoll = null; }
  }
  async function refreshMembers() {
    if (!circleId) return;
    const data = await api(`/circles/${encodeURIComponent(circleId)}/members`);
    const host = $("cloudMembers"); if (!host) return; host.replaceChildren(); activeMembers = [];
    for (const person of data.members || []) { addMemberRow(host, person); if (person.role === "guardian" && person.status === "active") activeMembers.push(person); }
    if (!host.childElementCount) host.textContent = "No contacts have joined this circle yet.";
  }
  async function refreshLatest() {
    if (!circleId || role !== "guardian") return;
    try {
      const data = await api(`/circles/${encodeURIComponent(circleId)}/latest`);
      const host = $("cloudLive"); if (!host) return; host.replaceChildren();
      if (!data.sharing) { host.textContent = "The patient has stopped sharing. No live reading is available."; return; }
      if (!data.reading) { host.textContent = "Sharing is on; waiting for a fresh sensor or location reading."; return; }
      const r = data.reading;
      const title = document.createElement("strong"); title.textContent = data.stale ? "Last update is stale" : "Live circle reading"; host.append(title);
      const details = document.createElement("p");
      const fields = [r.heartRate != null && `Heart rate ${r.heartRate} BPM`, r.spo2 != null && `SpO₂ ${r.spo2}%`, r.stepCount != null && `${r.stepCount} steps`, r.cadence != null && `Cadence ${r.cadence}/min`, r.movement && `Movement ${r.movement}`, r.location && `Location ${r.location.latitude.toFixed(5)}, ${r.location.longitude.toFixed(5)} (±${Math.round(r.location.accuracy)} m)`].filter(Boolean);
      details.textContent = fields.length ? fields.join(" · ") : "No selected values in this update."; host.append(details);
      const stamp = document.createElement("small"); stamp.textContent = `Collected ${new Date(r.collectedAt).toLocaleString()}`; host.append(stamp);
    } catch (e) { status(e.message, "RECONNECTING"); }
  }
  function getChoices() {
    return { location: $("shareLocation")?.checked, heartRate: $("shareHeart")?.checked, spo2: $("shareSpo2")?.checked, stepCount: $("shareSteps")?.checked, movement: $("shareMovement")?.checked };
  }
  function firstLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) { reject(new Error("This browser cannot provide location.")); return; }
      navigator.geolocation.getCurrentPosition((pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy }), (err) => reject(new Error(err.code === 1 ? "Location permission was denied." : "Could not read the current location.")), { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 });
    });
  }
  async function uploadLatest() {
    if (!circleId || role !== "patient" || !shareChoices) return;
    const sensors = window.AURA_SENSOR_BRIDGE?.snapshot?.() || {};
    const body = { collectedAt: new Date().toISOString() };
    if (shareChoices.location && currentLocation) body.location = currentLocation;
    if (shareChoices.heartRate && sensors.heartRate != null) body.heartRate = sensors.heartRate;
    if (shareChoices.spo2 && sensors.spo2 != null) body.spo2 = sensors.spo2;
    if (shareChoices.stepCount && sensors.stepCount != null) body.stepCount = sensors.stepCount;
    if (shareChoices.movement) {
      if (sensors.cadence != null) body.cadence = sensors.cadence;
      if (sensors.movement) body.movement = sensors.movement;
    }
    if (Object.keys(body).length === 1) { status("Sharing is on, but no selected live sensor/location reading is available yet.", "WAITING FOR DATA"); return; }
    try { await api(`/circles/${encodeURIComponent(circleId)}/readings`, "POST", body); status("Selected live values are securely updating the approved circle.", "SHARING LIVE"); }
    catch (e) { status(e.message, "UPLOAD PAUSED"); }
  }
  async function startSharing() {
    if (!circleId || role !== "patient") throw new Error("Sign in as the patient who owns a circle.");
    if (!activeMembers.length) throw new Error("Approve the intended guardian’s verified email first.");
    shareChoices = getChoices();
    if (!Object.values(shareChoices).some(Boolean)) throw new Error("Select at least one data type to share.");
    currentLocation = shareChoices.location ? await firstLocation() : null;
    const fields = [];
    if (shareChoices.location) fields.push("location");
    if (shareChoices.heartRate) fields.push("heartRate");
    if (shareChoices.spo2) fields.push("spo2");
    if (shareChoices.stepCount) fields.push("stepCount");
    if (shareChoices.movement) fields.push("cadence", "movement");
    await api(`/circles/${encodeURIComponent(circleId)}/sharing`, "POST", { consent: true, fields });
    if (shareChoices.location && navigator.geolocation) locationWatch = navigator.geolocation.watchPosition((pos) => { currentLocation = { latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy }; void uploadLatest(); }, () => status("Location updates paused. Check browser location permission.", "LOCATION PAUSED"), { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
    visible("cloudStartShare", false); visible("cloudStopShare", true);
    await uploadLatest(); shareTimer = setInterval(() => void uploadLatest(), 5000);
  }
  async function stopSharing() {
    clearInterval(shareTimer); shareTimer = null;
    if (locationWatch !== null) navigator.geolocation.clearWatch(locationWatch);
    locationWatch = null; currentLocation = null; shareChoices = null;
    await api(`/circles/${encodeURIComponent(circleId)}/sharing`, "DELETE");
    visible("cloudStartShare", true); visible("cloudStopShare", false);
    status("Remote sharing stopped. The latest reading was deleted.", "SHARING OFF");
  }
  async function run(action) { try { await action(); } catch (e) { status(e.message, "ACTION NEEDED"); } }

  if (!configured) { status("AWS is not deployed/configured yet. The local preview works, but no remote guardian can connect.", "NOT SET UP"); $("cloudLogin")?.setAttribute("disabled", "disabled"); return; }
  $("cloudLogin")?.removeAttribute("disabled");
  $("cloudLogin")?.addEventListener("click", () => void run(login));
  $("cloudCreateCircle")?.addEventListener("click", () => void run(async () => { const data = await api("/circles", "POST", {}); circleId = data.circleId; sessionStorage.setItem("aura.aws.circleId", circleId); await refreshCircles(); }));
  $("cloudMakeInvite")?.addEventListener("click", () => void run(async () => { const data = await api(`/circles/${encodeURIComponent(circleId)}/invites`, "POST", {}); const box = $("cloudInviteResult"); box.replaceChildren(); const line = document.createElement("p"); line.textContent = `One-time code (expires in 24 hours): ${data.inviteCode}. Give this only to the intended person; it is not sent automatically.`; box.append(line); visible("cloudInviteResult", true); }));
  $("cloudJoin")?.addEventListener("click", () => void run(async () => { const inviteCode = $("cloudInviteInput").value.trim(); const data = await api("/invites/accept", "POST", { inviteCode }); circleId = data.circleId; sessionStorage.setItem("aura.aws.circleId", circleId); await refreshCircles(); status(data.message, "PENDING APPROVAL"); }));
  $("cloudRefresh")?.addEventListener("click", () => void run(refreshCircles));
  $("cloudStartShare")?.addEventListener("click", () => void run(startSharing));
  $("cloudStopShare")?.addEventListener("click", () => void run(stopSharing));
  $("cloudLogout")?.addEventListener("click", () => {
    sessionStorage.removeItem("aura.aws.accessToken"); sessionStorage.removeItem("aura.aws.circleId"); accessToken = ""; circleId = "";
    const url = new URL("/logout", cfg.cognitoDomain); url.search = new URLSearchParams({ client_id: cfg.clientId, logout_uri: redirectUri() }); location.assign(url.toString());
  });
  void (async () => {
    try { await handleCallback(); if (!accessToken) { status("AWS service configured. Sign in to create or join a guardian circle."); return; } visible("cloudLogin", false); await refreshCircles(); }
    catch (e) { status(e.message, "SIGN-IN NEEDED"); }
  })();
})();
