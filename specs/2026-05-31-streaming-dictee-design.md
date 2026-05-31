# Streaming append-only de la dictée — Spec design

> Date : 2026-05-31 · Branche : `feat/streaming-dictee` · Statut : design validé, à implémenter

## Contexte

VoiceTyper v1.3 transcrit en **une seule passe à la fin** du push-to-talk. Pendant qu'on parle, l'audio s'accumule dans `audio_queue` ; au relâchement, `stop_recording` lance `_process_audio` qui draine toute la queue, concatène, appelle `model.transcribe()` une fois sur le bloc entier, puis colle le texte d'un coup via le presse-papier (`_type_text`).

Conséquence : sur une dictée longue, la latence perçue = **durée de parole + temps de transcription du bloc complet**. Rien n'apparaît avant la fin.

## Objectif

Le texte se pose **au fil de l'eau** pendant qu'on parle, au lieu d'attendre le relâchement. Tuer la latence perçue sur les gros textes.

Succès = « le texte n'attend plus la fin pour apparaître ».

## Non-objectifs (YAGNI)

- **Pas d'auto-correction rétroactive** type Apple : on ne réécrit jamais un mot déjà collé. Donc pas de backspaces simulés, pas de re-décodage en boucle.
- Pas de fenêtre glissante / LocalAgreement (`whisper_streaming`).
- **Réversibilité** : le comportement v1.3 (mode bloc) reste disponible et récupérable via un flag, sans rien casser.

C'est une optimisation-confort, jetable si l'essai n'est pas probant.

## Approche : streaming append-only par segments

Pendant l'enregistrement, un fil consomme l'audio et le découpe en **segments** sur une **frontière** = silence détecté **OU** durée max atteinte. Chaque segment est transcrit indépendamment (réutilise la passe `transcribe` actuelle), collé en append, puis oublié. La fin du segment précédent est passée en `initial_prompt` au suivant pour la continuité (quasi gratuit). Au relâchement, le reliquat est transcrit + collé.

Le découpage gère les deux modes de dictée de l'utilisateur : phrases avec pauses (frontière = silence) **et** flot continu (frontière = filet durée).

## Composants (tout dans `voice_typer.py`, mono-fichier)

1. **Détecteur de frontière** — mesure l'énergie RMS des blocs entrants. Silence continu ≥ `STREAM_SILENCE_MS` → frontière. Filet : buffer courant ≥ `STREAM_MAX_SEGMENT_SEC` → frontière forcée même sans silence.
2. **Boucle de streaming** `_stream_loop` — thread lancé par `start_recording`. Accumule l'audio, détecte une frontière, transcrit le segment, le colle, garde la queue de contexte (derniers mots) pour le prompt suivant, vide le buffer. Quand `stop_recording` lève le drapeau de fin : transcrit le reliquat, colle, s'arrête.
3. **Collage incrémental** — presse-papier original sauvegardé **une seule fois** au début ; chaque segment collé sans restaurer entre ; restauration à la toute fin. Le 1er collage remplace une sélection éventuelle (comme aujourd'hui), les suivants s'ajoutent à la suite.
4. **Bascule de mode** — `STREAMING_MODE`. Si `False`, on garde exactement le chemin v1.3 (`_process_audio` actuel). Si `True`, on emprunte `_stream_loop`.

## Flux de données

```
audio callback → audio_queue → _stream_loop (draine par bouts)
   → détecteur de frontière (RMS silence | durée max)
   → model.transcribe(segment, initial_prompt = vocab + contexte précédent)
   → apply_replacements → _type_text(append)
   → mise à jour du contexte → vidage buffer
stop_recording → drapeau fin → transcription du reliquat → collage final → restore presse-papier
```

## Config exposée (haut de fichier, comme le reste)

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `STREAMING_MODE` | `True` | Active le streaming ; `False` = comportement v1.3 |
| `STREAM_MAX_SEGMENT_SEC` | `7` | Filet : coupe forcée si pas de silence |
| `STREAM_SILENCE_MS` | `600` | Durée de silence qui déclenche une frontière |
| `STREAM_SILENCE_RMS` | `0.01` | Seuil d'énergie sous lequel c'est du silence — **à calibrer** sur micro/voix |

## Gestion d'erreur

- Échec de transcription d'un segment : log + on continue (on ne perd pas la suite). Le `try/except` de `_process_audio` est conservé dans `_stream_loop`.
- Presse-papier non restaurable : les retries existants de `_type_text` sont conservés.
- Silence mal calibré (frontière jamais déclenchée) : le filet `STREAM_MAX_SEGMENT_SEC` garantit qu'on colle quand même.

## Validation

Le projet n'a **pas de suite de tests automatisés** (`test_micro.py` est un diagnostic micro manuel). Validation manuelle :

- Lancer le script du worktree avec le venv existant (console, pour voir les logs).
- **Cas 1 — pauses** : dicter 3-4 phrases en respirant → les segments doivent tomber sur les silences.
- **Cas 2 — flot continu** : parler ~20 s sans pause → le filet durée doit découper.
- Vérifier : texte final cohérent, **pas de doublon ni de perte aux jointures**.
- Tester dans **Notepad/app standard** ET dans un **terminal** (collage `Ctrl+Shift+V`) — règle projet sur le hook/collage.
- **A/B** : `STREAMING_MODE = False` → retour au comportement v1.3 identique.

## Risques / à valider tôt

- **Calibrage `STREAM_SILENCE_RMS`** : dépend du micro et de la voix (interaction avec `AUDIO_GAIN = 3.0`). Le maillon à régler à l'oreille.
- **Ressenti** : texte par bouts = agréable ou haché ? À juger en main.
- **Perf** : a priori OK — le log réel montre un ratio ~0,3 (7,7 s transcrits en 1,8 s), le GPU va ~3× plus vite que le temps réel, les segments ne s'empileront pas.
- **Concurrence** : la transcription d'un segment tourne pendant que l'audio continue d'arriver dans la queue (thread-safe, pas de perte → va au segment suivant). Le flag `is_processing`, qui bloque aujourd'hui un nouveau `start` pendant la transcription, est à revoir pour le mode streaming (le « processing » devient continu).
