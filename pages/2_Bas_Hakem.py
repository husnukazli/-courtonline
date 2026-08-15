import streamlit as st
import pdfplumber
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Baş Hakem Paneli", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kort Akış Paneli")

def githubdan_veri_getir(dosya_yolu="mac_programi.json"):
    """GitHub'daki güncel maç programını çeker."""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError:
        return None

    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    cevap = requests.get(url, headers=headers)
    if cevap.status_code == 200:
        icerik_b64 = cevap.json().get("content", "")
        if icerik_b64:
            icerik_json = base64.b64decode(icerik_b64).decode('utf-8')
            return json.loads(icerik_json)
    return None

def github_a_kaydet(veri_listesi, dosya_yolu="mac_programi.json"):
    """Veriyi GitHub reposuna JSON olarak kaydeder."""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError:
        return False, "Hata: Streamlit Secrets içinde GITHUB_TOKEN veya REPO_NAME bulunamadı!"

    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
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
                    "Kort": kort.strip(),
                    "Saat": saat,
                    "Kategori": kategori,
                    "Oyuncu 1": oyuncu_1,
                    "Oyuncu 2": oyuncu_2,
                    "Durum": "Baslamadi" # Bekliyor (Gri) / Oynaniyor (Yesil) / Bitti (Kirmizi)
                })
                
    return pd.DataFrame(mac_listesi)

# --- ANA AKIŞ ---
mevcut_program = githubdan_veri_getir()

if mevcut_program:
    st.success("🟢 Aktif Maç Programı Yüklendi. Kort Akışı Aşağıdadır:")
    
    df_maclar = pd.DataFrame(mevcut_program)
    
    # 6 Kort için yan yana 6 sütun oluşturuyoruz
    kortlar = [f"Kort {i}" for i in range(1, 7)]
    sutunlar = st.columns(6)
    
    for idx, kort_adi in enumerate(kortlar):
        with sutunlar[idx]:
            st.markdown(f"### 🏟️ {kort_adi}")
            st.divider()
            
            # Bu korta ait maçları filtrele
            kort_maclari = df_maclar[df_maclar["Kort"] == kort_adi]
            
            if kort_maclari.empty:
                st.caption("Maç yok")
            else:
                for _, mac in kort_maclari.iterrows():
                    # Maç durumuna göre görsel renk ikonları
                    durum = mac.get("Durum", "Baslamadi")
                    ikon = "⚪"
                    if durum == "Oynaniyor":
                        ikon = "🟢"
                    elif durum == "Bitti":
                        ikon = "🔴"
                        
                    # Kompakt Maç Kutusu
                    with st.container(border=True):
                        st.markdown(f"**{mac['Saat']}** {ikon}")
                        st.caption(f"{mac['Kategori']}")
                        st.write(f"👤 {mac['Oyuncu 1']}")
                        st.write(f"👤 {mac['Oyuncu 2']}")
                        
    st.divider()
    with st.expander("🛠️ Yeni PDF Yükle ve Programı Güncelle"):
        yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")
        if yuklenen_pdf:
            # (PDF İşleme ve Kaydetme Mantığı)
            with st.spinner("PDF işleniyor..."):
                tum_temiz_veriler = pd.DataFrame()
                with pdfplumber.open(yuklenen_pdf) as pdf:
                    for sayfa in pdf.pages:
                        tablo = sayfa.extract_table()
                        if tablo:
                            df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                            if None in df_ham.columns:
                                df_ham = df_ham.dropna(axis=1, how='all')
                                df_ham.columns = [f"Kort {i+1}" for i in range(len(df_ham.columns))]
                            df_temiz = ayarlari_ayikla(df_ham)
                            if not df_temiz.empty:
                                tum_temiz_veriler = pd.concat([tum_temiz_veriler, df_temiz], ignore_index=True)
                
                if not tum_temiz_veriler.empty:
                    st.dataframe(tum_temiz_veriler, use_container_width=True)
                    if st.button("Onayla ve GitHub'a Kaydet", type="primary"):
                        basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"))
                        if basarili:
                            st.success("Güncellendi! Sayfayı yenileyebilirsiniz.")
                        else:
                            st.error(mesaj)
else:
    st.warning("Sistemde kayıtlı maç programı bulunamadı. Lütfen aşağıdan PDF yükleyin.")
    yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")
    if yuklenen_pdf:
        # Aynı PDF yükleme akışı
        with st.spinner("İlk yükleme yapılıyor..."):
            tum_temiz_veriler = pd.DataFrame()
            with pdfplumber.open(yuklenen_pdf) as pdf:
                for sayfa in pdf.pages:
                    tablo = sayfa.extract_table()
                    if tablo:
                        df_ham = pd.DataFrame(tablo[1:], columns=tablo[0])
                        if None in df_ham.columns:
                            df_ham = df_ham.dropna(axis=1, how='all')
                            df_ham.columns = [f"Kort {i+1}" for i in range(len(df_ham.columns))]
                        df_temiz = ayarlari_ayikla(df_ham)
                        if not df_temiz.empty:
                            tum_temiz_veriler = pd.concat([tum_temiz_veriler, df_temiz], ignore_index=True)
            if not tum_temiz_veriler.empty:
                st.dataframe(tum_temiz_veriler, use_container_width=True)
                if st.button("Programı Kaydet", type="primary"):
                    basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"))
                    if basarili:
                        st.success("Kayıt başarılı! Sayfayı yenileyin.")
