# CLAUDE.md — VoiceTyper

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
- Avant toute modif hook souris : vérifier non-régression terminal (Claude Code, PowerShell)
- `venv/` ne doit pas être commité

**Workflow release** : modifier `voice_typer.py` → tester (terminal + app + admin) → mettre à jour Changelog dans `README.md` → commit + push GitHub

## État actuel

v1.3 stable, publié sur GitHub. Pas de features en cours.

## Dernière session

**Date** : — (session non datée)
**Fait** :
- Migration vers le nouveau format CLAUDE.md unique (suppression index.md)
- README conservé tel quel (projet publié sur GitHub)
- CLAUDE.md reformaté au nouveau format

**État** : Terminé — index.md supprimé, CLAUDE.md propre
**Reprise** : Aucune action en attente — projet stable v1.3
