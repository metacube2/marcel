#!/bin/bash
# stream_konvertieren.sh - Optimiert für FFmpeg 6.1 und kontinuierliches Streaming

# Beim Start alte Dateien aufräumen
rm -f /var/www/html/segment_*.ts
rm -f /var/www/html/test_video.m3u8

echo "Starte Stream-Konverter (FFmpeg 6.1)..."

while true; do
    ffmpeg -analyzeduration 10M -probesize 10M \
    -rtsp_transport tcp \
    -i "rtsp://aurora:%2B61946194@192.168.1.133:554/videoMain" \
    -c:v libx264 \
    -preset veryfast \
    -tune zerolatency \
    -crf 28 \
    -s 1920x1080 \
    -r 25 \
    -b:v 3M \
    -maxrate 3M \
    -bufsize 6M \
    -g 50 \
    -keyint_min 25 \
    -sc_threshold 0 \
    -an \
    -f hls \
    -hls_time 4 \
    -hls_list_size 20 \
    -hls_flags delete_segments+independent_segments+append_list \
    -hls_segment_type mpegts \
    -hls_segment_filename "/var/www/html/segment_%03d.ts" \
    -hls_base_url "" \
    /var/www/html/test_video.m3u8 2>&1 | tee /tmp/ffmpeg.log

    if [ $? -ne 0 ]; then
        echo "FFmpeg Fehler - Neustart in 5 Sekunden..."
        sleep 5
        # Aufräumen vor Neustart
        rm -f /var/www/html/segment_*.ts
        rm -f /var/www/html/test_video.m3u8
    fi
done
