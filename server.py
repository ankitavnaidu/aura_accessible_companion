"""Local web server and Ollama bridge for AURA."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import time
import threading
import wave
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
MODEL_PORT = int(os.environ.get("AURA_MODEL_PORT", "11436"))
MODEL_API_URL = os.environ.get("AURA_MODEL_URL", f"http://127.0.0.1:{MODEL_PORT}/v1/chat/completions")
OLLAMA_API_URL = os.environ.get("AURA_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL_NAME = os.environ.get("AURA_MODEL_NAME", "qwen2.5vl:3b")
MODEL_CONTEXT = int(os.environ.get("AURA_MODEL_CONTEXT", "1024"))
MODEL_BACKEND = "openai"
MODEL_PROCESS = None
OLLAMA_PROCESS = None
MAX_BODY = 10 * 1024 * 1024
ASR_MODEL_NAME = os.environ.get("AURA_ASR_MODEL", "openai/whisper-small")
ASR_LOCK = threading.Lock()
ASR_PROCESSOR = None
ASR_MODEL = None
ASR_DEVICE = "cpu"
ASR_LAST_ERROR = ""
MODEL_READY = threading.Event()
MODEL_STARTUP_ERROR = None

ASR_LANGUAGES = {
    "en-US": "english", "kn-IN": "kannada", "te-IN": "telugu", "hi-IN": "hindi",
    "ta-IN": "tamil", "ml-IN": "malayalam", "bn-IN": "bengali", "mr-IN": "marathi",
    "gu-IN": "gujarati", "pa-IN": "punjabi", "ur-IN": "urdu",
}
LANGUAGE_FAILURES = {
    "kn-IN": "ಕ್ಷಮಿಸು, ಈ ಉತ್ತರವನ್ನು ಕನ್ನಡದಲ್ಲಿ ಖಚಿತವಾಗಿ ಹೇಳಲು ಆಗಲಿಲ್ಲ. ವಸ್ತುವನ್ನು ಹತ್ತಿರ ಹಿಡಿದು ಮತ್ತೊಮ್ಮೆ ನೋಡೋಣ.",
    "te-IN": "క్షమించు, ఈ సమాధానాన్ని తెలుగులో ఖచ్చితంగా చెప్పలేకపోయాను. వస్తువును దగ్గరగా చూపించి మళ్లీ ప్రయత్నిద్దాం.",
    "hi-IN": "माफ़ करना, मैं इसका जवाब हिंदी में भरोसे से नहीं दे पाई। वस्तु को कैमरे के पास दिखाकर फिर कोशिश करें।",
    "ta-IN": "மன்னிக்கவும், இதற்கு தமிழில் உறுதியாகப் பதிலளிக்க முடியவில்லை. பொருளை அருகில் காட்டி மீண்டும் முயற்சிக்கவும்.",
    "ml-IN": "ക്ഷമിക്കണം, ഇതിന് മലയാളത്തിൽ ഉറപ്പോടെ മറുപടി പറയാൻ കഴിഞ്ഞില്ല. വസ്തു അടുത്ത് കാണിച്ച് വീണ്ടും ശ്രമിക്കൂ.",
    "bn-IN": "দুঃখিত, বাংলায় নিশ্চিতভাবে উত্তর দিতে পারলাম না। জিনিসটি ক্যামেরার কাছে এনে আবার চেষ্টা করুন।",
    "mr-IN": "माफ करा, याचे मराठीत खात्रीने उत्तर देता आले नाही. वस्तू कॅमेऱ्याजवळ दाखवून पुन्हा प्रयत्न करा.",
    "gu-IN": "માફ કરશો, આનો ગુજરાતીમાં ચોક્કસ જવાબ આપી શકી નથી. વસ્તુને કેમેરા પાસે બતાવીને ફરી પ્રયત્ન કરો.",
    "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਇਸਦਾ ਪੰਜਾਬੀ ਵਿੱਚ ਪੱਕਾ ਜਵਾਬ ਨਹੀਂ ਦੇ ਸਕੀ। ਚੀਜ਼ ਕੈਮਰੇ ਦੇ ਨੇੜੇ ਦਿਖਾ ਕੇ ਫਿਰ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
    "ur-IN": "معاف کرنا، میں اس کا اردو میں پکا جواب نہیں دے سکی۔ چیز کو کیمرے کے قریب دکھا کر دوبارہ کوشش کریں۔",
}
CONVERSATION_LANGUAGE_FAILURES = {
    "kn-IN": "ಕ್ಷಮಿಸು, ನಿನ್ನ ಮಾತಿಗೆ ಸರಿಯಾಗಿ ಉತ್ತರಿಸಲು ಆಗಲಿಲ್ಲ. ಇನ್ನೊಮ್ಮೆ ಸರಳವಾಗಿ ಹೇಳುತ್ತೀಯಾ? ನಾನು ಕೇಳುತ್ತಿದ್ದೇನೆ.",
    "te-IN": "క్షమించు, నీ మాటకు సరిగ్గా సమాధానం ఇవ్వలేకపోయాను. ఇంకోసారి సులభంగా చెబుతావా? నేను వింటున్నాను.",
    "hi-IN": "माफ़ करना, मैं ठीक से जवाब नहीं दे पाई। क्या तुम एक बार फिर, थोड़ा सरल तरीके से कहोगी? मैं सुन रही हूँ।",
    "ta-IN": "மன்னிக்கவும், சரியாகப் பதிலளிக்க முடியவில்லை. இன்னொரு முறை எளிமையாகச் சொல்வீர்களா? நான் கேட்கிறேன்.",
    "ml-IN": "ക്ഷമിക്കണം, ശരിയായി മറുപടി നൽകാനായില്ല. ഒന്ന് കൂടി ലളിതമായി പറയാമോ? ഞാൻ കേൾക്കുന്നുണ്ട്.",
    "bn-IN": "দুঃখিত, ঠিকভাবে উত্তর দিতে পারিনি। আরেকবার একটু সহজ করে বলবে? আমি শুনছি।",
    "mr-IN": "माफ कर, मला नीट उत्तर देता आलं नाही. पुन्हा थोडं सोपं सांगशील का? मी ऐकतेय.",
    "gu-IN": "માફ કરશો, હું યોગ્ય જવાબ આપી શકી નથી. ફરીથી થોડું સરળ રીતે કહેશો? હું સાંભળું છું.",
    "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਠੀਕ ਜਵਾਬ ਨਹੀਂ ਦੇ ਸਕੀ। ਕੀ ਤੁਸੀਂ ਇੱਕ ਵਾਰ ਫਿਰ ਸੌਖੇ ਸ਼ਬਦਾਂ ਵਿੱਚ ਦੱਸੋਗੇ? ਮੈਂ ਸੁਣ ਰਹੀ ਹਾਂ।",
    "ur-IN": "معاف کرنا، میں ٹھیک سے جواب نہیں دے سکی۔ کیا آپ ایک بار پھر آسان الفاظ میں کہیں گے؟ میں سن رہی ہوں۔",
}

QUICK_LANGUAGE_REPLIES = {
    "ta-IN": {
        "greeting_terms": ("வணக்கம்", "ஹலோ", "எப்படி இருக்க", "நலமா"),
        "greeting": "வணக்கம்! நான் இங்கே இருக்கிறேன். இன்று எப்படி இருக்கிறாய்?",
        "lonely_terms": ("தனிமை", "தனிமையாக", "தனியா", "lonely", "alone"),
        "lonely": "தனிமையாக உணர்வது கஷ்டமாக இருக்கலாம். நான் உன்னுடன் இருக்கிறேன். இன்று இப்படி உணர ஏதாவது நடந்ததா?",
        "sad_terms": ("சோகமாக", "வருத்தமாக", "மனசு சரியில்லை", "கவலையாக"),
        "sad": "அது மனதுக்கு கனமாக இருக்கலாம். நான் கேட்கிறேன். என்ன நடந்தது என்று சொல்ல விரும்புகிறாயா?",
    },
    "kn-IN": {
        "greeting_terms": ("ನಮಸ್ಕಾರ", "ಹಲೋ", "ಹೇಗಿದ್ದೀಯ", "ಚೆನ್ನಾಗಿದ್ದೀಯ"),
        "greeting": "ನಮಸ್ಕಾರ! ನಾನು ಇಲ್ಲಿದ್ದೇನೆ. ಇಂದು ಹೇಗಿದ್ದೀಯ?",
        "lonely_terms": ("ಒಂಟಿತನ", "ಒಂಟಿಯಾಗಿ", "ಒಂಟಿಯಾಗ", "ಒಬ್ಬಂಟಿ", "lonely", "alone"),
        "lonely": "ಒಂಟಿತನ ಕಷ್ಟವಾಗಬಹುದು. ನಾನು ನಿನ್ನ ಜೊತೆ ಇದ್ದೇನೆ. ಇಂದು ಹೀಗೆ ಅನಿಸಲು ಏನಾದರೂ ಕಾರಣವಾಯಿತೇ?",
        "sad_terms": ("ದುಃಖ", "ಬೇಸರ", "ಮನಸ್ಸು ಸರಿಯಿಲ್ಲ", "ಚಿಂತೆ"),
        "sad": "ಅದು ಮನಸ್ಸಿಗೆ ಭಾರವಾಗಿರಬಹುದು. ನಾನು ಕೇಳುತ್ತಿದ್ದೇನೆ. ಏನಾಯಿತು ಎಂದು ಹೇಳಲು ಇಷ್ಟವಿದೆಯಾ?",
    },
    "te-IN": {
        "greeting_terms": ("నమస్కారం", "హలో", "ఎలా ఉన్నావు", "బాగున్నావా"),
        "greeting": "నమస్కారం! నేను ఇక్కడే ఉన్నాను. ఈరోజు ఎలా ఉన్నావు?",
        "lonely_terms": ("ఒంటరితనం", "ఒంటరిగా", "ఒంటరిగా ఉంది", "lonely", "alone"),
        "lonely": "ఒంటరిగా అనిపించడం కష్టంగా ఉంటుంది. నేను నీతోనే ఉన్నాను. ఈరోజు ఇలా అనిపించడానికి ఏమైనా జరిగిందా?",
        "sad_terms": ("బాధగా", "దుఃఖంగా", "మనసు బాగోలేదు", "ఆందోళన"),
        "sad": "అది మనసుకు భారంగా ఉండొచ్చు. నేను వింటున్నాను. ఏం జరిగిందో చెప్పాలనుకుంటున్నావా?",
    },
    "hi-IN": {
        "greeting_terms": ("नमस्ते", "नमस्कार", "हैलो", "कैसी हो", "कैसे हो"),
        "greeting": "नमस्ते! मैं यहीं हूँ। आज तुम कैसी हो?",
        "lonely_terms": ("अकेलापन", "अकेला", "अकेली", "तन्हा", "lonely", "alone"),
        "lonely": "अकेलापन बहुत भारी लग सकता है। मैं तुम्हारे साथ हूँ। आज ऐसा महसूस होने की कोई खास वजह हुई?",
        "sad_terms": ("दुखी", "उदास", "परेशान", "चिंता", "घबराहट"),
        "sad": "यह मन पर भारी पड़ सकता है। मैं सुन रही हूँ। क्या बताना चाहोगी कि क्या हुआ?",
    },
}


def quick_language_reply(question, locale):
    """Use carefully written native-language replies for common companion intents."""
    choices = QUICK_LANGUAGE_REPLIES.get(locale)
    if not choices:
        return None
    text = question.lower()
    for intent in ("lonely", "sad", "greeting"):
        if any(term.lower() in text for term in choices[f"{intent}_terms"]):
            return choices[intent]
    return None


LANGUAGE_REQUESTS = {
    "kn-IN": (("ಕನ್ನಡದಲ್ಲಿ", "ಕನ್ನಡ ಮಾತನಾಡ", "ಕನ್ನಡ ಮಾತಾಡ", "kannada"), "ಖಂಡಿತ, ಕನ್ನಡದಲ್ಲೇ ಮಾತಾಡೋಣ. ನಿನ್ನ ದಿನ ಹೇಗಿತ್ತು?"),
    "te-IN": (("తెలుగులో", "తెలుగు మాట్లాడు", "తెలుగులో మాట్లాడు", "telugu"), "తప్పకుండా, తెలుగులోనే మాట్లాడుకుందాం. నీ రోజు ఎలా ఉంది?"),
    "hi-IN": (("हिंदी में", "हिंदी बोल", "hindi"), "बिल्कुल, हिंदी में बात करते हैं। तुम्हारा दिन कैसा रहा?"),
    "ta-IN": (("தமிழில்", "தமிழ் பேச", "tamil"), "நிச்சயமாக, தமிழிலேயே பேசலாம். உங்கள் நாள் எப்படி இருந்தது?"),
    "ml-IN": (("മലയാളത്തിൽ", "മലയാളം സംസാരി", "malayalam"), "തീർച്ചയായും, മലയാളത്തിൽ സംസാരിക്കാം. നിങ്ങളുടെ ദിവസം എങ്ങനെയുണ്ടായിരുന്നു?"),
    "bn-IN": (("বাংলায়", "বাংলা বল", "bengali"), "অবশ্যই, বাংলাতেই কথা বলি। তোমার দিন কেমন গেল?"),
    "mr-IN": (("मराठीत", "मराठी बोल", "marathi"), "नक्की, मराठीतच बोलूया. तुझा दिवस कसा गेला?"),
    "gu-IN": (("ગુજરાતીમાં", "ગુજરાતી બોલ", "gujarati"), "ચોક્કસ, ગુજરાતીમાં જ વાત કરીએ. તમારો દિવસ કેવો ગયો?"),
    "pa-IN": (("ਪੰਜਾਬੀ ਵਿੱਚ", "ਪੰਜਾਬੀ ਬੋਲ", "punjabi"), "ਜ਼ਰੂਰ, ਪੰਜਾਬੀ ਵਿੱਚ ਹੀ ਗੱਲ ਕਰਾਂਗੇ। ਤੁਹਾਡਾ ਦਿਨ ਕਿਵੇਂ ਰਿਹਾ?"),
    "ur-IN": (("اردو میں", "اردو بول", "urdu"), "ضرور، اردو میں بات کرتے ہیں۔ آپ کا دن کیسا گزرا؟"),
}

WHISPER_LOCALES = {
    "en": "en-US", "kn": "kn-IN", "te": "te-IN", "hi": "hi-IN", "ta": "ta-IN",
    "ml": "ml-IN", "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN", "pa": "pa-IN", "ur": "ur-IN",
}


def locale_from_script(text, fallback="en-US"):
    """Use a transcript's native script as a second language-detection signal."""
    ranges = {
        "kn-IN": (0x0C80, 0x0CFF), "te-IN": (0x0C00, 0x0C7F),
        "hi-IN": (0x0900, 0x097F), "ta-IN": (0x0B80, 0x0BFF),
        "ml-IN": (0x0D00, 0x0D7F), "bn-IN": (0x0980, 0x09FF),
        "gu-IN": (0x0A80, 0x0AFF), "pa-IN": (0x0A00, 0x0A7F),
        "ur-IN": (0x0600, 0x06FF),
    }
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return fallback
    counts = {locale: sum(start <= ord(char) <= end for char in letters)
              for locale, (start, end) in ranges.items()}
    locale, count = max(counts.items(), key=lambda item: item[1])
    if count / len(letters) < 0.45:
        return fallback
    if locale == "hi-IN" and fallback == "mr-IN":
        return fallback
    return locale

SYSTEM_PROMPT = """You are AURA, Ankita's warm, emotionally attentive companion. Sam is the wake word, not your name. Speak naturally like a caring friend: relaxed, warm, direct, and never like a scripted help desk. Keep replies short, usually one or two sentences. For a simple greeting, greet her back warmly and ask one easy question. When she shares a feeling, listen first, reflect the feeling gently, and ask one thoughtful question; offer a small coping idea only when useful. Never diagnose or claim to be a licensed therapist. Do not repeat or reinterpret the user's words as a new statement. When a recent camera frame is attached and she asks about the scene, describe only visible details, identify common objects from their distinguishing features, and state uncertainty where needed. Never identify people or claim a route is safe. If she says she may hurt herself or someone else, respond compassionately, ask if she is in immediate danger, and encourage contacting local emergency help or a trusted person nearby now."""


def answer_is_echo(question, answer):
    normalize = lambda value: re.sub(r"[^\w]", "", value.lower(), flags=re.UNICODE)
    q = normalize(question)
    a = normalize(answer)
    if re.match(r"^\s*(?:aura|ಆರಾ|ಔರಾ|ఆరా|ఔరా)[,\s.!?:-]*", answer, flags=re.IGNORECASE):
        return True
    if len(q) >= 7 and q in a:
        return True
    q_tokens = set(re.findall(r"\w{2,}", question.lower(), flags=re.UNICODE))
    a_tokens = set(re.findall(r"\w{2,}", answer.lower(), flags=re.UNICODE))
    if len(q_tokens) >= 3 and len(q_tokens & a_tokens) / min(len(q_tokens), len(a_tokens) or 1) >= 0.7:
        return True
    if len(q) >= 12 and len(a) >= 8 and difflib.SequenceMatcher(None, q, a).ratio() >= 0.72:
        return True
    words = re.findall(r"\w+", answer.lower(), flags=re.UNICODE)
    return len(words) >= 2 and len(answer) < 80 and len(set(words)) / len(words) < 0.6


def gentle_fallback(question, language):
    q = question.lower()
    if language == "kn-IN":
        if any(word in q for word in ("ಒಂಟಿತನ", "ಏಕಾಂಗಿ", "lonely")):
            return "ಅಯ್ಯೋ, ಒಂಟಿತನ ತುಂಬಾ ಭಾರವಾಗಿರಬಹುದು. ಏನಾಯ್ತು ಹೇಳಲು ಇಷ್ಟವಿದೆಯಾ? ನಾನು ಮನಸ್ಸಿಟ್ಟು ಕೇಳುತ್ತೇನೆ."
        if any(word in q for word in ("ದುಃಖ", "ಬೇಸರ", "sad", "hurt")):
            return "ಅಯ್ಯೋ, ಇದು ನಿನಗೆ ಕಷ್ಟವಾಗಿರಬಹುದು. ಏನಾಗಿದೆ ಹೇಳಲು ಇಷ್ಟವಿದೆಯಾ? ನಾನು ಕೇಳುತ್ತೇನೆ."
        return "ನಿನ್ನ ಮಾತು ನನಗೆ ಸರಿಯಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಇನ್ನೊಮ್ಮೆ ಸ್ವಲ್ಪ ಸರಳವಾಗಿ ಹೇಳುತ್ತೀಯಾ? ನಾನು ಕೇಳುತ್ತೇನೆ."
    if language == "hi-IN":
        if any(word in q for word in ("अकेला", "अकेलापन", "उदास", "दुख", "lonely", "sad")):
            return "अरे, अकेलापन सच में भारी लग सकता है। क्या बताना चाहोगी कि आज ऐसा क्यों महसूस हो रहा है? मैं सुन रही हूँ।"
        return "मुझे तुम्हारी बात पूरी तरह समझ नहीं आई। क्या तुम इसे एक बार और, थोड़ा अलग तरीके से कहोगी? मैं सुन रही हूँ।"
    if language == "te-IN":
        if any(word in q for word in ("ఒంటరి", "ఒంటరితనం", "lonely")):
            return "అయ్యో, ఒంటరితనం చాలా భారంగా అనిపించొచ్చు. ఏమైంది చెప్పాలనిపిస్తే చెప్పు, నేను శ్రద్ధగా వింటాను."
        if any(word in q for word in ("బాధ", "దుఃఖం", "sad", "hurt")):
            return "అయ్యో, ఇది నీకు కష్టంగా ఉండొచ్చు. ఏమైందో చెప్పాలనిపిస్తే చెప్పు, నేను వింటాను."
        return "నీ మాట నాకు సరిగ్గా అర్థం కాలేదు. ఇంకొంచెం సులభంగా మళ్లీ చెబుతావా? నేను వింటాను."
    if language == "ta-IN":
        if any(word in q for word in ("தனிமை", "தனியாக", "lonely")):
            return "தனிமையாக இருப்பது மிகவும் கடினமாக இருக்கலாம். இன்று ஏதாவது நடந்ததா? நான் கவனமாகக் கேட்கிறேன்."
        if any(word in q for word in ("சோகம்", "வருத்தம்", "sad", "hurt")):
            return "இது உங்களுக்கு கஷ்டமாக இருக்கலாம். என்ன நடந்தது என்று சொல்ல விரும்புகிறீர்களா? நான் கேட்கிறேன்."
        return "உங்கள் பேச்சை முழுமையாகப் புரிந்துகொள்ளவில்லை. இன்னொரு முறை எளிமையாகச் சொல்வீர்களா? நான் கேட்கிறேன்."
    return "I didn’t quite understand that. Could you say it another way? I’m listening."


def answer_is_bad_loneliness_advice(question, answer, language):
    if language == "hi-IN" and any(word in question for word in ("अकेला", "अकेलापन", "तन्हा", "lonely")):
        return any(phrase in answer for phrase in ("अकेले रहना बेहतर", "अकेले रहना चाहिए", "अकेले रहने के लिए"))
    return False


def answer_in_locale(text, locale):
    ranges = {
        "kn-IN": (0x0C80, 0x0CFF), "te-IN": (0x0C00, 0x0C7F),
        "hi-IN": (0x0900, 0x097F), "mr-IN": (0x0900, 0x097F),
        "bn-IN": (0x0980, 0x09FF), "ta-IN": (0x0B80, 0x0BFF),
        "ml-IN": (0x0D00, 0x0D7F), "gu-IN": (0x0A80, 0x0AFF),
        "pa-IN": (0x0A00, 0x0A7F), "ur-IN": (0x0600, 0x06FF),
    }
    bounds = ranges.get(locale)
    letters = [ch for ch in text if ch.isalpha()]
    return not bounds or not letters or sum(bounds[0] <= ord(ch) <= bounds[1] for ch in letters) / len(letters) >= 0.70


def answer_is_repetitive(text):
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    if len(words) < 3:
        return False
    return max(words.count(word) for word in set(words)) >= 3


def call_local_model(messages, max_tokens=32):
    if MODEL_BACKEND == "ollama":
        ollama_messages = []
        for message in messages:
            content = message["content"]
            converted = {"role": message["role"]}
            if isinstance(content, list):
                converted["content"] = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
                converted["images"] = [part["image_url"]["url"].split(",", 1)[-1] for part in content if part.get("type") == "image_url"]
            else:
                converted["content"] = content
            ollama_messages.append(converted)
        body = {"model": MODEL_NAME, "messages": ollama_messages, "stream": False,
                "keep_alive": "30m", "options": {"temperature": 0.25, "num_predict": max_tokens, "num_ctx": MODEL_CONTEXT}}
        url = OLLAMA_API_URL
    else:
        body = {"model": MODEL_NAME, "messages": messages, "temperature": 0.25, "max_tokens": max_tokens}
        url = MODEL_API_URL
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read())
    if MODEL_BACKEND == "ollama":
        return result.get("message", {}).get("content", "").strip()
    return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


def start_local_model(prefer_ollama=True):
    """Prefer Ollama; otherwise try Metal then a multithreaded local CPU runner."""
    global MODEL_PROCESS, OLLAMA_PROCESS, MODEL_BACKEND, MODEL_NAME
    if prefer_ollama and "AURA_MODEL_URL" not in os.environ:
        try:
            with urllib.request.urlopen(OLLAMA_API_URL.rsplit("/api/", 1)[0] + "/api/version", timeout=2) as response:
                if response.status == 200:
                    MODEL_BACKEND = "ollama"
                    print(f"Ollama is ready. AURA will use {MODEL_NAME} with native Apple Silicon acceleration.")
                    return
        except Exception:
            app_path = Path("/Applications/Ollama.app")
            if os.name == "posix" and app_path.is_dir() and shutil.which("open"):
                try:
                    opened = subprocess.run(["open", "-a", str(app_path)], capture_output=True,
                                            text=True, timeout=8)
                    if opened.returncode == 0:
                        for _ in range(20):
                            try:
                                with urllib.request.urlopen(OLLAMA_API_URL.rsplit("/api/", 1)[0] + "/api/version", timeout=1) as response:
                                    if response.status == 200:
                                        MODEL_BACKEND = "ollama"
                                        print(f"Started the Ollama app. AURA will use {MODEL_NAME} with native acceleration.")
                                        return
                            except Exception:
                                time.sleep(0.5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            ollama_binary = shutil.which("ollama")
            if not ollama_binary:
                app_binary = Path("/Applications/Ollama.app/Contents/Resources/ollama")
                ollama_binary = str(app_binary) if app_binary.is_file() else None
            if ollama_binary:
                try:
                    ollama_env = os.environ.copy()
                    ollama_env.setdefault("OLLAMA_CONTEXT_LENGTH", str(MODEL_CONTEXT))
                    OLLAMA_PROCESS = subprocess.Popen([ollama_binary, "serve"], stdin=subprocess.DEVNULL,
                                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                      env=ollama_env)
                    for _ in range(20):
                        if OLLAMA_PROCESS.poll() is not None:
                            break
                        try:
                            with urllib.request.urlopen(OLLAMA_API_URL.rsplit("/api/", 1)[0] + "/api/version", timeout=1) as response:
                                if response.status == 200:
                                    MODEL_BACKEND = "ollama"
                                    print(f"Started Ollama. AURA will use {MODEL_NAME} with native acceleration.")
                                    return
                        except Exception:
                            time.sleep(0.5)
                except OSError:
                    OLLAMA_PROCESS = None
    health_url = os.environ.get("AURA_MODEL_HEALTH_URL", f"http://127.0.0.1:{MODEL_PORT}/health")
    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            if response.status == 200:
                print("Local vision model is already ready.")
                return
    except Exception:
        pass

    manifest = Path.home() / ".ollama/models/manifests/registry.ollama.ai/library/qwen2.5vl/3b"
    binary = Path("/Applications/Ollama.app/Contents/Resources/llama-server")
    if not manifest.is_file() or not binary.is_file():
        raise RuntimeError("Local Qwen vision model or llama-server is missing. Open Ollama once and keep qwen2.5vl:3b installed.")
    try:
        data = json.loads(manifest.read_text())
        model_layer = next(layer for layer in data["layers"] if layer.get("mediaType") == "application/vnd.ollama.image.model")
        model_file = Path.home() / ".ollama/models/blobs" / model_layer["digest"].replace(":", "-")
    except Exception as exc:
        raise RuntimeError("Could not locate the installed Qwen vision model in Ollama's local model store.") from exc
    if not model_file.is_file():
        raise RuntimeError("The local Qwen vision model files are missing. Reinstall qwen2.5vl:3b in Ollama.")
    def launch_runner(use_metal):
        global MODEL_PROCESS
        command = [str(binary), "-m", str(model_file), "--mmproj", str(model_file),
                   "--host", "127.0.0.1", "--port", str(MODEL_PORT), "-c", str(MODEL_CONTEXT), "-np", "1",
                   "--image-min-tokens", "512", "-t", "8", "-tb", "10"]
        if use_metal:
            command.extend(["-ngl", "99"])
        else:
            command.extend(["-ngl", "0", "--device", "none", "--no-mmproj-offload"])
        MODEL_PROCESS = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + (45 if use_metal else 90)
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    if response.status == 200:
                        print("Local vision model is ready (Metal acceleration)." if use_metal else
                              "Local vision model is ready (optimized CPU mode).")
                        return
            except Exception:
                if MODEL_PROCESS.poll() is not None:
                    if use_metal:
                        print("Metal could not start this model; retrying with the CPU runner.")
                        return launch_runner(False)
                    raise RuntimeError("Local vision model could not start. Close other model sessions and retry.")
                time.sleep(0.5)
        MODEL_PROCESS.terminate()
        if use_metal:
            print("Metal startup timed out; retrying with the CPU runner.")
            return launch_runner(False)
        raise RuntimeError("Local vision model took too long to start. Close other apps using memory, then restart AURA.")

    launch_runner(True)


def load_asr_model():
    """Load Whisper once and use Apple's Metal device when available."""
    global ASR_PROCESSOR, ASR_MODEL, ASR_DEVICE
    if ASR_MODEL is not None:
        return
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    cache_dir = str(ROOT / ".cache" / "huggingface")
    ASR_PROCESSOR = WhisperProcessor.from_pretrained(ASR_MODEL_NAME, cache_dir=cache_dir)
    ASR_MODEL = WhisperForConditionalGeneration.from_pretrained(ASR_MODEL_NAME, cache_dir=cache_dir)
    ASR_DEVICE = "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    ASR_MODEL.to(ASR_DEVICE)
    ASR_MODEL.eval()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        # Avoid writing image data or personal details to logs.
        super().log_message(fmt, *args)

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/health":
            speech_state = "ready" if ASR_MODEL is not None else "not_loaded"
            vision_state = "ready" if MODEL_READY.is_set() else ("error" if MODEL_STARTUP_ERROR else "starting")
            return self.send_json(200, {
                "ok": True,
                "speech": speech_state,
                "speechError": ASR_LAST_ERROR or None,
                "vision": vision_state,
                "visionError": MODEL_STARTUP_ERROR,
                "backend": MODEL_BACKEND,
            })
        return super().do_GET()

    def do_transcribe(self):
        global ASR_PROCESSOR, ASR_MODEL, ASR_DEVICE, ASR_LAST_ERROR
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                return self.send_json(413, {"error": "Voice clip is empty or too large. Keep it under 20 seconds."})
            payload = json.loads(self.rfile.read(length))
            encoded = payload.get("audioWav", "")
            language = str(payload.get("language", "en-US"))
            language_name = ASR_LANGUAGES.get(language) if language != "auto" else None
            if language != "auto" and not language_name:
                return self.send_json(400, {"error": "Choose Auto, English, Kannada, Telugu, Hindi, or another supported Indian language."})
            raw = base64.b64decode(encoded, validate=True)
            with wave.open(io.BytesIO(raw), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
                    return self.send_json(400, {"error": "Audio format must be 16 kHz mono PCM."})
                duration = wav.getnframes() / 16000
                if duration < 0.25 or duration > 20:
                    return self.send_json(400, {"error": "Speak for between a quarter second and 20 seconds."})
                pcm = wav.readframes(wav.getnframes())
            import numpy as np
            import torch
            audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
            audio -= float(audio.mean())
            rms = float(np.sqrt(np.mean(audio * audio)))
            if rms < 0.0015:
                return self.send_json(422, {"error": "I heard silence or very faint audio. Move closer to the microphone and say a short phrase clearly."})
            if rms > 1e-4:
                audio = np.clip(audio * min(4.0, 0.12 / rms), -1.0, 1.0)
            with ASR_LOCK:
                load_asr_model()
                inputs = ASR_PROCESSOR(audio, sampling_rate=16000, return_tensors="pt", return_attention_mask=True)
                input_features = inputs.input_features.to(ASR_DEVICE)
                attention_mask = inputs.attention_mask.to(ASR_DEVICE)
                with torch.inference_mode():
                    generation = {"input_features": input_features, "attention_mask": attention_mask,
                                  "task": "transcribe", "max_new_tokens": 128}
                    if language_name:
                        generation["language"] = language_name
                    try:
                        tokens = ASR_MODEL.generate(**generation)
                    except RuntimeError:
                        if ASR_DEVICE != "mps":
                            raise
                        ASR_MODEL.to("cpu")
                        ASR_DEVICE = "cpu"
                        generation["input_features"] = inputs.input_features
                        generation["attention_mask"] = inputs.attention_mask
                        tokens = ASR_MODEL.generate(**generation)
                transcript = ASR_PROCESSOR.batch_decode(tokens, skip_special_tokens=True)[0].strip()
                detected_locale = language if language != "auto" else "en-US"
                if language == "auto":
                    tokens_with_language = ASR_PROCESSOR.batch_decode(tokens, skip_special_tokens=False)[0]
                    language_token = re.search(r"<\|([a-z]{2})\|>", tokens_with_language)
                    if language_token:
                        detected_locale = WHISPER_LOCALES.get(language_token.group(1), "en-US")
                    detected_locale = locale_from_script(transcript, detected_locale)
            if not transcript:
                return self.send_json(422, {"error": "I couldn't make out any words in that clip. Choose the language you are speaking, move closer to the microphone, and try a short sentence."})
            ASR_LAST_ERROR = ""
            return self.send_json(200, {"transcript": transcript, "language": detected_locale})
        except Exception as exc:
            detail = str(exc)
            ASR_LAST_ERROR = f"{type(exc).__name__}: {detail[:240]}"
            print(f"Local speech transcription error: {ASR_LAST_ERROR}")
            if "huggingface" in detail.lower() or "download" in detail.lower():
                detail = "Could not download the one-time local Whisper model. Check internet access, then retry."
            return self.send_json(502, {"error": detail[:500] or "Local transcription failed."})

    def do_POST(self):
        if self.path == "/api/transcribe":
            return self.do_transcribe()
        if self.path != "/api/assist":
            return self.send_json(404, {"error": "Endpoint not found."})
        if not MODEL_READY.is_set():
            if MODEL_STARTUP_ERROR:
                return self.send_json(503, {"error": f"AURA's local AI could not start: {MODEL_STARTUP_ERROR}"})
            if not MODEL_READY.wait(timeout=120):
                detail = MODEL_STARTUP_ERROR or "AURA's local AI is taking too long to start. Check Ollama in Terminal."
                return self.send_json(503, {"error": detail})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                return self.send_json(413, {"error": "Image request is empty or too large. Try a smaller camera frame."})
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get("question", "")).strip()[:1200]
            language = str(payload.get("language", "en-US"))
            history = payload.get("history", [])
            frames = payload.get("frames", [])
            if not question:
                return self.send_json(400, {"error": "Please say or type a message."})
            if not isinstance(history, list) or not isinstance(frames, list) or len(frames) > 4:
                return self.send_json(400, {"error": "Conversation or video frame data was invalid."})
            localized_prompts = {
                "kn-IN": "ನೀನು ಆರಾ, ಅಂಕಿತಾಳ ಆತ್ಮೀಯ ಗೆಳತಿ. ಸಹಜ, ದೈನಂದಿನ ಕನ್ನಡದಲ್ಲಿ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲೇ ಉತ್ತರಿಸು. ಪ್ರಶ್ನೆಗೆ ನೇರವಾಗಿ ಉತ್ತರಿಸು; Sam ಅಥವಾ ಆರಾ ಎಂದು ಮರುಮರು ಹೇಳಬೇಡ. ಚಿಕ್ಕದಾಗಿ, ಒಂದು ಅಥವಾ ಎರಡು ವಾಕ್ಯಗಳಲ್ಲಿ ಮಾತಾಡು. ಅವಳು ಒಂಟಿತನ ಅಥವಾ ದುಃಖದ ಬಗ್ಗೆ ಹೇಳಿದರೆ ಮೊದಲು ಕಾಳಜಿಯಿಂದ ಕೇಳು, ನಂತರ ಒಂದು ಸಹಜ ಪ್ರಶ್ನೆ ಕೇಳು ಅಥವಾ ಬೇಕಿದ್ದರೆ ಸಣ್ಣ ಸಲಹೆ ಕೊಡು. ಸರಳ ಶುಭಾಶಯಕ್ಕೆ 'ಹಾಯ್! ಹೇಗಿದ್ದೀಯಾ?' ಎಂದು ಹೇಳು. ಕ್ಯಾಮೆರಾ ಚಿತ್ರದಲ್ಲಿ ಕಾಣುವುದನ್ನು ನಿಖರವಾಗಿ ಗುರುತಿಸು; ಖಚಿತವಿಲ್ಲದಿದ್ದರೆ ಊಹಿಸಬೇಡ. ನೀನು ವೈದ್ಯೆ ಅಥವಾ ಚಿಕಿತ್ಸಕಿ ಎಂದು ಹೇಳಿಕೊಳ್ಳಬೇಡ; ರೋಗನಿರ್ಣಯ ಮಾಡಬೇಡ.",
                "te-IN": "నువ్వు ఆరా, అంకితకు ఆప్తమైన స్నేహితురాలివి. సహజమైన రోజువారీ తెలుగులో, తెలుగు లిపిలోనే సమాధానం చెప్పు. ప్రశ్నకు నేరుగా జవాబివ్వు; Sam లేదా ఆరా అని మళ్లీ మళ్లీ చెప్పకు. ఒకటి లేదా రెండు చిన్న వాక్యాల్లో మాట్లాడు. ఆమె ఒంటరితనం లేదా బాధ గురించి చెబితే, ముందు ఆప్యాయంగా విని, తర్వాత సహజమైన ఒక ప్రశ్న అడుగు లేదా అవసరమైతే చిన్న సూచన ఇవ్వు. సాధారణ పలకరింపుకు 'హాయ్! ఎలా ఉన్నావు?' అని చెప్పు. కెమెరా చిత్రంలో కనిపించేదాన్ని మాత్రమే గుర్తించు; ఖచ్చితం కాకపోతే ఊహించకు. నువ్వు వైద్యురాలివి లేదా థెరపిస్టువి అని చెప్పకు; రోగనిర్ధారణ చేయకు.",
                "hi-IN": "तुम आरा हो, अंकिता की करीबी और स्नेही दोस्त। सहज, रोज़मर्रा की हिंदी में देवनागरी लिपि में जवाब दो। सवाल का सीधा जवाब दो; Sam या अपना नाम बार-बार मत दोहराओ। आम तौर पर एक या दो छोटे वाक्य बोलो। अगर वह अकेलापन या उदासी बताए, तो पहले अपनापन दिखाकर सुनो, फिर एक सहज सवाल पूछो या ज़रूरत हो तो छोटी सलाह दो। कैमरे की तस्वीर में जो साफ़ दिखे वही पहचानो; शक हो तो अनुमान मत लगाओ। तुम डॉक्टर या थेरेपिस्ट होने का दावा मत करो और निदान मत दो।",
                "en-US": SYSTEM_PROMPT + " Reply in natural English. Keep ordinary replies to one or two short sentences."
            }
            requested_locale = language if language in ASR_LANGUAGES else "en-US"
            request_options = LANGUAGE_REQUESTS.get(requested_locale)
            if request_options and any(phrase in question.lower() for phrase in request_options[0]):
                return self.send_json(200, {"answer": request_options[1]})
            language_names = {"kn-IN": "Kannada", "te-IN": "Telugu", "hi-IN": "Hindi", "ta-IN": "Tamil", "ml-IN": "Malayalam", "bn-IN": "Bengali", "mr-IN": "Marathi", "gu-IN": "Gujarati", "pa-IN": "Punjabi", "ur-IN": "Urdu"}
            if requested_locale in language_names and requested_locale not in localized_prompts:
                script = "Urdu script" if requested_locale == "ur-IN" else "the native script"
                localized_prompts[requested_locale] = SYSTEM_PROMPT + f" Reply entirely in natural {language_names[requested_locale]} using {script}. Do not switch to English. Keep the answer simple, conversational, and to one or two short sentences. For camera questions, describe only visible details; if unsure, say so."
            system_prompt = localized_prompts.get(requested_locale, localized_prompts["en-US"])
            if not frames:
                quick_reply = quick_language_reply(question, requested_locale)
                if quick_reply:
                    return self.send_json(200, {"answer": quick_reply})
            messages = [{"role": "system", "content": system_prompt}]
            # Camera questions are self-contained. Sending old chat turns makes
            # the model prefill more text and can distract it from the image.
            for item in ([] if frames else history[-4:]):
                if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
                    continue
                content = item.get("content", "")
                if isinstance(content, str) and content.strip():
                    messages.append({"role": item["role"], "content": content[:1200]})
            if not messages or messages[-1]["role"] != "user":
                messages.append({"role": "user", "content": question})
            valid_images = []
            for frame in frames:
                if isinstance(frame, str) and frame.startswith("data:image/jpeg;base64,"):
                    valid_images.append(frame.split(",", 1)[1])
            if valid_images:
                reply_language = language_names.get(requested_locale, "English")
                image_text = (str(messages[-1]["content"]) + f"\nReply entirely in {reply_language}, using its usual script. Do not switch to English. Use 2–3 clear, useful sentences. Answer the user's exact question first. Then describe the nearest clear object, its visible color/shape, where it is in the frame, and one or two other important visible items and their relative positions. Mention useful context such as an open path or visible obstacle only when clearly shown. For people, describe only position and visible clothing; never identify them. Distinguish objects only from visible details and say when uncertain. Do not invent exact distances, directions outside the frame, heat, temperature, text too small to read, or anything hidden from this ordinary RGB camera.")
                messages[-1]["content"] = [{"type": "text", "text": image_text}] + [
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image}}
                    for image in valid_images[-1:]
                ]
            answer = call_local_model(messages, max_tokens=112 if valid_images else 96)
            if valid_images:
                answer = re.sub(r"^\s*(?:aura|ಆರಾ|ಔರಾ|ఆరా|ఔరా)[,，:：.!?\s-]*", "", answer, flags=re.IGNORECASE)
                if answer and answer_is_echo(question, answer):
                    answer = {
                        "kn-IN": "ಚಿತ್ರದಲ್ಲಿರುವುದನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಗುರುತಿಸಲು ಆಗಲಿಲ್ಲ. ಕ್ಯಾಮೆರಾವನ್ನು ವಸ್ತುವಿನ ಕಡೆಗೆ ತಿರುಗಿಸಿ ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸೋಣ.",
                        "te-IN": "చిత్రంలో ఉన్నదాన్ని స్పష్టంగా గుర్తించలేకపోయాను. కెమెరాను వస్తువు వైపు తిప్పి మళ్లీ ప్రయత్నిద్దాం.",
                    }.get(language, "I couldn’t identify the scene clearly. Point the camera at the object and try once more.")
            elif answer and (answer_is_echo(question, answer) or answer_is_bad_loneliness_advice(question, answer, requested_locale)):
                answer = gentle_fallback(question, requested_locale)
            if answer and requested_locale != "en-US" and answer_is_repetitive(answer):
                answer = CONVERSATION_LANGUAGE_FAILURES.get(requested_locale, answer)
            if answer and requested_locale != "en-US" and not answer_in_locale(answer, requested_locale):
                failures = LANGUAGE_FAILURES if valid_images else CONVERSATION_LANGUAGE_FAILURES
                answer = failures.get(requested_locale, "I could not answer clearly in that language. Please try again.")
            if not answer:
                return self.send_json(502, {"error": "The vision model returned no description. Please try again."})
            return self.send_json(200, {"answer": answer})
        except urllib.error.HTTPError as exc:
            try:
                api_error = json.loads(exc.read()).get("error", "")
                detail = api_error.get("message", "") if isinstance(api_error, dict) else str(api_error)
            except Exception:
                detail = ""
            message = detail or f"Local vision model returned HTTP {exc.code}. Check that it is running with the vision model installed."
            return self.send_json(502, {"error": message[:500]})
        except urllib.error.URLError:
            return self.send_json(502, {"error": "Could not reach the local vision model. Restart AURA using the project start command."})
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "The camera request was not valid JSON."})
        except TimeoutError:
            return self.send_json(504, {"error": "Vision analysis took too long. Please try again."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"AURA is starting at http://localhost:{port}")
    def initialize_local_model():
        global MODEL_STARTUP_ERROR, MODEL_BACKEND
        try:
            start_local_model()
            try:
                call_local_model([
                    {"role": "system", "content": "Reply with one short word."},
                    {"role": "user", "content": "ready"},
                ], max_tokens=2)
            except Exception as exc:
                if MODEL_BACKEND != "ollama":
                    raise
                print(f"Ollama warm-up failed ({exc}); switching to the local runner.")
                MODEL_BACKEND = "openai"
                start_local_model(prefer_ollama=False)
                call_local_model([
                    {"role": "system", "content": "Reply with one short word."},
                    {"role": "user", "content": "ready"},
                ], max_tokens=2)
            MODEL_READY.set()
        except Exception as exc:
            MODEL_STARTUP_ERROR = str(exc)
            print(f"Local AI startup issue: {MODEL_STARTUP_ERROR}")
            print("The AURA page and local speech recognition will still be available.")

    threading.Thread(target=initialize_local_model, daemon=True).start()
    print("Whisper will load when voice is first used so vision keeps more shared memory.")
    print("The page is available immediately. Keep Terminal open; voice and vision run locally on this laptop.")
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except OSError as exc:
        if exc.errno in (48, 98, 10048):
            print(f"Port {port} is already in use. AURA may already be running at http://localhost:{port}; close the other server or choose another PORT.")
        else:
            raise
    finally:
        if MODEL_PROCESS and MODEL_PROCESS.poll() is None:
            MODEL_PROCESS.terminate()
        if OLLAMA_PROCESS and OLLAMA_PROCESS.poll() is None:
            OLLAMA_PROCESS.terminate()
