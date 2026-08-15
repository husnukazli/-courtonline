import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kontrol Paneli")
st.write("Burada PDF yükleme ekranı ve tüm kortların anlık durumu görünecek.")

def ayarlari_ayikla(df):
    """Karmaşık tablo hücrelerini okuyup temiz bir maç listesine dönüştürür."""
    mac_listesi = []
    
    # Sadece "Kort" ile başlayan sütunları döngüye alıyoruz
    for kort in df.columns:
        if not str(kort).startswith("Kort"):
            continue
            
        for hucre in df[kort]:
            if pd.isna(hucre) or str(hucre).strip() == "":
                continue
            
            # Hücre içindeki satırları yeni satır karakterine (\n) göre bölüyoruz
            satirlar = [s.strip() for s in str(hucre).split('\n') if s.strip()]
            
            # Eğer hücre geçerli bir maç hücresiyse (saat, oyuncular, kategori)
            if len(satirlar) >= 4:
                saat = satirlar[0] 
                oyuncu_1 = satirlar[1] 
                
                # Kategoriyi ("Yaş" kelimesi geçen satırı) bul
                kategori = next((s for s in satirlar if "Yaş" in s or "Kategori" in s), "Kategori Bulunamadı")
                
                # İkinci oyuncuyu bul (kategoriden sonraki satır)
                try:
                    kat_index = satirlar.index(kategori)
                    oyuncu_2 = satirlar[kat_index + 1]
                except:
                    oyuncu_2 = "Bilinmiyor"

                mac_listesi.append({
                    "Kort": kort,
                    "Saat": saat,
                    "Kategori": kategori,
                    "Oyuncu 1": oyuncu_1,
                    "Oyuncu 2": oyuncu_2,
                    "Durum": "Baslamadi" 
                })
                
    return pd.DataFrame(mac_listesi)

# PDF Yükleme Alanı
yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")

if yuklenen_pdf:
    with st.spinner("PDF ayrıştırılıyor... Lütfen bekleyin."):
        try:
            with pdfplumber.open(yuklenen_pdf) as pdf:
                sayfa = pdf.pages[0]
                tablo = sayfa.extract_table()
                
                if tablo:
                    # Ham tabloyu dataframe yapıyoruz
                    df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                    
                    # Ayıklama fonksiyonunu çalıştırıp temiz listeyi alıyoruz
                    df_temiz = ayarlari_ayikla(df_ham)
                    
                    st.success("Maçlar başarıyla ayrıştırıldı!")
                    
                    st.subheader("📋 Temizlenmiş Maç Listesi")
                    st.write("Veriler JSON dosyasına yazılmadan önceki son hali:")
                    
                    # Temizlenmiş veriyi ekranda göster
                    st.dataframe(df_temiz, use_container_width=True)
                    
                else:
                    st.error("PDF içinde tablo bulunamadı.")
        except Exception as e:
            st.error(f"Okuma hatası: {e}")
