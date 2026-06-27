FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Outils de base + PPA deadsnakes pour Python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl gnupg && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev \
        # VLC (libvlc) requis à la compilation car le .spec importe vlc
        vlc libvlc-dev \
        # SDL/pygame s'appuient sur ces libs au runtime de l'analyse
        libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
        # compression UPX (le spec a upx=True)
        upx-ucl \
        binutils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Dépendances Python dans un venv Python 3.12
COPY requirements.txt .
RUN python3.12 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt pyinstaller

# 3. Code source
COPY . .

# 4. Build PyInstaller
RUN /opt/venv/bin/pyinstaller --clean -y five_spots_player.spec

# --- Build & récupération du livrable ---
#
#   docker build -t five-spots-build .
#
# Pour sortir le bundle : créer l'archive DANS le conteneur puis copier ce fichier
# unique. NE PAS `docker cp` tout le dossier dist/ sous Windows (symlinks pygame_ce
# impossibles à créer sur NTFS -> copie interrompue, exécutable manquant), et NE PAS
# rediriger tar via le `>` de PowerShell (ré-encodage UTF-16 -> archive corrompue,
# "gzip: not in gzip format"). La méthode ci-dessous évite les deux (PowerShell + bash) :
#
#   docker run --name fsp-pack five-spots-build \
#     sh -c 'cd /app/dist && tar czf /tmp/fsp.tar.gz five-spots-player-1.0.0'
#   docker cp fsp-pack:/tmp/fsp.tar.gz ./five-spots-player-1.0.0-linux-x86_64.tar.gz
#   docker rm fsp-pack
#
# (Linux/macOS/Git Bash, en une ligne :
#   docker run --rm five-spots-build sh -c 'cd /app/dist && tar czf - five-spots-player-1.0.0' > five-spots-player-1.0.0-linux-x86_64.tar.gz )
#
# Côté Linux : tar xzf ...tar.gz && cd five-spots-player-1.0.0 && ./five-spots-player-1.0.0
