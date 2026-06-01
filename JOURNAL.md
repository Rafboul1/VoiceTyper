# JOURNAL — VoiceTyper

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
