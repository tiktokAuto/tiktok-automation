FROM python:3.11-slim

# Installer FFmpeg et dépendances
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire de l'application
WORKDIR /app

# Copier les requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY app.py .

# Créer le dossier temporaire
RUN mkdir -p /tmp/tiktok_videos

# Exposer le port
EXPOSE 5000

# Commande de démarrage
CMD ["python", "app.py"]
