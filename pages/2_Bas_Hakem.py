import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kontrol Paneli")
st.write("Burada PDF yükleme ekranı ve tüm kortların anlık durumu görünecek.")

def ayarlari_ayikla(df):
    """Karmaşık tablo hücrelerini okuyup temiz bir maç listesine dönüştürür."""
    mac_listesi = []
    
    for kort in df.columns:
        if not str(kort).startswith("Kort"):
            continue
            
        for hucre in df[kort]:
            if pd.isna(hucre) or str(hucre).strip() == "":
                continue
            
            satirlar = [s.strip() for s in str(hucre).split('\n') if s.strip()]
            
            if len(satirlar) >= 4:
                saat = satirlar[0] 
                oyuncu_1 = satirlar[1] 
                
                kategori = next((s for s in satirlar if "Yaş" in s or "Kategori" in s), "Kategori Bulunamadı")
                
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

yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")

if yuklenen_pdf:
    with st.spinner("PDF ayrıştırılıyor... Lütfen bekleyin."):
        try:
            tum_temiz_veriler = pd.DataFrame() # Tüm sayfaların birleşeceği boş DataFrame
            toplam_mac_sayisi = 0

            with pdfplumber.open(yuklenen_pdf) as pdf:
                # PDF'teki tüm sayfaları döngüye al
                for sayfa_no, sayfa in enumerate(pdf.pages):
                    tablo = sayfa.extract_table()
                    
                    if tablo:
                        # Tablonun ilk satırını sütun başlıkları yap
                        df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                        
                        # Eğer alt sayfalarda sütun başlıkları düzgün gelmediyse (None olduysa), düzeltmeye çalış
                        if None in df_ham.columns:
                             df_ham = df_ham.dropna(axis=1, how='all') # Tamamen boş sütunları at
                             
                             # Sütun başlıklarını düzeltmek için kort sayısına göre (Kort 1, Kort 2...) yeniden adlandırma (Gerekirse)
                             yeni_sutunlar = [f"Kort {i+1}" for i in range(len(df_ham.columns))]
                             df_ham.columns = yeni_sutunlar


                        df_temiz = ayarlari_ayikla(df_ham)
                        
                        if not df_temiz.empty:
                            tum_temiz_veriler = pd.concat([tum_temiz_veriler, df_temiz], ignore_index=True)
                            toplam_mac_sayisi += len(df_temiz)
            
            if not tum_temiz_veriler.empty:
                st.success(f"Tüm sayfalar başarıyla ayrıştırıldı! Toplam {toplam_mac_sayisi} maç bulundu.")
                
                st.subheader("📋 Temizlenmiş Maç Listesi (Tüm Sayfalar)")
                st.write("Veriler JSON dosyasına yazılmadan önceki son hali:")
                
                st.dataframe(tum_temiz_veriler, use_container_width=True)
                
            else:
                st.error("PDF içinde tablo bulunamadı veya veriler çıkartılamadı.")
                
        except Exception as e:
            st.error(f"Okuma hatası: {e}")
