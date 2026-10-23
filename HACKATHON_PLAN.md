# AURA hackathon plan

AURA cannot guarantee a win. This plan aligns the working demo with published judging requirements and avoids claiming integrations or health capabilities that are not implemented.

## Amazon Developer Hackathon — Alexa+ track

Use the **Alexa+ simulated experience** path. Keep the app visibly labeled as a simulation; it is not an Alexa+ or Echo integration. Do not enter the Bee track: this build has no Bee data source. The repository now includes an AWS guardian-sharing stack, but it is only source code until deployed to an AWS account, configured, and demonstrated with consenting accounts. Do not claim a live AWS integration before that has happened.

For judging, show one complete workflow: enable voice → ask AURA to find a named object → move the camera → say “look again” → hear a position-based answer. Follow with one supportive companion turn. Keep the public English video under three minutes, include the runnable source repository and setup steps, and complete the required product feedback. Explain which capabilities were significantly added during the submission period.

## PES University — likely match: Kodikon 6.0 HMI

**Proposed problem statement:** How might a person with low vision locate a familiar everyday object and orient toward it through short spoken interactions, without needing to read a screen or send continuous video to a cloud service?

AURA fits **Human-Machine Interfaces (HMI)**: it supports spoken requests, a live camera, a local vision model, target memory for “look again,” spoken answers, and uncertainty-aware scan guidance. Lead with the hands-free named-item scan loop; keep the heartbeat card out of the primary story because it is simulated.

The official Kodikon page lists exactly four undergraduate engineering team members, idea submissions closing October 25, and an in-person finale on October 31–November 1. Confirm the prompt and team eligibility before submitting. This code is a prototype, not a certified assistive device.

**Evaluation to run before presenting:** prepare 10 common objects and 20 camera views; record whether the voice command was transcribed correctly, whether the target was detected correctly or uncertainty was stated, end-to-end response time, and whether the user can complete the task without touching the screen after setup. Report the actual results and laptop/model used; do not invent accuracy or latency claims. Keep a short failure log and use it to improve the demo.

If “PES AI Hackathon” means Hashcode 14.0 instead, its official page describes paper-led tracks and says the registration deadline was October 19; the event is October 24–25 with 2–3 members per team. That is a different fit from Kodikon HMI, so check that your team is already registered and identify the chosen paper and contribution.

## Demo integrity

- Do not describe a simulated heart rate as a sensor reading, or say an SOS reached a guardian or ambulance.
- Do not claim a scene model can identify every object, exact distance, people, or thermal information.
- Show transcript evidence and select a language manually for the demo; local model and speech quality vary by language and installed voice.
- Use a public, non-sensitive camera scene. Avoid filming private papers or precise home location.

## Official references

- [Amazon Developer Hackathon rules](https://amazonappdev2026.devpost.com/rules)
- [Amazon Developer Hackathon FAQ](https://amazonappdev2026.devpost.com/details/faqs)
- [PES Kodikon 6.0](https://www.embrionepes.in/kodikon-6)
- [PES Hashcode 14.0](https://hashcode.theinnovationlab.in/)
