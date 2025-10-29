# Base image
FROM mcr.microsoft.com/vscode/devcontainers/python:3.10 [cite: 11]

# Instalar dependencias del SO y Google Chrome en una sola capa
# Eliminamos curl y unzip, ya que webdriver_manager gestiona chromedriver
RUN apt-get update && apt-get install -y \
    wget \
    xvfb \
    libxi6 \
    --no-install-recommends \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb; \
    apt-get -fy install \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Nota: No instalamos chromedriver manualmente.
# webdriver_manager lo hará cuando ejecutes el script.
