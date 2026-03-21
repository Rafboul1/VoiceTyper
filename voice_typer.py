"""
VoiceTyper v1.1 - Dictée vocale locale push-to-talk pour Windows
=================================================================
Utilise faster-whisper sur GPU pour transcrire ta voix en texte
partout sur ton PC (system-wide).

Maintiens le bouton souris (côté) ou une touche → parle → relâche → le texte est tapé.
Si du texte est sélectionné, il est remplacé par la transcription.

Auteur: @Rafboul 
"""

import sys
import os
import threading
import time
import ctypes
import ctypes.wintypes
import json
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller as KBController
import pystray
from PIL import Image, ImageDraw
import pyperclip


# ╔══════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION — Modifie ici selon tes préférences          ║
# ╚══════════════════════════════════════════════════════════════╝

# --- Whisper (modèle de transcription) ---
WHISPER_MODEL = "large-v3"       # "medium" = plus rapide, "large-v3" = meilleure qualité
WHISPER_DEVICE = "cuda"          # "cuda" pour GPU (recommandé), "cpu" sinon
COMPUTE_TYPE = "float16"         # "float16" pour GPU, "int8" pour CPU

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
MOUSE_BUTTON = "x2"

# Touche clavier (si PTT_MODE = "keyboard") : utilise le nom pynput
# Exemples : Key.scroll_lock, Key.pause, Key.f24, Key.ctrl_r
KEYBOARD_KEY = Key.ctrl_r

# --- Sons de feedback ---
SOUND_ENABLED = False            # True = bip sonore quand on commence/arrête
SOUND_START_FREQ = 700           # Fréquence du bip de début (Hz)
SOUND_STOP_FREQ = 400            # Fréquence du bip de fin (Hz)
SOUND_DURATION_MS = 80           # Durée du bip (ms)

# --- Sensibilité micro ---
AUDIO_GAIN = 3.0                 # Amplification du volume (1.0 = normal, 2-4 = voix basse)

# --- Divers ---
PASTE_DELAY = 0.05               # Délai avant de coller le texte (secondes)
ADD_TRAILING_SPACE = True        # Ajouter un espace après le texte transcrit

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
    # "Rafboul", "FastAPI",
]

# Dictionnaire de remplacement APRÈS transcription.
# Si Whisper transcrit mal un mot, corrige-le ici.
# Format : "ce_que_whisper_dit": "ce_que_tu_veux"
# La recherche est insensible à la casse.
DEFAULT_REPLACEMENTS = {
    # Exemples (remplace par les tiens) :
    # "rafboul": "Rafboul",
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  CODE PRINCIPAL — Pas besoin de toucher en dessous           ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Windows API pour Ctrl+V fiable ───────────────────────────

user32 = ctypes.windll.user32

VK_CONTROL = 0x11
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


# ── Vocabulaire ──────────────────────────────────────────────

class VocabManager:
    """Gère le vocabulaire personnalisé et les remplacements."""

    def __init__(self, vocab_file):
        self.vocab_file = vocab_file
        self.hint_words = list(HINT_WORDS)
        self.replacements = dict(DEFAULT_REPLACEMENTS)
        self._load()

    def _load(self):
        """Charge le vocabulaire depuis le fichier JSON."""
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
                print(f"  ✓ Vocabulaire chargé : {len(self.hint_words)} mots, {len(self.replacements)} remplacements")
            except Exception as e:
                print(f"  ⚠ Erreur lecture vocabulaire : {e}")
        else:
            self._save_default()

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
            ],
            "replacements": self.replacements if self.replacements else {
                "# exemple_whisper_dit": "# ce_que_tu_veux",
            },
        }
        try:
            with open(self.vocab_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✓ Fichier vocabulaire créé : {self.vocab_file}")
            print("    Édite-le pour ajouter tes mots persos !")
        except Exception as e:
            print(f"  ⚠ Impossible de créer {self.vocab_file} : {e}")

    def get_initial_prompt(self) -> str:
        """Construit le prompt initial pour Whisper avec les mots à reconnaître."""
        # Filtrer les commentaires (lignes commençant par #)
        words = [w for w in self.hint_words if not w.startswith("#")]
        if not words:
            return ""
        # Whisper utilise le prompt initial comme contexte pour mieux reconnaître
        return ", ".join(words) + ". "

    def apply_replacements(self, text: str) -> str:
        """Applique les remplacements de vocabulaire sur le texte transcrit."""
        if not self.replacements:
            return text
        for wrong, correct in self.replacements.items():
            if wrong.startswith("#"):
                continue
            # Remplacement insensible à la casse mais préserve la structure
            import re
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            text = pattern.sub(correct, text)
        return text


# ── Auto-détection du micro ───────────────────────────────────

def auto_detect_microphone():
    """Détecte automatiquement le meilleur micro disponible.

    Teste chaque device d'entrée en enregistrant 0.5s de son.
    Retourne le device_id et le nombre de canaux du premier micro qui fonctionne.
    Priorité : micros Realtek / intégrés > autres.
    """
    print("  🔍 Auto-détection du micro...")
    devs = sd.query_devices()

    # Collecter tous les devices d'entrée
    input_devices = []
    for i, d in enumerate(devs):
        if d["max_input_channels"] > 0:
            input_devices.append((i, d))

    if not input_devices:
        print("  ✗ Aucun micro détecté !")
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
            print(f"    [{dev_id}] {name} → OK ✓")
            return dev_id, channels

        except Exception as e:
            print(f"    [{dev_id}] {name} → échec ({e})")
            continue

    print("  ✗ Aucun micro fonctionnel trouvé !")
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
        self.audio_chunks = []
        self.stream = None
        self.model = None
        self.kb = KBController()
        self.ptt_button = get_mouse_button(MOUSE_BUTTON)
        self.selected_text_on_start = None
        self._record_channels = 1

        # Auto-détection du micro si besoin
        global AUDIO_DEVICE
        if AUDIO_DEVICE == "auto":
            detected_id, detected_channels = auto_detect_microphone()
            if detected_id is not None:
                AUDIO_DEVICE = detected_id
                self._record_channels = detected_channels
                print(f"  ✓ Micro sélectionné : device {AUDIO_DEVICE}")
            else:
                print("  ⚠ Auto-détection échouée, utilisation du micro par défaut")
                AUDIO_DEVICE = None
        else:
            # Device manuel : récupérer le nombre de canaux
            try:
                info = sd.query_devices(AUDIO_DEVICE, kind="input")
                self._record_channels = max(1, min(int(info["max_input_channels"]), 2))
            except Exception:
                self._record_channels = 1
        print()

        # Vocabulaire custom
        self.vocab = VocabManager(VOCAB_FILE)

        # Icônes pour le tray
        self.icon_idle = create_tray_icon((100, 100, 100))       # Gris
        self.icon_loading = create_tray_icon((255, 165, 0))      # Orange
        self.icon_recording = create_tray_icon((220, 40, 40))    # Rouge
        self.icon_processing = create_tray_icon((40, 120, 220))  # Bleu

        # System tray
        self.tray = pystray.Icon(
            name="VoiceTyper",
            icon=self.icon_loading,
            title="VoiceTyper — Chargement du modèle...",
            menu=pystray.Menu(
                pystray.MenuItem("VoiceTyper v1.1", None, enabled=False),
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
                pystray.MenuItem("Quitter", self._quit),
            ),
        )

    # ── Chargement du modèle ─────────────────────────────────

    def _load_model(self):
        """Charge le modèle Whisper (peut prendre du temps au 1er lancement)."""
        print("=" * 50)
        print("  VoiceTyper — Chargement du modèle Whisper")
        print(f"  Modèle : {WHISPER_MODEL} | Device : {WHISPER_DEVICE}")
        print("=" * 50)
        print()

        if WHISPER_DEVICE == "cuda":
            print("  Utilisation du GPU (CUDA)")
        else:
            print("  Utilisation du CPU (plus lent)")

        print(f"  Téléchargement/chargement de '{WHISPER_MODEL}'...")
        print("  (Le 1er lancement télécharge le modèle ~3 Go)")
        print()

        try:
            self.model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=COMPUTE_TYPE,
            )
            print("  ✓ Modèle chargé avec succès ")
            print()
            self._set_idle()
            self._print_ready()
        except Exception as e:
            print(f"\n  ✗ Erreur au chargement du modèle : {e}")
            print("  Vérifie que CUDA est bien installé (nvidia-smi)")
            print("  Ou change WHISPER_DEVICE = 'cpu' dans la config")
            self.tray.title = "VoiceTyper — ERREUR"
            return

    def _print_ready(self):
        """Affiche les infos de fonctionnement."""
        print("  ┌──────────────────────────────────────────┐")
        print("  │          VoiceTyper v1.1 prêt            │")
        print("  ├──────────────────────────────────────────┤")
        if PTT_MODE == "mouse":
            btn_name = "avant (x2)" if MOUSE_BUTTON == "x2" else "arrière (x1)"
            print(f"  │  Bouton souris {btn_name} = push-to-talk │")
        else:
            print(f"  │  Ctrl droit = push-to-talk              │")
        print("  │                                          │")
        print("  │  Parle → texte tapé au curseur           │")
        print("  │  Texte sélectionné → remplacé            │")
        print("  │                                          │")
        print("  │             Icône tray  :                │")
        print("  │    Gris = veille | Rouge = écoute        │")
        print("  │    Bleu = transcription                  │")
        print("  │                                          │")
        print("  │  Vocabulaire : édite vocabulaire.json    │")
        print("  └──────────────────────────────────────────┘")
        print()

    # ── Capture de la sélection ──────────────────────────────

    def _capture_selection(self):
        """Capture le texte actuellement sélectionné via Ctrl+C."""
        try:
            # Sauvegarder le presse-papiers actuel
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        try:
            # Vider le presse-papiers
            pyperclip.copy("")
            time.sleep(0.02)

            # Ctrl+C pour copier la sélection
            win_ctrl_c()
            time.sleep(0.08)  # Laisser le temps au Ctrl+C

            # Vérifier si quelque chose a été copié
            current = pyperclip.paste()

            if current and current != old_clipboard:
                self.selected_text_on_start = current
                print(f"  → Texte sélectionné détecté ({len(current)} car.) → sera remplacé")
            else:
                self.selected_text_on_start = None

            # Restaurer le presse-papiers original
            pyperclip.copy(old_clipboard)

        except Exception:
            self.selected_text_on_start = None

    # ── Enregistrement audio ─────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback appelé par sounddevice pour chaque chunk audio."""
        if self.is_recording:
            self.audio_chunks.append(indata.copy())

    def start_recording(self):
        """Démarre l'enregistrement audio."""
        if self.is_recording or self.is_processing or self.model is None:
            return

        # Capturer la sélection AVANT de commencer l'enregistrement
        self._capture_selection()

        self.is_recording = True
        self.audio_chunks = []

        # Feedback visuel + sonore
        self.tray.icon = self.icon_recording
        self.tray.title = "VoiceTyper — Enregistrement..."
        play_beep(SOUND_START_FREQ, SOUND_DURATION_MS)

        # Démarrer le flux audio
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
        except Exception as e:
            print(f"  ✗ Erreur micro : {e}")
            self.is_recording = False
            self._set_idle()

    def stop_recording(self):
        """Arrête l'enregistrement et lance la transcription."""
        if not self.is_recording:
            return

        self.is_recording = False

        # Arrêter le flux audio
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

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
            if not self.audio_chunks:
                return

            # Assembler les chunks audio
            audio = np.concatenate(self.audio_chunks, axis=0)
            # Convertir en mono si stéréo (moyenne des canaux)
            if audio.ndim > 1 and audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            else:
                audio = audio.flatten()
            duration = len(audio) / SAMPLE_RATE

            if duration < MIN_DURATION:
                print(f"  → Audio trop court ({duration:.1f}s < {MIN_DURATION}s), ignoré")
                return

            # Amplifier le signal si voix basse
            if AUDIO_GAIN != 1.0:
                audio = audio * AUDIO_GAIN
                audio = np.clip(audio, -1.0, 1.0)

            print(f"  → Transcription de {duration:.1f}s d'audio...", end=" ", flush=True)
            start_time = time.time()

            # Construire le prompt initial avec le vocabulaire custom
            initial_prompt = self.vocab.get_initial_prompt()

            # Transcription avec faster-whisper
            segments, info = self.model.transcribe(
                audio,
                language=None,        # Auto-détection FR/EN
                beam_size=5,
                best_of=5,
                initial_prompt=initial_prompt if initial_prompt else None,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.3,
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
                mode = "REMPLACE" if self.selected_text_on_start else "INSERT"
                print(f"OK ({elapsed:.1f}s, {lang} {prob}) [{mode}]")
                print(f"  → \"{text}\"")
                self._type_text(text)
            else:
                print(f"(aucun texte détecté, {elapsed:.1f}s)")

        except Exception as e:
            print(f"\n  ✗ Erreur transcription : {e}")
        finally:
            self.is_processing = False
            self.selected_text_on_start = None
            self._set_idle()

    # ── Frappe du texte ──────────────────────────────────────

    def _type_text(self, text: str):
        """Tape le texte là où est le curseur. Remplace la sélection si il y en avait une."""
        if ADD_TRAILING_SPACE and not self.selected_text_on_start:
            # Pas d'espace trailing en mode remplacement
            text = text + " "

        # Sauvegarder le presse-papiers actuel
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        try:
            # Si du texte était sélectionné, on doit re-sélectionner
            # car le clic souris a pu désélectionner
            if self.selected_text_on_start:
                # Stratégie : on utilise Ctrl+Z pour annuler la désélection
                # potentielle, puis on re-sélectionne via recherche du texte
                # Approche plus simple et fiable : on utilise le fait que
                # la plupart des apps gardent la position du curseur.
                # On sélectionne en arrière la longueur du texte original.
                sel_len = len(self.selected_text_on_start)

                # Shift+Home puis Shift+End ne marche pas universellement.
                # Méthode la plus fiable : copier le texte sélectionné dans
                # le clipboard et faire Ctrl+V directement.
                # Si la sélection est encore active → Ctrl+V la remplace.
                # Si la sélection a été perdue → on tape quand même le texte.
                pass

            # Copier le texte transcrit dans le presse-papiers
            pyperclip.copy(text)
            time.sleep(PASTE_DELAY)

            # Coller via Windows API (plus fiable que pynput)
            win_ctrl_v()

            time.sleep(PASTE_DELAY)

        except Exception as e:
            print(f"  ✗ Erreur de frappe : {e}")
        finally:
            # Restaurer le presse-papiers après un court délai
            def restore():
                time.sleep(0.5)
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

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

    def _set_idle(self):
        """Remet l'icône en mode veille."""
        self.tray.icon = self.icon_idle
        self.tray.title = "VoiceTyper — En veille (prêt)"

    def _quit(self, icon, item):
        """Quitte l'application proprement."""
        print("\n  VoiceTyper arrêté")
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
        # Charger le modèle dans un thread pour ne pas bloquer le tray
        threading.Thread(target=self._load_model, daemon=True).start()

        # Démarrer le listener approprié
        if PTT_MODE == "mouse":
            listener = mouse.Listener(on_click=self._on_mouse_click)
            listener.start()
            print("  → Listener souris démarré")
        else:
            listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            listener.start()
            print("  → Listener clavier démarré")

        # Lancer le tray (bloquant)
        print("  → Lancement du system tray...")
        print()
        self.tray.run()


# ── Point d'entrée ───────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform != "win32":
        print("VoiceTyper est conçu pour Windows uniquement.")
        sys.exit(1)

    print()
    print("  ╔═══════════════════════════════════════╗")
    print("  ║        VoiceTyper v1.1                ║")
    print("  ╚═══════════════════════════════════════╝")
    print()

    app = VoiceTyper()
    app.run()
