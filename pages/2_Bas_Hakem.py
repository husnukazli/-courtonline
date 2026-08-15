import streamlit as st
import pdfplumber
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kontrol Paneli")
st.write("Burada PDF yükleme ekranı ve tüm kortların anlık durumu görünecek.")

def github_a_kaydet(veri_listesi, dosya_yolu="mac_programi.json"):
    """Veriyi GitHub reposuna JSON olarak kaydeder."""
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
    except KeyError:
        return False, "Hata: .streamlit/secrets.toml dosyasında github token veya repo bilgisi eksik!"

    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Dosya zaten var mı diye kontrol edip SHA kodunu alıyoruz (Güncelleme için zorunlu)
    sha = None
    cevap_get = requests.get(url, headers=headers)
    if cevap_get.status_code == 200:
        sha = cevap_get.json().get("sha")
        
    icerik_json = json.dumps(veri_listesi, indent=4, ensure_ascii=False)
    icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"Başhakem onayı: {dosya_yolu} güncellendi",
        "content": icerik_b64
    }
    if sha:
        payload["sha"] = sha
        
    cevap_put = requests.put(url, headers=headers, json=payload)
    
    if cevap_put.status_code in [200, 201]:
        return True, "Başarılı"
    else:
        return False, f"GitHub Hatası: {cevap_put.text}"

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
            tum_temiz_veriler = pd.DataFrame()
            toplam_mac_sayisi = 0

            with pdfplumber.open(yuklenen_pdf) as pdf:
                for sayfa_no, sayfa in enumerate(pdf.pages):
                    tablo = sayfa.extract_table()
                    
                    if tablo:
                        df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                        
                        if None in df_ham.columns:
                             df_ham = df_ham.dropna(axis=1, how='all')
                             yeni_sutunlar = [f"Kort {i+1}" for i in range(len(df_ham.columns))]
                             df_ham.columns = yeni_sutunlar

                        df_temiz = ayarlari_ayikla(df_ham)
                        
                        if not df_temiz.empty:
                            tum_temiz_veriler = pd.concat([tum_temiz_veriler, df_temiz], ignore_index=True)
                            toplam_mac_sayisi += len(df_temiz)
            
            if not tum_temiz_veriler.empty:
                st.success(f"Tüm sayfalar başarıyla ayrıştırıldı! Toplam {toplam_mac_sayisi} maç bulundu.")
                
                st.subheader("📋 Temizlenmiş Maç Listesi")
                
                # İndeksi 1'den başlatma düzeltmesi burada
                tum_temiz_veriler.index = tum_temiz_veriler.index + 1
                
                st.dataframe(tum_temiz_veriler, use_container_width=True)
                
                st.divider()
                st.subheader("⚙️ Programı Yayınla")
                
                if st.button("✅ Programı Onayla ve GitHub'a Kaydet", type="primary"):
                    with st.spinner("GitHub'a kaydediliyor..."):
                        # DataFrame'i sözlük (JSON) listesine çevir
                        kayit_verisi = tum_temiz_veriler.to_dict(orient="records")
                        
                        basarili_mi, mesaj = github_a_kaydet(kayit_verisi)
                        
                        if basarili_mi:
                            st.success("Harika! Maç programı GitHub'a (mac_programi.json) başarıyla kaydedildi.")
                        else:
                            st.error(f"Kayıt işlemi başarısız oldu: {mesaj}")
                            
            else:
                st.error("PDF içinde tablo bulunamadı veya veriler çıkartılamadı.")
                
        except Exception as e:
            st.error(f"Okuma hatası: {e}")
