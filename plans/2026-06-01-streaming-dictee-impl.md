# Streaming append-only de la dictée — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire que le texte dicté se pose au fil de l'eau (par segments) pendant qu'on parle, au lieu d'attendre le relâchement du push-to-talk — réversible via un flag.

**Architecture:** Un thread de streaming (`_stream_loop`) draine `audio_queue`, découpe l'audio en segments sur une frontière (silence RMS détecté **OU** durée max), transcrit chaque segment indépendamment (réutilise la passe `transcribe` existante via `_transcribe_audio`), et le colle en append sans jamais réécrire. Le détecteur de frontière est de la logique pure (numpy), testée en TDD ; le reste (collage, thread, GPU) est validé à la main. Le mode bloc v1.3 reste accessible via `STREAMING_MODE = False`.

**Tech Stack:** Python 3, `faster-whisper`/CTranslate2 (CUDA), `numpy`, `sounddevice`, `pyperclip`, Windows API (ctypes), `pytest` (dev).

---

## Contexte d'exécution

- **Worktree** : `C:\Users\visit\.config\superpowers\worktrees\VoiceTyper\streaming-dictee` (branche `feat/streaming-dictee`). Tout le travail se fait ici. Ne pas toucher au repo principal `C:\Vault\Projects\VOICE_TYPER` (qui reste sur `master` = v1.3 intacte).
- **Python du venv** (réutilisé depuis le repo principal, pas de venv local au worktree) :
  `C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe`
  Dans tout le plan, on le note `$PY`. Les commandes pytest se lancent **depuis la racine du worktree** pour que `import voice_typer` résolve le fichier du worktree.
- **Spec de référence** : `specs/2026-05-31-streaming-dictee-design.md`.
- **Pas de suite de tests existante** : seul le détecteur de frontière est testé automatiquement (logique pure). Le reste = validation manuelle décrite dans chaque tâche.

## File Structure

| Fichier | Création / Modif | Responsabilité |
|---------|------------------|----------------|
| `voice_typer.py` | Modif | Tout le code runtime (mono-fichier, conforme à la spec) : flags de config, classe `BoundaryDetector`, refactor transcription/collage, `_stream_loop`, câblage start/stop |
| `test_segmentation.py` | Création (racine worktree) | Tests unitaires de `BoundaryDetector` (importé depuis `voice_typer`) |
| `requirements-dev.txt` | Création | Dépendance de dev (`pytest`), non-runtime |
| `README.md` | Modif | Entrée changelog v1.4 |
| `CLAUDE.md` | Modif | `## État actuel` + `## Dernière session` |

---

### Task 1: Setup outillage de test

**Files:**
- Create: `requirements-dev.txt`

- [ ] **Step 1: Installer pytest dans le venv réutilisé**

Run (depuis n'importe où) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -m pip install pytest
```
Expected: `Successfully installed pytest-...` (ou « already satisfied »).

- [ ] **Step 2: Tracer la dépendance de dev**

Create `requirements-dev.txt` (racine worktree) :
```
# Dépendances de développement uniquement (non requises pour faire tourner VoiceTyper).
pytest
```

- [ ] **Step 3: Vérifier que pytest tourne**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -m pytest --version
```
Expected: `pytest 8.x.x` (une version s'affiche, pas d'erreur).

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt
git commit -m "chore: ajoute pytest (dev) pour tester la segmentation"
```

---

### Task 2: Flags de configuration du streaming

**Files:**
- Modify: `voice_typer.py` (section CONFIGURATION, après le bloc `# --- Divers ---`, autour de la ligne 97)

- [ ] **Step 1: Ajouter les 4 paramètres exposés**

Dans `voice_typer.py`, juste après les lignes `PASTE_DELAY` / `ADD_TRAILING_SPACE` (fin de la section `# --- Divers ---`), insérer :

```python
# --- Streaming append-only de la dictée ---
# Si True, le texte se pose au fil de l'eau par segments pendant qu'on parle.
# Si False, comportement v1.3 : transcription en une passe au relâchement.
STREAMING_MODE = True
STREAM_MAX_SEGMENT_SEC = 7        # Filet : coupe forcée d'un segment si aucun silence
STREAM_SILENCE_MS = 600          # Durée de silence continu qui déclenche une frontière
STREAM_SILENCE_RMS = 0.01        # Seuil d'énergie RMS sous lequel un bloc est du silence
#                                  ⚠ à calibrer sur ton micro + AUDIO_GAIN (voir Task 6)
```

- [ ] **Step 2: Vérifier que le fichier s'importe toujours**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -c "import voice_typer; print('OK', voice_typer.STREAMING_MODE, voice_typer.STREAM_SILENCE_RMS)"
```
Expected: `OK True 0.01`

- [ ] **Step 3: Commit**

```bash
git add voice_typer.py
git commit -m "feat: flags de config du streaming (STREAMING_MODE + seuils)"
```

---

### Task 3: BoundaryDetector (détecteur de frontière) — TDD

**Files:**
- Test: `test_segmentation.py` (racine worktree)
- Modify: `voice_typer.py` (nouvelle classe, à insérer après la classe `VocabManager`, avant `# ── Auto-détection du micro ──`)

- [ ] **Step 1: Écrire les tests d'abord**

Create `test_segmentation.py` :
```python
"""Tests unitaires du BoundaryDetector — logique pure, sans audio ni GPU."""
import numpy as np
from voice_typer import BoundaryDetector

SR = 16000
SILENCE_RMS = 0.01
SILENCE_MS = 600
MAX_SEC = 7


def _new():
    return BoundaryDetector(SR, SILENCE_RMS, SILENCE_MS, MAX_SEC)


def speech(seconds, level=0.1):
    """Signal constant au-dessus du seuil (RMS = level)."""
    return np.full(int(seconds * SR), level, dtype=np.float32)


def silence(seconds):
    return np.zeros(int(seconds * SR), dtype=np.float32)


def feed_blocks(det, audio, block=1024):
    """Feed l'audio par blocs de 1024 (comme le stream réel).

    Retourne (fired, samples_vus_au_moment_du_fire).
    """
    seen = 0
    for i in range(0, len(audio), block):
        b = audio[i:i + block]
        seen += len(b)
        if det.feed(b):
            return True, seen
    return False, seen


def test_silence_pur_ne_declenche_jamais():
    det = _new()
    fired, _ = feed_blocks(det, silence(3.0))
    assert fired is False


def test_parole_puis_silence_declenche():
    det = _new()
    audio = np.concatenate([speech(1.0), silence(0.8)])
    fired, _ = feed_blocks(det, audio)
    assert fired is True


def test_silence_court_ne_declenche_pas():
    det = _new()
    audio = np.concatenate([speech(1.0), silence(0.3)])
    fired, _ = feed_blocks(det, audio)
    assert fired is False


def test_filet_duree_declenche_sans_silence():
    det = _new()
    fired, samples = feed_blocks(det, speech(8.0))
    assert fired is True
    assert samples >= MAX_SEC * SR          # pas avant le filet
    assert samples < int(8.0 * SR)          # mais avant la fin


def test_reset_repart_a_zero():
    det = _new()
    feed_blocks(det, np.concatenate([speech(1.0), silence(0.8)]))
    det.reset()
    fired, _ = feed_blocks(det, silence(1.0))
    assert fired is False
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -m pytest test_segmentation.py -v
```
Expected: FAIL — `ImportError: cannot import name 'BoundaryDetector' from 'voice_typer'`.

- [ ] **Step 3: Implémenter BoundaryDetector**

Dans `voice_typer.py`, après la fin de la classe `VocabManager` (juste avant `# ── Auto-détection du micro ──`), insérer :

```python
# ── Détection de frontière de segment (streaming) ────────────

class BoundaryDetector:
    """Décide où couper un segment pendant le streaming de la dictée.

    Émet une frontière quand, depuis le dernier reset :
      - de la parole a été captée ET un silence continu >= silence_ms est observé, OU
      - le buffer atteint max_segment_sec (filet, même sans silence).

    Logique pure numpy : aucune dépendance audio/GPU, donc testable en isolation.
    Alimenté bloc par bloc via feed() ; l'unité de comptage interne est l'échantillon.
    """

    def __init__(self, sample_rate, silence_rms, silence_ms, max_segment_sec):
        self.sample_rate = sample_rate
        self.silence_rms = silence_rms
        self._silence_samples_needed = int(silence_ms / 1000.0 * sample_rate)
        self._max_samples = int(max_segment_sec * sample_rate)
        self.reset()

    def reset(self):
        """Repart à zéro (après l'émission d'une frontière ou pour un nouveau segment)."""
        self._buffer_samples = 0
        self._silence_run = 0
        self._has_speech = False

    def feed(self, chunk):
        """Ingère un bloc audio mono float32. Retourne True si une frontière est atteinte."""
        n = len(chunk)
        if n == 0:
            return False
        self._buffer_samples += n
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        if rms >= self.silence_rms:
            self._has_speech = True
            self._silence_run = 0
        else:
            self._silence_run += n
        if not self._has_speech:
            return False
        if self._buffer_samples >= self._max_samples:
            return True
        if self._silence_run >= self._silence_samples_needed:
            return True
        return False
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -m pytest test_segmentation.py -v
```
Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add test_segmentation.py voice_typer.py
git commit -m "feat: BoundaryDetector (frontière silence RMS ou durée max) + tests"
```

---

### Task 4: Extraire `_transcribe_audio` (refactor DRY)

> But : isoler « audio numpy → texte » pour le réutiliser en mode bloc ET en streaming. Comportement du mode bloc inchangé.

**Files:**
- Modify: `voice_typer.py` — méthode `_process_audio` (actuellement lignes ~758-837)

- [ ] **Step 1: Ajouter la méthode `_transcribe_audio`**

Dans la classe `VoiceTyper`, juste avant `_process_audio`, insérer :

```python
def _transcribe_audio(self, audio, extra_prompt=""):
    """Transcrit un bloc audio mono float32 → texte (gain, whisper, remplacements).

    extra_prompt : contexte additionnel (derniers mots du segment précédent en
    streaming) ajouté au vocab dans l'initial_prompt. "" en mode bloc.
    Retourne le texte corrigé, ou "" si rien n'est détecté.
    """
    if AUDIO_GAIN != 1.0:
        audio = np.clip(audio * AUDIO_GAIN, -1.0, 1.0)

    duration = len(audio) / SAMPLE_RATE
    log(f"→ Transcription de {duration:.1f}s d'audio...")
    start_time = time.time()

    initial_prompt = self.vocab.get_initial_prompt() + extra_prompt

    segments, info = self.model.transcribe(
        audio,
        language=None,
        beam_size=2,
        initial_prompt=initial_prompt if initial_prompt else None,
        vad_filter=True,
        vad_parameters=dict(
            threshold=VAD_THRESHOLD,
            min_silence_duration_ms=200,
            speech_pad_ms=300,
            min_speech_duration_ms=100,
        ),
    )

    text = " ".join(seg.text for seg in segments).strip()
    if text:
        text = self.vocab.apply_replacements(text)

    elapsed = time.time() - start_time
    lang = info.language if info else "?"
    prob = f"{info.language_probability:.0%}" if info else "?"
    if text:
        log(f"OK ({elapsed:.1f}s, {lang} {prob})")
        log(f'→ "{text}"')
    else:
        log(f"(aucun texte détecté, {elapsed:.1f}s)")
    return text
```

- [ ] **Step 2: Réécrire `_process_audio` pour utiliser `_transcribe_audio`**

Remplacer **tout le corps** de `_process_audio` (du `try:` jusqu'au `finally:` inclus) par :

```python
def _process_audio(self):
    """Mode bloc (v1.3) : draine toute la queue, transcrit en une passe, colle."""
    try:
        chunks = []
        while not self.audio_queue.empty():
            try:
                chunks.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not chunks:
            return

        audio = np.concatenate(chunks, axis=0)
        if audio.ndim > 1 and audio.shape[1] > 1:
            audio = audio.mean(axis=1)
        else:
            audio = audio.flatten()

        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION:
            log(f"→ Audio trop court ({duration:.1f}s < {MIN_DURATION}s), ignoré")
            return

        text = self._transcribe_audio(audio)
        if text:
            self._type_text(text)

    except Exception as e:
        log_err(f"✗ Erreur transcription : {e}")
    finally:
        self.is_processing = False
        self._set_idle()
```

- [ ] **Step 3: Vérifier l'import + non-régression au lint d'import**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -c "import voice_typer; print('import OK')"
```
Expected: `import OK` (aucune `SyntaxError` / `NameError`).

- [ ] **Step 4: Validation manuelle — mode bloc identique à v1.3**

Mettre temporairement `STREAMING_MODE = False` en haut de `voice_typer.py`, puis :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" voice_typer.py
```
- Attendre « VoiceTyper v1.3 prêt », maintenir le bouton x2, dicter une phrase, relâcher.
- Vérifier dans la console : `→ Transcription de Xs...` puis `OK (...)` puis `→ "..."`, et le texte est collé au curseur (Notepad ouvert).
- Quitter via le tray. Remettre `STREAMING_MODE = True`.

- [ ] **Step 5: Commit**

```bash
git add voice_typer.py
git commit -m "refactor: extrait _transcribe_audio (réutilisé bloc + streaming)"
```

---

### Task 5: Collage incrémental (session de presse-papier)

> But : pouvoir coller plusieurs segments à la suite sans restaurer le presse-papier entre chaque, et le restaurer une seule fois à la fin. Le mode bloc garde son comportement (remplace la sélection, restaure ensuite).

**Files:**
- Modify: `voice_typer.py` — méthode `_type_text` (actuellement lignes ~841-892) + `__init__`

- [ ] **Step 1: Ajouter les helpers presse-papier dans `__init__`**

Dans `VoiceTyper.__init__`, ajouter à la fin du bloc d'initialisation des attributs (par ex. juste après `self.is_paused = False`) :

```python
        # Session de collage (streaming) — presse-papier sauvé une fois, restauré à la fin
        self._saved_clipboard = ""
```

- [ ] **Step 2: Remplacer `_type_text` par une version factorisée + les helpers de session**

Remplacer **toute** la méthode `_type_text` par le bloc suivant (même nom + 4 nouvelles méthodes) :

```python
def _read_clipboard(self):
    """Lit le presse-papier avec retry. Retourne "" en cas d'échec."""
    for _ in range(3):
        try:
            return pyperclip.paste()
        except Exception:
            time.sleep(0.05)
    return ""

def _restore_clipboard(self, value):
    """Restaure le presse-papier en arrière-plan (laisse le collage se faire d'abord)."""
    def restore():
        time.sleep(0.1)
        for _ in range(3):
            try:
                pyperclip.copy(value)
                break
            except Exception:
                time.sleep(0.05)
    threading.Thread(target=restore, daemon=True).start()

def _do_paste(self, text):
    """Copie le texte dans le presse-papier et déclenche le collage.

    Ne sauvegarde ni ne restaure le presse-papier (géré par l'appelant).
    Ctrl+Shift+V dans un terminal, Ctrl+V ailleurs.
    """
    for attempt in range(3):
        try:
            pyperclip.copy(text)
            break
        except Exception:
            if attempt == 2:
                log_err("✗ Impossible de copier dans le presse-papiers après 3 essais")
                return
            time.sleep(0.05)

    time.sleep(PASTE_DELAY)
    if is_terminal_focused():
        win_ctrl_shift_v()
    else:
        win_ctrl_v()
    time.sleep(PASTE_DELAY)

def _type_text(self, text):
    """Mode bloc : sauve le presse-papier, colle (remplace la sélection), restaure."""
    if ADD_TRAILING_SPACE:
        text = text + " "
    old_clipboard = self._read_clipboard()
    try:
        self._do_paste(text)
    finally:
        self._restore_clipboard(old_clipboard)

def _begin_paste_session(self):
    """Streaming : sauve le presse-papier une fois, avant le 1er segment."""
    self._saved_clipboard = self._read_clipboard()

def _paste_segment(self, text):
    """Streaming : colle un segment à la suite, sans toucher à la sauvegarde."""
    self._do_paste(text)

def _end_paste_session(self):
    """Streaming : restaure le presse-papier sauvé au début de la session."""
    self._restore_clipboard(self._saved_clipboard)
```

- [ ] **Step 3: Vérifier l'import**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -c "import voice_typer; print('import OK')"
```
Expected: `import OK`.

- [ ] **Step 4: Validation manuelle — mode bloc toujours OK**

Avec `STREAMING_MODE = False`, relancer `voice_typer.py`, dicter dans Notepad :
- le texte est collé au curseur ;
- sélectionner du texte puis dicter → la sélection est **remplacée** ;
- après collage, vérifier que **l'ancien contenu du presse-papier est restauré** (Ctrl+V manuel recolle l'ancien). Remettre `STREAMING_MODE = True`.

- [ ] **Step 5: Commit**

```bash
git add voice_typer.py
git commit -m "refactor: factorise le collage (_do_paste) + session de presse-papier streaming"
```

---

### Task 6: Boucle de streaming `_stream_loop` + câblage start/stop

> But : brancher le mode streaming. C'est le cœur du chantier. Pas de test auto (thread + GPU + collage) → validation manuelle détaillée + A/B avec le mode bloc.

**Files:**
- Modify: `voice_typer.py` — `__init__`, `start_recording` (~718), `stop_recording` (~741), + 2 nouvelles méthodes `_stream_loop` / `_flush_segment`

- [ ] **Step 1: Ajouter les attributs d'état streaming dans `__init__`**

Dans `VoiceTyper.__init__`, à côté du `self._saved_clipboard = ""` ajouté en Task 5, ajouter :

```python
        self.detector = None        # BoundaryDetector, créé à chaque start en streaming
        self._stream_stop = False   # levé par stop_recording → le loop finit le reliquat
        self._stream_active = False # un loop de streaming tourne (bloque un nouveau start)
```

- [ ] **Step 2: Remplacer `start_recording` par la version qui branche le streaming**

Remplacer **toute** la méthode `start_recording` par :

```python
def start_recording(self):
    """Démarre la collecte audio (le stream reste ouvert)."""
    if self.is_recording or self.model is None:
        return
    if self.is_paused:
        return
    if TERMINAL_DETECTION and is_terminal_focused():
        return

    if STREAMING_MODE:
        if self._stream_active:
            return  # un loop précédent finit encore son reliquat
        self.is_recording = True
        self._stream_active = True
        self._stream_stop = False
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        self.detector = BoundaryDetector(
            SAMPLE_RATE, STREAM_SILENCE_RMS, STREAM_SILENCE_MS, STREAM_MAX_SEGMENT_SEC
        )
        self._begin_paste_session()
        self.tray.icon = self.icon_recording
        self.tray.title = "VoiceTyper — Enregistrement (streaming)..."
        play_beep(SOUND_START_FREQ, SOUND_DURATION_MS)
        threading.Thread(target=self._stream_loop, daemon=True).start()
        return

    # --- Mode bloc (v1.3) ---
    if self.is_processing:
        return
    self.is_recording = True
    with self.audio_queue.mutex:
        self.audio_queue.queue.clear()
    self.tray.icon = self.icon_recording
    self.tray.title = "VoiceTyper — Enregistrement..."
    play_beep(SOUND_START_FREQ, SOUND_DURATION_MS)
```

- [ ] **Step 3: Remplacer `stop_recording` par la version qui termine le streaming**

Remplacer **toute** la méthode `stop_recording` par :

```python
def stop_recording(self):
    """Arrête la collecte audio et déclenche la transcription (stream reste ouvert)."""
    if not self.is_recording:
        return
    self.is_recording = False
    play_beep(SOUND_STOP_FREQ, SOUND_DURATION_MS)

    if STREAMING_MODE:
        # Le loop transcrit le reliquat puis s'arrête de lui-même.
        self.tray.icon = self.icon_processing
        self.tray.title = "VoiceTyper — Transcription du reliquat..."
        self._stream_stop = True
        return

    # --- Mode bloc (v1.3) ---
    self.is_processing = True
    self.tray.icon = self.icon_processing
    self.tray.title = "VoiceTyper — Transcription..."
    threading.Thread(target=self._process_audio, daemon=True).start()
```

- [ ] **Step 4: Ajouter `_stream_loop` et `_flush_segment`**

Dans la classe `VoiceTyper`, juste après `_process_audio`, insérer :

```python
def _stream_loop(self):
    """Streaming : draine l'audio en continu, coupe en segments, transcrit + colle au fil de l'eau."""
    segment_chunks = []
    context = ""
    try:
        while True:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                if self._stream_stop:
                    break  # plus rien à lire ET stop demandé → on finit
                continue

            # Mono
            if chunk.ndim > 1 and chunk.shape[1] > 1:
                mono = chunk.mean(axis=1)
            else:
                mono = chunk.flatten()

            segment_chunks.append(mono)
            if self.detector.feed(mono):
                context = self._flush_segment(segment_chunks, context)
                segment_chunks = []
                self.detector.reset()

        # Reliquat final (ce qui restait après le dernier silence / au relâchement)
        if segment_chunks:
            self._flush_segment(segment_chunks, context)

    except Exception as e:
        log_err(f"✗ Erreur streaming : {e}")
    finally:
        self._end_paste_session()
        self._stream_active = False
        self.is_processing = False
        self._set_idle()

def _flush_segment(self, chunks, context):
    """Transcrit un segment et le colle en append.

    Retourne le nouveau contexte (derniers mots) pour l'initial_prompt du segment suivant.
    Un échec de transcription est loggé et n'interrompt pas le streaming.
    """
    if not chunks:
        return context
    audio = np.concatenate(chunks, axis=0)
    if len(audio) / SAMPLE_RATE < MIN_DURATION:
        return context
    try:
        text = self._transcribe_audio(audio, extra_prompt=context)
    except Exception as e:
        log_err(f"✗ Erreur transcription segment : {e}")
        return context
    if not text:
        return context
    self._paste_segment(text + " " if ADD_TRAILING_SPACE else text)
    # Contexte = derniers ~24 mots cumulés, pour la continuité du prompt suivant
    return " ".join((context + " " + text).split()[-24:])
```

- [ ] **Step 5: Vérifier l'import**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -c "import voice_typer; print('import OK')"
```
Expected: `import OK`.

- [ ] **Step 6: Lancer toute la suite de tests (non-régression segmentation)**

Run (depuis la racine worktree) :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" -m pytest -v
```
Expected: 5 passed.

- [ ] **Step 7: Validation manuelle — le cœur du chantier**

Avec `STREAMING_MODE = True`, lancer en console pour voir les logs :
```
& "C:\Vault\Projects\VOICE_TYPER\venv\Scripts\python.exe" voice_typer.py
```
Ouvrir **Notepad**, maintenir x2 et tester les cas de la spec :
- **Cas 1 — pauses** : dicter 3-4 phrases en respirant entre chaque. Attendu : un segment tombe sur chaque silence, le texte apparaît **avant** le relâchement, log `→ "..."` répété.
- **Cas 2 — flot continu** : parler ~20 s sans pause. Attendu : le filet `STREAM_MAX_SEGMENT_SEC` découpe (segments ~7 s), pas d'attente bloc unique.
- **Jointures** : relire le texte final → **pas de doublon ni de mot perdu** entre segments.
- **Terminal** : refaire le Cas 1 en dictant dans Windows Terminal (collage `Ctrl+Shift+V`).
- **A/B** : repasser `STREAMING_MODE = False`, redicter → comportement v1.3 identique. Remettre `True`.

- [ ] **Step 8: Calibrage de `STREAM_SILENCE_RMS` (le maillon fragile)**

Pendant le Cas 1, observer : si les frontières silence **ne tombent jamais** (seuls les segments de 7 s du filet apparaissent) → `STREAM_SILENCE_RMS` est trop bas pour ton micro/`AUDIO_GAIN`. L'augmenter par paliers (`0.01` → `0.02` → `0.03`) jusqu'à ce que les pauses coupent net, sans couper en plein milieu d'un mot. Noter la valeur retenue.

- [ ] **Step 9: Commit**

```bash
git add voice_typer.py
git commit -m "feat: streaming append-only (_stream_loop + câblage start/stop)"
```

---

### Task 7: Documentation (changelog + état projet)

**Files:**
- Modify: `README.md` (section Changelog)
- Modify: `CLAUDE.md` (`## État actuel`, `## Dernière session`)

- [ ] **Step 1: Ajouter l'entrée changelog dans `README.md`**

Repérer la section Changelog du `README.md` et ajouter en tête (adapter le numéro de version au schéma existant, p. ex. v1.4) :

```markdown
### v1.4 — Streaming append-only de la dictée
- Le texte se pose au fil de l'eau pendant qu'on parle (segments coupés sur silence ou durée max), au lieu d'attendre le relâchement.
- Réversible : `STREAMING_MODE = False` restaure le comportement v1.3 (transcription en une passe).
- Jamais de réécriture rétroactive (append-only). Nouveaux réglages : `STREAM_MAX_SEGMENT_SEC`, `STREAM_SILENCE_MS`, `STREAM_SILENCE_RMS`.
```

- [ ] **Step 2: Mettre à jour `CLAUDE.md`**

Dans `## État actuel`, remplacer le paragraphe « Chantier en cours sur la branche `feat/streaming-dictee`... » par :

```markdown
v1.4 : streaming append-only livré sur `feat/streaming-dictee` — le texte se pose au fil de l'eau (segments, frontière = silence RMS OU durée max), réversible via `STREAMING_MODE`. Mode bloc v1.3 conservé. Détecteur de frontière testé (`test_segmentation.py`) ; reste validé manuellement. `STREAM_SILENCE_RMS` calibré à <valeur retenue Task 6 Step 8>.
```

Dans `## Dernière session`, remplacer le bloc par :

```markdown
**Date** : 2026-06-01
**Fait** :
- Implémenté le streaming append-only (plan `plans/2026-06-01-streaming-dictee-impl.md`)
- `BoundaryDetector` + tests (`test_segmentation.py`), refactor `_transcribe_audio` / collage, `_stream_loop`
**État** : terminé — validé manuellement (pauses, flot continu, terminal, A/B mode bloc)
**Reprise** : merger `feat/streaming-dictee` → `master` puis push GitHub ; supprimer le plan livré
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: changelog v1.4 streaming + état projet à jour"
```

---

## Couverture de la spec (self-review)

| Élément spec | Tâche |
|--------------|-------|
| Détecteur de frontière (RMS silence / durée max) | Task 3 (TDD) |
| Boucle de streaming `_stream_loop` (contexte → initial_prompt) | Task 6 |
| Collage incrémental (sauve 1×, append, restaure à la fin) | Task 5 |
| Bascule de mode `STREAMING_MODE` | Task 2 + 6 |
| Config exposée (4 paramètres) | Task 2 |
| Gestion d'erreur par segment (continue sur échec) | Task 6 (`_flush_segment` try/except) |
| Réversibilité v1.3 (A/B) | Task 4/5/6 (validations) |
| Risque calibrage `STREAM_SILENCE_RMS` | Task 6 Step 8 |
| Concurrence (transcription pendant que l'audio arrive) | Task 6 (queue thread-safe, `_stream_active` bloque un re-start) |
| Non-objectif : pas d'auto-correction | respecté (append-only, jamais de backspace) |

**Note de remise** : ce plan s'exécute dans le worktree existant `feat/streaming-dictee` (déjà créé via `using-git-worktrees`) — ne pas en recréer un.
