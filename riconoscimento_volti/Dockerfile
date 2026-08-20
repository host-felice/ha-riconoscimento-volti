# Debian, non Alpine: opencv, onnxruntime e i loro modelli non hanno pacchetti
# pronti per musl. Il Supervisor propone la sua immagine di base, che e' Alpine,
# e qui non serve.
FROM python:3.12-slim-bookworm

# Due librerie di sistema e basta: una per opencv senza interfaccia, una per il
# lettore della MRZ, che i jpeg se li decodifica da solo. Debian ferma
# libjpeg-turbo alla 2, e per questo PyTurboJPEG e' fissato alla 1 fra i
# requisiti: la 2 pretende una libreria di sistema che qui non esiste.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libglib2.0-0 libturbojpeg0 curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# **I modelli stanno prima delle librerie, e l'ordine e' il punto.** Docker
# rifa' tutto quello che viene dopo la prima riga cambiata: con i modelli sotto,
# aggiungere una libreria buttava via anche i 166 MB di buffalo_l e li
# riscaricava. Misurato il 20 agosto 2026 su Teramo: tre minuti e diciassette
# per un aggiornamento che di suo non toccava nessun modello.
# I modelli, scaricati una volta sola qui e non a ogni avvio.
# YuNet trova le facce (227 KB), ArcFace le trasforma in numeri (166 MB),
# MiniFASNet dice se davanti all'obiettivo c'era una persona (1,7 MB).
# SFace fa lo stesso lavoro di ArcFace con 37 MB invece di 166: ci sono tutti e
# due per poterli misurare sulle stesse facce, e l'opzione 'modello' sceglie.
RUN mkdir -p /modelli \
    && curl -fsSL -o /modelli/yunet.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    && curl -fsSL -o /modelli/minifasnet_v2.onnx \
       https://huggingface.co/garciafido/minifasnet-v2-anti-spoofing-onnx/resolve/main/minifasnet_v2.onnx \
    && curl -fsSL -o /modelli/sface.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx \
    && curl -fsSL -o /tmp/buffalo_l.zip \
       https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip \
    && unzip -j -o /tmp/buffalo_l.zip w600k_r50.onnx -d /modelli \
    && rm -f /tmp/buffalo_l.zip \
    && apt-get purge -y curl unzip && apt-get autoremove -y

COPY requirements.txt /tmp/requirements.txt

# Il lettore della MRZ pretende opencv-python, quello con l'interfaccia grafica,
# che dentro un contenitore senza schermo non si carica affatto. Si toglie e si
# rimette quello senza: e' lo stesso cv2, meno le finestre.
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && pip3 uninstall -y opencv-python \
    && pip3 install --no-cache-dir --force-reinstall opencv-python-headless==4.12.0.88

# Anche i modelli della MRZ una volta sola qui: si scaricano da Google Drive,
# e un add-on che parte non deve dipendere da quel viaggio.
RUN python3 -c "from mrzscanner import MRZScanner; MRZScanner()"

# La lettura del testo stampato porta i suoi modelli dentro il pacchetto, quindi
# non scarica niente: questa riga serve a farlo scoprire **qui**, se un giorno
# cambiasse, invece che a casa di un cliente il giorno del check-in.
RUN python3 -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"

# Ogni thread di calcolo si tiene la sua area di memoria, e qui le richieste
# sono poche: due bastano, e l'add-on occupa meno.
ENV OMP_NUM_THREADS=2     OPENBLAS_NUM_THREADS=2     MKL_NUM_THREADS=2

COPY app /app

LABEL \
  io.hass.name="Riconoscimento volti" \
  io.hass.description="Confronto documento-selfie, lettura della MRZ e riconoscimento all'ingresso" \
  io.hass.type="addon" \
  io.hass.version="0.6.1"

CMD ["python3", "-u", "/app/server.py"]
