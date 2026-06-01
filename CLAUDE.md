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

**Perf observée** : large-v3 sur ce GPU transcrit à RTF ~0,3 (ex. 7,7 s d'audio → 1,8 s) — marge confortable pour du streaming par segments.

**Workflow release** : modifier `voice_typer.py` → tester (terminal + app + admin) → mettre à jour Changelog dans `README.md` → commit + push GitHub

## État actuel

v1.4 : **streaming append-only** livré sur la branche `feat/streaming-dictee` (pas encore mergé dans `master`) — le texte se pose au fil de l'eau (segments, frontière = silence RMS OU durée max 7 s) au lieu d'attendre le relâchement. Réversible via `STREAMING_MODE` ; mode bloc v1.3 conservé à l'identique. `STREAM_SILENCE_RMS` calibré à `0.02` à l'usage (plafond d'un détecteur à seuil fixe — pas perfectible au bouton). Détecteur de frontière testé (`test_segmentation.py`, 5 tests, lancé via le venv du repo principal) ; collage/threads/GPU validés manuellement (pauses, flot continu, terminal, A/B mode bloc).

## Décisions

### 2026-05-31 — Streaming append-only, sans auto-correction
Le texte se pose par segments au fil de l'eau, jamais réécrit. Tue la latence perçue sur les gros textes. Rejeté : auto-correction rétroactive type Apple (fenêtre glissante / LocalAgreement) → re-décodage en boucle + charge GPU + backspaces fragiles (frappe par presse-papier), pour un confort déjà acquis à ~80 % en mode bloc.

### 2026-05-31 — Worktree hors vault via git fallback
Worktree créé par `git worktree add` dans `~/.config/superpowers/worktrees/VoiceTyper/streaming-dictee` (branche `feat/streaming-dictee`). Rejeté : outil natif `EnterWorktree` → cible le repo vault (racine), interdit + mauvais repo. Hors vault → pas de churn Syncthing, master reste la v1.3 intacte. venv existant réutilisé (pas de réinstall des deps).

## Dernière session

**Date** : 2026-06-01
**Fait** :
- Implémenté le streaming append-only (plan `plans/2026-06-01-streaming-dictee-impl.md`)
- `BoundaryDetector` + tests, refactor `_transcribe_audio` / collage incrémental, `_stream_loop` + câblage start/stop, bump v1.4
- Calibrage `STREAM_SILENCE_RMS = 0.02` validé à l'oreille
**État** : terminé — validé manuellement (pauses OK, flot continu OK, ressenti bon)
**Reprise** : merger `feat/streaming-dictee` → `master` puis push GitHub ; supprimer le plan livré
