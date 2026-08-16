import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Kort Hakemi", layout="centered")

# --- MOBİL KLAVYE VE GÖRSEL AYARLAR (JS ENJEKSİYONU) ---
st.markdown("""
<script>
document.addEventListener('focusin', function(e) {
    if (e.target.matches('.stSelectbox input')) {
        e.target.blur();
    }
});
</script>
<style>
/* Klavye tetiklemesini engellemek için */
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
    except Exception:
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
    if not skor_str or skor_str == "-":
        return sets
    try:
        parcalar = skor_str.split()
        for i, p in enumerate(parcalar):
            s = p.split("/")
            if len(s) == 2:
                sets[f"s{i+1}_p1"] = int(s[0])
                sets[f"s{i+1}_p2"] = int(s[1])
    except Exception:
        pass
    return sets

def set_skoru_gecerli_mi(p1, p2, is_set_3=False, format_str="Normal (6) + 10 Puanlık Maç Tie-Break"):
    """ Gelişmiş formata duyarlı Tenis kural motoru """
    if p1 == 0 and p2 == 0: return False # Tamamlanmış sette skor 0-0 olamaz
    
    is_short_set = "Kısa Set" in format_str or "3 Kısa" in format_str
    is_3rd_set_tiebreak = "Maç Tie-Break" in format_str
    
    # 3. Set Maç Tie-Break Kuralları (Hedef 10 veya 7 Puan olabilir)
    if is_set_3 and is_3rd_set_tiebreak:
        hedef_puan = 10
        if "7 Puanlık" in format_str: 
            hedef_puan = 7
            
        if (p1 >= hedef_puan and p1 - p2 >= 2) or (p2 >= hedef_puan and p2 - p1 >= 2): return True
        return False
        
    # Normal veya Kısa Set Kuralları (1., 2. setler veya Tam oynanan 3. setler)
    if is_short_set:
        if (p1 == 4 and p2 <= 2) or (p2 == 4 and p1 <= 2): return True
        if (p1 == 5 and p2 in [3, 4]) or (p2 == 5 and p1 in [3, 4]): return True
    else: # Normal Set (6)
        if (p1 == 6 and p2 <= 4) or (p2 == 6 and p1 <= 4): return True
        if (p1 == 7 and p2 in [5, 6]) or (p2 == 7 and p1 in [5, 6]): return True
        
    return False

# --- OTURUM YÖNETİMİ ---
hakem_verileri = githubdan_veri_getir("hakemler.json") or {}

if "hakem_giris" not in st.session_state:
    st.session_state.hakem_giris = False
if "hakem_mod" not in st.session_state:
    st.session_state.hakem_mod = "kurulum"

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
    # GÖREV ALANI
    col_h1, col_h2 = st.columns([7, 3])
    with col_h1:
        st.write(f"Görevli Hakem: **{st.session_state.kullanici}**")
    with col_h2:
        if st.button("⬅️ Çıkış"):
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
        
        # --- VERİ TEMİZLİĞİ VE OTOMATİK SKOR DÜZELTMESİ ---
        if "Skor" not in df_maclar.columns:
            df_maclar["Skor"] = "-"
        if "Skor_Formati" not in df_maclar.columns:
            df_maclar["Skor_Formati"] = "Normal (6) + 10 Puanlık Maç Tie-Break"
            
        for idx in df_maclar.index:
            skor_val = str(df_maclar.loc[idx, "Skor"]).strip()
            if pd.isna(df_maclar.loc[idx, "Skor"]) or skor_val.lower() in ["none", "nan", "null", ""]:
                skor_val = "-"
            if df_maclar.loc[idx, "Durum"] == "Oynaniyor" and skor_val == "-":
                skor_val = "0/0 0/0"
            df_maclar.loc[idx, "Skor"] = skor_val
        
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
                
                st.markdown(f"**{secilen_mac['Oyuncu 1']} vs {secilen_mac['Oyuncu 2']}**")
                
                durum_listesi = ["Baslamadi", "Oynaniyor", "Retired", "Bitti", "Walkover"]
                mevcut_durum = secilen_mac.get("Durum", "Baslamadi")
                durum_idx = durum_listesi.index(mevcut_durum) if mevcut_durum in durum_listesi else 0
                yeni_durum = st.selectbox("Maç Durumu", durum_listesi, index=durum_idx, key=f"kur_d_{gercek_idx}")
                
                # YENİ EKLENEN SEÇENEKLERLE SKOR FORMATI (PDF ekranı yapılana kadar buradan da müdahale edilebilir)
                format_ops = [
                    "Normal (6) + 10 Puanlık Maç Tie-Break", 
                    "Normal (6) + 3. Set Tam Oynanır", 
                    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
                    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
                    "3 Kısa Set (4)"
                ]
                mevcut_format = secilen_mac.get("Skor_Formati", format_ops[0])
                f_idx = format_ops.index(mevcut_format) if mevcut_format in format_ops else 0
                secilen_format = st.selectbox("Skor Formatı (Baş Hakem Ayarı)", format_ops, index=f_idx, key=f"k_form_{gercek_idx}")
                
                # Kurumsal Özellikler
                kaz_ops = ["Secilmedi", secilen_mac['Oyuncu 1'], secilen_mac['Oyuncu 2']]
                kura_val = secilen_mac.get("Kura_Kazanan", "Secilmedi")
                kura_idx = kaz_ops.index(kura_val) if kura_val in kaz_ops else 0
                kura_kazanan = st.selectbox("Kura Kazanan", kaz_ops, index=kura_idx, key=f"k_kaz_{gercek_idx}")
                
                tercih_ops = ["Secilmedi", "Servis", "Karşılama", "Kort Seçimi"]
                ter_val = secilen_mac.get("Kura_Tercih", "Secilmedi")
                ter_idx = tercih_ops.index(ter_val) if ter_val in tercih_ops else 0
                kura_tercih = st.selectbox("Kura Tercihi", tercih_ops, index=ter_idx, key=f"k_ter_{gercek_idx}")
                
                saha_ops = ["Secilmedi", "Sandalyenin Sağı", "Sandalyenin Solu"]
                tar_val = secilen_mac.get("Saha_Tarafi", "Secilmedi")
                tar_idx = saha_ops.index(tar_val) if tar_val in saha_ops else 0
                saha_tarafi = st.selectbox("Saha Tarafı", saha_ops, index=tar_idx, key=f"k_tar_{gercek_idx}")

                # Saat Seçiciler
                m_bas = secilen_mac.get("Baslangic_Saati", "")
                m_bit = secilen_mac.get("Bitis_Saati", "")
                
                bas_idx = SAAT_LISTESI.index(m_bas) if m_bas in SAAT_LISTESI else CURRENT_TIME_IDX
                bit_idx = SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else CURRENT_TIME_IDX
                
                baslangic_saati = st.selectbox("Başlama Saati", SAAT_LISTESI, index=bas_idx, key=f"bas_{gercek_idx}")
                bitis_saati = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=bit_idx, key=f"bit_{gercek_idx}")
                
                if st.button("Kurulumu Kaydet", type="primary"):
                    b_str = baslangic_saati if baslangic_saati != "Secilmedi" else ""
                    bit_str = bitis_saati if bitis_saati != "Secilmedi" else ""
                    
                    df_maclar.loc[gercek_idx, "Durum"] = yeni_durum
                    df_maclar.loc[gercek_idx, "Skor_Formati"] = secilen_format
                    df_maclar.loc[gercek_idx, "Kura_Kazanan"] = kura_kazanan
                    df_maclar.loc[gercek_idx, "Kura_Tercih"] = kura_tercih
                    df_maclar.loc[gercek_idx, "Saha_Tarafi"] = saha_tarafi
                    df_maclar.loc[gercek_idx, "Baslangic_Saati"] = b_str
                    df_maclar.loc[gercek_idx, "Bitis_Saati"] = bit_str
                    df_maclar.loc[gercek_idx, "Son_Hakem"] = st.session_state.kullanici

                    if yeni_durum == "Oynaniyor" and df_maclar.loc[gercek_idx, "Skor"] == "-":
                        df_maclar.loc[gercek_idx, "Skor"] = "0/0 0/0"
                    
                    basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                    if basarili:
                        st.success("Maç kurulum bilgileri kaydedildi!")
                    else:
                        st.error(mesaj)
            else:
                st.info("Bu kortta maç bulunmuyor.")

        # --- SKOR PANELİ VE VALIDASYON MANTIĞI ---
        elif st.session_state.hakem_mod == "skor":
            st.subheader("Aktif Maçlar Skor Girişi")
            aktif = df_maclar[df_maclar["Durum"] == "Oynaniyor"]
            
            if aktif.empty:
                st.info("Şu an devam eden maç bulunmuyor.")
            else:
                for idx, row in aktif.iterrows():
                    m_formati = row.get("Skor_Formati", "Normal (6) + 10 Puanlık Maç Tie-Break")
                    
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; border-left: 6px solid #00FF66; padding: 10px 14px; margin-top: 12px; border-radius: 6px;">
                        <span style="color: #ffffff; font-weight: bold;">{row['Kort'].upper()} | {row['Oyuncu 1']} vs {row['Oyuncu 2']}</span>
                        <span style="float: right; color: #00FF66; font-weight: bold;">{row['Skor']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"⚙️ Skor Güncelle (Kural: {m_formati.split('+')[0].strip()})"):
                        mevcut_skorlar = skor_cozumle(row.get("Skor", "-"))
                        
                        durum_listesi_skor = ["Oynaniyor", "Retired", "Bitti", "Walkover"]
                        mevcut_durum_skor = row.get("Durum", "Oynaniyor")
                        d_idx = durum_listesi_skor.index(mevcut_durum_skor) if mevcut_durum_skor in durum_listesi_skor else 0
                        yeni_d = st.selectbox("Durum Güncelle", durum_listesi_skor, index=d_idx, key=f"d_{idx}")
                        
                        kazanan = "Secilmedi"
                        if yeni_d in ["Retired", "Walkover", "Bitti"]:
                            kaz_ops = ["Secilmedi", row['Oyuncu 1'], row['Oyuncu 2']]
                            kaz_val = row.get("Kazanan", "Secilmedi")
                            k_idx = kaz_ops.index(kaz_val) if kaz_val in kaz_ops else 0
                            kazanan = st.selectbox("Kazanan", kaz_ops, index=k_idx, key=f"k_{idx}")
                        
                        s1p1 = st.number_input(f"{row['Oyuncu 1']} (Set 1)", 0, 7, mevcut_skorlar["s1_p1"], key=f"s1p1_{idx}")
                        s1p2 = st.number_input(f"{row['Oyuncu 2']} (Set 1)", 0, 7, mevcut_skorlar["s1_p2"], key=f"s1p2_{idx}")
                        s2p1 = st.number_input(f"{row['Oyuncu 1']} (Set 2)", 0, 7, mevcut_skorlar["s2_p1"], key=f"s2p1_{idx}")
                        s2p2 = st.number_input(f"{row['Oyuncu 2']} (Set 2)", 0, 7, mevcut_skorlar["s2_p2"], key=f"s2p2_{idx}")
                        s3p1 = st.number_input(f"{row['Oyuncu 1']} (Set 3)", 0, 30, mevcut_skorlar["s3_p1"], key=f"s3p1_{idx}")
                        s3p2 = st.number_input(f"{row['Oyuncu 2']} (Set 3)", 0, 30, mevcut_skorlar["s3_p2"], key=f"s3p2_{idx}")
                        
                        m_bit = row.get("Bitis_Saati", "")
                        bit_idx_s = SAAT_LISTESI.index(m_bit) if m_bit in SAAT_LISTESI else CURRENT_TIME_IDX
                        bit_val = st.selectbox("Bitiş Saati", SAAT_LISTESI, index=bit_idx_s, key=f"b_{idx}")
                        
                        if st.button("Skoru Kaydet", key=f"btn_{idx}", type="primary"):
                            hata_mesaji = ""
                            
                            # Formata Duyarlı Validasyon
                            if yeni_d == "Bitti":
                                if not set_skoru_gecerli_mi(s1p1, s1p2, format_str=m_formati):
                                    hata_mesaji = "1. Set skoru maçın formatına uygun değil!"
                                elif not set_skoru_gecerli_mi(s2p1, s2p2, format_str=m_formati):
                                    hata_mesaji = "2. Set skoru maçın formatına uygun değil!"
                                else:
                                    s1_kazanan = 1 if s1p1 > s1p2 else 2
                                    s2_kazanan = 1 if s2p1 > s2p2 else 2
                                    
                                    if s1_kazanan == s2_kazanan:
                                        if s3p1 != 0 or s3p2 != 0:
                                            hata_mesaji = "Maç 2-0 bittiğinde 3. set skoru girilemez (0/0 olmalıdır)."
                                    else:
                                        if s3p1 == 0 and s3p2 == 0:
                                            hata_mesaji = "Setler 1-1 ise 3. set mutlaka oynanmalıdır!"
                                        elif not set_skoru_gecerli_mi(s3p1, s3p2, is_set_3=True, format_str=m_formati):
                                            uyari_metni = "Kısa Set" if "3 Kısa Set" in m_formati else m_formati.split('+')[-1].strip()
                                            hata_mesaji = f"3. Set skoru hatalı! Kural: {uyari_metni}"
                                            
                                if kazanan == "Secilmedi":
                                    hata_mesaji = "Maç 'Bitti' durumundaysa Kazanan oyuncu seçilmelidir!"

                            if hata_mesaji:
                                st.error(f"❌ {hata_mesaji}")
                            else:
                                skor_metni = f"{s1p1}/{s1p2} {s2p1}/{s2p2}"
                                if s3p1 > 0 or s3p2 > 0:
                                    skor_metni += f" {s3p1}/{s3p2}"
                                
                                b_bitis_str = bit_val if bit_val != "Secilmedi" else ""
                                
                                df_maclar.loc[idx, "Durum"] = yeni_d
                                df_maclar.loc[idx, "Kazanan"] = kazanan
                                df_maclar.loc[idx, "Skor"] = skor_metni
                                df_maclar.loc[idx, "Bitis_Saati"] = b_bitis_str
                                df_maclar.loc[idx, "Son_Hakem"] = st.session_state.kullanici
                                
                                basarili, mesaj = github_a_kaydet(df_maclar.to_dict(orient="records"), "mac_programi.json")
                                if basarili:
                                    st.success("Güncellendi!")
                                else:
                                    st.error(mesaj)
    else:
        st.warning("Program verisi çekilemedi.")
