"""Tests unitaires du découpage en segments — logique pure, sans audio ni GPU.

Le vrai modèle Silero (ONNX) n'est jamais chargé : on injecte un faux modèle
déterministe (proba dérivée du RMS de chaque fenêtre) pour tester la mécanique
d'alignement, l'hystérésis et la logique de frontière sans dépendre du contenu audio.
"""
import numpy as np
from voice_typer import BoundaryDetector, SileroClassifier, VAD_WINDOW

SR = 16000
SILENCE_MS = 600
MAX_SEC = 7


def fake_model(audio, **kwargs):
    """Faux Silero : 1.0 (parole) si la fenêtre a de l'énergie, 0.0 (silence) sinon.

    Reproduit la convention des helpers speech()/silence() ci-dessous, et émet
    une proba par fenêtre de 512 samples comme le modèle réel.
    """
    windows = np.asarray(audio, dtype=np.float64).reshape(-1, VAD_WINDOW)
    rms = np.sqrt((windows ** 2).mean(axis=1))
    return (rms >= 0.01).astype(np.float32)


def _new():
    clf = SileroClassifier(threshold=0.5, sample_rate=SR, model=fake_model)
    return BoundaryDetector(SR, SILENCE_MS, MAX_SEC, clf)


def speech(seconds, level=0.1):
    """Signal constant au-dessus du seuil d'énergie du faux modèle."""
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


# ── Logique de frontière (BoundaryDetector) ──────────────────

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


# ── Mécanique du classifieur Silero ──────────────────────────

def test_classifier_aligne_sur_512():
    """Un bloc non multiple de 512 ne produit un verdict que par fenêtre complète."""
    clf = SileroClassifier(0.5, SR, model=fake_model)
    verdicts = clf.classify(np.full(1100, 0.1, dtype=np.float32))  # 2*512 + 76
    assert len(verdicts) == 2
    assert all(verdicts)


def test_classifier_hysteresis_garde_l_etat():
    """Une proba dans la zone grise [neg_threshold, threshold) garde l'état précédent."""
    probs = iter([0.9, 0.4, 0.4, 0.2])  # parole, gris, gris, silence

    def model(audio, **k):  # une proba par fenêtre de 512, la courante en dernier
        nwin = len(audio) // VAD_WINDOW
        return np.concatenate([np.zeros(nwin - 1, dtype=np.float32),
                               np.array([next(probs)], dtype=np.float32)])

    clf = SileroClassifier(0.5, SR, model=model)  # neg_threshold = 0.35
    out = [clf.classify(np.zeros(VAD_WINDOW, dtype=np.float32))[0] for _ in range(4)]
    assert out == [True, True, True, False]


def test_classifier_reset_vide_le_residu():
    """Après reset, le résidu d'alignement non consommé est jeté."""
    clf = SileroClassifier(0.5, SR, model=fake_model)
    assert clf.classify(np.full(100, 0.1, dtype=np.float32)) == []   # < 512 → rien
    clf.reset()
    assert clf.classify(np.full(412, 0.1, dtype=np.float32)) == []   # 100 jetés → 412 < 512
