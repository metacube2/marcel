# rtps_daily_recorder.py
import os
import time
import sys
from datetime import datetime, timedelta
import subprocess
import logging
from pathlib import Path
try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("PIL/numpy nicht installiert. Führen Sie 'pip install Pillow numpy' aus.")
    sys.exit(1)

# Einheitliche Konfiguration
CONFIG = {
    "BASE_DIR": "/var/www/html/image/",
    "RESIZE_DIR": "/var/www/html/images/",
    "RTSP_URL": "rtsp://aurora:%2B61946194@192.168.1.133:88/videoMain",
    "LOG_FILE": "/var/www/html/rtsp-recorder.log",
    "HOURS_TO_RUN": 24,
    "SCREENSHOT_INTERVAL": 33,
    "VIDEO_FPS": 5,
    "VIDEO_RETENTION_DAYS": 7,
    "TARGET_WIDTH": 274,
    "TARGET_HEIGHT": 52,
    "SCREENSHOTS_PER_HOUR": 109,
    "GREY_THRESHOLD": 20,  # NEU: RGB-Differenz Schwellwert für Grau-Erkennung
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

    def check_and_create_missing_videos(self):
        """Prüft ob Videos für die letzten 7 Tage existieren und erstellt fehlende"""
        logging.info("Prüfe auf fehlende Videos der letzten 7 Tage...")
        
        for days_ago in range(CONFIG["VIDEO_RETENTION_DAYS"]):
            target_date = datetime.now() - timedelta(days=days_ago)
            date_str = target_date.strftime("%Y%m%d")
            
            existing_videos = list(self.base_dir.glob(f"daily_video_{date_str}_*.mp4"))
            
            if not existing_videos:
                logging.info(f"Kein Video für {date_str} gefunden. Erstelle aus vorhandenen Screenshots...")
                self.create_video_for_date(target_date)
            else:
                logging.info(f"Video für {date_str} bereits vorhanden: {existing_videos[0].name}")

    def is_grey_image(self, image_path, max_rgb_diff=None):
        """
        VERBESSERTE Grau-Erkennung mit RGB-Differenz-Methode
        Funktioniert auch bei sehr dunklen Bildern!
        
        Prüft ob R ≈ G ≈ B für alle Pixel (bei Grau sind RGB-Werte identisch)
        """
        if max_rgb_diff is None:
            max_rgb_diff = CONFIG["GREY_THRESHOLD"]
            
        try:
            img = Image.open(image_path)
            
            # Direkter Graustufen-Modus
            if img.mode == 'L':
                logging.info(f"✓ Graubild (L-Modus): {image_path.name}")
                return True
            
            # RGB Bild analysieren mit NumPy
            if img.mode in ('RGB', 'RGBA'):
                img_rgb = img.convert('RGB')
                
                # Resize für Performance (behält Genauigkeit)
                img_rgb.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                # NumPy Array - vektorisierte Berechnung
                img_array = np.array(img_rgb, dtype=np.float32)
                
                r = img_array[:, :, 0]
                g = img_array[:, :, 1]
                b = img_array[:, :, 2]
                
                # Berechne maximale Differenz zwischen R, G, B für jeden Pixel
                diff_rg = np.abs(r - g)
                diff_gb = np.abs(g - b)
                diff_rb = np.abs(r - b)
                
                max_diff_per_pixel = np.maximum(np.maximum(diff_rg, diff_gb), diff_rb)
                
                # Statistiken
                mean_diff = np.mean(max_diff_per_pixel)
                p95_diff = np.percentile(max_diff_per_pixel, 95)
                
                # ENTSCHEIDUNG: Grau wenn 95% der Pixel RGB-Differenz < Schwellwert haben
                ist_grau = p95_diff < max_rgb_diff
                
                if ist_grau:
                    logging.info(f"✓ Graubild (P95={p95_diff:.1f}, Mean={mean_diff:.1f}): {image_path.name}")
                else:
                    logging.debug(f"✗ Farbig (P95={p95_diff:.1f}, Mean={mean_diff:.1f}): {image_path.name}")
                
                return ist_grau
                
        except Exception as e:
            logging.error(f"Fehler bei Graubildprüfung {image_path.name}: {e}")
            return False
        
        return False

    def create_video_for_date(self, target_date):
        """Erstellt ein Video für ein spezifisches Datum aus vorhandenen Screenshots"""
        date_str = target_date.strftime("%Y%m%d")
        
        jpg_files = []
        for jpg in sorted(self.base_dir.glob(f"screenshot_{date_str}_*.jpg")):
            # Filtere auch hier graue Bilder aus
            if not self.is_grey_image(jpg):
                jpg_files.append(jpg)
        
        if len(jpg_files) < 10:
            logging.warning(f"Zu wenige Screenshots für {date_str} ({len(jpg_files)} gefunden)")
            return False
        
        timestamp = target_date.strftime("%Y%m%d_%H%M%S")
        output_file = self.base_dir / f"daily_video_{timestamp}.mp4"
        temp_list = Path(f"/tmp/files_{timestamp}.txt")
        
        try:
            with temp_list.open('w') as f:
                for jpg in jpg_files:
                    f.write(f"file '{jpg.absolute()}'\n")
                    f.write(f"duration 0.2\n")

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
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if output_file.exists() and output_file.stat().st_size > 0:
                logging.info(f"Nachträglich Video erstellt für {date_str}: {output_file}")
                return True
                
        except Exception as e:
            logging.error(f"Fehler beim Erstellen des Videos für {date_str}: {e}")
            return False
        finally:
            if temp_list.exists():
                temp_list.unlink()

    def resize_image(self, image_path):
        """Passt die Bildgröße an die Zielgröße an und behält das Seitenverhältnis bei"""
        try:
            with Image.open(image_path) as img:
                current_width, current_height = img.size
                target_width = CONFIG["TARGET_WIDTH"]
                target_height = CONFIG["TARGET_HEIGHT"]

                aspect_ratio = current_width / current_height
                target_ratio = target_width / target_height

                if current_width != target_width or current_height != target_height:
                    if aspect_ratio > target_ratio:
                        new_width = target_width
                        new_height = int(target_width / aspect_ratio)
                    else:
                        new_height = target_height
                        new_width = int(target_height * aspect_ratio)

                    background = Image.new('RGB', (target_width, target_height), (255, 255, 255))
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    x = (target_width - new_width) // 2
                    y = (target_height - new_height) // 2
                    
                    background.paste(resized_img, (x, y))
                    background.save(image_path, "PNG", optimize=True)
                    logging.info(f"Bild angepasst: {image_path}")
                    return True
                return False
        except Exception as e:
            logging.error(f"Fehler bei Bildanpassung {image_path}: {e}")
            return False

    def resize_all_images(self):
        """Passt alle PNG-Bilder im RESIZE_DIR an"""
        for png_file in Path(CONFIG["RESIZE_DIR"]).glob("*.png"):
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

    def create_daily_video(self):
        """Erstelle ein Video aus den gesammelten Screenshots - LÖSCHE GRAUE BILDER"""
        logging.info("="*60)
        logging.info("Starte Videoerstellung mit verbessertem Graufilter...")
        logging.info("="*60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.base_dir / f"daily_video_{timestamp}.mp4"
        temp_list = Path(f"/tmp/files_{timestamp}.txt")

        cutoff_time = datetime.now() - timedelta(hours=CONFIG["HOURS_TO_RUN"])
        
        # Sammle ALLE JPG-Dateien
        all_jpg_files = sorted([
            f for f in self.base_dir.glob("screenshot_*.jpg")
            if f.stat().st_mtime > cutoff_time.timestamp()
        ])
        
        logging.info(f"Gefunden: {len(all_jpg_files)} Screenshots insgesamt")
        
        # FILTERE und LÖSCHE graue Bilder
        jpg_files = []
        grey_files_to_delete = []
        
        for idx, jpg in enumerate(all_jpg_files, 1):
            if idx % 50 == 0:
                logging.info(f"  Prüfe Bild {idx}/{len(all_jpg_files)}...")
                
            if not self.is_grey_image(jpg):
                jpg_files.append(jpg)
            else:
                grey_files_to_delete.append(jpg)
        
        # LÖSCHE alle grauen Bilder
        for grey_file in grey_files_to_delete:
            try:
                grey_file.unlink()
                logging.info(f"🗑️  Graues Bild gelöscht: {grey_file.name}")
            except Exception as e:
                logging.error(f"Fehler beim Löschen von {grey_file.name}: {e}")
        
        grey_count = len(grey_files_to_delete)
        logging.info("")
        logging.info("="*60)
        logging.info(f"FILTER-ERGEBNIS:")
        logging.info(f"  Gute Bilder: {len(jpg_files)}")
        logging.info(f"  Graue gelöscht: {grey_count}")
        
        if len(all_jpg_files) > 0:
            filter_rate = (grey_count / len(all_jpg_files)) * 100
            logging.info(f"  Löschrate: {filter_rate:.1f}%")
            
            if filter_rate > 50:
                logging.warning("⚠️  WARNUNG: Über 50% gelöscht - Filter möglicherweise zu strikt!")
                logging.warning(f"⚠️  Erhöhe GREY_THRESHOLD in CONFIG (aktuell: {CONFIG['GREY_THRESHOLD']})")
        logging.info("="*60)

        if len(jpg_files) < 10:
            logging.warning(f"Zu wenige Bilder ({len(jpg_files)}) für Video")
            return False

        try:
            with temp_list.open('w') as f:
                for jpg in jpg_files:
                    f.write(f"file '{jpg.absolute()}'\n")
                    f.write(f"duration 0.2\n")

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
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if output_file.exists() and output_file.stat().st_size > 0:
                logging.info(f"✓ Video erstellt: {output_file}")
                
                # Lösche nur die GUTEN JPGs (graue wurden schon gelöscht)
                for jpg in jpg_files:
                    jpg.unlink()
                logging.info(f"✓ {len(jpg_files)} gute Screenshots gelöscht nach Videoerstellung")
                return True
                
        except Exception as e:
            logging.error(f"Fehler bei Videoerstellung: {e}")
            return False
        finally:
            if temp_list.exists():
                temp_list.unlink()

    def cleanup_old_files(self):
        """Lösche alte Video- und Bilddateien (nur älter als 7 Tage)"""
        cutoff_time = datetime.now() - timedelta(days=CONFIG["VIDEO_RETENTION_DAYS"])
        
        # Lösche verwaiste Screenshots älter als 7 Tage
        for jpg in self.base_dir.glob("screenshot_*.jpg"):
            if jpg.stat().st_mtime < cutoff_time.timestamp():
                jpg.unlink()
                logging.info(f"Verwaistes Bild gelöscht (>7 Tage): {jpg}")

    def cleanup(self):
        """Aufräumen vor Beendigung"""
        try:
            self.cleanup_old_files()
            logging.info("Aufräumen abgeschlossen")
        except Exception as e:
            logging.error(f"Fehler beim Aufräumen: {e}")

def main():
    service = CameraService()
    logging.info("="*60)
    logging.info("Starte Kamera-Service mit verbesserter Grau-Erkennung")
    logging.info(f"Grau-Schwellwert: RGB-Differenz < {CONFIG['GREY_THRESHOLD']}")
    logging.info("="*60)
    

    # Warte unbegrenzt bis grey.py fertig ist
    logging.info("Starte Grau-Filterung (warte auf Abschluss)...")
    returncode = subprocess.call([sys.executable, "grey.py"])
    
    if returncode == 0:
        logging.info("✓ Grau-Filterung abgeschlossen")
    else:
        logging.error(f"✗ Grau-Filterung fehlgeschlagen (Exit-Code: {returncode})")
    

    retry_count = 0
    max_retries = 3

    try:
        if not service.validate_config():
            raise RuntimeError("Ungültige Konfiguration")

        service.check_and_create_missing_videos()

        while True:
            service.execution_count = 0
            total_screenshots = CONFIG["HOURS_TO_RUN"] * CONFIG["SCREENSHOTS_PER_HOUR"]
            logging.info(f"Starte neuen 24-Stunden-Zyklus mit {total_screenshots} Screenshots")
            
            service.resize_all_images()
            
            while service.execution_count < total_screenshots:
                if service.take_screenshot():
                    service.execution_count += 1
                    retry_count = 0
                    logging.info(f"Screenshot {service.execution_count} von {total_screenshots}")
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.error(f"Screenshot nach {max_retries} Versuchen fehlgeschlagen")
                        raise RuntimeError("Zu viele fehlgeschlagene Versuche")
                    logging.warning(f"Screenshot fehlgeschlagen ({retry_count}/{max_retries}), warte 60 Sekunden...")
                    time.sleep(60)
                    continue

                if service.execution_count % 100 == 0:
                    service.cleanup_old_files()
                
                if service.execution_count < total_screenshots:
                    time.sleep(CONFIG["SCREENSHOT_INTERVAL"])

            if service.create_daily_video():
                logging.info("✓ 24-Stunden-Video erfolgreich erstellt")
            else:
                logging.error("✗ Fehler beim Erstellen des Tagesvideos")
            
            service.check_and_create_missing_videos()
            
            logging.info("Starte neuen 24-Stunden-Zyklus...")

    except KeyboardInterrupt:
        logging.info("Programm durch Benutzer beendet")
    except Exception as e:
        logging.error(f"Unerwarteter Fehler: {e}")
        raise
    finally:
        service.cleanup()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "video":
        service = CameraService()
        service.create_daily_video()
        sys.exit(0)
    else:
        main()
