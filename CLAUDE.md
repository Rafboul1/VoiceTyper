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
- Lancer via le python du venv en direct (`venv\Scripts\python.exe`), jamais `activate` + `python` : avec plusieurs Python installés, le `python` du PATH ne résout pas le venv (→ `ModuleNotFoundError`)
- `SileroVADModel.__call__` (faster-whisper) réinitialise son état LSTM (h/c) à chaque appel → en streaming, garder le contexte glissant ; passer la fenêtre seule donne un LSTM froid (classification dégradée)

**Perf observée** : large-v3 sur ce GPU transcrit à RTF ~0,3 (ex. 7,7 s d'audio → 1,8 s) — marge confortable pour du streaming par segments.

**Workflow release** : modifier `voice_typer.py` → tester (terminal + app + admin) → mettre à jour Changelog dans `README.md` → commit + push GitHub

## État actuel

v1.5 : **découpage par Silero VAD** livré et en prod (`main` + `master` alignés, GitHub `Rafboul1/VoiceTyper`, commit `9974f42`). Le streaming append-only pose le texte au fil de l'eau ; la frontière de segment est décidée par le VAD Silero (modèle ML embarqué dans faster-whisper, fenêtre glissante + hystérésis) au lieu de l'ancien seuil d'énergie RMS — segments sur de vraies fins d'énoncé, robustes au bruit, indépendants du micro/`AUDIO_GAIN`. Seuil = `STREAM_SPEECH_THRESHOLD = 0.5` (probabilité de parole) ; filet durée max 7 s conservé. Réversible via `STREAMING_MODE` ; mode bloc v1.3 conservé. Tests : `test_segmentation.py` (8 tests, modèle injectable, lancés via le venv du repo) ; validé au micro (pauses plus nettes et plus rapides).

## Décisions

### 2026-06-01 — Silero VAD pour la détection de frontière (remplace le seuil RMS)
Le découpage de segments écoute la *parole* (proba Silero) au lieu du *volume* (RMS). Frontières sur de vraies fins d'énoncé, robustes au bruit de fond, seuil indépendant du micro/`AUDIO_GAIN`. Modèle déjà embarqué dans faster-whisper → zéro nouvelle dépendance. Rejeté : (a) garder le seuil RMS (`STREAM_SILENCE_RMS` — plafond non perfectible au bouton, ne coupe jamais si l'ambiance > seuil) ; (b) LLM de nettoyage type Wispr (ajoute latence + charge GPU + dépendance, hors-sujet pour du 100 % local) ; (c) re-décodage live mot-à-mot (backspaces fragiles via presse-papier — déjà rejeté) ; (d) VAD streaming stateful via `session.run` (couple à l'interne non-public de faster-whisper pour un gain CPU négligeable).

### 2026-05-31 — Streaming append-only, sans auto-correction
Le texte se pose par segments au fil de l'eau, jamais réécrit. Tue la latence perçue sur les gros textes. Rejeté : auto-correction rétroactive type Apple (fenêtre glissante / LocalAgreement) → re-décodage en boucle + charge GPU + backspaces fragiles (frappe par presse-papier), pour un confort déjà acquis à ~80 % en mode bloc.

## Dernière session

**Date** : 2026-06-01
**Fait** :
- Remplacé la détection de frontière RMS par Silero VAD (`SileroClassifier` injectable, fenêtre glissante 1 s + hystérésis ; `BoundaryDetector` refactoré, logique de comptage inchangée)
- Code-review (high) : 2 correctifs (frontière manquée sur reprise dans le même bloc ; race `lru_cache` au warm-up) + test d'hystérésis renforcé ; 1 faux-fix efficiency écarté
- Fix `start.bat` : appel direct du python du venv (corrige `ModuleNotFoundError` multi-Python)
- Bump v1.5, changelog + table params README, 8 tests verts
**État** : fini — v1.5 en prod sur `main` + `master` (commit `9974f42`), validé au micro
**Reprise** : rien en cours. Réglage éventuel à l'usage : `STREAM_SPEECH_THRESHOLD` (0.5).
