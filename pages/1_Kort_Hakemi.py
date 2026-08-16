import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime

st.set_page_config(page_title="Kort Hakemi", layout="centered")

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

def set_skoru_gecerli_mi(p1, p2, durum):
    if p1 == 0 and p2 == 0: return True
    if durum not in ["Bitti"]: return True
    valid_completed = [
        (6,0),(6,1),(6,2),(6,3),(6,4),
        (0,6),(1,6),(2,6),(3,6),(4,6),
        (7,5),(7,6),(5,7),(6,7)
    ]
    return (p1, p2) in valid_completed

SAAT_LISTESI = ["Secilmedi"] + [f"{h:02d}:{m:02d}" for h in range(7, 23) for m in range(0, 60, 5)]

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
    with col_h1:
        st.write(f"Gorevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Cikis Yap"):
            st.session_state.hakem_giris = False
            st.rerun()
        
    st.divider()
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("🎾 Maç Seç / Başlat (Kurulum)", use_container_width=True, type="primary" if st.session_state.hakem_mod == "kurulum" else "secondary"):
            st.session_state.hakem_mod = "kurulum"
            st.rerun()
    with col_t2:
        if st.button("📊 Skor Gir (Aktif Maçlar)", use_container_width=True, type="primary" if st.session_state.hakem_mod == "skor" else "secondary"):
            st.session_state.hakem_mod = "skor"
            st.rerun()
            
    st.divider()
    
    program = githubdan_veri_getir("mac_programi.json")
    if program:
        df_maclar = pd.DataFrame(program)
        
        # MOD 1: MAÇ SEÇ / BAŞLAT (KURULUM)
        if st.session_state.hakem_mod == "kurulum":
            st.subheader("Maç Kurulum ve Detay Ekranı")
            aktif_kortlar = sorted(df_maclar["Kort"].unique())
            secilen_kort = st.selectbox("Kort Seçin", aktif_kortlar, key="kurulum_kort_sec")
            
            kort_maclari = df_maclar[df_maclar["Kort"] == secilen_kort]
            mac_secenekleri = []
            for idx, row in kort_maclari.iterrows():
                durum = row.get('Durum', 'Baslamadi')
                simgeler = {"Oynaniyor": "🟢", "Bitti": "🔴", "Walkover": "🔴", "Retired": "🟡", "Baslamadi": "⚪"}
                metin = f"{simgeler.get(durum, '⚪')} {row['Saat']} | {row['Oyuncu 1']} vs {row['Oyuncu 2']} [{durum}]"
                mac_secenekleri.append((metin, idx))
                
            if mac_secenekleri:
                secilen_text = st.selectbox("Maç Seçin", [m[0] for m in mac_secenekleri], key="kurulum_mac_sec")
                gercek_idx = next(m[1] for m in mac_secenekleri if m[0] == secilen_text)
                secilen_mac = df_maclar.loc[gercek_idx]
                
                p1_isim = secilen_mac['Oyuncu 1']
                p2_isim = secilen_mac['Oyuncu 2']
                
                st.markdown(f"**Seçilen Maç:** {p1_isim} vs {p2_isim}")
                st.caption(f"Kategori: {secilen_mac['Kategori']}")
                
                mevcut_durum = secilen_mac.get("Durum", "Baslamadi")
                durum_ops = ["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"]
                yeni_durum = st.selectbox("Maç Durumu", durum_ops, index=durum_ops.index(mevcut_durum) if mevcut_durum in durum_ops else 0, key=f"kurulum_durum_{gercek_idx}")
                
                # Walkover veya Retired durumunda kazanan seçimi
                kazanan_secim = "Secilmedi"
                if yeni_durum in ["Walkover", "Retired"]:
                    kaz_ops = ["Secilmedi", p1_isim, p2_isim]
                    mevcut_kazanan = secilen_mac.get("Kazanan", "Secilmedi")
                    kazanan_secim = st.selectbox("Maçı Kazanan Oyuncu", kaz_ops, index=kaz_ops.index(mevcut_kazanan) if mevcut_kazanan in kaz_ops else 0, key=f"kurulum_kazanan_{gercek_idx}")

                m_bas = secilen_mac.get("Baslangic_Saati", "Secilmedi")
                m_bit = secilen_mac.get("Bitis_Saati", "Secilmedi")
                
                col_z1, col_z2 = st.columns(2)
                with col_z1:
                    baslangic_saati = st.selectbox("Başlama Saati", SAAT_LISTESI, index=SAAT_LISTESI.index(m_bas) if m_bas in SAAT_LISTESI else 0, key=f"k_bas_{gercek_idx}")
                with col_z2:
                    bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else 0, key=f"k_bit_{gercek_idx}")
                    
                kura_ops = ["Secilmedi", p1_isim, p2_isim]
                kz = secilen_mac.get("Kura_Kazanan", "Secilmedi")
                kura_kazanan = st.selectbox("Kurayı Kazanan", kura_ops, index=kura_ops.index(kz) if kz in kura_ops else 0, key=f"k_kaz_{gercek_idx}")
                
                tercih_ops = ["Secilmedi", "Servis", "Karsilama", "Kort Secimi"]
                kt = secilen_mac.get("Kura_Tercih", "Secilmedi")
                kura_tercih = st.selectbox("Kura Tercihi", tercih_ops, index=tercih_ops.index(kt) if kt in tercih_ops else 0, key=f"k_ter_{gercek_idx}")
                
                taraf_ops = ["Secilmedi", "Sandalyenin Sagi / Sahanin Sagi", "Sandalyenin Solu / Sahanin Solu"]
                st_val = secilen_mac.get("Saha_Tarafi", "Secilmedi")
                saha_tarafi = st.selectbox("Oyuncunun Başlangıç Tarafı", taraf_ops, index=taraf_ops.index(st_val) if st_val in taraf_ops else 0, key=f"k_tar_{gercek_idx}")
                
                if st.button("Kurulumu Kaydet", type="primary"):
                    b_saat_str = baslangic_saati if baslangic_saati != "Secilmedi" else ""
                    bit_saat_str = bitis_saati if bitis_saati != "Secilmedi" else ""
                    
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Kazanan"] = kazanan_secim
                    df_maclar.loc[gercek_idx, "Baslangic_Saati"] = b_saat_str
                    df_maclar.loc[gercek_idx, "Bitis_Saati"] = bit_saat_str
                    df_maclar.loc[gercek_idx, "Kura_Kazanan"] = kura_kazanan
                    df_maclar.loc[gercek_idx, "Kura_Tercih"] = kura_tercih
                    df_maclar.loc[gercek_idx, "Saha_Tarafi"] = saha_tarafi
                    
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili: st.success("Maç kurulum bilgileri kaydedildi!")
                    else: st.error(mesaj)
            else:
                st.info("Bu kortta maç bulunmuyor.")

        # MOD 2: SKOR GİR (AKTİF MAÇLAR - KORT SEÇMEDEN ALT ALTA LİSTE VE BELİRGİN KORT NUMARALARI)
        elif st.session_state.hakem_mod == "skor":
            st.subheader("Aktif Maçlar Skor Listesi")
            aktif_maclar = df_maclar[df_maclar["Durum"] == "Oynaniyor"]
            
            if aktif_maclar.empty:
                st.info("Şu anda devam eden (`Oynaniyor` statüsünde) aktif maç bulunmuyor. Önce 'Maç Seç / Başlat' sekmesinden maçları başlatın.")
            else:
                st.caption("Aşağıdaki aktif maçlardan işlem yapmak istediğinizin üzerine tıklayarak skorunu güncelleyebilirsiniz:")
                
                for idx, row in aktif_maclar.iterrows():
                    kort_no = row['Kort']
                    p1 = row['Oyuncu 1']
                    p2 = row['Oyuncu 2']
                    mevcut_skor = row.get("Skor", "-")
                    
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; border-left: 6px solid #00FF66; padding: 10px 14px; margin-top: 12px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0px 2px 5px rgba(0,0,0,0.3);">
                        <span style="background-color: #FF3D00; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 15px; letter-spacing: 0.5px;">{kort_no.upper()}</span>
                        <span style="color: #ffffff; font-size: 13px; font-weight: 600;">{p1} vs {p2}</span>
                        <span style="color: #00FF66; font-size: 13px; font-weight: bold;">Skor: {mevcut_skor}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"⚙️ Detaylar ve Skor Güncelle"):
                        mevcut_skorlar = skor_cozumle(mevcut_skor)
                        
                        mevcut_durum = row.get("Durum", "Oynaniyor")
                        durum_ops = ["Oynaniyor", "Retired", "Bitti", "Walkover"]
                        yeni_durum = st.selectbox("Maç Durumu", durum_ops, index=durum_ops.index(mevcut_durum) if mevcut_durum in durum_ops else 0, key=f"s_durum_{idx}")
                        
                        kazanan_secim = "Secilmedi"
                        if yeni_durum in ["Walkover", "Retired"]:
                            kaz_ops = ["Secilmedi", p1, p2]
                            mevcut_kazanan = row.get("Kazanan", "Secilmedi")
                            kazanan_secim = st.selectbox("Maçı Kazanan Oyuncu", kaz_ops, index=kaz_ops.index(mevcut_kazanan) if mevcut_kazanan in kaz_ops else 0, key=f"skor_kazanan_{idx}")

                        st.markdown("---")
                        st.markdown("#### 1. Set")
                        c1, c2 = st.columns(2)
                        with c1: s1_p1 = st.number_input(f"{p1}", 0, 7, mevcut_skorlar["s1_p1"], key=f"s1_p1_{idx}")
                        with c2: s1_p2 = st.number_input(f"{p2}", 0, 7, mevcut_skorlar["s1_p2"], key=f"s1_p2_{idx}")
                        
                        st.divider()
                        st.markdown("#### 2. Set")
                        c3, c4 = st.columns(2)
                        with c3: s2_p1 = st.number_input(f"{p1}", 0, 7, mevcut_skorlar["s2_p1"], key=f"s2_p1_{idx}")
                        with c4: s2_p2 = st.number_input(f"{p2}", 0, 7, mevcut_skorlar["s2_p2"], key=f"s2_p2_{idx}")
                        
                        st.divider()
                        st.markdown("#### 3. Set (Tie-break / Final)")
                        c5, c6 = st.columns(2)
                        with c5: s3_p1 = st.number_input(f"{p1}", 0, 7, mevcut_skorlar["s3_p1"], key=f"s3_p1_{idx}")
                        with c6: s3_p2 = st.number_input(f"{p2}", 0, 7, mevcut_skorlar["s3_p2"], key=f"s3_p2_{idx}")
                        
                        m_bit = row.get("Bitis_Saati", "Secilmedi")
                        bitis_saati = st.selectbox("Bitiş Saati (Maç Bitişi İçin)", SAAT_LISTESI, index=SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else 0, key=f"s_bit_{idx}")

                        st.markdown("---")
                        if st.button("Skoru Kaydet", key=f"btn_kaydet_{idx}", type="primary"):
                            hata_var = False
                            setler = [(s1_p1, s1_p2), (s2_p1, s2_p2)]
                            if s3_p1 > 0 or s3_p2 > 0: setler.append((s3_p1, s3_p2))
                            
                            for i, (p_1, p_2) in enumerate(setler, 1):
                                if not set_skoru_gecerli_mi(p_1, p_2, yeni_durum):
                                    st.error(f"❌ {i}. Set skoru ({p_1}-{p_2}) maç bitişi için geçerli bir tenis skoruna uymuyor!")
                                    hata_var = True

                            if not hata_var:
                                skor_metni = f"{s1_p1}/{s1_p2} {s2_p1}/{s2_p2}"
                                if s3_p1 > 0 or s3_p2 > 0: skor_metni += f" {s3_p1}/{s3_p2}"
                                
                                b_saat_str = row.get("Baslangic_Saati", "")
                                bit_saat_str = bitis_saati if bitis_saati != "Secilmedi" else ""
                                
                                if yeni_durum in ["Bitti", "Walkover", "Retired"] and not row.get("sure_islendi", False):
                                    if b_saat_str and bit_saat_str:
                                        try:
                                            t1 = datetime.strptime(b_saat_str.strip(), "%H:%M")
                                            t2 = datetime.strptime(bit_saat_str.strip(), "%H:%M")
                                            diff = (t2 - t1).total_seconds() / 60
                                            if diff > 0:
                                                istatistikler = githubdan_veri_getir("turnuva_istatistikleri.json")
                                                if not isinstance(istatistikler, dict): istatistikler = {"sureler": []}
                                                if "sureler" not in istatistikler: istatistikler["sureler"] = []
                                                istatistikler["sureler"].append(int(diff))
                                                github_a_kaydet(istatistikler, "turnuva_istatistikleri.json")
                                                row["sure_islendi"] = True
                                        except: pass

                                df_maclar.loc[idx, "Durum"] = yeni_durum
                                df_maclar.loc[idx, "Kazanan"] = kazanan_secim
                                df_maclar.loc[idx, "Skor"] = skor_metni
                                df_maclar.loc[idx, "Bitis_Saati"] = bitis_saat_str
                                df_maclar.loc[idx, "sure_islendi"] = row.get("sure_islendi", False)
                                
                                basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                                if basarili: st.success("Skor başarıyla güncellendi!")
                                else: st.error(mesaj)
    else:
        st.warning("Aktif maç programı bulunamadı.")
