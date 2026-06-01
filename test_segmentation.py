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
