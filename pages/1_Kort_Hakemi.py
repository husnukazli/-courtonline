import streamlit as st
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Kort Hakemi", layout="centered")

st.title("Kort Hakemi Paneli")

# Yardımcı Fonksiyonlar
def githubdan_veri_getir(dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError: return None
    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    cevap = requests.get(url, headers=headers)
    if cevap.status_code == 200:
        icerik_b64 = cevap.json().get("content", "")
        if icerik_b64: return json.loads(base64.b64decode(icerik_b64).decode('utf-8'))
    return None

def github_a_kaydet(veri_listesi, dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
    except KeyError: return False, "Token eksik."
    url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    sha = None
    cevap_get = requests.get(url, headers=headers)
    if cevap_get.status_code == 200: sha = cevap_get.json().get("sha")
    icerik_json = json.dumps(veri_listesi, indent=4, ensure_ascii=False)
    icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Skor guncelleme", "content": icerik_b64}
    if sha: payload["sha"] = sha
    cevap_put = requests.put(url, headers=headers, json=payload)
    return (True, "Basarili") if cevap_put.status_code in [200, 201] else (False, cevap_put.text)

def skor_cozumle(skor_str):
    sets = {"s1_p1": 0, "s1_p2": 0, "s2_p1": 0, "s2_p2": 0, "s3_p1": 0, "s3_p2": 0}
    if not skor_str or skor_str == "-": return sets
    try:
        parcalar = skor_str.split()
        for i, p in enumerate(parcalar):
            s = p.split("/")
            if len(s) == 2:
                sets[f"s{i+1}_p1"] = int(s[0])
                sets[f"s{i+1}_p2"] = int(s[1])
    except: pass
    return sets

# Giriş Yönetimi
hakem_verileri = githubdan_veri_getir("hakemler.json") or {}

if "hakem_giris" not in st.session_state: st.session_state.hakem_giris = False

if not st.session_state.hakem_giris:
    st.subheader("Hakem Giris")
    kullanici_adi = st.selectbox("Hakem İsminizi Secin", [""] + list(hakem_verileri.keys()))
    sifre = st.text_input("Sifre", type="password")
    if st.button("Giris Yap"):
        if kullanici_adi and hakem_verileri.get(kullanici_adi) == sifre:
            st.session_state.hakem_giris = True
            st.session_state.kullanici = kullanici_adi
            st.rerun()
        else: st.error("Hatali bilgi.")
else:
    # Çıkış Butonu
    if st.button("⬅️ Cikis Yap"):
        st.session_state.hakem_giris = False
        st.rerun()
        
    program = githubdan_veri_getir("mac_programi.json")
    if program:
        df_maclar = pd.DataFrame(program)
        secilen_kort = st.selectbox("Kort Secin", sorted(df_maclar["Kort"].unique()))
        
        # Maç Seçimi (Durum simgeli)
        kort_maclari = df_maclar[df_maclar["Kort"] == secilen_kort]
        mac_secenekleri = []
        for idx, row in kort_maclari.iterrows():
            durum = row.get('Durum', 'Baslamadi')
            simgeler = {"Oynaniyor": "🟢", "Bitti": "🔴", "Baslamadi": "⚪"}
            metin = f"{simgeler.get(durum, '⚪')} {row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}"
            mac_secenekleri.append((metin, idx))
            
        secilen_text = st.selectbox("Mac Secin", [m[0] for m in mac_secenekleri])
        gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_text)
        secilen_mac = df_maclar.loc[gercek_idx]
        
        # Düzenleme Alanı (Mobil Dostu)
        st.markdown(f"**{secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}**")
        yeni_durum = st.selectbox("Durum", ["Baslamadi", "Oynaniyor", "Bitti"], index=["Baslamadi", "Oynaniyor", "Bitti"].index(secilen_mac.get("Durum", "Baslamadi")))
        
        # Skorlar
        mevcut_skorlar = skor_cozumle(secilen_mac.get("Skor", "-"))
        col1, col2, col3 = st.columns(3)
        with col1:
            s1_p1 = st.number_input("S1-O1", 0, 7, mevcut_skorlar["s1_p1"])
            s1_p2 = st.number_input("S1-O2", 0, 7, mevcut_skorlar["s1_p2"])
        with col2:
            s2_p1 = st.number_input("S2-O1", 0, 7, mevcut_skorlar["s2_p1"])
            s2_p2 = st.number_input("S2-O2", 0, 7, mevcut_skorlar["s2_p2"])
        with col3:
            s3_p1 = st.number_input("S3-O1", 0, 7, mevcut_skorlar["s3_p1"])
            s3_p2 = st.number_input("S3-O2", 0, 7, mevcut_skorlar["s3_p2"])
            
        # Güvenli Kura Seçimi
        kura_ops = ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']]
        kz = secilen_mac.get("Kura_Kazanan", "Secilmedi")
        kura_kazanan = st.selectbox("Kurayi Kazanan", kura_ops, index=kura_ops.index(kz) if kz in kura_ops else 0)
        
        if st.button("Kaydet", type="primary"):
            skor_metni = f"{s1_p1}/{s1_p2} {s2_p1}/{s2_p2}"
            if s3_p1 > 0 or s3_p2 > 0: skor_metni += f" {s3_p1}/{s3_p2}"
            df_maclar.loc[gercek_idx, ["Durum", "Skor", "Kura_Kazanan"]] = [yeni_durum, skor_metni, kura_kazanan]
            basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
            if basarili: st.success("Kaydedildi!")
            else: st.error(mesaj)
