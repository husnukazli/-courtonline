import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Kort Hakemi", layout="centered")

# Mobil Klavye Engelleyici
st.markdown("""
<script>
document.addEventListener('click', function(e) {
    if (e.target.matches('.stSelectbox input')) {
        e.target.setAttribute('inputmode', 'none');
    }
});
</script>
<style>
div[data-baseweb="input"] input { height: 48px !important; font-size: 20px !important; font-weight: bold !important; text-align: center !important; }
button[data-baseweb="button"] { height: 38px !important; width: 38px !important; }
</style>
""", unsafe_allow_html=True)

st.title("Kort Hakemi Paneli")

# Yardımcı: Şu anki TRT saatine en yakın 5 dk'lık indexi bul
def get_current_time_index(saat_listesi):
    TRT = timezone(timedelta(hours=3))
    simdi = datetime.now(TRT)
    # Dakikayı 5'in katına yuvarla
    yeni_dk = (simdi.minute // 5) * 5
    target = f"{simdi.hour:02d}:{yeni_dk:02d}"
    if target in saat_listesi:
        return saat_listesi.index(target)
    return 0

SAAT_LISTESI = ["Secilmedi"] + [f"{h:02d}:{m:02d}" for h in range(7, 23) for m in range(0, 60, 5)]
CURRENT_TIME_IDX = get_current_time_index(SAAT_LISTESI)

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

def set_skoru_gecerli_mi(p1, p2, durum):
    if p1 == 0 and p2 == 0: return True
    if durum != "Bitti": return True
    valid_completed = [(6,0),(6,1),(6,2),(6,3),(6,4),(0,6),(1,6),(2,6),(3,6),(4,6),(7,5),(7,6),(5,7),(6,7)]
    return (p1, p2) in valid_completed

hakem_verileri = githubdan_veri_getir("hakemler.json") or {}

if "hakem_giris" not in st.session_state: st.session_state.hakem_giris = False
if "hakem_mod" not in st.session_state: st.session_state.hakem_mod = "kurulum"

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
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1: st.write(f"Gorevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Cikis Yap"):
            st.session_state.hakem_giris = False
            st.rerun()
    st.divider()
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("🎾 Maç Seç / Başlat (Kurulum)", use_container_width=True, type="primary" if st.session_state.hakem_mod == "kurulum" else "secondary"):
            st.session_state.hakem_mod = "kurulum"; st.rerun()
    with col_t2:
        if st.button("📊 Skor Gir (Aktif Maçlar)", use_container_width=True, type="primary" if st.session_state.hakem_mod == "skor" else "secondary"):
            st.session_state.hakem_mod = "skor"; st.rerun()
            
    st.divider()
    
    program = githubdan_veri_getir("mac_programi.json")
    if program:
        df_maclar = pd.DataFrame(program)
        
        if st.session_state.hakem_mod == "kurulum":
            aktif_kortlar = sorted(df_maclar["Kort"].unique())
            secilen_kort = st.selectbox("Kort Seçin", aktif_kortlar, key="kurulum_kort_sec")
            st.divider()
            
            kort_maclari = df_maclar[df_maclar["Kort"] == secilen_kort]
            mac_secenekleri = [(f"{row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{row.get('Durum', 'Baslamadi')}]", idx) for idx, row in kort_maclari.iterrows()]
            
            if mac_secenekleri:
                secilen_text = st.selectbox("Maç Seçin", [m[0] for m in mac_secenekleri], key="kurulum_mac_sec")
                st.divider()
                gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_text)
                secilen_mac = df_maclar.loc[gercek_idx]
                
                yeni_durum = st.selectbox("Maç Durumu", ["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"], index=["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"].index(secilen_mac.get("Durum", "Baslamadi")), key=f"kur_d_{gercek_idx}")
                
                # Saat seçimi: Kayıtlı saat varsa onu, yoksa şimdiki saati seç
                idx_b = SAAT_LISTESI.index(secilen_mac.get("Baslangic_Saati", "")) if secilen_mac.get("Baslangic_Saati") in SAAT_LISTESI else CURRENT_TIME_IDX
                baslangic_saati = st.selectbox("Başlama Saati", SAAT_LISTESI, index=idx_b, key=f"k_bas_{gercek_idx}")
                
                idx_bit = SAAT_LISTESI.index(secilen_mac.get("Bitis_Saati", "")) if secilen_mac.get("Bitis_Saati") in SAAT_LISTESI else 0
                bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=idx_bit, key=f"k_bit_{gercek_idx}")

                if st.button("Kurulumu Kaydet", type="primary"):
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Baslangic_Saati"] = baslangic_saati if baslangic_saati != "Secilmedi" else ""
                    df_maclar.loc[gercek_idx, "Bitis_Saati"] = bitis_saati if bitis_saati != "Secilmedi" else ""
                    df_maclar.loc[gercek_idx, "Son_Hakem"] = st.session_state.kullanici
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili: st.success("Kaydedildi!") else: st.error(mesaj)

        elif st.session_state.hakem_mod == "skor":
            aktif_maclar = df_maclar[df_maclar["Durum"] == "Oynaniyor"]
            for idx, row in aktif_maclar.iterrows():
                with st.expander(f"🟢 {row['Kort']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}"):
                    mevcut_skorlar = skor_cozumle(row.get("Skor", "-"))
                    yeni_durum = st.selectbox("Durum", ["Oynaniyor", "Retired", "Bitti", "Walkover"], index=["Oynaniyor", "Retired", "Bitti", "Walkover"].index(row.get("Durum", "Oynaniyor")), key=f"s_d_{idx}")
                    s1p1 = st.number_input("P1 S1", 0, 7, mevcut_skorlar["s1_p1"], key=f"s1p1_{idx}")
                    s1p2 = st.number_input("P2 S1", 0, 7, mevcut_skorlar["s1_p2"], key=f"s1p2_{idx}")
                    
                    bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=0, key=f"s_b_{idx}")
                    
                    if st.button("Kaydet", key=f"btn_{idx}", type="primary"):
                        df_maclar.loc[idx, "Durum"] = yeni_durum
                        df_maclar.loc[idx, "Skor"] = f"{s1p1}/{s1p2}"
                        df_maclar.loc[idx, "Bitis_Saati"] = bitis_saati if bitis_saati != "Secilmedi" else ""
                        df_maclar.loc[idx, "Son_Hakem"] = st.session_state.kullanici
                        basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                        if basarili: st.success("Güncellendi!") else: st.error(mesaj)
