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

COPY requirements.txt /tmp/requirements.txt

# Il lettore della MRZ pretende opencv-python, quello con l'interfaccia grafica,
# che dentro un contenitore senza schermo non si carica affatto. Si toglie e si
# rimette quello senza: e' lo stesso cv2, meno le finestre.
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && pip3 uninstall -y opencv-python \
    && pip3 install --no-cache-dir --force-reinstall opencv-python-headless==4.12.0.88

# I modelli dei volti, scaricati una volta sola qui e non a ogni avvio.
# YuNet trova le facce (227 KB), ArcFace le trasforma in numeri (166 MB).
RUN mkdir -p /modelli \
    && curl -fsSL -o /modelli/yunet.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    && curl -fsSL -o /tmp/buffalo_l.zip \
       https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip \
    && unzip -j -o /tmp/buffalo_l.zip w600k_r50.onnx -d /modelli \
    && rm -f /tmp/buffalo_l.zip \
    && apt-get purge -y curl unzip && apt-get autoremove -y

# Anche i modelli della MRZ una volta sola qui: si scaricano da Google Drive,
# e un add-on che parte non deve dipendere da quel viaggio.
RUN python3 -c "from mrzscanner import MRZScanner; MRZScanner()"

COPY app /app

LABEL \
  io.hass.name="Riconoscimento volti" \
  io.hass.description="Confronto documento-selfie, lettura della MRZ e riconoscimento all'ingresso" \
  io.hass.type="addon" \
  io.hass.version="0.4.1"

CMD ["python3", "-u", "/app/server.py"]
