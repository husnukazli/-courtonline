import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime

st.set_page_config(page_title="Kort Hakemi", layout="centered")

# Sayı giriş kutularını ve butonlarını mobil uyumlu/büyük yapacak CSS enjeksiyonu
st.markdown("""
<style>
div[data-baseweb="input"] input {
    height: 48px !important;
    font-size: 20px !important;
    font-weight: bold !important;
    text-align: center !important;
}
button[data-baseweb="button"] {
    height: 38px !important;
    width: 38px !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Kort Hakemi Paneli")

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

# Tenis set skoru geçerlilik kontrolü (Sadece "Bitti" seçildiğinde kurallara takılır)
def set_skoru_gecerli_mi(p1, p2, durum):
    if p1 == 0 and p2 == 0:
        return True
        
    # Eğer maç Oynaniyor veya Başlamadı ise canlı skor/ara skorlara (örn: 3-2, 6-5) izin verilir
    if durum != "Bitti":
        return True

    # Maç BİTTİ ise setin kurallara uygun bitmiş olması gerekir
    valid_completed = [
        (6,0),(6,1),(6,2),(6,3),(6,4),
        (0,6),(1,6),(2,6),(3,6),(4,6),
        (7,5),(7,6),(5,7),(6,7)
    ]
    return (p1, p2) in valid_completed

SAAT_LISTESI = ["Secilmedi"] + [f"{h:02d}:{m:02d}" for h in range(7, 23) for m in range(0, 60, 5)]

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
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1:
        st.write(f"Gorevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Cikis Yap"):
            st.session_state.hakem_giris = False
            st.rerun()
        
    st.divider()
    
    program = githubdan_veri_getir("mac_programi.json")
    if program:
        df_maclar = pd.DataFrame(program)
        secilen_kort = st.selectbox("Kort Secin", sorted(df_maclar["Kort"].unique()), key="kort_secim_selectbox")
        
        kort_maclari = df_maclar[df_maclar["Kort"] == secilen_kort]
        mac_secenekleri = []
        for idx, row in kort_maclari.iterrows():
            durum = row.get('Durum', 'Baslamadi')
            simgeler = {"Oynaniyor": "🟢", "Bitti": "🔴", "Baslamadi": "⚪"}
            metin = f"{simgeler.get(durum, '⚪')} {row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}"
            mac_secenekleri.append((metin, idx))
            
        secilen_text = st.selectbox("Mac Secin", [m[0] for m in mac_secenekleri], key="mac_secim_selectbox")
        gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_text)
        secilen_mac = df_maclar.loc[gercek_idx]
        
        p1_isim = secilen_mac['Oyuncu 1']
        p2_isim = secilen_mac['Oyuncu 2']
        
        st.markdown(f"**{p1_isim} vs {p2_isim}**")
        st.caption(f"Kategori: {secilen_mac['Kategori']}")
        
        mevcut_durum = secilen_mac.get("Durum", "Baslamadi")
        durum_ops = ["Baslamadi", "Oynaniyor", "Bitti"]
        yeni_durum = st.selectbox("Mac Durumu", durum_ops, index=durum_ops.index(mevcut_durum) if mevcut_durum in durum_ops else 0, key=f"durum_{gercek_idx}")
        
        st.markdown("---")
        mevcut_skorlar = skor_cozumle(secilen_mac.get("Skor", "-"))
        
        st.markdown("#### 1. Set")
        col1, col2 = st.columns(2)
        with col1:
            s1_p1 = st.number_input(f"{p1_isim}", 0, 7, mevcut_skorlar["s1_p1"], key=f"s1_p1_{gercek_idx}")
        with col2:
            s1_p2 = st.number_input(f"{p2_isim}", 0, 7, mevcut_skorlar["s1_p2"], key=f"s1_p2_{gercek_idx}")
            
        st.divider()
        
        st.markdown("#### 2. Set")
        col3, col4 = st.columns(2)
        with col3:
            s2_p1 = st.number_input(f"{p1_isim}", 0, 7, mevcut_skorlar["s2_p1"], key=f"s2_p1_{gercek_idx}")
        with col4:
            s2_p2 = st.number_input(f"{p2_isim}", 0, 7, mevcut_skorlar["s2_p2"], key=f"s2_p2_{gercek_idx}")
            
        st.divider()
        
        st.markdown("#### 3. Set (Tie-break / Final)")
        col5, col6 = st.columns(2)
        with col5:
            s3_p1 = st.number_input(f"{p1_isim}", 0, 7, mevcut_skorlar["s3_p1"], key=f"s3_p1_{gercek_idx}")
        with col6:
            s3_p2 = st.number_input(f"{p2_isim}", 0, 7, mevcut_skorlar["s3_p2"], key=f"s3_p2_{gercek_idx}")
            
        with st.expander("Ek Detaylar (Saat, Kura Tercihi ve Saha Tarafı)"):
            m_bas = secilen_mac.get("Baslangic_Saati", "Secilmedi")
            m_bit = secilen_mac.get("Bitis_Saati", "Secilmedi")
            
            col_z1, col_z2 = st.columns(2)
            with col_z1:
                baslangic_saati = st.selectbox("Baslama Saati", SAAT_LISTESI, index=SAAT_LISTESI.index(m_bas) if m_bas in SAAT_LISTESI else 0, key=f"bas_{gercek_idx}")
            with col_z2:
                bitis_saati = st.selectbox("Bitis Saati", SAAT_LISTESI, index=SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else 0, key=f"bit_{gercek_idx}")
                
            kura_ops = ["Secilmedi", p1_isim, p2_isim]
            kz = secilen_mac.get("Kura_Kazanan", "Secilmedi")
            kura_kazanan = st.selectbox("Kurayi Kazanan", kura_ops, index=kura_ops.index(kz) if kz in kura_ops else 0, key=f"kura_kaz_{gercek_idx}")
            
            tercih_ops = ["Secilmedi", "Servis", "Karsilama", "Kort Secimi"]
            kt = secilen_mac.get("Kura_Tercih", "Secilmedi")
            kura_tercih = st.selectbox("Kura Tercihi", tercih_ops, index=tercih_ops.index(kt) if kt in tercih_ops else 0, key=f"kura_ter_{gercek_idx}")
            
            taraf_ops = ["Secilmedi", "Sandalyenin Sagi / Sahanin Sagi", "Sandalyenin Solu / Sahanin Solu"]
            st_val = secilen_mac.get("Saha_Tarafi", "Secilmedi")
            saha_tarafi = st.selectbox("Oyuncunun Baslangic Tarafi (Sandalyeye Gore)", taraf_ops, index=taraf_ops.index(st_val) if st_val in taraf_ops else 0, key=f"saha_tar_{gercek_idx}")
        
        st.markdown("---")
        if st.button("Kaydet ve Guncelle", type="primary"):
            hata_var = False
            
            b_saat_str = baslangic_saati if baslangic_saati != "Secilmedi" else ""
            bit_saat_str = bitis_saati if bitis_saati != "Secilmedi" else ""
            
            if b_saat_str and bit_saat_str:
                idx_b = SAAT_LISTESI.index(baslangic_saati)
                idx_bit = SAAT_LISTESI.index(bitis_saati)
                if idx_bit < idx_b:
                    st.error("❌ Bitiş saati başlangıç saatinden erken olamaz!")
                    hata_var = True

            setler = [(s1_p1, s1_p2), (s2_p1, s2_p2)]
            if s3_p1 > 0 or s3_p2 > 0: 
                setler.append((s3_p1, s3_p2))
                
            for i, (p1, p2) in enumerate(setler, 1):
                if not set_skoru_gecerli_mi(p1, p2, yeni_durum):
                    st.error(f"❌ {i}. Set skoru ({p1}-{p2}) maç bitişi için geçerli bir tenis skoruna uymuyor!")
                    hata_var = True

            if not hata_var:
                skor_metni = f"{s1_p1}/{s1_p2} {s2_p1}/{s2_p2}"
                if s3_p1 > 0 or s3_p2 > 0: 
                    skor_metni += f" {s3_p1}/{s3_p2}"
                    
                if yeni_durum == "Bitti" and not secilen_mac.get("sure_islendi", False):
                    if b_saat_str and bit_saat_str:
                        try:
                            t1 = datetime.strptime(b_saat_str.strip(), "%H:%M")
                            t2 = datetime.strptime(bit_saat_str.strip(), "%H:%M")
                            diff = (t2 - t1).total_seconds() / 60
                            if diff > 0:
                                istatistikler = githubdan_veri_getir("turnuva_istatistikleri.json")
                                if not isinstance(istatistikler, dict):
                                    istatistikler = {"sureler": []}
                                if "sureler" not in istatistikler:
                                    istatistikler["sureler"] = []
                                
                                istatistikler["sureler"].append(int(diff))
                                github_a_kaydet(istatistikler, "turnuva_istatistikleri.json")
                                secilen_mac["sure_islendi"] = True
                        except:
                            pass

                df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                df_maclar.loc[gercek_idx, "Skor"] = skor_metni
                df_maclar.loc[gercek_idx, "Baslangic_Saati"] = b_saat_str
                df_maclar.loc[gercek_idx, "Bitis_Saati"] = bit_saat_str
                df_maclar.loc[gercek_idx, "Kura_Kazanan"] = kura_kazanan
                df_maclar.loc[gercek_idx, "Kura_Tercih"] = kura_tercih
                df_maclar.loc[gercek_idx, "Saha_Tarafi"] = saha_tarafi
                df_maclar.loc[gercek_idx, "sure_islendi"] = secilen_mac.get("sure_islendi", False)
                
                basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                if basarili: 
                    st.success("Skor ve detaylar başarıyla güncellendi!")
                else: 
                    st.error(f"Hata: {mesaj}")
    else:
        st.warning("Aktif maç programı bulunamadı.")
