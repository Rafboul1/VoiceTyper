# STATUS — VoiceTyper

**Mis à jour** : 2026-07-19

## Maintenant

v1.5 : **découpage par Silero VAD** livré et en prod (`main` + `master` alignés, GitHub `Rafboul1/VoiceTyper`, commit `9974f42`). Le streaming append-only pose le texte au fil de l'eau ; la frontière de segment est décidée par le VAD Silero (modèle ML embarqué dans faster-whisper, fenêtre glissante + hystérésis) au lieu de l'ancien seuil d'énergie RMS — segments sur de vraies fins d'énoncé, robustes au bruit, indépendants du micro/`AUDIO_GAIN`. Seuil = `STREAM_SPEECH_THRESHOLD = 0.5` (probabilité de parole) ; filet durée max 7 s conservé. Réversible via `STREAMING_MODE` ; mode bloc v1.3 conservé. Tests : `test_segmentation.py` (8 tests, modèle injectable, lancés via le venv du repo) ; validé au micro (pauses plus nettes et plus rapides).

## Dernière session

**Date** : 2026-07-19
**Fait** :
- Migration de continuité appliquée : `AGENTS.md` garde les règles durables, l'état courant reste ici et l'historique vit dans `JOURNAL.md`.
- Ancien `STATUS.md` archivé dans `JOURNAL.md` sans perte.
**État** : terminé — documentation uniquement, état produit inchangé.
**Reprise** : rien en cours. Réglage éventuel à l'usage : `STREAM_SPEECH_THRESHOLD` (0.5).
