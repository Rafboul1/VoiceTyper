# AGENTS.md — VoiceTyper

## Projet

Dictée vocale locale Windows via faster-whisper (Whisper large-v3 GPU). Push-to-talk souris ou clavier, system-wide, 100% local, open-source MIT.

- **Code** : `C:\Vault\Projects\VOICE_TYPER\`
- **Type** : gros projet — repo GitHub `Rafboul1/VoiceTyper` (README.md séparé)

## Stack & Architecture

| Fichier | Rôle |
|---------|------|
| `voice_typer.py` | Script principal (config en haut du fichier) |
| `requirements.txt` | Dépendances pip |
| `setup.bat` | Crée le venv + installe les dépendances |
| `start.bat` | Lance avec console (debug) |
| `start_silencieux.bat` | Lance en background (usage quotidien) |
| `test_micro.py` | Diagnostic micro |
| `vocabulaire.json` | hint_words + replacements custom |

**Architecture interne**
- Hook souris : `SetWindowsHookEx` Windows API (annule la propagation, compatible terminal)
- Transcription : `faster-whisper` + CTranslate2 sur CUDA
- Audio : `sounddevice` + `queue.Queue` (thread-safe, sans dropout)
- Frappe : Windows API native `win_ctrl_v()` / `win_ctrl_shift_v()` (compatible apps Admin)
- Tray : `pystray`

**Paramètres clés** (haut de `voice_typer.py`)
- `WHISPER_MODEL` : `"large-v3"` — `WHISPER_DEVICE` : `"cuda"` / `"cpu"`
- `PTT_MODE` : `"mouse"` / `"keyboard"` — `MOUSE_BUTTON` : `"x1"` / `"x2"`
- `VAD_THRESHOLD` : `0.5` (anti-hallucinations) — `TERMINAL_DETECTION` : `False`

**Contraintes**
- Toujours tester les modifs hook dans un terminal ET une app standard
- Avant toute modif hook souris : vérifier non-régression terminal (Codex, Claude Code, PowerShell)
- `venv/` ne doit pas être commité
- Lancer via le python du venv en direct (`venv\Scripts\python.exe`), jamais `activate` + `python` : avec plusieurs Python installés, le `python` du PATH ne résout pas le venv (→ `ModuleNotFoundError`)
- `SileroVADModel.__call__` (faster-whisper) réinitialise son état LSTM (h/c) à chaque appel → en streaming, garder le contexte glissant ; passer la fenêtre seule donne un LSTM froid (classification dégradée)

**Perf observée** : large-v3 sur ce GPU transcrit à RTF ~0,3 (ex. 7,7 s d'audio → 1,8 s) — marge confortable pour du streaming par segments.

**Workflow release** : modifier `voice_typer.py` → tester (terminal + app + admin) → mettre à jour Changelog dans `README.md` → commit + push GitHub

## Continuité

- À chaque reprise, lire `STATUS.md` avant d'agir.
- Consulter `JOURNAL.md` uniquement pour retracer une décision ou une ancienne session.
- Garder ici seulement les règles durables ; l'état courant et l'historique n'appartiennent pas à ce fichier.
