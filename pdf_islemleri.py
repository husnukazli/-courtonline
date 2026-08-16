import streamlit as st
import pandas as pd
import pdfplumber
import requests
import base64
import json
import io

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="PDF Program Yükleme", layout="wide")
st.title("📂 PDF Maç Programı Yükleme ve Format Ayarları")

# --- YARDIMCI FONKSİYONLAR ---
def githubdan_veri_getir(dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        cevap = requests.get(url, headers=headers)
        if cevap.status_code == 200:
            icerik_b64 = cevap.json().get("content", "")
            if icerik_b64:
                return json.loads(base64.b64decode(icerik_b64).decode('utf-8'))
    except Exception as e:
        pass
    return None

def github_a_kaydet(veri, dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        sha = None
        cevap_get = requests.get(url, headers=headers)
        if cevap_get.status_code == 200:
            sha = cevap_get.json().get("sha")
            
        icerik_json = json.dumps(veri, indent=4, ensure_ascii=False)
        icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
        
        payload = {"message": f"{dosya_yolu} Güncellemesi", "content": icerik_b64}
        if sha:
            payload["sha"] = sha
            
        cevap_put = requests.put(url, headers=headers, json=payload)
        if cevap_put.status_code in [200, 201]:
            return True, "Başarılı"
        else:
            return False, cevap_put.text
    except Exception as e:
        return False, str(e)

def pdf_programi_oku(pdf_file):
    """TTF Maç programı PDF'ini okuyup yapılandırılmış bir tabloya çevirir."""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            sayfa = pdf.pages[0]
            tablo = sayfa.extract_table()
            
            if not tablo:
                return None, "Hata: PDF içinde okunabilir bir tablo bulunamadı."
            
            # Satır sonu karakterlerini temizleyerek DF oluştur
            temiz_tablo = [[str(hucre).replace('\n', ' ').strip() if hucre else "" for hucre in satir] for satir in tablo]
            df = pd.DataFrame(temiz_tablo[1:], columns=temiz_tablo[0])
            
            # Boş satırları temizle
            df.dropna(how='all', inplace=True)
            return df, "Başarılı"
    except Exception as e:
        return None, f"PDF Okuma Hatası: {e}"

# --- SİSTEM DEĞİŞKENLERİ ---
FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

# --- PDF YÜKLEME ALANI ---
yuklenen_pdf = st.file_uploader("TTF Maç Programı PDF Dosyasını Yükleyin", type=["pdf"])

if yuklenen_pdf is not None:
    df, mesaj = pdf_programi_oku(yuklenen_pdf)
    
    if df is not None:
        st.success("PDF başarıyla okundu!")
        with st.expander("PDF'ten Çekilen Ham Tabloyu Gör"):
            st.dataframe(df)
        
        st.divider()
        st.subheader("⚙️ Kategori ve Format Eşleştirme")
        st.info("Kategorileri sistemdeki skor formatlarıyla eşleştirin. Sistem yaptığınız seçimleri hatırlayacak ve yarınki PDF'te otomatik olarak karşınıza getirecektir.")
        
        # PDF'teki sütunları alıp kullanıcıya "Kategori" sütununu seçtiriyoruz (PDF formatı değişirse diye güvenlik önlemi)
        sutunlar = df.columns.tolist()
        kategori_sutunu = st.selectbox("Kategori Bilgisinin Bulunduğu Sütun (Örn: 'Kategori', 'Grup', 'Yaş')", sutunlar, index=sutunlar.index("Kategori") if "Kategori" in sutunlar else 0)
        
        # Kategori sütunundaki benzersiz değerleri bul
        benzersiz_kategoriler = df[kategori_sutunu].unique()
        
        # Geçmiş hafızayı GitHub'dan çek
        hafiza = githubdan_veri_getir("kategori_format_hafizasi.json") or {}
        
        # Eşleştirme Sözlüğü (Yeni seçimleri tutacak)
        yeni_hafiza = {}
        
        # Her kategori için UI oluştur
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Kategori Adı (PDF'ten gelen)**")
        with col2:
            st.markdown("**Uygulanacak Skor Formatı**")
            
        for i, kat in enumerate(benzersiz_kategoriler):
            if not kat: continue # Boş kategorileri atla
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<div style='padding-top: 10px; font-size: 18px;'>🎾 <b>{kat}</b></div>", unsafe_allow_html=True)
            with c2:
                # Hafızada varsa onu bul, yoksa varsayılan olarak ilkini seç
                eski_secim = hafiza.get(kat, FORMAT_SECENEKLERI[0])
                idx = FORMAT_SECENEKLERI.index(eski_secim) if eski_secim in FORMAT_SECENEKLERI else 0
                secilen_format = st.selectbox(f"Format - {kat}", FORMAT_SECENEKLERI, index=idx, key=f"fmt_{i}", label_visibility="collapsed")
                yeni_hafiza[kat] = secilen_format
        
        st.divider()
        st.warning("⚠️ DİKKAT: 'Programı Onayla ve Kaydet' butonuna bastığınızda, sahadaki mevcut maç programı SIFIRLANACAK ve yerine bu PDF'teki maçlar yüklenecektir. Hakemler, skor istatistikleri ve şifreler korunacaktır.")
        
        if st.button("✅ Programı Onayla ve Kort Hakemlerine Gönder", type="primary", use_container_width=True):
            # Formata göre DataFrame'i güncelle
            df["Skor_Formati"] = df[kategori_sutunu].map(yeni_hafiza)
            
            # Kort Hakemi uygulamasının beklediği standart sütunları garanti altına al
            if "Durum" not in df.columns: df["Durum"] = "Baslamadi"
            if "Skor" not in df.columns: df["Skor"] = "-"
            if "Kura_Kazanan" not in df.columns: df["Kura_Kazanan"] = "Secilmedi"
            if "Kura_Tercih" not in df.columns: df["Kura_Tercih"] = "Secilmedi"
            if "Saha_Tarafi" not in df.columns: df["Saha_Tarafi"] = "Secilmedi"
            if "Baslangic_Saati" not in df.columns: df["Baslangic_Saati"] = ""
            if "Bitis_Saati" not in df.columns: df["Bitis_Saati"] = ""
            if "Son_Hakem" not in df.columns: df["Son_Hakem"] = ""
            if "Kazanan" not in df.columns: df["Kazanan"] = "Secilmedi"
            
            # Sütun isimleri TTF'ye göre değişebiliyor. Hakem uygulamasının Kort, Saat, Oyuncu 1, Oyuncu 2 beklediğini unutma!
            # Eğer PDF sütun adları farklıysa DataFrame'i kaydetmeden önce yeniden adlandırman (rename) gerekebilir.
            # Şu an PDF tablosundaki orijinal başlıklarla kaydediyoruz.
            
            # 1. Maç Programını Kaydet
            basarili_mac, msg_mac = github_a_kaydet(df.to_dict(orient="records"), "mac_programi.json")
            
            # 2. Format Hafızasını Kaydet (Gelecek günler için)
            basarili_hafiza, msg_hafiza = github_a_kaydet(yeni_hafiza, "kategori_format_hafizasi.json")
            
            if basarili_mac and basarili_hafiza:
                st.success("🎉 Maç programı, hakemlerin format kurallarıyla birlikte başarıyla sisteme yüklendi!")
                st.balloons()
            else:
                if not basarili_mac: st.error(f"Maç programı kaydedilirken hata: {msg_mac}")
                if not basarili_hafiza: st.error(f"Hafıza kaydedilirken hata: {msg_hafiza}")
                
    else:
        st.error(mesaj)
