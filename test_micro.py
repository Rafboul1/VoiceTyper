import sounddevice as sd
import numpy as np

print("=== Test du micro ===")
print()

# Lister les micros disponibles
print("Micros disponibles :")
devs = sd.query_devices()
for i, d in enumerate(devs):
    if d["max_input_channels"] > 0:
        marker = " >>> DEFAUT" if d["name"] == sd.query_devices(kind="input")["name"] else ""
        print(f"  [{i}] {d['name']} ({d['max_input_channels']} canaux){marker}")

print()
device = 2
info = sd.query_devices(device, kind="input")
channels = int(info["max_input_channels"])
print(f"Test du device {device}: {info['name']} ({channels} canaux)")
print()
print(">>> PARLE PENDANT 3 SECONDES <<<")
print()

audio = sd.rec(3 * 16000, samplerate=16000, channels=channels, device=device, dtype="float32")
sd.wait()

mono = audio.mean(axis=1) if audio.ndim > 1 else audio.flatten()
vol = np.abs(mono).mean()
peak = np.abs(mono).max()

print(f"Volume moyen : {vol:.6f}")
print(f"Volume peak  : {peak:.6f}")
print()

if peak > 0.01:
    print("RESULTAT : OK ! Le micro capte du son.")
elif peak > 0.001:
    print("RESULTAT : Tres faible. Le micro capte un peu mais c'est tres bas.")
else:
    print("RESULTAT : RIEN. Le micro ne capte aucun son.")
    print("  -> Verifie dans Parametres Windows > Son > Entree que ce micro est actif")
    print("  -> Essaie un autre device (change le numero en haut du script)")

print()
input("Appuie sur Entree pour fermer...")
