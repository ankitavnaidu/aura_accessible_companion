# AURA — a voice-first visual companion

AURA is a voice-first visual companion for people who are blind or have low vision. Ask what is around you or say “Sam, find my keys,” move the camera as AURA guides the search, and ask “Sam, look again.” The prototype is designed around hands-free interaction and local processing on a laptop.

## What the demo shows

- **Ask about a live view:** request a concise description or ask a specific question about visible objects.
- **Search by voice:** name an item, hear where it appears in the camera frame, then scan again while AURA remembers the target.
- **Talk naturally:** start hands-free listening once; AURA transcribes, responds, speaks, and resumes listening.
- **Choose a language:** Whisper provides local transcription, with language selection or best-effort auto-detection. Available spoken voices depend on the computer.
- **Keep camera and speech local:** the local server sends a frame to the local vision model only for a visual request. Video is not saved as a recording.

## Amazon hackathon direction

AURA is presented as a web-based **Alexa+ simulated experience**: a voice-first assistant workflow built for the browser. It is a prototype and does not connect to an Echo device or the Alexa service. Check the [official hackathon rules](https://amazonappdev2026.devpost.com/rules) and make sure the submitted demo matches the current requirements.

See [`SUBMISSION.md`](SUBMISSION.md) for copy-ready submission details, [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for a timed video outline, and [`HACKATHON_PLAN.md`](HACKATHON_PLAN.md) for the project’s judging story.

## Run AURA

You need Python 3, [Ollama](https://ollama.com/), and a compatible local vision model. The first voice request downloads/loads the local Whisper model.

```sh
python3 -m pip install -r requirements.txt
ollama pull qwen2.5vl:3b
cd /path/to/aura-final
PORT=8006 python3 server.py
```

Keep Terminal open and visit <http://localhost:8006>. Grant the browser microphone and camera permissions, then select **Enable AURA once**. While the page remains open, say **“Sam”** to start a request. Use **Pause microphone** whenever you want to stop listening. For a local server check, visit <http://localhost:8006/api/health>.

The default vision model is `qwen2.5vl:3b`. A larger `qwen3-vl:4b` can be selected with `AURA_MODEL_NAME=qwen3-vl:4b`, but may run more slowly. Response speed and recognition quality depend on the laptop, model, camera view, microphone, and chosen language. For language switching, choose **Auto-detect speech**; for a single-language demo, select that language before speaking.

## Heart-rate and guardian prototype

The interface includes a heart-rate/SOS demonstration card and a local safety preview. The heart-rate values in the demo are generated examples. A browser can read live measurements only from a nearby Bluetooth LE device that exposes a supported standard service; watch compatibility varies.

The local preview can show permitted location and compatible sensor readings on the same device. It does not send live data to guardian phones. The `aws-sharing/` backend and `ios/AURAHealthBridge/` HealthKit bridge are starter code for future integration; neither is deployed or connected in this demo. The prototype does not diagnose a medical event or contact emergency services.

## Privacy and responsible use

Microphone audio is sent to AURA’s local server for transcription. AURA processes visual requests with the local vision model, and does not save video recordings. The camera is an ordinary RGB camera: AURA can describe visible clues and approximate frame position, but cannot provide calibrated distance, identify a person, or detect heat. Local vision models can make mistakes, so confirm important observations directly.

AURA is a supportive companion prototype, not a therapist, medical device, or emergency service.
