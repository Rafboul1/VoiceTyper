# VoiceTyper 

**Dictée vocale locale, gratuite et open-source pour Windows.**

Parle → le texte s'écrit là où est ton curseur. Partout. Dans n'importe quelle app.

Comme [Wispr Flow](https://wispr.com), mais local, gratuit, et tes données 


---

## Comment ça marche

1. Tu maintiens un **bouton de ta souris** (bouton latéral) ou une **touche clavier**
2. Tu parles
3. Tu relâches → le texte est tapé automatiquement là où est ton curseur

C'est du **push-to-talk** : ça n'écoute que quand tu appuies. Pas de micro ouvert en permanence.

### Fonctionnalités

- **System-wide** : fonctionne dans n'importe quelle application (navigateur, Word, VS Code, Discord, Notion...)
- **100% local** : utilise [faster-whisper](https://github.com/SYSTRAN/faster-whisper) sur ton GPU, aucune donnée envoyée sur internet
- **Français + Anglais** : détection automatique de la langue
- **Remplacement de sélection** : sélectionne du texte, parle, et il est remplacé par ta dictée
- **Vocabulaire custom** : ajoute tes noms propres, acronymes et termes techniques pour une meilleure reconnaissance
- **Auto-détection du micro** : trouve automatiquement le bon micro au lancement
- **Push-to-talk** : bouton souris latéral (x1/x2) ou touche clavier configurable
- **Icône system tray** : indicateur visuel discret (gris = veille, rouge = écoute, bleu = transcription)

---

## Prérequis

- **Windows 10/11**
- **Python 3.10+** → [python.org](https://python.org) (coche "Add Python to PATH" à l'installation)
- **GPU NVIDIA** avec au moins 4 Go de VRAM (GTX 1070+ / RTX série)
- **CUDA Toolkit 12.x** → [nvidia.com](https://developer.nvidia.com/cuda-downloads)
- **Drivers NVIDIA à jour**

> Pas de GPU NVIDIA ? Change `WHISPER_DEVICE = "cpu"` dans `voice_typer.py`. C'est plus lent mais ça marche.

---

## Installation

```bash
# 1. Clone le repo
git clone https://github.com/ton-user/VoiceTyper.git
cd VoiceTyper

# 2. Double-clique sur setup.bat
# ou manuellement :
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Le premier lancement télécharge automatiquement le modèle Whisper (~3 Go)

---

## Utilisation

```bash
# Double-clique sur start.bat
# ou manuellement :
venv\Scripts\activate
python voice_typer.py
```

**Par défaut :** maintiens le **bouton latéral avant de ta souris (x2)** pour parler.

### Changer le bouton push-to-talk

Édite `voice_typer.py` en haut du fichier :

```python
# Bouton souris latéral
MOUSE_BUTTON = "x2"    # "x1" = arrière, "x2" = avant

# Ou passe en mode clavier
PTT_MODE = "keyboard"
KEYBOARD_KEY = Key.ctrl_r   # Ctrl droit
```

---

## Vocabulaire custom

Au premier lancement, un fichier `vocabulaire.json` est créé. Édite-le pour ajouter :

```json
{
  "hint_words": [
    "Rafboul",
    "FastAPI",
    "A.E.I."
  ],
  "replacements": {
    "raph boule": "Rafboul",
    "aei": "A.E.I."
  }
}
```

- **hint_words** : mots que Whisper doit reconnaître (noms propres, termes techniques)
- **replacements** : corrections automatiques après transcription

Relance VoiceTyper après modification.

---

## Problème de micro ?

Si VoiceTyper ne capte pas ta voix :

```bash
# Active le venv puis lance le diagnostic
venv\Scripts\Activate.ps1
python test_micro.py
```

Le script liste tous tes micros et teste celui sélectionné. Note le numéro du bon micro, puis dans `voice_typer.py` :

```python
AUDIO_DEVICE = 2   # remplace par ton numéro
```

---

## Configuration

Tout se configure dans les premières lignes de `voice_typer.py` :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `WHISPER_MODEL` | `"large-v3"` | Modèle Whisper (`"medium"` = plus rapide, `"large-v3"` = meilleure qualité) |
| `WHISPER_DEVICE` | `"cuda"` | `"cuda"` pour GPU, `"cpu"` sinon |
| `AUDIO_DEVICE` | `"auto"` | `"auto"` ou numéro du micro |
| `AUDIO_GAIN` | `3.0` | Amplification du volume (1.0 = normal, augmente si voix basse) |
| `PTT_MODE` | `"mouse"` | `"mouse"` ou `"keyboard"` |
| `MOUSE_BUTTON` | `"x2"` | `"x1"` (arrière) ou `"x2"` (avant) |
| `SOUND_ENABLED` | `False` | Bip sonore au début/fin d'enregistrement |

---

## Stack technique

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper optimisé GPU via CTranslate2
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Capture audio
- [pynput](https://pynput.readthedocs.io/) — Détection souris/clavier
- [pystray](https://github.com/moses-palmer/pystray) — Icône system tray
- [pyperclip](https://github.com/asweigart/pyperclip) — Presse-papiers

---

## Licence

MIT — fais-en ce que tu veux.

---

## Auteur

Créé par [@Rafboul](https://twitter.com/Rafboul) — étudiant ingénieur LLM
