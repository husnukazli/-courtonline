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

def skor_cozumle(skor_str):
    sets = {"s1_p1": 0, "s1_p2": 0, "s2_p1": 0, "s2_p2": 0, "s3_p1": 0, "s3_p2": 0}
    if not skor_str or skor_str == "-":
        return sets
    try:
        parcalar = skor_str.split()
        if len(parcalar) >= 1:
            s1 = parcalar[0].split("/")
            sets["s1_p1"] = int(s1[0])
            sets["s1_p2"] = int(s1[1])
        if len(parcalar) >= 2:
            s2 = parcalar[1].split("/")
            sets["s2_p1"] = int(s2[0])
            sets["s2_p2"] = int(s2[1])
        if len(parcalar) >= 3:
            s3 = parcalar[2].split("/")
            sets["s3_p1"] = int(s3[0])
            sets["s3_p2"] = int(s3[1])
    except:
        pass
    return sets

hakem_verileri = githubdan_veri_getir("hakemler.json")
if not isinstance(hakem_verileri, dict):
    hakem_verileri = {}

if "hakem_giris" not in st.session_state:
    st.session_state.hakem_giris = False
    st.session_state.kullanici = ""

if not st.session_state.hakem_giris:
    st.subheader("Hakem Giris Ekrani")
    
    if not hakem_verileri:
        st.warning("Sistemde tanimli hakem bulunamadi. Bashakem panelinden hakem ekleyin.")
        hakem_listesi = []
    else:
        hakem_listesi = list(hakem_verileri.keys())
        
    secilen_hakem = st.selectbox("Hakem İsminizi Secin", [""] + hakem_listesi)
    sifre = st.text_input("Sifre", type="password")
    
    if st.button("Giris Yap"):
        if secilen_hakem and secilen_hakem in hakem_verileri and hakem_verileri[secilen_hakem] == sifre:
            st.session_state.hakem_giris = True
            st.session_state.kullanici = secilen_hakem
            st.rerun()
        else:
            st.error("Lutfen isminizi secin ve dogru sifreyi girin.")
else:
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1:
        st.write(f"Gorevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
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
        
        secilen_kort = st.selectbox("Gorevli Oldugunuz Kort", aktif_kortlar)
        
        if secilen_kort:
            st.markdown(f"### {secilen_kort} Mac Durum Listesi")
            
            kort_maskesi = df_maclar["Kort"] == secilen_kort
            kort_maclari = df_maclar[kort_maskesi]
            
            # --- HAKEM İÇİN GÖRSEL RENKLİ MAÇ LİSTESİ ÖNİZLEMESİ ---
            for idx, row in kort_maclari.iterrows():
                durum = row.get('Durum', 'Baslamadi')
                skor = row.get('Skor', '-')
                
                # Renk kodlaması (Bitenler Kırmızı, Devam edenler Yeşil, Bekleyenler Gri)
                if durum == "Oynaniyor":
                     satir_style = "color: #00FF66; font-weight: bold;"
                     durum_etiketi = "DEVAM EDIYOR"
                elif durum == "Bitti":
                     satir_style = "color: #FF1744; font-weight: bold;"
                     durum_etiketi = "BITTI"
                else:
                     satir_style = "color: #AAAAAA;"
                     durum_etiketi = "Bekliyor"
                     
                st.markdown(f"<div style='{satir_style} font-size: 13px; padding: 2px 0;'>🕒 {row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{durum_etiketi}] (Skor: {skor})</div>", unsafe_allow_html=True)

            st.markdown("---")

            mac_secenekleri = []
            mac_indexleri = []
            
            for idx, row in kort_maclari.iterrows():
                durum = row.get('Durum', 'Baslamadi')
                metin = f"{row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{durum}]"
                mac_secenekleri.append(metin)
                mac_indexleri.append(idx)
                
            if mac_secenekleri:
                secilen_mac_metin = st.selectbox("Uzerinde Islem Yapilacak Maci Secin", mac_secenekleri)
                secilen_index = mac_secenekleri.index(secilen_mac_metin)
                gercek_idx = mac_indexleri[secilen_index]
                secilen_mac = df_maclar.loc[gercek_idx]
                
                mevcut_skorlar = skor_cozumle(secilen_mac.get("Skor", "-"))
                
                st.divider()
                st.markdown(f"**Secilen Mac:** {secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}")
                st.markdown(f"**Kategori:** {secilen_mac['Kategori']} | **Planlanan Saat:** {secilen_mac['Saat']}")
                
                mevcut_durum = secilen_mac.get("Durum", "Baslamadi")
                yeni_durum = st.selectbox(
                    "Mac Durumu", 
                    ["Baslamadi", "Oynaniyor", "Bitti"], 
                    index=["Baslamadi", "Oynaniyor", "Bitti"].index(mevcut_durum)
                )
                
                col_z1, col_z2 = st.columns(2)
                with col_z1:
                    baslangic_saati = st.text_input("Mac Baslama Saati", value=secilen_mac.get("Baslangic_Saati", ""))
                with col_z2:
                    bitis_saati = st.text_input("Mac Bitis Saati", value=secilen_mac.get("Bitis_Saati", ""))
                
                st.markdown("---")
                st.markdown("**Kura Bilgileri**")
                col_k1, col_k2 = st.columns(2)
                with col_k1:
                    kura_kazanan = st.selectbox(
                        "Kurayi Kazanan", 
                        ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']],
                        index=0 if not secilen_mac.get("Kura_Kazanan") else (0 if secilen_mac.get("Kura_Kazanan") == "Secilmedi" else (1 if secilen_mac.get("Kura_Kazanan") == secilen_mac['Oyuncu 1'] else 2))
                    )
                with col_k2:
                    kura_tercih = st.selectbox(
                        "Kura Tercihi", 
                        ["Secilmedi", "Servis", "Karsilama", "Kort Secimi"],
                        index=0 if not secilen_mac.get("Kura_Tercih") else ["Secilmedi", "Servis", "Karsilama", "Kort Secimi"].index(secilen_mac.get("Kura_Tercih", "Secilmedi"))
                    )

                st.markdown("---")
                st.markdown("**Set Skorlari**")
                
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.text("1. Set")
                    s1_p1 = st.number_input(f"{secilen_mac['Oyuncu 1']} (Set 1)", min_value=0, max_value=7, value=mevcut_skorlar["s1_p1"], key="s1_p1")
                    s1_p2 = st.number_input(f"{secilen_mac['Oyuncu 2']} (Set 1)", min_value=0, max_value=7, value=mevcut_skorlar["s1_p2"], key="s1_p2")
                with col_s2:
                    st.text("2. Set")
                    s2_p1 = st.number_input(f"{secilen_mac['Oyuncu 1']} (Set 2)", min_value=0, max_value=7, value=mevcut_skorlar["s2_p1"], key="s2_p1")
                    s2_p2 = st.number_input(f"{secilen_mac['Oyuncu 2']} (Set 2)", min_value=0, max_value=7, value=mevcut_skorlar["s2_p2"], key="s2_p2")
                with col_s3:
                    st.text("3. Set")
                    s3_p1 = st.number_input(f"{secilen_mac['Oyuncu 1']} (Set 3)", min_value=0, max_value=7, value=mevcut_skorlar["s3_p1"], key="s3_p1")
                    s3_p2 = st.number_input(f"{secilen_mac['Oyuncu 2']} (Set 3)", min_value=0, max_value=7, value=mevcut_skorlar["s3_p2"], key="s3_p2")
                
                if st.button("Skoru ve Durumu Kaydet", type="primary"):
                    skor_metni = f"{s1_p1}/{s1_p2} {s2_p1}/{s2_p2}"
                    if s3_p1 > 0 or s3_p2 > 0:
                        skor_metni += f" {s3_p1}/{s3_p2}"
                        
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Skor"] = skor_metni
                    df_maclar.loc[gercek_idx, "Baslangic_Saati"] = baslangic_saati
                    df_maclar.loc[gercek_idx, "Bitis_Saati"] = bitis_saati
                    df_maclar.loc[gercek_idx, "Kura_Kazanan"] = kura_kazanan
                    df_maclar.loc[gercek_idx, "Kura_Tercih"] = kura_tercih
                    
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili:
                        st.success("Skor ve durum basariyla güncellendi!")
                    else:
                        st.error(f"Hata: {mesaj}")
            else:
                st.info("Bu kortta mac bulunmuyor.")
