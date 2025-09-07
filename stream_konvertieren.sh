0~#!/bin/bash
while true; do
    ffmpeg -analyzeduration 20M -probesize 20M \
    -rtsp_transport tcp \
    -i "rtsp://aurora:%2B61946194@192.168.1.133:554/videoMain" \
    -c:v libx264 \
    -preset superfast \
    -crf 28 \
    -s 3840x2160 \
    -r 25 \
    -b:v 4M \
    -maxrate 4M \
    -bufsize 8M \
    -g 40 \
    -keyint_min 40 \
    -sc_threshold 0 \
    -an \
    -f hls \
    -hls_time 6 \
    -hls_list_size 5 \
    -hls_flags delete_segments \
    -hls_segment_filename "/var/www/html/segment_%03d.ts" \
    /var/www/html/test_video.m3u8 2>&1 | tee /tmp/ffmpeg.log

    # Prüfe Verbindung
    if [ $? -ne 0 ]; then
        echo "Fehler aufgetreten - warte 5 Sekunden..." >> /tmp/ffmpeg.log
        sleep 5
    fi
done

