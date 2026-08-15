import streamlit as st
import pdfplumber
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Bashekim Paneli", layout="wide")

st.title("Bashekim Kort Akis Paneli")

def githubdan_veri_getir(dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError:
        return None

    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    cevap = requests.get(url, headers=headers)
    if cevap.status_code == 200:
        icerik_b64 = cevap.json().get("content", "")
        if icerik_b64:
            return json.loads(base64.b64decode(icerik_b64).decode('utf-8'))
    return None

def github_a_kaydet(veri_listesi, dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError:
        return False, "Token eksik."

    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    sha = None
    cevap_get = requests.get(url, headers=headers)
    if cevap_get.status_code == 200:
        sha = cevap_get.json().get("sha")
        
    icerik_json = json.dumps(veri_listesi, indent=4, ensure_ascii=False)
    icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
    
    payload = {"message": f"Guncelleme: {dosya_yolu}", "content": icerik_b64}
    if sha:
        payload["sha"] = sha
        
    cevap_put = requests.put(url, headers=headers, json=payload)
    if cevap_put.status_code in [200, 201]:
        return True, "Basarili"
    else:
        return False, cevap_put.text

def ayarlari_ayikla(df):
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
                kategori = next((s for s in satirlar if "Yas" in s or "Kategori" in s or "Yaş" in s), "Kategori Yok")
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
                    "Durum": "Baslamadi",
                    "Skor": "-",
                    "Baslangic_Saati": "",
                    "Bitis_Saati": "",
                    "Kura_Kazanan": "",
                    "Kura_Tercih": ""
                })
    return pd.DataFrame(mac_listesi)

# Zoom Kontrolü
col_zoom1, _, _ = st.columns([2, 6, 4])
with col_zoom1:
    zoom_seviyesi = st.slider("Gorunum Olcegi (%)", min_value=50, max_value=120, value=100, step=10)

st.markdown(f"""
    <style>
    .stApp {{
        zoom: {zoom_seviyesi}%;
    }}
    </style>
""", unsafe_allow_html=True)

st.divider()

# Hakem Yönetimi Paneli
with st.expander("Hakem Yonetimi (Hakem Ekle / Listele)"):
    kayitli_hakemler = githubdan_veri_getir("hakemler.json")
    if not isinstance(kayitli_hakemler, dict):
        kayitli_hakemler = {}
        
    yeni_kullanici = st.text_input("Hakem Kullanici Adi / Ismi")
    yeni_sifre = st.text_input("Hakem Sifresi", type="password")
    
    if st.button("Hakem Ekle / Guncelle"):
        if yeni_kullanici.strip() and yeni_sifre.strip():
            kayitli_hakemler[yeni_kullanici.strip()] = yeni_sifre.strip()
            basarili, mesaj = github_a_kaydet(kayitli_hakemler, "hakemler.json")
            if basarili:
                st.success(f"'{yeni_kullanici}' basariyla kaydedildi.")
            else:
                st.error(f"Kayıt hatası: {mesaj}")
        else:
            st.warning("Kullanici adi ve sifre bos olamaz.")
            
    if kayitli_hakemler:
        st.write("Sistemde Kayitli Hakemler:")
        df_hakem = pd.DataFrame(list(kayitli_hakemler.items()), columns=["Kullanici Adi", "Sifre"])
        st.dataframe(df_hakem, use_container_width=True)

st.divider()

# Ana Maç Akışı ve Renk Kodlu Izgara
mevcut_program = githubdan_veri_getir("mac_programi.json")

if mevcut_program:
    df_maclar = pd.DataFrame(mevcut_program)
    aktif_kortlar = sorted(df_maclar["Kort"].unique(), key=lambda x: int(x.replace("Kort", "").strip()) if x.replace("Kort", "").strip().isdigit() else x)
    
    if aktif_kortlar:
        sutunlar = st.columns(len(aktif_kortlar))
        
        for idx, kort_adi in enumerate(aktif_kortlar):
            with sutunlar[idx]:
                st.subheader(kort_adi)
                
                kort_maclari = df_maclar[df_maclar["Kort"] == kort_adi]
                
                if kort_maclari.empty:
                    st.caption("Mac yok")
                else:
                    for i, mac in kort_maclari.iterrows():
                        durum = mac.get("Durum", "Baslamadi")
                        skor = mac.get("Skor", "-")
                        
                        # Renkli durum etiketleri
                        if durum == "Oynaniyor":
                            durum_etiketi = "DEVAM EDIYOR"
                            renk_style = "color: green; font-weight: bold;"
                        elif durum == "Bitti":
                            durum_etiketi = "BITTI"
                            renk_style = "color: red; font-weight: bold;"
                        else:
                            durum_etiketi = "Bekliyor"
                            renk_style = "color: gray;"
                            
                        with st.container(border=True):
                            st.markdown(f"<span style='{renk_style}'>[{durum_etiketi}]</span> Saat: {mac['Saat']}", unsafe_allow_html=True)
                            st.caption(f"{mac['Kategori']}")
                            st.write(f"{mac['Oyuncu 1']}")
                            st.write("vs")
                            st.write(f"{mac['Oyuncu 2']}")
                            
                            if skor != "-":
                                st.code(skor, language=None)
    
    st.divider()
    with st.expander("Yeni Program (PDF) Yukle"):
        yuklenen_pdf = st.file_uploader("PDF Sec", type="pdf")
        if yuklenen_pdf:
            with st.spinner("Isleniyor..."):
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
                    if st.button("Onayla ve Kaydet"):
                        basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"), "mac_programi.json")
                        if basarili:
                            st.success("Kaydedildi. Sayfayi yenileyin.")
                        else:
                            st.error(mesaj)
else:
    st.info("Sistemde kayitli mac programi yok. Asagidan PDF yukleyin.")
    yuklenen_pdf = st.file_uploader("Mac Programi Yukle", type="pdf")
    if yuklenen_pdf:
        with st.spinner("Yukleniyor..."):
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
                if st.button("Ilk Kaydi Olustur"):
                    basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"), "mac_programi.json")
                    if basarili:
                        st.success("Basarili! Sayfayi yenileyin.")
