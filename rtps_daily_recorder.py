import os
import time
import sys
from datetime import datetime, timedelta
import subprocess
import logging
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    print("PIL nicht installiert. Führen Sie 'pip install Pillow' aus.")
    sys.exit(1)

# Einheitliche Konfiguration
CONFIG = {
    "BASE_DIR": "/var/www/html/image/",          # Für RTSP-Screenshots und Videos
    "RESIZE_DIR": "/var/www/html/images/",        # Für die zu resizenden Bilder
  "RTSP_URL": "rtsp://aurora:%2B61946194@192.168.1.133:88/videoMain",  # @ escaped als %40
    "LOG_FILE": "/var/www/html/rtsp-recorder.log",
    "HOURS_TO_RUN": 24,
    "SCREENSHOT_INTERVAL": 33, #3600,
    "VIDEO_FPS": 5,
    "VIDEO_RETENTION_DAYS": 7,
    "TARGET_WIDTH": 274,
    "TARGET_HEIGHT": 52,
    "SCREENSHOTS_PER_HOUR": 109,           # 12 Screenshots pro Stunde (NEU)
}

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(CONFIG["LOG_FILE"]),
        logging.StreamHandler()
    ]
)


class CameraService:
    def __init__(self):
        self.execution_count = 0
        self.base_dir = Path(CONFIG["BASE_DIR"])
        self.resize_dir = Path(CONFIG["RESIZE_DIR"])
        self.ensure_directories()

    def ensure_directories(self):
        """Stelle sicher, dass alle benötigten Verzeichnisse existieren"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.resize_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Arbeitsverzeichnisse bereit: {self.base_dir}, {self.resize_dir}")

    def validate_config(self):
        """Überprüft die Konfigurationswerte"""
        if not self.base_dir.exists():
            logging.error(f"Verzeichnis nicht gefunden: {self.base_dir}")
            return False
        return True

    def resize_image(self, image_path):
        """Passt die Bildgröße an die Zielgröße an und behält das Seitenverhältnis bei"""
        try:
            with Image.open(image_path) as img:
                current_width, current_height = img.size
                target_width = CONFIG["TARGET_WIDTH"]
                target_height = CONFIG["TARGET_HEIGHT"]

                # Berechne das Seitenverhältnis
                aspect_ratio = current_width / current_height
                target_ratio = target_width / target_height

                if current_width != target_width or current_height != target_height:
                    # Berechne neue Dimensionen mit Hintergrund
                    if aspect_ratio > target_ratio:
                        # Bild ist breiter als Zielformat
                        new_width = target_width
                        new_height = int(target_width / aspect_ratio)
                    else:
                        # Bild ist höher als Zielformat
                        new_height = target_height
                        new_width = int(target_height * aspect_ratio)

                    # Erstelle neues Bild mit WEISSEM Hintergrund
                    background = Image.new('RGB', (target_width, target_height), (255, 255, 255))
                    
                    # Resize Original
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Berechne Position zum Zentrieren
                    x = (target_width - new_width) // 2
                    y = (target_height - new_height) // 2
                    
                    # Füge das resized Bild in den Hintergrund ein
                    background.paste(resized_img, (x, y))
                    
                    # Speichern
                    background.save(image_path, "PNG", optimize=True)
                    logging.info(f"Bild angepasst: {image_path}")
                    return True
                return False
        except Exception as e:
            logging.error(f"Fehler bei Bildanpassung {image_path}: {e}")
            return False




    def resize_all_images(self):
        """Passt alle PNG-Bilder im RESIZE_DIR an"""
        for png_file in Path(CONFIG["RESIZE_DIR"]).glob("*.png"):  # *.png statt *.jpg
            self.resize_image(png_file)


    def take_screenshot(self):
        """Erstelle einen Screenshot von der RTSP-Kamera"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.base_dir / f"screenshot_{timestamp}.jpg"
        
        logging.info("Erstelle Screenshot...")
        
        try:
  
            cmd = [
            'ffmpeg', '-y', '-rtsp_transport', 'tcp',
            '-analyzeduration', '20M', '-probesize', '20M',
            '-i', CONFIG["RTSP_URL"], '-vframes', '1', '-q:v', '2',
            '-ss', '00:00:01', str(output_file)
            ]


            # Verbose Logging hinzufügen
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logging.error(f"FFmpeg Fehler: {process.stderr}")
                return False
                
            if output_file.exists():
                logging.info(f"Screenshot erstellt: {output_file}")
                return True
            return False
        except subprocess.CalledProcessError as e:
            logging.error(f"Screenshot-Fehler: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Unerwarteter Fehler: {e}")
            return False




    def resize_all_images(self):
        """Passt NUR die PNG-Bilder im RESIZE_DIR an"""
        # Nur Bilder in /var/www/html/images/ werden resized
        for png_file in Path(CONFIG["RESIZE_DIR"]).glob("*.png"):
            self.resize_image(png_file)
        logging.info("Website-Bilder in /images/ angepasst")



    def create_daily_video(self):
        """Erstelle ein Video aus den gesammelten Screenshots"""
        logging.info("Starte Videoerstellung...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.base_dir / f"daily_video_{timestamp}.mp4"
        temp_list = Path(f"/tmp/files_{timestamp}.txt")

        # Finde das vorherige Video
        previous_videos = sorted(self.base_dir.glob("daily_video_*.mp4"))
        previous_video = previous_videos[-1] if previous_videos else None

        cutoff_time = datetime.now() - timedelta(hours=CONFIG["HOURS_TO_RUN"])
        jpg_files = sorted([
            f for f in self.base_dir.glob("screenshot_*.jpg")
            if f.stat().st_mtime > cutoff_time.timestamp()
        ])

        if not jpg_files:
            logging.warning("Keine Bilder für Video gefunden")
            return False

        try:
            # Erstelle die Dateiliste
            with temp_list.open('w') as f:
                for jpg in jpg_files:
                    f.write(f"file '{jpg.absolute()}'\n")
                    f.write(f"duration 0.2\n")  # Jedes Bild 0.2 Sekunden zeigen

            # FFmpeg Befehl
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(temp_list),
                '-vsync', 'vfr',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'fast',
                '-crf', '23',
                str(output_file)
            ]
            
            # Führe FFmpeg aus
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Prüfe ob das neue Video erfolgreich erstellt wurde
            if output_file.exists() and output_file.stat().st_size > 0:
                logging.info(f"Video erstellt: {output_file}")
                
                # Lösche das alte Video erst nach erfolgreicher Erstellung des neuen
                # if previous_video and previous_video != output_file:
                 #    previous_video.unlink()
                #     logging.info(f"Altes Video gelöscht: {previous_video}")
                
                # Lösche die verwendeten JPGs
                for jpg in jpg_files:
                    jpg.unlink()
                logging.info(f"{len(jpg_files)} Screenshots verarbeitet und gelöscht")
                return True
            else:
                logging.error("Neues Video wurde nicht korrekt erstellt")
                return False

        except subprocess.CalledProcessError as e:
            logging.error(f"Videoverarbeitung fehlgeschlagen: {e}")
            return False
        except Exception as e:
            logging.error(f"Fehler bei Videoerstellung: {e}")
            return False
        finally:
            if temp_list.exists():
                temp_list.unlink()



    def cleanup_old_files(self):
        """Lösche alte Video- und Bilddateien"""
        cutoff_time = datetime.now() - timedelta(days=CONFIG["VIDEO_RETENTION_DAYS"])
        
        for video in self.base_dir.glob("daily_video_*.mp4"):
            if video.stat().st_mtime < cutoff_time.timestamp():
                video.unlink()
                logging.info(f"Altes Video gelöscht: {video}")

        for jpg in self.base_dir.glob("screenshot_*.jpg"):
            if jpg.stat().st_mtime < cutoff_time.timestamp():
                jpg.unlink()
                logging.info(f"Verwaistes Bild gelöscht: {jpg}")

    def cleanup(self):
        """Aufräumen vor Beendigung"""
        try:
            self.cleanup_old_files()
            logging.info("Aufräumen abgeschlossen")
        except Exception as e:
            logging.error(f"Fehler beim Aufräumen: {e}")

def main():
    service = CameraService()
    logging.info("Starte Kamera-Service...")
    retry_count = 0
    max_retries = 3

    try:
        if not service.validate_config():
            raise RuntimeError("Ungültige Konfiguration")

        while True:  # Endlosschleife
            service.execution_count = 0
            total_screenshots = CONFIG["HOURS_TO_RUN"] * CONFIG["SCREENSHOTS_PER_HOUR"]
            
            service.resize_all_images()
            
            while service.execution_count < total_screenshots:
                if service.take_screenshot():
                    service.execution_count += 1
                    retry_count = 0  # Reset retry counter on success
                    logging.info(f"Screenshot {service.execution_count} von {total_screenshots}")
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.error(f"Screenshot nach {max_retries} Versuchen fehlgeschlagen")
                        raise RuntimeError("Zu viele fehlgeschlagene Versuche")
                    logging.warning(f"Screenshot fehlgeschlagen ({retry_count}/{max_retries}), warte 60 Sekunden...")
                    time.sleep(60)
                    continue

                service.cleanup_old_files()
                
                if service.execution_count < total_screenshots:
                    time.sleep(CONFIG["SCREENSHOT_INTERVAL"])  # Nutze den Wert aus CONFIG

            if service.create_daily_video():
                logging.info("Täglicher Zyklus erfolgreich abgeschlossen")
            else:
                logging.error("Fehler beim Erstellen des Tagesvideos")
            
            logging.info("Starte neuen 12-Stunden-Zyklus...")

    except KeyboardInterrupt:
        logging.info("Programm durch Benutzer beendet")
    except Exception as e:
        logging.error(f"Unerwarteter Fehler: {e}")
        raise
    finally:
        service.cleanup()



if __name__ == "__main__":
    main()
