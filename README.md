# VoiceTyper

**Dictée vocale locale, gratuite et open-source pour Windows.**

Parle → le texte s'écrit là où est ton curseur. Partout. Dans n'importe quelle app.

Comme [Wispr Flow](https://wispr.com), mais local, gratuit, et tes données reste sur ta machine


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
- **Vocabulaire custom** : ajoute tes noms propres, acronymes et termes techniques pour une meilleure reconnaissance
- **Auto-détection du micro** : trouve automatiquement le bon micro au lancement
- **Push-to-talk** : bouton souris latéral (x1/x2) ou touche clavier configurable
- **Icône system tray** : indicateur visuel discret (gris = veille, rouge = écoute, bleu = transcription, orange = pause)
- **Compatible terminal** : en mode souris, le bouton x1/x2 est intercepté via un hook Windows natif — le terminal ne reçoit jamais le clic, donc pas de navigation parasite. Dicte directement dans Claude Code, PowerShell, etc.
- **Pause manuelle** : clic droit sur l'icône → "Mettre en pause" / "Reprendre"

---

## Prérequis

- **Windows 10/11**
- **Python 3.10+** → [python.org](https://python.org) (coche "Add Python to PATH" à l'installation)
- **GPU NVIDIA** avec au moins 4 Go de VRAM (GTX 1070+ / RTX série)
- **CUDA Toolkit 12.x** → [nvidia.com](https://developer.nvidia.com/cuda-downloads)
- **Drivers NVIDIA à jour**

> Pas de GPU NVIDIA ? Change `WHISPER_DEVICE = "cpu"` dans `voice_typer.py`. C'est plus lent mais ça marche

---

## Installation

```bash
# 1. Clone le repo
git clone https://github.com/Rafboul1/VoiceTyper.git
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

### Avec fenêtre console (pour déboguer)
```bash
# Double-clique sur start.bat
```

### Sans fenêtre — mode quotidien (recommandé)
```bash
# Double-clique sur start_silencieux.bat
```
VoiceTyper tourne en arrière-plan, seule l'icône dans le tray est visible. Suffit de le mettre dans le dossier Démarrage Windows pour un lancement automatique au boot (`Windows + R` → `shell:startup`).

### Voir les logs en cas de problème
```bash
# Double-clique sur voir_logs.bat
```
Ouvre le fichier `voice_typer.log` dans le Bloc-notes, toutes les transcriptions et erreurs y sont enregistrées.

---

**Par défaut :** maintiens le **bouton latéral avant de ta souris (x2)** pour parler

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

## Utilisation avec des terminaux (Claude Code, PowerShell...)

En mode souris (x1/x2), VoiceTyper utilise un **hook Windows natif bas niveau** (`SetWindowsHookEx`). Quand tu appuies sur x2 :

1. VoiceTyper capture l'événement en premier
2. Il retourne `1` → Windows annule la propagation
3. Le terminal ne reçoit jamais le clic → **aucune navigation parasite**

Tu peux donc dicter directement dans un terminal, dans Claude Code, dans n'importe quelle app — sans aucun conflit.

### Pause manuelle

Si tu veux désactiver temporairement le PTT : clic droit sur l'icône tray → **⏸ Mettre en pause**. L'icône passe en orange.
Clic droit → **▶ Reprendre** pour revenir en mode normal.

### Option : ignorer le PTT quand un terminal est au premier plan (mode clavier)

Si tu utilises `PTT_MODE = "keyboard"`, la suppression bas niveau n'est pas disponible. Dans ce cas tu peux activer la détection de fenêtre :

```python
TERMINAL_DETECTION = True   # Ignore le PTT si terminal actif
TERMINAL_BLACKLIST = {
    "windowsterminal.exe",
    "cmd.exe",
    "powershell.exe",
    # ...
}
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

Relance VoiceTyper après modification

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
| `COMPUTE_TYPE` | `"float16"` | Précision GPU : `"float16"` = max qualité, `"int8_float16"` = plus rapide. Basculé automatiquement sur `"int8"` si `WHISPER_DEVICE = "cpu"` |
| `VAD_THRESHOLD` | `0.5` | Seuil de détection vocale : `0.3` = très sensible, `0.5` = recommandé, `0.7` = strict |
| `TERMINAL_DETECTION` | `False` | Ignorer le PTT quand un terminal est au premier plan (fonctionne en mode souris ET clavier) |
| `TERMINAL_BLACKLIST` | voir code | Liste des processus terminaux à exclure |

---

## Changelog

### v1.3 — Optimisations fiabilité & performance

**Fiabilité**

- **Frappe via Windows API** : `_type_text` utilise désormais exclusivement `win_ctrl_v()` / `win_ctrl_shift_v()` (API Windows native) au lieu de `pynput`. Plus de problèmes de collage sur les applications lancées en mode Administrateur.
- **`TERMINAL_DETECTION` maintenant effectif** : la variable était déclarée mais jamais lue. Elle bloque désormais `start_recording` si un terminal est au premier plan — en plus du bon raccourci de collage (`Ctrl+Shift+V`) déjà actif dans `_type_text`.
- **Crash CPU corrigé** : `COMPUTE_TYPE = "float16"` avec `WHISPER_DEVICE = "cpu"` faisait crasher CTranslate2. Bascule automatique sur `"int8"` détectée au chargement, avec un log d'avertissement.
- **Architecture audio sans dropout** : le callback `_audio_callback` utilisait `list.append()` dans un thread haute priorité (risque de blocage GIL → craquements audio). Remplacé par `queue.Queue` — `put()` est non-bloquant et thread-safe.
- **Retry presse-papiers** : les appels `pyperclip.copy()` et `paste()` sont entourés d'une boucle retry ×3 (50 ms entre essais) pour absorber les verrouillages brefs du presse-papiers Windows.

**Performance**

- **Latence Whisper réduite** : `beam_size` réduit de 5 à 2. Temps de transcription divisé par 2-3, qualité quasi-identique sur de la dictée vocale claire.
- **Regex pré-compilées** : les patterns de remplacement du `VocabManager` sont compilés une seule fois au chargement (dans `_load()`), plus à chaque transcription.
- **Restauration presse-papiers accélérée** : délai de restauration réduit de 500 ms à 100 ms — la fenêtre de race condition est minimisée.
- **MouseHook sans threads inutiles** : les callbacks `on_press` / `on_release` sont appelés directement dans le hook (synchrone) au lieu de spawner un nouveau thread à chaque clic. `start_recording` ne fait que changer des booléens — pas besoin d'isolation.

**Nouveau paramètre configurable**

- `VAD_THRESHOLD = 0.5` — seuil de détection vocale (était hardcodé à `0.3`). Réduit les hallucinations Whisper sur les souffles et bruits mécaniques.

### v1.2 — Compatibilité terminal & pause manuelle

**Compatibilité terminal (fix majeur)**

- **Hook souris natif** : abandonne `pynput` au profit de `SetWindowsHookEx` (Windows API). Le clic x1/x2 est désormais capturé *et annulé* avant d'atteindre Windows Terminal — aucune navigation parasite, dictée possible directement dans Claude Code, PowerShell, etc.
- **Suppression du Ctrl+C** : `_capture_selection()` envoyait un Ctrl+C réel à chaque démarrage d'enregistrement pour détecter du texte sélectionné. Dans un terminal, Ctrl+C = interruption de process — ça coupait la session Claude Code. Supprimé.
- **Feature "remplacement de sélection" supprimée** : dépendante du Ctrl+C, non fonctionnelle en pratique. Retirée proprement.
- **Collage adapté aux terminaux** : Windows Terminal utilise `Ctrl+Shift+V` (pas `Ctrl+V`). VoiceTyper détecte maintenant si la fenêtre active est un terminal et utilise le bon raccourci automatiquement.

**Nouvelle fonctionnalité**

- **Pause manuelle** : clic droit sur l'icône tray → **⏸ Mettre en pause** / **▶ Reprendre**. L'icône passe en orange quand le PTT est suspendu.

---

## Stack technique

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper optimisé GPU via CTranslate2
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Capture audio
- [pynput](https://pynput.readthedocs.io/) — Détection clavier (mode keyboard)
- [pystray](https://github.com/moses-palmer/pystray) — Icône system tray
- [pyperclip](https://github.com/asweigart/pyperclip) — Presse-papiers
- Windows API (`ctypes`) — Hook souris bas niveau (`SetWindowsHookEx`), simulation clavier (`win_ctrl_v`), détection de fenêtre active

---

## Licence

MIT — fais-en ce que tu veux

---

## Auteur

Créé par [@Rafboul](https://twitter.com/Rafboul) — étudiant ingénieur LLM (Built with Claude)
