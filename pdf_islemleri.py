import pdfplumber
import pandas as pd

def pdf_programi_oku(pdf_yolu):
    """TTF Maç programı PDF'ini okuyup yapılandırılmış bir tabloya çevirir."""
    maclar = []
    
    try:
        with pdfplumber.open(pdf_yolu) as pdf:
            # Sadece ilk sayfayı okuyoruz (genelde program tek sayfadır)
            sayfa = pdf.pages[0]
            
            # PDF içindeki tabloyu çekiyoruz
            tablo = sayfa.extract_table()
            
            if not tablo:
                return "Hata: PDF içinde okunabilir bir tablo bulunamadı."
            
            # DataFrame'e çeviriyoruz
            df = pd.DataFrame(tablo[1:], columns=tablo[0])
            return df
            
    except Exception as e:
        return f"PDF Okuma Hatası: {e}"

# Test etmek için alt kısım:
if __name__ == "__main__":
    # PDF dosyanın tam adını buraya yazarak yerelde test edebiliriz
    dosya_adi = "tournament_court_players.pdf" 
    sonuc = pdf_programi_oku(dosya_adi)
    print(sonuc)
