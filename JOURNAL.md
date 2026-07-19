# JOURNAL — VoiceTyper

## 2026-06-01 — Continuité précédente [archive STATUS]

**Mis à jour** : 2026-06-01

### Maintenant

v1.5 : **découpage par Silero VAD** livré et en prod (`main` + `master` alignés, GitHub `Rafboul1/VoiceTyper`, commit `9974f42`). Le streaming append-only pose le texte au fil de l'eau ; la frontière de segment est décidée par le VAD Silero (modèle ML embarqué dans faster-whisper, fenêtre glissante + hystérésis) au lieu de l'ancien seuil d'énergie RMS — segments sur de vraies fins d'énoncé, robustes au bruit, indépendants du micro/`AUDIO_GAIN`. Seuil = `STREAM_SPEECH_THRESHOLD = 0.5` (probabilité de parole) ; filet durée max 7 s conservé. Réversible via `STREAMING_MODE` ; mode bloc v1.3 conservé. Tests : `test_segmentation.py` (8 tests, modèle injectable, lancés via le venv du repo) ; validé au micro (pauses plus nettes et plus rapides).

### Dernière session

**Date** : 2026-06-01
**Fait** :
- Remplacé la détection de frontière RMS par Silero VAD (`SileroClassifier` injectable, fenêtre glissante 1 s + hystérésis ; `BoundaryDetector` refactoré, logique de comptage inchangée)
- Code-review (high) : 2 correctifs (frontière manquée sur reprise dans le même bloc ; race `lru_cache` au warm-up) + test d'hystérésis renforcé ; 1 faux-fix efficiency écarté
- Fix `start.bat` : appel direct du python du venv (corrige `ModuleNotFoundError` multi-Python)
- Bump v1.5, changelog + table params README, 8 tests verts
**État** : fini — v1.5 en prod sur `main` + `master` (commit `9974f42`), validé au micro
**Reprise** : rien en cours. Réglage éventuel à l'usage : `STREAM_SPEECH_THRESHOLD` (0.5).

---

## 2026-07-18 — Décisions migrées depuis AGENTS.md

> Archive créée lors du passage au contrat `AGENTS.md` stable + `STATUS.md` courant. Les conséquences actives restent dans `STATUS.md`, les règles durables dans `AGENTS.md` ou leur source de vérité.

### 2026-06-01 — Silero VAD pour la détection de frontière (remplace le seuil RMS)
Le découpage de segments écoute la *parole* (proba Silero) au lieu du *volume* (RMS). Frontières sur de vraies fins d'énoncé, robustes au bruit de fond, seuil indépendant du micro/`AUDIO_GAIN`. Modèle déjà embarqué dans faster-whisper → zéro nouvelle dépendance. Rejeté : (a) garder le seuil RMS (`STREAM_SILENCE_RMS` — plafond non perfectible au bouton, ne coupe jamais si l'ambiance > seuil) ; (b) LLM de nettoyage type Wispr (ajoute latence + charge GPU + dépendance, hors-sujet pour du 100 % local) ; (c) re-décodage live mot-à-mot (backspaces fragiles via presse-papier — déjà rejeté) ; (d) VAD streaming stateful via `session.run` (couple à l'interne non-public de faster-whisper pour un gain CPU négligeable).

### 2026-05-31 — Streaming append-only, sans auto-correction
Le texte se pose par segments au fil de l'eau, jamais réécrit. Tue la latence perçue sur les gros textes. Rejeté : auto-correction rétroactive type Apple (fenêtre glissante / LocalAgreement) → re-décodage en boucle + charge GPU + backspaces fragiles (frappe par presse-papier), pour un confort déjà acquis à ~80 % en mode bloc.

---

## 2026-06-01 — Streaming append-only v1.4 livré

**Date** : 2026-06-01
**Fait** :
- Implémenté le streaming append-only (plan `plans/2026-06-01-streaming-dictee-impl.md`)
- `BoundaryDetector` + tests, refactor `_transcribe_audio` / collage incrémental, `_stream_loop` + câblage start/stop, bump v1.4
- Calibrage `STREAM_SILENCE_RMS = 0.02` validé à l'oreille
**État** : terminé — validé manuellement (pauses OK, flot continu OK, ressenti bon)
**Reprise** : aucune action en attente — v1.4 en prod sur `main`.

**Décision archivée — Worktree hors vault via git fallback (2026-05-31)** : worktree créé par `git worktree add` dans `~/.config/superpowers/worktrees/VoiceTyper/streaming-dictee` (branche `feat/streaming-dictee`), `EnterWorktree` natif rejeté (cible le repo vault). Caduque : v1.4 puis v1.5 livrées et mergées, worktree dissoute.

## 2026-05-31 — Migration format CLAUDE.md (ancien bloc « Dernière session »)

**Date** : — (session non datée)
**Fait** :
- Migration vers le nouveau format CLAUDE.md unique (suppression index.md)
- README conservé tel quel (projet publié sur GitHub)
- CLAUDE.md reformaté au nouveau format

**État** : Terminé — index.md supprimé, CLAUDE.md propre
**Reprise** : Aucune action en attente — projet stable v1.3
