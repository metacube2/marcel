import os
import numpy as np
from PIL import Image
import shutil
import time

def ist_graubild_einfach(bildpfad, max_rgb_diff=20):
    """
    EINFACHSTE Methode: Prüfe ob R ≈ G ≈ B für alle Pixel
    Bei Grau sind die RGB-Werte fast identisch!
    """
    try:
        img = Image.open(bildpfad)
        
        if img.mode == 'L':
            return True, {'methode': 'Graustufen-Modus'}
        
        img_rgb = img.convert('RGB')
        # Kleiner für Speed
        img_rgb.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
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
        median_diff = np.median(max_diff_per_pixel)
        p90_diff = np.percentile(max_diff_per_pixel, 90)
        p95_diff = np.percentile(max_diff_per_pixel, 95)
        
        # ENTSCHEIDUNG: Grau wenn 95% der Pixel RGB-Differenz < Schwellwert haben
        ist_grau = p95_diff < max_rgb_diff
        
        return ist_grau, {
            'mean_diff': float(mean_diff),
            'median_diff': float(median_diff),
            'p90_diff': float(p90_diff),
            'p95_diff': float(p95_diff),
            'ist_grau': ist_grau
        }
        
    except Exception as e:
        print(f"Fehler bei {bildpfad}: {e}")
        return False, {}

def filtere_graue_bilder_final(quellordner, zielordner_grau=None, 
                                max_rgb_diff=20, verschieben=True,  loeschen=False):
    """
    Finale optimierte Version - einfach und effektiv
    
    max_rgb_diff: Schwellwert für RGB-Differenz
      - 15 = sehr streng (nur pure Graubilder)
      - 20 = empfohlen (auch leicht getönte Graubilder)
      - 25 = lockerer (auch stark entsättigte Bilder)
    """
    
    if zielordner_grau and not os.path.exists(zielordner_grau):
        os.makedirs(zielordner_grau)
    
    bilddateien = [f for f in sorted(os.listdir(quellordner)) 
                   if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    graue_bilder = []
    farbige_bilder = []
    
    gesamt = len(bilddateien)
    print(f"Verarbeite {gesamt} Bilder...")
    print(f"Schwellwert: RGB-Differenz < {max_rgb_diff}\n")
    
    start_zeit = time.time()
    
    for idx, datei in enumerate(bilddateien, 1):
        vollpfad = os.path.join(quellordner, datei)
        
        ist_grau, metriken = ist_graubild_einfach(vollpfad, max_rgb_diff)
        
        if idx % 100 == 0 or idx == gesamt:
            verstrichene_zeit = time.time() - start_zeit
            bilder_pro_sek = idx / verstrichene_zeit if verstrichene_zeit > 0 else 0
            verbleibend = (gesamt - idx) / bilder_pro_sek if bilder_pro_sek > 0 else 0
            print(f"  [{idx}/{gesamt}] - {bilder_pro_sek:.1f} Bilder/Sek - "
                  f"~{int(verbleibend)}s verbleibend")
        
        if ist_grau:
            graue_bilder.append((datei, metriken))
            if loeschen:  # ← NEU: Löschen statt verschieben
                os.remove(vollpfad)
            elif zielordner_grau:
                ziel = os.path.join(zielordner_grau, datei)
                if verschieben:
                    shutil.move(vollpfad, ziel)
                else:
                    shutil.copy2(vollpfad, ziel)
        else:
            farbige_bilder.append((datei, metriken))
    
    gesamt_zeit = time.time() - start_zeit
    print(f"\n{'='*60}")
    print(f"✓ FERTIG in {gesamt_zeit:.1f} Sekunden ({gesamt/gesamt_zeit:.1f} Bilder/Sek)")
    print(f"✓ ERGEBNIS: {len(graue_bilder)} graue, {len(farbige_bilder)} farbige Bilder")
    print(f"{'='*60}\n")
    
    # Details
    if graue_bilder:
        print("GRAUE BILDER (erste 10):")
        for datei, metriken in graue_bilder[:10]:
            print(f"  {datei}: P95-Diff={metriken.get('p95_diff', 0):.1f}")
        if len(graue_bilder) > 10:
            print(f"  ... und {len(graue_bilder) - 10} weitere")
    
    if farbige_bilder:
        print("\nFARBIGE BILDER (erste 10):")
        for datei, metriken in farbige_bilder[:10]:
            print(f"  {datei}: P95-Diff={metriken.get('p95_diff', 0):.1f}")
        if len(farbige_bilder) > 10:
            print(f"  ... und {len(farbige_bilder) - 10} weitere")

if __name__ == "__main__":
    quellordner = "./image"
    zielordner_grau = "graue_bilder"
    
    # Starte mit Schwellwert 20
    # Wenn zu viele Farbbilder als grau erkannt werden: auf 15 senken
    # Wenn zu viele Graubilder durchrutschen: auf 25 erhöhen
    filtere_graue_bilder_final(
        quellordner, 
        zielordner_grau,
        max_rgb_diff=20,
        verschieben=True,loeschen=False
    )
