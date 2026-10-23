# AURA — Accessible Companion

AURA is a voice-first visual prototype companion for people with low vision or visually impaired. The assistant and guardian preview run locally on the laptop. This no-AWS setup does not share health or location data with contacts on other devices.

## Hackathon track fit

- **Primary track:** Alexa+ simulated experience. The official rules allow a web app built with the entrant's choice of AI or agentic tools; no Echo device or MCP surface is required for this alternate path. The source code and demo must clearly show the simulation working.
- **What AURA demonstrates:** intent routing between a camera-vision request and a supportive conversation, short spoken answers, and voice interaction in supported languages. The camera frame is sent only for requests routed to visual assistance.
- **Not claimed:** Bee track (AURA has no Bee device or Bee software), Fire TV track, Ring track, or Open Source mini challenge.
- The AWS guardian feature is a deployable starter stack, not a deployed service or a claim of AWS challenge eligibility. It is not Bee data and does not qualify for the Bee track.

Read [`SUBMISSION.md`](SUBMISSION.md) for the copy-ready project description and checklist, and [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for a time-coded recording plan. See [`HACKATHON_PLAN.md`](HACKATHON_PLAN.md) for the Amazon track fit and submission strategy. Check the live [official rules](https://amazonappdev2026.devpost.com/rules) before submitting.

## Start AURA

Install the local voice dependencies once (the Whisper model is downloaded on first voice use):

```sh
python3 -m pip install -r requirements.txt
ollama pull qwen2.5vl:3b
```

Then open Terminal and run:

```sh
cd /path/to/aura-final
PORT=8006 python3 server.py
```

Keep Terminal open, then open <http://localhost:8006>. AURA defaults to `qwen2.5vl:3b`. It connects to Ollama if it is already running, or starts the installed Ollama service itself, then warms the model before reporting that vision is ready. The model stays resident for 30 minutes. If Ollama is missing or unavailable, AURA tries its local runner. Whisper loads only when voice is first used so it does not compete with vision for shared memory. The optional larger `qwen3-vl:4b` can be selected manually with `AURA_MODEL_NAME=qwen3-vl:4b`, but may respond more slowly. Response time depends on laptop memory, model, and image; a one-second description cannot be guaranteed.

## Voice and languages

Choose **Auto-detect speech** to detect the language separately for each spoken turn, or select English, Kannada, Telugu, Hindi, Tamil, Malayalam, Bengali, Marathi, Gujarati, Punjabi, or Urdu. A selected language is a lock: choosing Hindi makes AURA answer in Hindi even if the next utterance is Tamil. Use Auto-detect if you will switch languages. For more reliable Kannada, Hindi, Telugu, and Tamil recognition, choose the language before speaking; automatic detection is best-effort, especially with short or mixed-language phrases. If you switch languages each turn, use Auto-detect. Local Whisper transcribes on this laptop. AURA selects the matching macOS/browser speech voice (including macOS locale tags written with underscores); choose **Preview** to confirm the voice available on this laptop.

Tap **Enable AURA once** and grant the browser microphone and camera permissions. The app then keeps listening for **“Sam”** while the page is open, automatically sends the transcript to the local model, speaks the reply, and resumes listening; there is no stop or send step in normal use. If you previously enabled it, it tries to resume automatically on later visits. Use **Pause microphone** only when you want privacy. Camera access is requested during the same one-time setup. Keep the page visible and the server running.

If speech says **“Failed to fetch”**, reload AURA from http://localhost:8006 while server.py is still running in Terminal. Do not open index.html as a file or use an old tab on another port. The app retries a local request once and now gives a specific server-address error. For a local diagnostic, open <http://localhost:8006/api/health>; speech: "not_loaded" is normal until the first speech request, while speechError shows a local transcription setup failure.

## Camera and object recognition

Start AURA hands-free once and say **“Sam, find my keys”** or **“Sam, where are my earbuds?”** You do not need to type into the optional Find an item field. AURA turns on the camera during hands-free setup, checks the live frame, speaks its answer, and remembers the target for **“Sam, look again.”** You can also use **Describe view** or type a specific question such as “Are these earbuds or a remote?” AURA keeps recent frames in memory, but sends a frame to the local vision model only when the agent routes a request to visual assistance. The answer describes visible objects and positions in the frame. The finder reports only frame position and visible clues; it does not claim exact distance or track objects outside the camera view. It will not provide a person's identity, a precise 50-metre distance, or thermal/heat information: this laptop camera is an ordinary RGB camera with no calibrated depth or thermal sensor. Small local models can still mistake objects. If an object is tiny or blurry, move it closer, keep it centered, and ask again; do not treat an uncertain answer as proof.

## Heart-rate and SOS demo

Use **Run heart-rate + SOS demo** to show the end-to-end alert screen without a watch. The displayed 76 → 42 BPM values are generated demo data, not measurements. **Add my location** asks the browser for permission and keeps the resulting coordinates on this page; nothing is transmitted. Do not include precise personal coordinates in a public video.

### Nearby Bluetooth devices

**Connect a BLE sensor** can read heart rate, SpO₂, and running cadence only when a nearby device exposes the corresponding standard Bluetooth LE service and the browser supports Web Bluetooth. Many consumer watches expose data only inside their maker's phone app. The browser cannot read universal step totals from every watch.

### Local guardian preview (no AWS)

The **Local safety preview** asks for location permission and displays that location plus available live BLE readings on this device. Stop sharing clears the preview. No guardian account is connected and nothing is sent to another phone. A remote circle requires an online backend and user accounts; this run intentionally does not use AWS. The optional `aws-sharing/` and `guardian.html` files are not part of the no-AWS flow.

The preview is not an emergency-response system: it does not diagnose a heart attack, detect breathlessness, send an SOS, text emergency services, or dispatch an ambulance.

### Apple Watch path

Apple Watch health data is read by an iPhone app through HealthKit; a web page cannot directly read the watch's HealthKit store. [`ios/AURAHealthBridge/HealthLocationBridge.swift`](ios/AURAHealthBridge/HealthLocationBridge.swift) is an optional native iOS bridge starter, not connected in this no-AWS run. It needs an Xcode host app, HealthKit capability and privacy strings, location permission, sign-in, and a remote backend before it can share data with guardians. Setup notes are in [`ios/README.md`](ios/README.md).

## Privacy and companion behavior

Microphone audio is posted to the local server for local transcription and is not intentionally written to disk. Camera frames are sent to the local Ollama model on this laptop only when a visual request is made. Video is not saved as a recording. AURA responds in a warm, supportive way and can suggest coping steps. It does not diagnose or replace a qualified professional or emergency service.

## Project limitations

AURA needs Ollama and a compatible local vision model for its local AI path. Browser camera, microphone, and Bluetooth permissions depend on browser support. The Alexa+ experience is a web simulation and does not connect to Alexa+ or an Echo. The current no-AWS build keeps guardian readings on this device; remote guardian connections require a deployed backend.
