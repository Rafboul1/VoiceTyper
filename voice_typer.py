"""
VoiceTyper v1.3 - Dictée vocale locale push-to-talk pour Windows
=================================================================
Utilise faster-whisper sur GPU pour transcrire ta voix en texte
partout sur ton PC (system-wide).

Maintiens le bouton souris (côté) ou une touche → parle → relâche → le texte est tapé.
Si du texte est sélectionné, il est remplacé par la transcription.

Auteur: @Rafboul 
"""

import sys
import os
import re
import queue
import threading
import time
import ctypes
import ctypes.wintypes
import json
import logging
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import mouse, keyboard
from pynput.keyboard import Key
import pystray
from PIL import Image, ImageDraw
import pyperclip


# ── Logging vers fichier (pour mode silencieux) ───────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_typer.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),  # Garde aussi la console si elle existe
    ],
)
log = logging.info
log_err = logging.error


# ╔══════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION — Modifie ici selon tes préférences          ║
# ╚══════════════════════════════════════════════════════════════╝

# --- Whisper (modèle de transcription) ---
WHISPER_MODEL = "large-v3"       # "medium" = plus rapide, "large-v3" = meilleure qualité
WHISPER_DEVICE = "cuda"          # "cuda" pour GPU (recommandé), "cpu" sinon
COMPUTE_TYPE = "float16"         # "float16" = GPU précis, "int8_float16" = GPU rapide, "int8" = CPU

# --- Audio ---
SAMPLE_RATE = 16000              # Ne pas changer (Whisper attend 16kHz)
MIN_DURATION = 0.4               # Durée min d'audio pour transcrire (en secondes)
# Micro : "auto" = détection automatique, ou un numéro pour forcer un device
# Si "auto" ne trouve pas le bon, lance test_micro.py pour trouver le numéro
AUDIO_DEVICE = "auto"

# --- Push-to-talk ---
# Mode : "mouse" = bouton souris latéral, "keyboard" = touche clavier
PTT_MODE = "mouse"

# Boutons souris : "x1" = bouton arrière (pouce), "x2" = bouton avant (pouce)
# ✅ Les boutons x1/x2 sont interceptés ET supprimés via un hook Windows natif,
#    donc le terminal ne voit pas le clic — plus de conflit avec Windows Terminal.
MOUSE_BUTTON = "x2"

# Touche clavier (si PTT_MODE = "keyboard") : utilise le nom pynput
# ✅ Key.pause      → touche Pause/Break  (safe partout, y compris dans les terminaux)
# ✅ Key.scroll_lock → touche Scroll Lock (idem)
# ✅ Key.ctrl_r     → Ctrl droit          (safe dans la plupart des apps)
# ⚠️ Key.shift_l   → Shift gauche        (peut interférer avec la sélection de texte)
KEYBOARD_KEY = Key.pause

# --- Sons de feedback ---
SOUND_ENABLED = False            # True = bip sonore quand on commence/arrête
SOUND_START_FREQ = 700           # Fréquence du bip de début (Hz)
SOUND_STOP_FREQ = 400            # Fréquence du bip de fin (Hz)
SOUND_DURATION_MS = 80           # Durée du bip (ms)

# --- Sensibilité micro ---
AUDIO_GAIN = 3.0                 # Amplification du volume (1.0 = normal, 2-4 = voix basse)

# --- VAD (Voice Activity Detection) ---
# Seuil de détection de la voix. Plus haut = moins sensible aux bruits parasites.
# 0.3 = très sensible (risque d'hallucinations sur bruits), 0.5 = recommandé, 0.7 = strict
VAD_THRESHOLD = 0.5

# --- Divers ---
PASTE_DELAY = 0.05               # Délai avant de coller le texte (secondes)
ADD_TRAILING_SPACE = True        # Ajouter un espace après le texte transcrit

# --- Exclusion de terminaux ---
# Si TERMINAL_DETECTION = True, le PTT est ignoré quand un terminal est au premier plan.
# ⚠️  Si tu veux DICTER dans le terminal → mets False.
# ✅  Si tu veux juste éviter les conflits accidentels en terminal → mets True.
TERMINAL_DETECTION = False

# Liste des noms de processus à exclure (en minuscules, avec .exe).
# Ajoute d'autres processus si besoin.
TERMINAL_BLACKLIST = {
    "windowsterminal.exe",  # Windows Terminal (Claude Code, PowerShell, WSL...)
    "cmd.exe",              # Invite de commandes Windows
    "powershell.exe",       # PowerShell classique
    "pwsh.exe",             # PowerShell 7+
    "bash.exe",             # WSL / Git Bash
    "wsl.exe",              # Windows Subsystem for Linux
    "wslhost.exe",
    "mintty.exe",           # Git Bash (mintty)
    "alacritty.exe",        # Terminal Alacritty
    "hyper.exe",            # Terminal Hyper
    "conhost.exe",          # Console Host Windows
}

# --- Vocabulaire custom ---
# Fichier JSON avec tes mots personnalisés (créé automatiquement au 1er lancement)
VOCAB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocabulaire.json")

# ╔══════════════════════════════════════════════════════════════╗
# ║  VOCABULAIRE CUSTOM                                          ║
# ║  Édite le fichier vocabulaire.json ou modifie ici            ║
# ╚══════════════════════════════════════════════════════════════╝

# Mots que Whisper doit connaître (aide à la reconnaissance).
# Mets ici les noms propres, termes techniques, acronymes, etc.
# que tu utilises souvent. Whisper essaiera de les reconnaître.
HINT_WORDS = [
    # Exemples (remplace par tes propres mots) :
    # "Rafboul", "A.E.I.", "FastAPI",
]

# Dictionnaire de remplacement APRÈS transcription.
# Si Whisper transcrit mal un mot, corrige-le ici.
# Format : "ce_que_whisper_dit": "ce_que_tu_veux"
# La recherche est insensible à la casse.
DEFAULT_REPLACEMENTS = {
    # Exemples (remplace par les tiens) :
    # "rafboul": "Rafboul",
    # "aei": "A.E.I.",
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  CODE PRINCIPAL — Pas besoin de toucher en dessous           ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Windows API pour Ctrl+V fiable ───────────────────────────

user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_SHIFT   = 0x10
VK_V = 0x56
VK_A = 0x41
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002


def win_key_combo(vk_modifier, vk_key):
    """Simule un raccourci clavier via l'API Windows (plus fiable que pynput)."""
    user32.keybd_event(vk_modifier, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(vk_key, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(vk_key, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)
    user32.keybd_event(vk_modifier, 0, KEYEVENTF_KEYUP, 0)


def win_ctrl_c():
    """Ctrl+C via Windows API."""
    win_key_combo(VK_CONTROL, VK_C)


def win_ctrl_v():
    """Ctrl+V via Windows API."""
    win_key_combo(VK_CONTROL, VK_V)


def win_ctrl_shift_v():
    """Ctrl+Shift+V via Windows API (collage dans les terminaux)."""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


# ── Hook souris bas niveau (supprime x1/x2 avant les autres applis) ──────────

WH_MOUSE_LL    = 14
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP   = 0x020C
XBUTTON1       = 0x0001
XBUTTON2       = 0x0002

class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt",          ctypes.wintypes.POINT),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

_LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)

# Déclaration explicite des argtypes/restype pour les fonctions Windows utilisées
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    _LowLevelMouseProc,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK

user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_long

user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype  = ctypes.wintypes.BOOL

user32.GetMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG),
    ctypes.wintypes.HWND,
    ctypes.c_uint,
    ctypes.c_uint,
]
user32.GetMessageW.restype = ctypes.wintypes.BOOL


class MouseHook:
    """Hook souris Windows natif — intercepte ET supprime les boutons x1/x2.

    Contrairement à pynput (qui laisse l'événement passer), ce hook retourne 1
    pour annuler la propagation : le terminal ne reçoit jamais le clic.
    """

    def __init__(self, button_name: str, on_press, on_release):
        self._target = XBUTTON2 if button_name == "x2" else XBUTTON1
        self._on_press = on_press
        self._on_release = on_release
        self._hook_handle = None
        self._proc = None       # Référence pour éviter le garbage-collect
        self._thread_id = None

    def start(self):
        """Lance le hook dans un thread dédié (requis par Windows)."""
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        """Installe le hook et tourne la boucle de messages."""
        self._thread_id = _kernel32.GetCurrentThreadId()

        def _proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                ms = ctypes.cast(lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                btn = (ms.mouseData >> 16) & 0xFFFF
                if btn == self._target:
                    cb = self._on_press if wParam == WM_XBUTTONDOWN else self._on_release
                    cb()  # Appel synchrone direct — start/stop_recording ne font que changer des booléens
                    return 1  # ← Supprime l'événement (terminal ne le voit pas)
            return user32.CallNextHookEx(self._hook_handle, nCode, wParam, lParam)

        self._proc = _LowLevelMouseProc(_proc)
        self._hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        if not self._hook_handle:
            log_err("✗ Impossible d'installer le hook souris bas niveau")
            return
        log("✓ Hook souris bas niveau installé (x2 supprimé pour les autres applis)")

        # Boucle de messages — nécessaire pour recevoir les événements du hook
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnhookWindowsHookEx(self._hook_handle)

    def stop(self):
        """Arrête le hook proprement."""
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT


# ── Détection de fenêtre active ───────────────────────────────

_kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def get_focused_process_name() -> str:
    """Retourne le nom du processus de la fenêtre actuellement au premier plan."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.wintypes.DWORD(260)
        ok = _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        _kernel32.CloseHandle(handle)
        if ok:
            return os.path.basename(buf.value).lower()
    except Exception:
        pass
    return ""


def is_terminal_focused() -> bool:
    """Retourne True si une fenêtre de terminal est active.

    Utilisé pour sauter le Ctrl+C de capture de sélection (qui interrompt
    les process dans un terminal). Indépendant de TERMINAL_DETECTION.
    """
    return get_focused_process_name() in TERMINAL_BLACKLIST


# ── Vocabulaire ──────────────────────────────────────────────

class VocabManager:
    """Gère le vocabulaire personnalisé et les remplacements."""

    def __init__(self, vocab_file):
        self.vocab_file = vocab_file
        self.hint_words = list(HINT_WORDS)
        self.replacements = dict(DEFAULT_REPLACEMENTS)
        self._compiled_replacements = []  # Liste de (pattern_compilé, correction)
        self._load()

    def _load(self):
        """Charge le vocabulaire depuis le fichier JSON et pré-compile les regex."""
        if os.path.exists(self.vocab_file):
            try:
                with open(self.vocab_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Fusionner avec les valeurs par défaut
                file_hints = data.get("hint_words", [])
                file_replacements = data.get("replacements", {})
                # Les mots du fichier s'ajoutent à ceux du script
                for word in file_hints:
                    if word not in self.hint_words:
                        self.hint_words.append(word)
                self.replacements.update(file_replacements)
                log(f"✓ Vocabulaire chargé : {len(self.hint_words)} mots, {len(self.replacements)} remplacements")
            except Exception as e:
                log(f"⚠ Erreur lecture vocabulaire : {e}")
        else:
            self._save_default()

        # Pré-compilation des regex — une seule fois au chargement
        self._compiled_replacements = [
            (re.compile(re.escape(wrong), re.IGNORECASE), correct)
            for wrong, correct in self.replacements.items()
            if not wrong.startswith("#")
        ]

    def _save_default(self):
        """Crée le fichier vocabulaire.json avec des exemples."""
        data = {
            "_aide": (
                "hint_words : mots que Whisper doit reconnaître (noms propres, termes techniques). "
                "replacements : corrections après transcription (clé = ce que Whisper dit, valeur = ce que tu veux). "
                "Relance VoiceTyper après modification."
            ),
            "hint_words": self.hint_words if self.hint_words else [
                "# Ajoute tes mots ici, un par ligne",
                "# Exemples :",
                "# Rafboul",
                "# A.E.I.",
            ],
            "replacements": self.replacements if self.replacements else {
                "# exemple_whisper_dit": "# ce_que_tu_veux",
            },
        }
        try:
            with open(self.vocab_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log(f"✓ Fichier vocabulaire créé : {self.vocab_file}")
            log("    Édite-le pour ajouter tes mots persos !")
        except Exception as e:
            log(f"⚠ Impossible de créer {self.vocab_file} : {e}")

    def get_initial_prompt(self) -> str:
        """Construit le prompt initial pour Whisper avec les mots à reconnaître."""
        # Filtrer les commentaires (lignes commençant par #)
        words = [w for w in self.hint_words if not w.startswith("#")]
        if not words:
            return ""
        # Whisper utilise le prompt initial comme contexte pour mieux reconnaître
        return ", ".join(words) + ". "

    def apply_replacements(self, text: str) -> str:
        """Applique les remplacements de vocabulaire sur le texte transcrit.

        Les regex sont pré-compilées dans _load() — aucun coût à chaque appel.
        """
        for pattern, correct in self._compiled_replacements:
            text = pattern.sub(correct, text)
        return text


# ── Auto-détection du micro ───────────────────────────────────

def auto_detect_microphone():
    """Détecte automatiquement le meilleur micro disponible.

    Teste chaque device d'entrée en enregistrant 0.5s de son.
    Retourne le device_id et le nombre de canaux du premier micro qui fonctionne.
    Priorité : micros Realtek / intégrés > autres.
    """
    log("  🔍 Auto-détection du micro...")
    devs = sd.query_devices()

    # Collecter tous les devices d'entrée
    input_devices = []
    for i, d in enumerate(devs):
        if d["max_input_channels"] > 0:
            input_devices.append((i, d))

    if not input_devices:
        log("  ✗ Aucun micro détecté !")
        return None, 1

    # Trier : prioriser les micros Realtek / réseau de microphones (micro intégré)
    # et dé-prioriser les "Mappeur de sons" et "Mixage stéréo"
    def priority(item):
        idx, d = item
        name = d["name"].lower()
        if "réseau de microphones" in name or "mic array" in name:
            return 0  # Micro intégré laptop = top priorité
        if "microphone" in name and "mappeur" not in name and "mixage" not in name:
            return 1  # Micro dédié
        if "realtek" in name and "haut-parleur" not in name and "speaker" not in name:
            return 2  # Realtek input
        if "mappeur" in name or "principal" in name:
            return 5  # Mappeurs génériques
        if "mixage" in name or "stereo" in name:
            return 6  # Mixage stéréo (pas un vrai micro)
        return 3

    input_devices.sort(key=priority)

    # Tester chaque micro
    for dev_id, dev_info in input_devices:
        name = dev_info["name"]
        channels = int(dev_info["max_input_channels"])
        channels = max(1, min(channels, 2))

        try:
            # Essayer d'ouvrir et enregistrer 0.5s
            audio = sd.rec(
                int(0.5 * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=channels,
                device=dev_id,
                dtype="float32",
            )
            sd.wait()

            # Vérifier que le stream s'est ouvert sans erreur
            log(f"  [{dev_id}] {name} → OK ✓")
            return dev_id, channels

        except Exception as e:
            log(f"  [{dev_id}] {name} → échec ({e})")
            continue

    log("  ✗ Aucun micro fonctionnel trouvé !")
    return None, 1


# ── Utilitaires ──────────────────────────────────────────────

def get_mouse_button(name: str):
    """Convertit le nom du bouton souris en objet pynput."""
    mapping = {
        "x1": mouse.Button.x1,
        "x2": mouse.Button.x2,
        "middle": mouse.Button.middle,
    }
    return mapping.get(name.lower(), mouse.Button.x2)


def play_beep(freq, duration_ms):
    """Joue un bip sonore en arrière-plan (Windows uniquement)."""
    if not SOUND_ENABLED:
        return
    try:
        import winsound
        threading.Thread(
            target=winsound.Beep, args=(freq, duration_ms), daemon=True
        ).start()
    except Exception:
        pass


def create_tray_icon(color, size=64):
    """Crée une icône ronde colorée pour le system tray."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
        outline=(255, 255, 255, 200),
        width=2,
    )
    cx, cy = size // 2, size // 2
    draw.rounded_rectangle(
        [cx - 6, cy - 14, cx + 6, cy + 2],
        radius=6,
        fill=(255, 255, 255, 220),
    )
    draw.line([cx, cy + 2, cx, cy + 10], fill=(255, 255, 255, 220), width=2)
    draw.line([cx - 6, cy + 10, cx + 6, cy + 10], fill=(255, 255, 255, 220), width=2)
    draw.arc(
        [cx - 10, cy - 6, cx + 10, cy + 6],
        start=0, end=180,
        fill=(255, 255, 255, 180),
        width=2,
    )
    return img


# ── Application principale ───────────────────────────────────

class VoiceTyper:
    """Application principale de dictée vocale."""

    def __init__(self):
        self.is_recording = False
        self.is_processing = False
        self.audio_queue = queue.Queue()  # Thread-safe, sans alloc dynamique dans le callback
        self.stream = None
        self.model = None
        self.ptt_button = get_mouse_button(MOUSE_BUTTON)
        self._record_channels = 1
        self._mouse_hook = None   # Hook souris bas niveau (mode mouse)

        # Auto-détection du micro si besoin
        global AUDIO_DEVICE
        if AUDIO_DEVICE == "auto":
            detected_id, detected_channels = auto_detect_microphone()
            if detected_id is not None:
                AUDIO_DEVICE = detected_id
                self._record_channels = detected_channels
                log(f"✓ Micro sélectionné : device {AUDIO_DEVICE}")
            else:
                log("  ⚠ Auto-détection échouée, utilisation du micro par défaut")
                AUDIO_DEVICE = None
        else:
            # Device manuel : récupérer le nombre de canaux
            try:
                info = sd.query_devices(AUDIO_DEVICE, kind="input")
                self._record_channels = max(1, min(int(info["max_input_channels"]), 2))
            except Exception:
                self._record_channels = 1
        log("")

        # Vocabulaire custom
        self.vocab = VocabManager(VOCAB_FILE)

        self.is_paused = False

        # Icônes pour le tray
        self.icon_idle = create_tray_icon((100, 100, 100))       # Gris
        self.icon_loading = create_tray_icon((200, 200, 50))     # Jaune (chargement)
        self.icon_recording = create_tray_icon((220, 40, 40))    # Rouge
        self.icon_processing = create_tray_icon((40, 120, 220))  # Bleu
        self.icon_paused = create_tray_icon((200, 130, 20))      # Orange (pause)

        # System tray
        self.tray = pystray.Icon(
            name="VoiceTyper",
            icon=self.icon_loading,
            title="VoiceTyper — Chargement du modèle...",
            menu=pystray.Menu(
                pystray.MenuItem("VoiceTyper v1.3", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    f"Mode: {PTT_MODE} ({MOUSE_BUTTON if PTT_MODE == 'mouse' else 'ctrl_r'})",
                    None,
                    enabled=False,
                ),
                pystray.MenuItem(f"Modèle: {WHISPER_MODEL}", None, enabled=False),
                pystray.MenuItem(
                    f"Vocab: {len(self.vocab.hint_words)} mots",
                    None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    lambda item: "▶ Reprendre" if self.is_paused else "⏸ Mettre en pause",
                    self._toggle_pause,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quitter", self._quit),
            ),
        )

    # ── Chargement du modèle ─────────────────────────────────

    def _load_model(self):
        """Charge le modèle Whisper (peut prendre du temps au 1er lancement)."""
        log("=" * 50)
        log("  VoiceTyper — Chargement du modèle Whisper")
        log(f"  Modèle : {WHISPER_MODEL} | Device : {WHISPER_DEVICE}")
        log("=" * 50)
        log("")

        if WHISPER_DEVICE == "cuda":
            log("  Utilisation du GPU (CUDA)")
        else:
            log("  Utilisation du CPU (plus lent)")

        log(f"  Téléchargement/chargement de '{WHISPER_MODEL}'...")
        log("  (Le 1er lancement télécharge le modèle ~3 Go)")
        log("")

        # Ajustement automatique du compute_type pour CPU
        # float16 n'est pas supporté par CTranslate2 sur CPU → fallback sur int8
        actual_compute_type = COMPUTE_TYPE
        if WHISPER_DEVICE == "cpu" and COMPUTE_TYPE == "float16":
            actual_compute_type = "int8"
            log("  ⚠ Avertissement : float16 incompatible avec CPU → bascule automatique sur int8")

        try:
            self.model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=actual_compute_type,
            )
            log("  ✓ Modèle chargé avec succès ")
            log("")
            self._set_idle()
            self._print_ready()
        except Exception as e:
            log(f"\n  ✗ Erreur au chargement du modèle : {e}")
            log("  Vérifie que CUDA est bien installé (nvidia-smi)")
            log("  Ou change WHISPER_DEVICE = 'cpu' dans la config")
            self.tray.title = "VoiceTyper — ERREUR"
            return

    def _print_ready(self):
        """Affiche les infos de fonctionnement."""
        log("  ┌──────────────────────────────────────────┐")
        log("  │          VoiceTyper v1.3 prêt            │")
        log("  ├──────────────────────────────────────────┤")
        if PTT_MODE == "mouse":
            btn_name = "avant (x2)" if MOUSE_BUTTON == "x2" else "arrière (x1)"
            log(f"  │  Bouton souris {btn_name} = push-to-talk │")
        else:
            log("  │  Ctrl droit = push-to-talk              │")
        log("  │                                          │")
        log("  │  Parle → texte tapé au curseur           │")
        log("  │  Texte sélectionné → remplacé            │")
        log("  │                                          │")
        log("  │             Icône tray  :                │")
        log("  │  Gris=veille | Rouge=écoute | Bleu=transco│")
        log("  │  Orange=pause (terminal détecté ou manuel)│")
        log("  │                                          │")
        log("  │  Vocabulaire : édite vocabulaire.json    │")
        log("  └──────────────────────────────────────────┘")
        log("")

    # ── Enregistrement audio ─────────────────────────────────

    def _open_stream(self):
        """Ouvre le stream audio une seule fois au démarrage et le garde ouvert."""
        try:
            self.stream = sd.InputStream(
                device=AUDIO_DEVICE,
                samplerate=SAMPLE_RATE,
                channels=self._record_channels,
                dtype="float32",
                blocksize=1024,
                callback=self._audio_callback,
            )
            self.stream.start()
            log("✓ Stream audio ouvert en permanence")
        except Exception as e:
            log_err(f"✗ Erreur ouverture stream audio : {e}")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback appelé par sounddevice — collecte uniquement si enregistrement actif.

        queue.put() est non-bloquant et thread-safe : pas d'alloc dynamique de liste
        dans le thread audio haute priorité → élimine les risques de dropout/craquement.
        """
        if self.is_recording:
            self.audio_queue.put(indata.copy())

    def start_recording(self):
        """Démarre la collecte audio (le stream reste ouvert)."""
        if self.is_recording or self.is_processing or self.model is None:
            return

        # Ne pas démarrer si en pause manuelle
        if self.is_paused:
            return

        # Ignorer le PTT si un terminal est au premier plan (mode clavier uniquement)
        if TERMINAL_DETECTION and is_terminal_focused():
            return

        self.is_recording = True
        # Vider la queue des résidus audio avant de commencer
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        # Feedback visuel + sonore
        self.tray.icon = self.icon_recording
        self.tray.title = "VoiceTyper — Enregistrement..."
        play_beep(SOUND_START_FREQ, SOUND_DURATION_MS)

    def stop_recording(self):
        """Arrête la collecte audio et lance la transcription (stream reste ouvert)."""
        if not self.is_recording:
            return

        self.is_recording = False

        play_beep(SOUND_STOP_FREQ, SOUND_DURATION_MS)

        # Lancer la transcription dans un thread séparé
        self.is_processing = True
        self.tray.icon = self.icon_processing
        self.tray.title = "VoiceTyper — Transcription..."
        threading.Thread(target=self._process_audio, daemon=True).start()

    # ── Transcription ────────────────────────────────────────

    def _process_audio(self):
        """Transcrit l'audio enregistré et tape le texte."""
        try:
            # Drainer la queue — récupère tous les chunks sans bloquer
            chunks = []
            while not self.audio_queue.empty():
                try:
                    chunks.append(self.audio_queue.get_nowait())
                except queue.Empty:
                    break

            if not chunks:
                return

            # Assembler les chunks audio
            audio = np.concatenate(chunks, axis=0)
            # Convertir en mono si stéréo (moyenne des canaux)
            if audio.ndim > 1 and audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            else:
                audio = audio.flatten()
            duration = len(audio) / SAMPLE_RATE

            if duration < MIN_DURATION:
                log(f"→ Audio trop court ({duration:.1f}s < {MIN_DURATION}s), ignoré")
                return

            # Amplifier le signal si voix basse
            if AUDIO_GAIN != 1.0:
                audio = audio * AUDIO_GAIN
                audio = np.clip(audio, -1.0, 1.0)

            log(f"→ Transcription de {duration:.1f}s d'audio...")
            start_time = time.time()

            # Construire le prompt initial avec le vocabulaire custom
            initial_prompt = self.vocab.get_initial_prompt()

            # Transcription avec faster-whisper
            segments, info = self.model.transcribe(
                audio,
                language=None,        # Auto-détection FR/EN
                beam_size=2,          # 1-2 = latence /2 à /3, qualité quasi-identique sur voix claire
                initial_prompt=initial_prompt if initial_prompt else None,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=VAD_THRESHOLD,
                    min_silence_duration_ms=200,
                    speech_pad_ms=300,
                    min_speech_duration_ms=100,
                ),
            )

            # Assembler le texte
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)

            text = " ".join(text_parts).strip()

            # Appliquer les remplacements de vocabulaire
            if text:
                text = self.vocab.apply_replacements(text)

            elapsed = time.time() - start_time
            lang = info.language if info else "?"
            prob = f"{info.language_probability:.0%}" if info else "?"

            if text:
                log(f"OK ({elapsed:.1f}s, {lang} {prob})")
                log(f"→ \"{text}\"")
                self._type_text(text)
            else:
                log(f"(aucun texte détecté, {elapsed:.1f}s)")

        except Exception as e:
            log_err(f"✗ Erreur transcription : {e}")
        finally:
            self.is_processing = False
            self._set_idle()

    # ── Frappe du texte ──────────────────────────────────────

    def _type_text(self, text: str):
        """Colle le texte transcrit là où est le curseur via le presse-papiers.

        Utilise exclusivement l'API Windows (win_ctrl_v / win_ctrl_shift_v)
        au lieu de pynput — plus fiable sur les applis lancées en Administrateur.
        """
        if ADD_TRAILING_SPACE:
            text = text + " "

        # Lecture de l'ancien presse-papiers avec retry
        old_clipboard = ""
        for _ in range(3):
            try:
                old_clipboard = pyperclip.paste()
                break
            except Exception:
                time.sleep(0.05)

        try:
            # Copie du texte avec retry
            for attempt in range(3):
                try:
                    pyperclip.copy(text)
                    break
                except Exception:
                    if attempt == 2:
                        log_err("✗ Impossible de copier dans le presse-papiers après 3 essais")
                        return
                    time.sleep(0.05)

            time.sleep(PASTE_DELAY)

            if is_terminal_focused():
                # Dans un terminal, Ctrl+Shift+V est le raccourci standard de collage
                win_ctrl_shift_v()
            else:
                win_ctrl_v()

            time.sleep(PASTE_DELAY)

        except Exception as e:
            log_err(f"✗ Erreur de frappe : {e}")
        finally:
            def restore():
                time.sleep(0.1)   # Réduit de 0.5 → 0.1s : fenêtre de race condition minimisée
                for _ in range(3):
                    try:
                        pyperclip.copy(old_clipboard)
                        break
                    except Exception:
                        time.sleep(0.05)
            threading.Thread(target=restore, daemon=True).start()

    # ── Listeners (souris / clavier) ─────────────────────────

    def _on_mouse_click(self, x, y, button, pressed):
        """Callback pour les clics souris."""
        if button == self.ptt_button:
            if pressed:
                self.start_recording()
            else:
                self.stop_recording()

    def _on_key_press(self, key):
        """Callback pour les touches clavier pressées."""
        if key == KEYBOARD_KEY:
            self.start_recording()

    def _on_key_release(self, key):
        """Callback pour les touches clavier relâchées."""
        if key == KEYBOARD_KEY:
            self.stop_recording()

    # ── Utilitaires ──────────────────────────────────────────

    def _toggle_pause(self, icon=None, item=None):
        """Bascule entre pause et veille active."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.tray.icon = self.icon_paused
            self.tray.title = "VoiceTyper — En pause (clic droit → Reprendre)"
            log("⏸ VoiceTyper mis en pause")
        else:
            self._set_idle()
            log("▶ VoiceTyper repris")

    def _set_idle(self):
        """Remet l'icône en mode veille."""
        if self.is_paused:
            self.tray.icon = self.icon_paused
            self.tray.title = "VoiceTyper — En pause (clic droit → Reprendre)"
        else:
            self.tray.icon = self.icon_idle
            self.tray.title = "VoiceTyper — En veille (prêt)"

    def _quit(self, icon, item):
        """Quitte l'application proprement."""
        log("\n  VoiceTyper arrêté")
        if self._mouse_hook:
            try:
                self._mouse_hook.stop()
            except Exception:
                pass
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        icon.stop()
        os._exit(0)

    # ── Lancement ────────────────────────────────────────────

    def run(self):
        """Lance l'application."""
        # Ouvrir le stream audio une seule fois (évite les clics à chaque push-to-talk)
        self._open_stream()

        # Charger le modèle dans un thread pour ne pas bloquer le tray
        threading.Thread(target=self._load_model, daemon=True).start()

        # Démarrer le listener approprié
        if PTT_MODE == "mouse":
            # Hook bas niveau : x2 supprimé → le terminal ne voit pas le clic
            self._mouse_hook = MouseHook(
                MOUSE_BUTTON,
                on_press=self.start_recording,
                on_release=self.stop_recording,
            )
            self._mouse_hook.start()
            log(f"  → Hook souris bas niveau démarré (bouton {MOUSE_BUTTON} supprimé)")
        else:
            listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            listener.start()
            log("  → Listener clavier démarré")

        # Lancer le tray (bloquant)
        log("  → Lancement du system tray...")
        log("")
        self.tray.run()


# ── Point d'entrée ───────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform != "win32":
        log("VoiceTyper est conçu pour Windows uniquement.")
        sys.exit(1)

    log("")
    log("  ╔═══════════════════════════════════════╗")
    log("  ║        VoiceTyper v1.3                ║")
    log("  ╚═══════════════════════════════════════╝")
    log("")

    app = VoiceTyper()
    app.run()
