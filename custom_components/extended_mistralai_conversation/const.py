"""Constants for the Extended Mistral AI Conversation integration."""
DOMAIN = "extended_mistralai_conversation"
DEFAULT_NAME = "Extended Mistral AI Conversation"
DEFAULT_MODEL = "mistral-medium-latest"
DEFAULT_TOOLS_CONFIG_PATH = "mistral_tools.yaml"
DEFAULT_PROMPT_PATH = "mistral_prompt.txt"
DEFAULT_ALLOWED_DOMAINS = ["light", "cover", "script", "media_player"]
DEFAULT_ALLOWED_SERVICES = {
    "light": ["turn_on", "turn_off", "toggle"],
    "cover": ["open_cover", "close_cover", "set_cover_position"],
    "script": ["turn_on", "turn_off", "assist_timer", "extinction_musique"],
    "media_player": ["volume_set", "media_play_pause", "turn_on", "turn_off"],
}
DEFAULT_BACKUP_PATH = "/share/extended_mistralai_conversation_options.json"

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
MISTRAL_API_BASE = "https://api.mistral.ai/v1"

# ---------------------------------------------------------------------------
# TTS / STT — repris de SnarfNL/HA_MistralAI (licence MIT, voir NOTICE_SnarfNL.md)
# ---------------------------------------------------------------------------
CONF_TTS_VOICE = "tts_voice"
CONF_TTS_MODE = "tts_mode"

TTS_MODE_STREAM = "stream"
TTS_MODE_BATCH = "batch"
TTS_MODES = [TTS_MODE_STREAM, TTS_MODE_BATCH]

DEFAULT_TTS_VOICE = "fr_marie_neutral"
DEFAULT_TTS_MODE = TTS_MODE_STREAM

STT_MODEL = "voxtral-mini-latest"
TTS_MODEL = "voxtral-mini-tts-2603"

TTS_VOICES = [
    "en_paul_angry", "en_paul_cheerful", "en_paul_confident", "en_paul_excited",
    "en_paul_frustrated", "en_paul_happy", "en_paul_neutral", "en_paul_sad",
    "fr_marie_angry", "fr_marie_curious", "fr_marie_excited", "fr_marie_happy",
    "fr_marie_neutral", "fr_marie_sad",
    "gb_jane_confused", "gb_jane_curious", "gb_jane_frustrated", "gb_jane_jealousy",
    "gb_jane_neutral", "gb_jane_sad", "gb_jane_sarcasm", "gb_jane_shameful",
    "gb_oliver_angry", "gb_oliver_cheerful", "gb_oliver_confident", "gb_oliver_curious",
    "gb_oliver_excited", "gb_oliver_neutral", "gb_oliver_sad",
]

# Cap on concurrently in-flight Mistral TTS requests (one per sentence).
CONF_TTS_MAX_INFLIGHT_SENTENCES = "tts_max_inflight_sentences"
DEFAULT_TTS_MAX_INFLIGHT_SENTENCES = 2

# Ne pas déclencher le TTS sur des phrases plus courtes que ceci (évite de
# spammer l'API sur des fragments du style "OK.").
CONF_TTS_MIN_SENTENCE_CHARS = "tts_min_sentence_chars"
DEFAULT_TTS_MIN_SENTENCE_CHARS = 12

# Taille standard d'en-tête WAV PCM pour le flux streaming de Mistral :
# RIFF(8) + WAVE(4) + fmt subchunk(24) + data subchunk header(8) = 44 octets.
# Fixe (format WAV), volontairement pas exposé comme option utilisateur.
TTS_WAV_HEADER_SIZE = 44

# Silence (PCM à zéro) inséré entre les phrases en mode streaming, pour une
# pause naturelle aux frontières de phrase. Exposé en millisecondes (plus
# parlant qu'un nombre d'octets) ; converti en octets à l'usage sur la base
# du flux Mistral (24 kHz x 16-bit x mono = 48 octets/ms).
CONF_TTS_SILENCE_MS = "tts_silence_ms"
DEFAULT_TTS_SILENCE_MS = 300
TTS_SILENCE_BYTES_PER_MS = 48

# Gain cible (headroom, en dB) appliqué par normalize() sur l'audio TTS —
# plus la valeur est basse, plus le volume final est fort.
CONF_TTS_HEADROOM = "tts_headroom"
DEFAULT_TTS_HEADROOM = 2.6
