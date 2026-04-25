#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Download and install ffmpeg
mkdir -p ffmpeg
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ --strip-components=1 -C ffmpeg
export PATH=$PATH:$(pwd)/ffmpeg