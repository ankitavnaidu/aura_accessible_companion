# Devpost submission notes — AURA

## Track selection

Select **Alexa+** and describe this as the permitted **web simulation** path. Do not select Bee, AWS Builder, Fire TV, Ring, or Open Source unless AURA is actually updated to use those track requirements. The current Bluetooth heart-rate feature is not Bee data. No live Alexa+ service or Echo integration is implemented.

## Copy-ready project description

**AURA is a voice-first visual companion designed to make everyday surroundings easier to explore for people with low vision. In this Alexa+ web simulation, AURA routes a spoken or typed request to the capability it needs: a local camera-vision model for questions about the scene, a guided target-item search that can be started hands-free with “Sam, find my keys” and remembers the target across a spoken scan follow-up, or a supportive conversation flow for other requests. It returns a brief spoken answer and can listen for the wake word “Sam” while the page remains open.**

**The camera feed stays in the browser. AURA sends one recent frame to the local vision model only when a request needs visual context; speech recognition and the vision model run on the laptop. The prototype supports English and several Indian languages, with language selection or best-effort Whisper auto-detection. The Find an item flow retains the requested target for a later scan command during the same page session.**

**The heart-rate + SOS walkthrough is a clearly labeled UI simulation; it does not contact guardians, emergency services, or ambulances. AURA is not a medical product or emergency service. The Alexa+ experience is a web simulation, not a live Alexa+ integration, and does not require an Echo or Bee device. The laptop's ordinary RGB camera cannot provide thermal readings or reliable exact distances, so AURA describes visible frame positions and should communicate uncertainty instead of presenting guesses as facts.**

## Built with

- Python standard-library HTTP server
- Ollama with Qwen2.5-VL for local vision and conversation
- Local Whisper speech recognition
- Browser camera, Web Audio, and speech synthesis APIs
- HTML, CSS, and JavaScript

## Demo outline (2:40; keep under 3:00)

Use the complete time-coded narration and recording checklist in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

1. **0:00–0:20 — Problem:** introduce AURA and the low-vision use case. State that this is the Alexa+ web simulation path.
2. **0:20–0:55 — Scene description:** ask AURA what is in view and let the real spoken answer finish.
3. **0:55–1:40 — Hands-free search:** say “Sam, find my keys,” move the camera, then say “Sam, look again.” Show the real spoken answer and target memory without typing.
4. **1:40–2:00 — Companion:** ask one conversational question and let its spoken answer finish.
5. **2:00–2:25 — Privacy and limits:** explain local processing and the limits of an ordinary camera and small local model.
6. **2:25–2:40 — Close:** restate the low-vision problem and that this entry is an Alexa+ web simulation, not a live integration.

Record the real visual and conversation workflows working. Upload a publicly viewable video under three minutes to YouTube or Vimeo and use footage/music only when you have permission.

## Product feedback draft

Edit this to match what you actually experienced before submitting.

- **Tools used and purpose:** Ollama/Qwen2.5-VL for on-device visual and conversational answers; Whisper for local voice transcription; browser camera/audio/speech APIs for the interaction; Python's standard-library HTTP server for the local bridge.
- **What worked well:** local inference avoids requiring an AURA cloud API key; the camera, voice input, and spoken response fit a hands-free accessibility flow.
- **What needs work:** local-model latency and recognition quality vary with laptop hardware, camera framing, language, and installed voices. Browser microphone/camera permissions and Bluetooth support vary across browsers.
- **Onboarding:** document the actual Ollama setup and model pull command you used; note any setup friction you encountered.
- **Would you build with these again?:** answer from your real experience after preparing and recording the demo.

## Submission checklist

- [ ] Join/register on the official Devpost page and select the Alexa+ track.
- [ ] Publish the repository to GitHub, or keep it private and share it with the reviewers listed in the rules.
- [ ] If public, keep the included MIT `LICENSE` at the repository root and make it visible in GitHub's About section.
- [ ] Confirm the repository contains all setup instructions and required source files; do not commit local model caches, API keys, or private data.
- [ ] Add the short demo video URL and make the video publicly viewable.
- [ ] Fill the required product feedback with accurate, first-hand notes.
- [ ] Describe AURA as a simulation. Do not claim a working Alexa+ integration, Bee use, AWS use, or health diagnosis.
