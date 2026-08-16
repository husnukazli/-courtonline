import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

# Sayfa yapılandırması
st.set_page_config(page_title="Kort Hakemi", layout="centered")

# --- MOBİL KLAVYE ENGELLEME VE GÖRSEL AYARLAR ---
st.markdown("""
<script>
document.addEventListener('focusin', function(e) {
    if (e.target.matches('.stSelectbox input')) {
        e.target.blur();
    }
});
</script>
<style>
/* Klavye tetiklemesini engelleme */
div[data-baseweb="input"] input { height: 48px !important; font-size: 20px !important; font-weight: bold !important; text-align: center !important; }
button[data-baseweb="button"] { height: 38px !important; width: 38px !important; }
</style>
""", unsafe_allow_html=True)

st.title("Kort Hakemi Paneli")

# --- YARDIMCI FONKSİYONLAR ---

# TR saatine göre en yakın 5 dk'lık listeyi bulma
def get_current_time_index(saat_listesi):
    try:
        TRT = timezone(timedelta(hours=3))
        simdi = datetime.now(TRT)
        yeni_dk = (simdi.minute // 5) * 5
        target = f"{simdi.hour:02d}:{yeni_dk:02d}"
        if target in saat_listesi:
            return saat_listesi.index(target)
    except:
        pass
    return 0

# Sabit saat listesi oluşturma
SAAT_LISTESI = ["Secilmedi"] + [f"{h:02d}:{m:02d}" for h in range(7, 23) for m in range(0, 60, 5)]
CURRENT_TIME_IDX = get_current_time_index(SAAT_LISTESI)

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
        st.error(f"Veri çekme hatası: {e}")
    return None

def github_a_kaydet(veri_listesi, dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        sha = None
        cevap_get = requests.get(url, headers=headers)
        if cevap_get.status_code == 200:
            sha = cevap_get.json().get("sha")
            
        icerik_json = json.dumps(veri_listesi, indent=4, ensure_ascii=False)
        icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
        
        payload = {"message": "Skor guncelleme", "content": icerik_b64}
        if sha:
            payload["sha"] = sha
            
        cevap_put = requests.put(url, headers=headers, json=payload)
        if cevap_put.status_code in [200, 201]:
            return True, "Basarili"
        else:
            return False, cevap_put.text
    except Exception as e:
        return False, str(e)

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

# --- UYGULAMA MANTIĞI ---

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
        else:
            st.error("Hatali bilgi.")
else:
    # GÖREV ALANI
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1: st.write(f"Gorevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Cikis"):
            st.session_state.hakem_giris = False
            st.rerun()
    st.divider()
    
    # MOD SEÇİMİ
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("🎾 Maç Kurulum", use_container_width=True, type="primary" if st.session_state.hakem_mod == "kurulum" else "secondary"):
            st.session_state.hakem_mod = "kurulum"
            st.rerun()
    with col_t2:
        if st.button("📊 Skor Giriş", use_container_width=True, type="primary" if st.session_state.hakem_mod == "skor" else "secondary"):
            st.session_state.hakem_mod = "skor"
            st.rerun()
            
    st.divider()
    
    program = githubdan_veri_getir("mac_programi.json")
    if program:
        df_maclar = pd.DataFrame(program)
        
        # --- KURULUM PANELİ ---
        if st.session_state.hakem_mod == "kurulum":
            st.subheader("Maç Kurulum Ekranı")
            aktif_kortlar = sorted(df_maclar["Kort"].unique())
            secilen_kort = st.selectbox("Kort Seçin", aktif_kortlar, key="kurulum_kort_sec")
            st.divider()
            
            kort_maclari = df_maclar[df_maclar["Kort"] == secilen_kort]
            mac_secenekleri = []
            default_index = 0
            
            for idx, row in kort_maclari.iterrows():
                durum = row.get('Durum', 'Baslamadi')
                label = f"{row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{durum}]"
                mac_secenekleri.append((label, idx))
                # Başlamamış ilk maçı otomatik yakala
                if durum == "Baslamadi" and default_index == 0:
                    default_index = len(mac_secenekleri) - 1
            
            if mac_secenekleri:
                secilen_label = st.selectbox("Maç Seçin", [m[0] for m in mac_secenekleri], index=default_index, key="kurulum_mac_sec")
                st.divider()
                
                gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_label)
                secilen_mac = df_maclar.loc[gercek_idx]
                
                st.markdown(f"**Maç:** {secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}")
                
                yeni_durum = st.selectbox("Durum", ["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"], 
                                          index=["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"].index(secilen_mac.get("Durum", "Baslamadi")))
                
                kazanan_secim = secilen_mac.get("Kazanan", "Secilmedi")
                if yeni_durum in ["Walkover", "Retired"]:
                    kazanan_secim = st.selectbox("Maçı Kazanan", ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']], 
                                                 index=["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']].index(kazanan_secim) if kazanan_secim in ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']] else 0)

                # Saat Seçiciler
                bas_idx = SAAT_LISTESI.index(secilen_mac.get("Baslangic_Saati", "")) if secilen_mac.get("Baslangic_Saati") in SAAT_LISTESI else CURRENT_TIME_IDX
                baslangic_saati = st.selectbox("Başlama Saati", SAAT_LISTESI, index=bas_idx)
                
                bit_idx = SAAT_LISTESI.index(secilen_mac.get("Bitis_Saati", "")) if secilen_mac.get("Bitis_Saati") in SAAT_LISTESI else 0
                bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=bit_idx)

                if st.button("Kurulumu Kaydet", type="primary"):
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Kazanan"] = kazanan_secim
                    df_maclar.loc[gercek_idx, "Baslangic_Saati"] = baslangic_saati if baslangic_saati != "Secilmedi" else ""
                    df_maclar.loc[gercek_idx, "Bitis_Saati"] = bitis_saati if bitis_saati != "Secilmedi" else ""
                    df_maclar.loc[gercek_idx, "Son_Hakem"] = st.session_state.kullanici
                    
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili: st.success("Kaydedildi!")
                    else: st.error(mesaj)
            else:
                st.info("Kortta maç yok.")

        # --- SKOR GİRİŞ PANELİ ---
        elif st.session_state.hakem_mod == "skor":
            st.subheader("Aktif Maçlar")
            aktif_maclar = df_maclar[df_maclar["Durum"] == "Oynaniyor"]
            
            if aktif_maclar.empty:
                st.info("Aktif maç bulunamadı.")
            else:
                for idx, row in aktif_maclar.iterrows():
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; border-left: 6px solid #00FF66; padding: 10px 14px; margin-top: 12px; border-radius: 6px;">
                        <span style="color: #ffffff; font-weight: bold;">{row['Kort'].upper()} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("⚙️ Skor Güncelle"):
                        mevcut_skorlar = skor_cozumle(row.get("Skor", "-"))
                        yeni_d = st.selectbox("Durum", ["Oynaniyor", "Retired", "Bitti", "Walkover"], index=["Oynaniyor", "Retired", "Bitti", "Walkover"].index(row.get("Durum", "Oynaniyor")), key=f"d_{idx}")
                        
                        kaz_ops = ["Secilmedi", row['Oyuncu 1'], row['Oyuncu 2']]
                        kazanan = st.selectbox("Kazanan", kaz_ops, index=0, key=f"k_{idx}") if yeni_d in ["Walkover", "Retired"] else "Secilmedi"
                        
                        s1p1 = st.number_input(f"{row['Oyuncu 1']} (Set 1)", 0, 7, mevcut_skorlar["s1_p1"], key=f"s1p1_{idx}")
                        s1p2 = st.number_input(f"{row['Oyuncu 2']} (Set 1)", 0, 7, mevcut_skorlar["s1_p2"], key=f"s1p2_{idx}")
                        
                        bitis_val = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=0, key=f"b_{idx}")
                        
                        if st.button("Skoru Kaydet", key=f"btn_{idx}", type="primary"):
                            df_maclar.loc[idx, "Durum"] = yeni_d
                            df_maclar.loc[idx, "Kazanan"] = kazanan
                            df_maclar.loc[idx, "Skor"] = f"{s1p1}/{s1p2}"
                            df_maclar.loc[idx, "Bitis_Saati"] = bitis_val if bitis_val != "Secilmedi" else ""
                            df_maclar.loc[idx, "Son_Hakem"] = st.session_state.kullanici
                            
                            basarili, msg = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                            if basarili: st.success("Güncellendi!")
                            else: st.error(msg)
    else:
        st.warning("Program verisi çekilemedi.")
