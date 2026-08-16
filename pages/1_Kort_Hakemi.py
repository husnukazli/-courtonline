import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
from datetime import datetime, timezone, timedelta

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Kort Hakemi", layout="centered")

# --- MOBİL KLAVYE AGRESİF ENGELLEME VE GÖRSEL AYARLAR ---
st.markdown("""
<script>
// Şifre alanı hariç hiçbir inputta (sayı, seçim vs.) klavyenin açılmasına izin verme
const preventKeyboard = function(e) {
    if (e.target.tagName === 'INPUT' && e.target.type !== 'password') {
        e.target.setAttribute('readonly', 'readonly');
        e.target.setAttribute('inputmode', 'none');
        e.target.blur();
    }
};
document.addEventListener('focusin', preventKeyboard, true);
document.addEventListener('touchstart', preventKeyboard, true);
</script>
<style>
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
}
.stApp {
    overflow-y: visible !important;
}
/* Klavye tetiklemesini engellemek için ince ayarlar */
input { caret-color: transparent !important; }
div[data-baseweb="input"] input { height: 48px !important; font-size: 20px !important; font-weight: bold !important; text-align: center !important; }
button[data-baseweb="button"] { height: 38px !important; width: 38px !important; }
</style>
""", unsafe_allow_html=True)

st.title("Kort Hakemi Paneli")

# --- YARDIMCI FONKSİYONLAR ---
def get_current_time_index(saat_listesi):
    try:
        TRT = timezone(timedelta(hours=3))
        simdi = datetime.now(TRT)
        yeni_dk = (simdi.minute // 5) * 5
        target = f"{simdi.hour:02d}:{yeni_dk:02d}"
        if target in saat_listesi:
            return saat_listesi.index(target)
    except Exception as e:
        pass
    return 0

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
        
        payload = {"message": "Güncelleme", "content": icerik_b64}
        if sha:
            payload["sha"] = sha
            
        cevap_put = requests.put(url, headers=headers, json=payload)
        if cevap_put.status_code in [200, 201]:
            return True, "Başarılı"
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

# --- OTURUM YÖNETİMİ ---
hakem_verileri = githubdan_veri_getir("hakemler.json") or {}

if "hakem_giris" not in st.session_state: st.session_state.hakem_giris = False
if "hakem_mod" not in st.session_state: st.session_state.hakem_mod = "kurulum"

if not st.session_state.hakem_giris:
    st.subheader("Hakem Giriş")
    kullanici_adi = st.selectbox("Hakem İsminizi Seçin", [""] + list(hakem_verileri.keys()))
    sifre = st.text_input("Şifre", type="password")
    if st.button("Giriş Yap"):
        if kullanici_adi and hakem_verileri.get(kullanici_adi) == sifre:
            st.session_state.hakem_giris = True
            st.session_state.kullanici = kullanici_adi
            st.rerun()
        else:
            st.error("Hatalı bilgi.")
else:
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1: st.write(f"Görevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Çıkış"):
            st.session_state.hakem_giris = False
            st.rerun()
    st.divider()
    
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
    
    if st.button("🔄 Ekranı Yenile / Güncel Veriyi Çek", use_container_width=True):
        with st.spinner("Veriler Çekiliyor..."):
            time.sleep(0.5)
            st.rerun()

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
            
            for idx, row in kort_maclari.iterrows():
                durum = row.get('Durum', 'Baslamadi')
                label = f"{row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{durum}]"
                mac_secenekleri.append((label, idx))
            
            if mac_secenekleri:
                default_idx = next((i for i, m in enumerate(mac_secenekleri) if "Baslamadi" in m[0]), 0)
                secilen_label = st.selectbox("Maç Seçin", [m[0] for m in mac_secenekleri], index=default_idx, key="kurulum_mac_sec")
                st.divider()
                
                gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_label)
                secilen_mac = df_maclar.loc[gercek_idx]
                
                # Kurulum paneli durum renk kodlaması
                durum_kurulum = secilen_mac.get("Durum", "Baslamadi")
                if durum_kurulum == "Oynaniyor": renk_k = "#00FF66"
                elif durum_kurulum in ["Bitti", "Walkover", "Retired"]: renk_k = "#FF1744"
                else: renk_k = "#aaaaaa"
                
                st.markdown(f"<h4 style='color: {renk_k}; text-align: center;'>{secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}</h4>", unsafe_allow_html=True)
                
                yeni_durum = st.selectbox("Maç Durumu", ["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"], 
                                          index=["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"].index(secilen_mac.get("Durum", "Baslamadi")), key=f"kur_d_{gercek_idx}")
                
                kaz_ops = ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']]
                kura_val = secilen_mac.get("Kura_Kazanan", "Secilmedi")
                kura_kazanan = st.selectbox("Kura Kazanan", kaz_ops, index=kaz_ops.index(kura_val) if kura_val in kaz_ops else 0, key=f"k_kaz_{gercek_idx}")
                
                tercih_ops = ["Secilmedi", "Servis", "Karşılama", "Kort Seçimi"]
                ter_val = secilen_mac.get("Kura_Tercih", "Secilmedi")
                kura_tercih = st.selectbox("Kura Tercihi", tercih_ops, index=tercih_ops.index(ter_val) if ter_val in tercih_ops else 0, key=f"k_ter_{gercek_idx}")
                
                saha_ops = ["Secilmedi", "Sandalyenin Sağı", "Sandalyenin Solu"]
                tar_val = secilen_mac.get("Saha_Tarafi", "Secilmedi")
                saha_tarafi = st.selectbox("Saha Tarafı", saha_ops, index=saha_ops.index(tar_val) if tar_val in saha_ops else 0, key=f"k_tar_{gercek_idx}")

                m_bas = secilen_mac.get("Baslangic_Saati", "")
                m_bit = secilen_mac.get("Bitis_Saati", "")
                
                bas_idx = SAAT_LISTESI.index(m_bas) if m_bas in SAAT_LISTESI else CURRENT_TIME_IDX
                bit_idx = SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else 0
                
                baslangic_saati = st.selectbox("Başlama Saati", SAAT_LISTESI, index=bas_idx, key=f"bas_{gercek_idx}")
                bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=bit_idx, key=f"bit_{gercek_idx}")
                
                if st.button("Kurulumu Kaydet", type="primary"):
                    with st.spinner("Buluta Kaydediliyor..."):
                        df_maclar.loc[gercek_idx, ["Durum", "Kura_Kazanan", "Kura_Tercih", "Saha_Tarafi", "Baslangic_Saati", "Bitis_Saati", "Son_Hakem"]] = [
                            yeni_durum, kura_kazanan, kura_tercih, saha_tarafi, (baslangic_saati if baslangic_saati != "Secilmedi" else ""), (bitis_saati if bitis_saati != "Secilmedi" else ""), st.session_state.kullanici
                        ]
                        basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                        if basarili: 
                            st.success("✅ Başarıyla Kaydedildi!")
                            time.sleep(0.7)
                            st.rerun()
                        else: 
                            st.error(mesaj)
            else:
                st.info("Bu kortta maç bulunmuyor.")

        # --- SKOR PANELİ ---
        elif st.session_state.hakem_mod == "skor":
            st.subheader("Aktif Maçlar Skor Girişi")
            aktif = df_maclar[df_maclar["Durum"] == "Oynaniyor"]
            
            if aktif.empty:
                st.info("Şu an devam eden maç bulunmuyor.")
            else:
                for idx, row in aktif.iterrows():
                    format_bilgisi = row.get("Skor_Formati", "3 Normal Set")
                    durum_skor = row.get("Durum", "Oynaniyor")
                    
                    # Skor Paneli Renk Kodlaması
                    if durum_skor == "Oynaniyor":
                        renk = "#00FF66" # Yeşil
                        durum_metni = "DEVAM EDİYOR"
                    elif durum_skor in ["Bitti", "Walkover", "Retired"]:
                        renk = "#FF1744" # Kırmızı
                        durum_metni = durum_skor.upper()
                    else:
                        renk = "#888888" # Gri
                        durum_metni = "BAŞLAMADI"

                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; border-left: 6px solid {renk}; padding: 10px 14px; margin-top: 12px; border-radius: 6px;">
                        <span style="color: {renk}; font-weight: bold; font-size: 15px;">{row['Kort'].upper()} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}</span><br>
                        <span style="color: #ccc; font-size: 12px;">Durum: <b style="color:{renk}">{durum_metni}</b> | Format: <span style="color: #B2FF59;">{format_bilgisi}</span></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("⚙️ Detaylar ve Skor Güncelle"):
                        mevcut_skorlar = skor_cozumle(row.get("Skor", "-"))
                        
                        yeni_d = st.selectbox("Durum Güncelle", ["Oynaniyor", "Retired", "Bitti", "Walkover"], index=["Oynaniyor", "Retired", "Bitti", "Walkover"].index(row.get("Durum", "Oynaniyor")), key=f"d_{idx}")
                        
                        kaz_ops = ["Secilmedi", row['Oyuncu 1'], row['Oyuncu 2']]
                        kaz_val = row.get("Kazanan", "Secilmedi")
                        kazanan = st.selectbox("Kazanan", kaz_ops, index=kaz_ops.index(kaz_val) if kaz_val in kaz_ops else 0, key=f"k_{idx}") if yeni_d in ["Retired", "Walkover"] else "Secilmedi"
                        
                        # FORMATLARA GÖRE SKOR GİRİŞ DENETİMİ
                        s1_max, s2_max, s3_max = 7, 7, 7
                        
                        if "3 Kısa Set" in format_bilgisi:
                            s1_max, s2_max, s3_max = 5, 5, 5
                        elif "3 Normal Set" in format_bilgisi:
                            s1_max, s2_max, s3_max = 7, 7, 7
                        elif "2 Normal Set" in format_bilgisi and "Tie-Break" in format_bilgisi:
                            s1_max, s2_max, s3_max = 7, 7, 50
                        elif "2 Kısa Set" in format_bilgisi and "Tie-Break" in format_bilgisi:
                            s1_max, s2_max, s3_max = 5, 5, 50
                            
                        # Hata vermemesi için min() ile koruma altına alındı
                        s1p1_val = min(mevcut_skorlar["s1_p1"], s1_max)
                        s1p2_val = min(mevcut_skorlar["s1_p2"], s1_max)
                        s2p1_val = min(mevcut_skorlar["s2_p1"], s2_max)
                        s2p2_val = min(mevcut_skorlar["s2_p2"], s2_max)
                        s3p1_val = min(mevcut_skorlar["s3_p1"], s3_max)
                        s3p2_val = min(mevcut_skorlar["s3_p2"], s3_max)

                        s1p1 = st.number_input(f"{row['Oyuncu 1']} (Set 1)", 0, s1_max, s1p1_val, key=f"s1p1_{idx}")
                        s1p2 = st.number_input(f"{row['Oyuncu 2']} (Set 1)", 0, s1_max, s1p2_val, key=f"s1p2_{idx}")
                        s2p1 = st.number_input(f"{row['Oyuncu 1']} (Set 2)", 0, s2_max, s2p1_val, key=f"s2p1_{idx}")
                        s2p2 = st.number_input(f"{row['Oyuncu 2']} (Set 2)", 0, s2_max, s2p2_val, key=f"s2p2_{idx}")
                        s3p1 = st.number_input(f"{row['Oyuncu 1']} (Set 3)", 0, s3_max, s3p1_val, key=f"s3p1_{idx}")
                        s3p2 = st.number_input(f"{row['Oyuncu 2']} (Set 3)", 0, s3_max, s3p2_val, key=f"s3p2_{idx}")
                        
                        bit_val = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=CURRENT_TIME_IDX, key=f"b_{idx}")
                        
                        if st.button("Skoru Kaydet", key=f"btn_{idx}", type="primary"):
                            with st.spinner("Buluta Kaydediliyor..."):
                                df_maclar.loc[idx, ["Durum", "Kazanan", "Skor", "Bitis_Saati", "Son_Hakem"]] = [
                                    yeni_d, kazanan, f"{s1p1}/{s1p2} {s2p1}/{s2p2} {s3p1}/{s3p2}", (bit_val if bit_val != "Secilmedi" else ""), st.session_state.kullanici
                                ]
                                
                                basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                                if basarili:
                                    st.success("✅ Skor Başarıyla Güncellendi!")
                                    time.sleep(0.7)
                                    st.rerun()
                                else:
                                    st.error(mesaj)
    else:
        st.warning("Program verisi çekilemedi.")
