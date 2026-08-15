import streamlit as st
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Kort Hakemi Paneli", layout="centered")

st.title("Kort Hakemi Paneli")

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
    
    payload = {"message": f"Skor guncelleme: {dosya_yolu}", "content": icerik_b64}
    if sha:
        payload["sha"] = sha
        
    cevap_put = requests.put(url, headers=headers, json=payload)
    if cevap_put.status_code in [200, 201]:
        return True, "Basarili"
    else:
        return False, cevap_put.text

# GitHub'dan güncel hakem şifrelerini çek
hakem_verileri = githubdan_veri_getir("hakemler.json")
if not isinstance(hakem_verileri, dict):
    hakem_verileri = {}

if "hakem_giris" not in st.session_state:
    st.session_state.hakem_giris = False
    st.session_state.kullanici = ""

if not st.session_state.hakem_giris:
    st.subheader("Hakem Giris Ekrani")
    
    if not hakem_verileri:
        st.warning("Sistemde tanimli hakem bulunamadi. Lutfen once Bashekim panelinden hakem ekleyin.")
    
    kullanici_adi = st.text_input("Kullanici Adi")
    sifre = st.text_input("Sifre", type="password")
    
    if st.button("Giris Yap"):
        if kullanici_adi in hakem_verileri and hakem_verileri[kullanici_adi] == sifre:
            st.session_state.hakem_giris = True
            st.session_state.kullanici = kullanici_adi
            st.rerun()
        else:
            st.error("Kullanici adi veya sifre hatali.")
else:
    st.write(f"Giris yapan hakem: **{st.session_state.kullanici}**")
    if st.button("Cikis Yap"):
        st.session_state.hakem_giris = False
        st.rerun()
        
    st.divider()
    
    program = githubdan_veri_getir("mac_programi.json")
    
    if not program:
        st.warning("Sistemde aktif mac programi bulunamadi.")
    else:
        df_maclar = pd.DataFrame(program)
        aktif_kortlar = sorted(df_maclar["Kort"].unique())
        
        secilen_kort = st.selectbox("Gorevli Oldugunuz Kortu Secin", aktif_kortlar)
        
        if secilen_kort:
            st.markdown(f"### {secilen_kort} Mac Listesi")
            
            kort_maskesi = df_maclar["Kort"] == secilen_kort
            kort_maclari = df_maclar[kort_maskesi]
            
            mac_secenekleri = []
            mac_indexleri = []
            
            for idx, row in kort_maclari.iterrows():
                durum_etiketi = "[Bekliyor]"
                if row['Durum'] == "Oynaniyor":
                    durum_etiketi = "[OYNANIYOR]"
                elif row['Durum'] == "Bitti":
                    durum_etiketi = "[BITTI]"
                    
                metin = f"Saat: {row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} {durum_etiketi}"
                mac_secenekleri.append(metin)
                mac_indexleri.append(idx)
                
            if mac_secenekleri:
                secilen_mac_metin = st.selectbox("Islem Yapilacak Maci Secin", mac_secenekleri)
                secilen_index = mac_secenekleri.index(secilen_mac_metin)
                gercek_idx = mac_indexleri[secilen_index]
                secilen_mac = df_maclar.loc[gercek_idx]
                
                st.divider()
                st.markdown(f"**Secilen Mac:** {secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}")
                st.markdown(f"**Kategori:** {secilen_mac['Kategori']} | **Saat:** {secilen_mac['Saat']}")
                
                yeni_durum = st.selectbox(
                    "Mac Durumu", 
                    ["Baslamadi", "Oynaniyor", "Bitti"], 
                    index=["Baslamadi", "Oynaniyor", "Bitti"].index(secilen_mac.get("Durum", "Baslamadi"))
                )
                
                yeni_skor = st.text_input("Skor (Orn: 6/4 6/2)", value=secilen_mac.get("Skor", ""))
                
                if st.button("Skoru ve Durumu Guncelle"):
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Skor"] = yeni_skor
                    
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili:
                        st.success("Guncelleme basariyla kaydedildi.")
                    else:
                        st.error(f"Hata: {mesaj}")
            else:
                st.info("Bu kortta tanimli mac bulunmuyor.")
