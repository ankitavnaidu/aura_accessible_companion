# AURA — PES hackathon pitch

## Proposed problem statement

How might a person with low vision find a familiar everyday object and orient toward it using short spoken interactions, without needing to read a screen or send continuous video to a cloud service?

## One-line solution

AURA is a voice-first visual companion: say “Sam, find my keys,” hear a brief description of where the object appears in the camera frame, move the camera, then ask “Sam, look again.”

## What the prototype demonstrates

- Hands-free interaction after one-time microphone and camera permission.
- Local speech transcription and a local vision model, with a single recent frame sent only for a visual request.
- A named-item search flow that keeps the target for a follow-up scan.
- Spoken output and best-effort support for English, Kannada, Telugu, Hindi, and Tamil.
- Uncertainty-aware wording: if the object is unclear, AURA asks the person to scan again instead of inventing a distance.

## 60-second pitch

“Finding something ordinary, like keys or earbuds, can be frustrating when you cannot rely on a screen. AURA is a voice-first visual companion built around that small but frequent task. After one-time setup, a person can say, ‘Sam, find my keys.’ AURA checks a recent camera frame locally, speaks where the item appears, and remembers the target for ‘look again’ as the person scans. The camera does not provide exact distance or heat, so AURA avoids those claims and asks for another scan when it is unsure. Our prototype focuses on a complete, hands-free interaction rather than a mockup. We are measuring speech transcription, item-location correctness, response time, and whether the task can be completed without touching the screen.”

## Evaluation worksheet — fill with real results

Use a fixed set of everyday objects and camera positions. Record the laptop model, Ollama model and version, speech model, browser, and whether the language was manually selected. Run each scenario more than once and report both successes and failures.

| Measure | How to record it | Result |
| --- | --- | --- |
| Voice intent success | Correctly understood “find [item]” / total trials | Fill after testing |
| Object localization success | Correct visible item and frame region / visible-item trials | Fill after testing |
| Honest uncertainty | Correctly says it is unclear or absent / unclear-or-absent trials | Fill after testing |
| Response time | Seconds from end of utterance to first spoken response; report median and slowest | Fill after testing |
| Hands-free completion | Tasks completed without touching the screen after setup / total tasks | Fill after testing |
| Language success | Correct transcript and intelligible reply, counted separately by language | Fill after testing |

Do not claim clinical safety, certified accessibility, exact distance, universal language accuracy, or emergency dispatch. The heart-rate/SOS panel is a UI simulation and should not be part of the core impact claim.

## PES event fit

This pitch is best suited to the HMI track if the target event is Kodikon 6.0. Its official page lists HMI as a track, four undergraduate engineering members per team, proposals due October 25, 2026, and an in-person finale October 31–November 1. If the target is Hashcode 14.0, adapt the project to a listed research-paper track and clearly state the paper, contribution, baseline, and evaluation; its registration deadline is listed as October 19, 2026.

## Demo sequence

1. Enable AURA once and grant camera and microphone access.
2. Say “Sam, find my keys.”
3. Show the live frame and let the spoken answer finish.
4. Move the camera and say “Sam, look again.”
5. Say one short supportive companion prompt.
6. State plainly that the model can be wrong and that the heart/SOS screen is simulated.
