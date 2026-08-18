# Debian, non Alpine: opencv e i suoi modelli non hanno pacchetti pronti per musl.
# Il Supervisor propone la sua immagine di base, che e' Alpine, e qui non serve.
FROM python:3.12-slim-bookworm

# OpenCV senza interfaccia grafica ha bisogno solo di questa, non di Qt ne' di GStreamer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# I due modelli, scaricati una volta sola qui e non a ogni avvio.
# YuNet trova le facce (227 KB), ArcFace le trasforma in numeri (166 MB).
RUN mkdir -p /modelli \
    && curl -fsSL -o /modelli/yunet.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    && curl -fsSL -o /tmp/buffalo_l.zip \
       https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip \
    && unzip -j -o /tmp/buffalo_l.zip w600k_r50.onnx -d /modelli \
    && rm -f /tmp/buffalo_l.zip \
    && apt-get purge -y curl unzip && apt-get autoremove -y

COPY app /app

LABEL \
  io.hass.name="Riconoscimento volti" \
  io.hass.description="Confronto documento-selfie e riconoscimento all'ingresso" \
  io.hass.type="addon" \
  io.hass.version="0.2.0"

CMD ["python3", "-u", "/app/server.py"]
