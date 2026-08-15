import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")
st.title("👑 Başhakem Kontrol Paneli")

def ayarlari_ayikla(df):
    """Karmaşık tablo hücrelerini okuyup temiz bir maç listesine dönüştürür."""
    mac_listesi = []
    
    # Kort sütunlarını döngüye alıyoruz (Kort 1, Kort 2 vb.)
    for kort in df.columns:
        for hucre in df[kort]:
            # Eğer hücre boşsa atla
            if pd.isna(hucre) or str(hucre).strip() == "":
                continue
            
            # Hücre içindeki satırları bölüyoruz
            satirlar = [s.strip() for s in str(hucre).split('\n') if s.strip()]
            
            # Eğer hücre bir maç hücresiyse (genelde en az 4 satır olur)
            if len(satirlar) >= 4:
                saat = satirlar[0] # İlk satır her zaman saat ve maç nosu (örn: "09:00 M 1")
                oyuncu_1 = satirlar[1] # İkinci satır birinci oyuncu
                
                # Kategoriyi ("10 Yaş", "9 Yaş" içeren satırı) bul
                kategori = next((s for s in satirlar if "Yaş" in s or "Kategori" in s), "Kategori Bulunamadı")
                
                # İkinci oyuncu genelde sondan bir veya iki önceki satırdadır (kulüp isminden dolayı)
                # Şimdilik basitçe kategoriden sonraki satırı alalım
                try:
                    kat_index = satirlar.index(kategori)
                    oyuncu_2 = satirlar[kat_index + 1]
                except:
                    oyuncu_2 = "Bilinmiyor"

                # Temiz maç sözlüğümüz (JSON formatına çok uygun)
                mac_listesi.append({
                    "Kort": kort,
                    "Saat": saat,
                    "Kategori": kategori,
                    "Oyuncu 1": oyuncu_1,
                    "Oyuncu 2": oyuncu_2,
                    "Durum": "Baslamadi" # İleride renkleri (gri/yeşil/pembe) bununla kontrol edeceğiz
                })
                
    return pd.DataFrame(mac_listesi)

# --- Arayüz ve Yükleme Kısmı ---
yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")

if yuklenen_pdf:
    with st.spinner("PDF ayrıştırılıyor..."):
        try:
            with pdfplumber.open(yuklenen_pdf) as pdf:
                sayfa = pdf.pages[0]
                tablo = sayfa.extract_table()
                
                if tablo:
                    # Ham tabloyu al
                    df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                    
                    # Karmaşık hücreleri temiz listeye dönüştür
                    df_temiz = ayarlari_ayikla(df_ham)
                    
                    st.success("Maçlar başarıyla ayrıştırıldı!")
                    
                    # Temizlenmiş veriyi ekranda göster
                    st.dataframe(df_temiz, use_container_width=True)
                    
                else:
                    st.error("PDF içinde tablo bulunamadı.")
        except Exception as e:
            st.error(f"Okuma hatası: {e}")
