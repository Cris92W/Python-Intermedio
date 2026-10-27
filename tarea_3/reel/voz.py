"""Narra guion.json con mi voz clonada (Qwen3-TTS) y verifica cada escena con Whisper (Tarea 3, reel).

Uso (desde tarea_3/reel, con el entorno de PRACTICA_2, que ya tiene qwen-tts y faster-whisper):
    ../../PRACTICA_2/.venv/Scripts/python voz.py
Entradas: guion.json y mi_voz.ogg (17 s de mi voz, con su transcripción en mi_voz.txt)
Salidas:  salidas/escena_NN.wav, salidas/reel.wav y salidas/tiempos.json (palabras con tiempos para los subtítulos)

Cada escena tiene dos textos: "frase", con las cifras en palabras, es lo que se narra; "subtitulo", con dígitos, es
lo que se lee en pantalla. Los tiempos de Whisper se ponen sobre las palabras del subtítulo.
Si una escena ya está generada con la misma frase, no se repite: borrar salidas/escena_NN.* para rehacerla.
"""
import difflib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# faster_whisper antes que torch: los dos traen OpenMP y en Windows el orden de carga importa
from faster_whisper import WhisperModel
import imageio_ffmpeg
import jiwer
import librosa
import numpy as np
import soundfile as sf
import torch
from num2words import num2words
from qwen_tts import Qwen3TTSModel

sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "salidas"
MODELO = AQUI.parent.parent / "PRACTICA_2" / "modelos" / "Qwen3-TTS-12Hz-0.6B-Base"  # el mismo de la Práctica 2
MAX_WER = 0.25   # control de la diapositiva: si Whisper entiende mal más del 25 % de las palabras, se genera de nuevo
INTENTOS = 3
HZ = 12   # pasos de audio por segundo del códec de Qwen3-TTS (12Hz)
MAX_SILENCIO = 0.35   # s: al unir, los silencios internos más largos se acortan a esto y se quita la cola muda
INICIO, PAUSA, COLA = 0.3, 0.35, 0.8   # silencios en segundos: antes, entre escenas y al final
EXT_AUDIO = {".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac"}


def a_wav(src, dst, sr):
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
                    "-ac", "1", "-ar", str(sr), str(dst)], check=True)


def normalizar(t):
    """Texto comparable entre guion (números en palabras) y Whisper (suele escribir dígitos)."""
    t = t.lower().replace("%", " por ciento ")
    t = re.sub(r"(\d)[.\s](\d{3})\b", r"\1\2", t)   # 1.647 o 1 647 -> 1647
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="es") + " ", t)
    return " ".join(t.split())


def alinear(frase, palabras):
    """Pone los tiempos de Whisper sobre las palabras del guion: el subtítulo dice el guion, no lo que Whisper creyó oír."""
    guion = frase.split()
    # Cada palabra se parte en fichas normalizadas («1647» da cinco); una palabra de Whisper reparte su tiempo entre sus fichas
    fg = [(t, k) for k, w in enumerate(guion) for t in normalizar(w).split()]
    fw = []
    for p in palabras:
        ts = normalizar(p["w"]).split()
        paso = (p["f"] - p["i"]) / max(len(ts), 1)
        fw += [(t, p["i"] + j * paso, p["i"] + (j + 1) * paso) for j, t in enumerate(ts)]
    sm = difflib.SequenceMatcher(a=[t for t, _ in fg], b=[t for t, _, _ in fw], autojunk=False)
    tiempos = [None] * len(guion)
    for a, b, n in sm.get_matching_blocks():
        for j in range(n):
            k, (_, i, f) = fg[a + j][1], fw[b + j]
            tiempos[k] = [i, f] if tiempos[k] is None else [min(tiempos[k][0], i), max(tiempos[k][1], f)]
    # Las palabras que Whisper no reconoció se reparten el hueco entre sus vecinas
    fin_audio = palabras[-1]["f"] if palabras else 0.0
    k = 0
    while k < len(guion):
        if tiempos[k] is not None:
            k += 1
            continue
        m = k
        while m < len(guion) and tiempos[m] is None:
            m += 1
        ini = tiempos[k - 1][1] if k > 0 else 0.0
        fin = tiempos[m][0] if m < len(guion) else fin_audio
        paso = max(fin - ini, 0.0) / (m - k)
        for j in range(k, m):
            tiempos[j] = [ini + (j - k) * paso, ini + (j - k + 1) * paso]
        k = m
    return [{"w": w, "i": round(i, 3), "f": round(f, 3)} for w, (i, f) in zip(guion, tiempos)]


def apretar(wav, sr, palabras):
    """Acorta los silencios internos a MAX_SILENCIO y quita la cola muda; corre los tiempos de las palabras.
    El modelo a veces deja pausas largas o, tras cerrar la frase, sigue en silencio hasta el tope."""
    v = int(sr * 0.05)
    rms = np.array([np.sqrt(np.mean(wav[i:i + v] ** 2)) for i in range(0, len(wav) - v + 1, v)])
    mudo = list(20 * np.log10(rms / rms.max() + 1e-9) < -35) + [False]
    quitar, ini = [], None   # tramos que se quitan, en muestras
    for j, m in enumerate(mudo):
        if m and ini is None:
            ini = j
        elif not m and ini is not None:
            a, b = ini * v, j * v
            if b >= len(wav) - v:                       # silencio hasta el final: quedan 0,15 s
                quitar.append((a + int(0.15 * sr), len(wav)))
            elif b - a > MAX_SILENCIO * sr:
                quitar.append((a + int(MAX_SILENCIO * sr), b))
            ini = None
    quitar = [(a, b) for a, b in quitar if b > a]

    def nuevo(seg):
        s = seg * sr
        return (s - sum(min(b, max(s, a)) - a for a, b in quitar)) / sr

    partes, prev = [], 0
    for a, b in quitar:
        partes.append(wav[prev:a])
        prev = b
    partes.append(wav[prev:])
    return np.concatenate(partes), [{**p, "i": round(nuevo(p["i"]), 3), "f": round(nuevo(p["f"]), 3)} for p in palabras]


def main():
    SAL.mkdir(exist_ok=True)
    escenas = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    fuentes = [p for p in AQUI.glob("mi_voz.*") if p.suffix.lower() in EXT_AUDIO]
    if len(fuentes) != 1:
        sys.exit(f"Debe haber exactamente un audio mi_voz.* en {AQUI} (hay {len(fuentes)}).")

    t0 = time.time()
    ref24, ref16 = SAL / "mi_voz_24k.wav", SAL / "mi_voz_16k.wav"
    a_wav(fuentes[0], ref24, 24000)
    a_wav(fuentes[0], ref16, 16000)

    # Whisper transcribe la muestra por ti; mi_voz.txt se puede corregir a mano y se respeta
    txt = AQUI / "mi_voz.txt"
    whisper = None
    if not txt.exists():
        whisper = WhisperModel("small", device="cpu", compute_type="int8")
        segs, _ = whisper.transcribe(sf.read(ref16, dtype="float32")[0], language="es")
        txt.write_text(" ".join(s.text.strip() for s in segs) + "\n", encoding="utf-8")
    ref_text = txt.read_text(encoding="utf-8").strip()
    print(f"Muestra de voz: {fuentes[0].name} -> «{ref_text}»")
    voz_id = f"{fuentes[0].name}:{fuentes[0].stat().st_size}:{ref_text}"

    def lista(i, e):
        """La escena ya está generada con la misma frase, subtítulo y voz."""
        wav_path, meta_path = SAL / f"escena_{i:02d}.wav", SAL / f"escena_{i:02d}.json"
        if not (wav_path.exists() and meta_path.exists()):
            return False
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return meta["frase"] == e["frase"] and meta.get("voz") == voz_id and meta.get("subtitulo") == e["subtitulo"]

    # Los modelos (unos 5 GB de memoria) se cargan solo si falta generar alguna escena
    if not all(lista(i, e) for i, e in enumerate(escenas, 1)):
        whisper = whisper or WhisperModel("small", device="cpu", compute_type="int8")
        torch.set_num_threads(os.cpu_count() or 4)
        tts = Qwen3TTSModel.from_pretrained(str(MODELO), device_map="cpu", dtype=torch.float32)
        prompt = tts.create_voice_clone_prompt(ref_audio=str(ref24), ref_text=ref_text)
        print(f"Modelos cargados en {time.time() - t0:.0f} s")

    for i, e in enumerate(escenas, 1):
        wav_path, meta_path = SAL / f"escena_{i:02d}.wav", SAL / f"escena_{i:02d}.json"
        if lista(i, e):
            print(f"Escena {i}: ya generada (WER {json.loads(meta_path.read_text(encoding='utf-8'))['wer']:.0%})")
            continue
        mejor = None
        for intento in range(1, INTENTOS + 1):
            t1 = time.time()
            torch.manual_seed(2026 + 10 * i + intento)
            # Tope de largo: si el modelo no cierra la frase, por defecto sigue hasta 2048 pasos (casi 3 min de audio,
            # horas en CPU). Con 0,55 s por palabra y 4 s de margen, una toma así se corta y Whisper la descarta.
            tope = int(HZ * (0.55 * len(e["frase"].split()) + 4))
            wavs, sr = tts.generate_voice_clone(text=e["frase"], language="spanish", voice_clone_prompt=prompt,
                                                max_new_tokens=tope)
            wav, _ = librosa.effects.trim(wavs[0].astype(np.float32), top_db=40)
            segs, _ = whisper.transcribe(librosa.resample(wav, orig_sr=sr, target_sr=16000),
                                         language="es", word_timestamps=True)
            palabras = [{"w": w.word.strip(), "i": round(w.start, 3), "f": round(w.end, 3)}
                        for s in segs for w in s.words]
            oido = " ".join(p["w"] for p in palabras)
            wer = jiwer.wer(normalizar(e["frase"]), normalizar(oido))
            print(f"Escena {i}, intento {intento}: {len(wav) / sr:.1f} s de audio en {time.time() - t1:.0f} s · WER {wer:.0%} · «{oido}»")
            if mejor is None or wer < mejor[0]:
                mejor = (wer, wav, sr, palabras)
            if wer <= MAX_WER:
                break
        wer, wav, sr, palabras = mejor
        sf.write(wav_path, wav, sr)
        meta = {"frase": e["frase"], "subtitulo": e["subtitulo"], "voz": voz_id, "wer": wer, "sr": sr, "dur": len(wav) / sr,
                "oido": " ".join(p["w"] for p in palabras), "palabras": alinear(e["subtitulo"], palabras)}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # Une las escenas (con sus silencios largos acortados) y guarda los tiempos globales de cada palabra
    partes, tiempos, t = [], [], INICIO
    sr = None
    for i in range(1, len(escenas) + 1):
        meta = json.loads((SAL / f"escena_{i:02d}.json").read_text(encoding="utf-8"))
        wav, sr = sf.read(SAL / f"escena_{i:02d}.wav", dtype="float32")
        wav, palabras = apretar(wav, sr, meta["palabras"])
        partes.append(wav)
        tiempos.append({"inicio": t, "fin": t + len(wav) / sr, "wer": meta["wer"],
                        "palabras": [{**p, "i": p["i"] + t, "f": p["f"] + t} for p in palabras]})
        t += len(wav) / sr + PAUSA
    sil = lambda s: np.zeros(int(s * sr), dtype=np.float32)
    audio = [sil(INICIO)]
    for k, p in enumerate(partes):
        audio += [p, sil(PAUSA if k < len(partes) - 1 else COLA)]
    audio = np.concatenate(audio)
    sf.write(SAL / "reel.wav", audio, sr)
    dur = len(audio) / sr
    (SAL / "tiempos.json").write_text(json.dumps({"duracion": dur, "escenas": tiempos}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(f"\nreel.wav: {dur:.1f} s en total ({time.time() - t0:.0f} s de cálculo)")
    # El reel dura 60 s: la narración más la tarjeta final de créditos (unos 4 s)
    if not 52 <= dur <= 57:
        print("OJO: la narración debería durar entre 52 y 57 s para un reel de 60 s; ajusta guion.json.")


if __name__ == "__main__":
    main()
