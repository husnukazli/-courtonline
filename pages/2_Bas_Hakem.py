import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kontrol Paneli")
st.write("Burada PDF yükleme ekranı ve tüm kortların anlık durumu görünecek.")

# PDF Yükleme Alanı
yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")

if yuklenen_pdf:
    st.success("PDF başarıyla yüklendi. Veriler ayrıştırılıyor...")
    
    try:
        # Yüklenen dosyayı pdfplumber ile açıyoruz
        with pdfplumber.open(yuklenen_pdf) as pdf:
            # Genelde program ilk sayfada olduğu için 0. indeksi alıyoruz
            sayfa = pdf.pages[0]
            
            # PDF içindeki tabloyu otomatik yakala
            tablo = sayfa.extract_table()
            
            if tablo:
                # Tablonun ilk satırını başlık (Kort 1, Kort 2 vb.), kalanını veri yapıyoruz
                df = pd.DataFrame(tablo[1:], columns=tablo[0])
                
                st.subheader("📋 Okunan Maç Programı Önizlemesi")
                st.write("Lütfen sistemin kortları ve saatleri doğru okuduğunu kontrol edin.")
                
                # Tabloyu tam genişlikte ekrana basıyoruz
                st.dataframe(df, use_container_width=True)
                
                # Onay bölümü
                st.divider()
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("✅ Programı Onayla ve Yayınla", type="primary"):
                        st.info("Bu aşamada veriler JSON dosyasına (GitHub'a) yazılacak.")
            else:
                st.error("PDF içinde okunabilir bir tablo bulunamadı. Lütfen standart TTF formatında bir dosya yükleyin.")
                
    except Exception as e:
        st.error(f"PDF okunurken bir hata oluştu: {e}")
