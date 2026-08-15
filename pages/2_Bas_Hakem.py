import streamlit as st
import pdfplumber
import pandas as pd
import requests
import base64
import json
from datetime import datetime

st.set_page_config(page_title="Bashakem Paneli", layout="wide")

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
                    "Kura_Tercih": "",
                    "Saha_Tarafi": "",
                    "sure_islendi": False
                })
    return pd.DataFrame(mac_listesi)

if "bashakem_giris" not in st.session_state:
    st.session_state.bashakem_giris = False

if "bashakem_sayfa" not in st.session_state:
    st.session_state.bashakem_sayfa = "Akis"

if not st.session_state.bashakem_giris:
    st.title("Bashakem Giris Ekrani")
    sifre_input = st.text_input("Bashakem Sifresi", type="password")
    if st.button("Giris Yap"):
        if sifre_input == "1234":
            st.session_state.bashakem_giris = True
            st.rerun()
        else:
            st.error("Hatali sifre.")
else:
    col_b1, col_b2, col_yenile, col_cikis = st.columns([2, 2, 2, 2])
    with col_b1:
        if st.button("Kort Akisi (Takip)", use_container_width=True):
            st.session_state.bashakem_sayfa = "Akis"
            st.rerun()
    with col_b2:
        if st.button("Yonetim Paneli", use_container_width=True):
            st.session_state.bashakem_sayfa = "Yonetim"
            st.rerun()
    with col_yenile:
        if st.button("Anlik Yenile", use_container_width=True):
            st.rerun()
    with col_cikis:
        if st.button("Cikis Yap", use_container_width=True):
            st.session_state.bashakem_giris = False
            st.rerun()

    st.divider()

    # --- 1. SAYFA: KORT AKIŞI ---
    if st.session_state.bashakem_sayfa == "Akis":
        col_zoom1, _ = st.columns([2, 8])
        with col_zoom1:
            zoom_seviyesi = st.slider("Gorunum Olcegi (%)", min_value=50, max_value=120, value=90, step=10)

        st.markdown(f"""
            <style>
            .stApp {{
                zoom: {zoom_seviyesi}%;
            }}
            /* Hover Pop-up Tooltip Tasarımı */
            .tooltip-container {{
                position: relative;
                display: block;
            }}
            .tooltip-container .tooltip-text {{
                visibility: hidden;
                width: 200px;
                background-color: #333;
                color: #fff;
                text-align: left;
                border-radius: 6px;
                padding: 8px;
                position: absolute;
                z-index: 100;
                bottom: 105%;
                left: 50%;
                transform: translateX(-50%);
                opacity: 0;
                transition: opacity 0.3s;
                font-size: 11px;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
            }}
            .tooltip-container:hover .tooltip-text {{
                visibility: visible;
                opacity: 1;
            }}
            </style>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        mevcut_program = githubdan_veri_getir("mac_programi.json")

        if mevcut_program:
            df_maclar = pd.DataFrame(mevcut_program)
            aktif_kortlar = sorted(df_maclar["Kort"].unique(), key=lambda x: int(x.replace("Kort", "").strip()) if x.replace("Kort", "").strip().isdigit() else x)
            
            if aktif_kortlar:
                kort_dict = {}
                max_rows = 0
                for k in aktif_kortlar:
                    m_list = df_maclar[df_maclar["Kort"] == k].to_dict(orient="records")
                    kort_dict[k] = m_list
                    if len(m_list) > max_rows:
                        max_rows = len(m_list)

                baslik_kolonlari = st.columns(len(aktif_kortlar))
                for idx, k in enumerate(aktif_kortlar):
                    with baslik_kolonlari[idx]:
                        st.markdown(f"**{k}**")

                st.markdown("<hr style='margin: 2px 0 10px 0;'>", unsafe_allow_html=True)

                for row_idx in range(max_rows):
                    cols = st.columns(len(aktif_kortlar))
                    for idx, k in enumerate(aktif_kortlar):
                        with cols[idx]:
                            m_list = kort_dict[k]
                            if row_idx < len(m_list):
                                mac = m_list[row_idx]
                                durum = mac.get("Durum", "Baslamadi")
                                skor = mac.get("Skor", "-")
                                b_saat = mac.get("Baslangic_Saati", "-")
                                bit_saat = mac.get("Bitis_Saati", "-")
                                k_kazanan = mac.get("Kura_Kazanan", "-")
                                k_tercih = mac.get("Kura_Tercih", "-")
                                s_tarafi = mac.get("Saha_Tarafi", "-")
                                
                                if durum == "Oynaniyor":
                                    durum_str = "DEVAM"
                                    durum_style = "color: #00FF66; font-weight: bold;"
                                    skor_style = "color: #00FF66; font-weight: bold; font-size: 16px;"
                                elif durum == "Bitti":
                                    durum_str = "BITTI"
                                    durum_style = "color: #FF1744; font-weight: bold;"
                                    skor_style = "color: #FF1744; font-weight: bold; font-size: 13px;"
                                else:
                                    durum_str = "Bekliyor"
                                    durum_style = "color: #888888;"
                                    skor_style = "color: #888888; font-size: 11px;"

                                card_html = f"""
                                <div class="tooltip-container">
                                    <div style="border: 1px solid #444; border-radius: 4px; padding: 6px; margin-bottom: 4px; background-color: #1a1a1a; color: #e0e0e0; font-size: 11px; line-height: 1.1; cursor: pointer;">
                                        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                                            <span style="font-weight: bold; color: #fff;">{mac['Saat']}</span>
                                            <span style="{durum_style}">{durum_str}</span>
                                        </div>
                                        <div style="color: #999; font-size: 9px; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{mac['Kategori']}</div>
                                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px;">{mac['Oyuncu 1']}</div>
                                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px;">{mac['Oyuncu 2']}</div>
                                        <div style="margin-top: 4px; border-top: 1px dashed #333; padding-top: 3px; text-align: center;">
                                            <span style="{skor_style}">Skor: {skor}</span>
                                        </div>
                                    </div>
                                    <span class="tooltip-text">
                                        <b>Mac Detaylari</b><br>
                                        Baslama: {b_saat} | Bitis: {bit_saat}<br>
                                        Kura Kazanan: {k_kazanan}<br>
                                        Tercih: {k_tercih}<br>
                                        Taraf: {s_tarafi}
                                    </span>
                                </div>
                                """
                                st.markdown(card_html, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div style="border: 1px dashed #222; border-radius: 4px; padding: 5px; margin-bottom: 4px; background-color: transparent; height: 75px;">
                                </div>
                                """, unsafe_allow_html=True)
        else:
            st.info("Sistemde kayitli mac programi yok. Yonetim panelinden PDF yukleyebilirsiniz.")

    # --- 2. SAYFA: YÖNETİM PANELİ VE İSTATİSTİKLER ---
    elif st.session_state.bashakem_sayfa == "Yonetim":
        st.subheader("Turnuva Yonetim ve İstatistik Paneli")
        
        program_data = githubdan_veri_getir("mac_programi.json")
        if program_data:
            df_stat = pd.DataFrame(program_data)
            toplam_mac = len(df_stat)
            biten_mac = len(df_stat[df_stat["Durum"] == "Bitti"])
            devam_eden = len(df_stat[df_stat["Durum"] == "Oynaniyor"])
            baslamayan = len(df_stat[df_stat["Durum"] == "Baslamadi"])
            oran = int((biten_mac / toplam_mac * 100)) if toplam_mac > 0 else 0
            
            istatistikler = githubdan_veri_getir("turnuva_istatistikleri.json")
            sureler = istatistikler.get("sureler", []) if isinstance(istatistikler, dict) else []
            ortalama_sure = int(sum(sureler) / len(sureler)) if sureler else 0

            st.markdown("### Turnuva İstatistikleri")
            st.metric(label="Gunluk Tamamlanma Orani", value=f"%{oran}", delta=f"{biten_mac} / {toplam_mac} Mac Bitti")
            
            st1, st2, st3, st4, st5 = st.columns(5)
            with st1:
                st.metric("Planlanan (Toplam)", toplam_mac)
            with st2:
                st.metric("Tamamlanan", biten_mac)
            with st3:
                st.metric("Devam Eden", devam_eden)
            with st4:
                st.metric("Baslamayan", baslamayan)
            with st5:
                st.metric("Turnuva Ort. Süre", f"{ortalama_sure} dk")
                
            st.divider()

        st.markdown("### Hakem Yonetimi")
        kayitli_hakemler = githubdan_veri_getir("hakemler.json")
        if not isinstance(kayitli_hakemler, dict):
            kayitli_hakemler = {}
            
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            yeni_kullanici = st.text_input("Hakem Kullanici Adi / Ismi")
        with col_h2:
            yeni_sifre = st.text_input("Hakem Sifresi", type="password")
            
        if st.button("Hakem Ekle / Guncelle"):
            if yeni_kullanici.strip() and yeni_sifre.strip():
                kayitli_hakemler[yeni_kullanici.strip()] = yeni_sifre.strip()
                basarili, mesaj = github_a_kaydet(kayitli_hakemler, "hakemler.json")
                if basarili:
                    st.success(f"'{yeni_kullanici}' basariyla kaydedildi.")
                else:
                    st.error(f"Kayit hatasi: {mesaj}")
            else:
                st.warning("Kullanici adi ve sifre bos olamaz.")
                
        if kayitli_hakemler:
            st.write("Sistemde Kayitli Hakemler:")
            df_hakem = pd.DataFrame(list(kayitli_hakemler.items()), columns=["Kullanici Adi", "Sifre"])
            st.dataframe(df_hakem, use_container_width=True)

        st.divider()

        st.markdown("### Yeni Program (PDF) Yükleme")
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
                    if st.button("Onayla ve Mevcut Programın Üzerine Yaz"):
                        basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"), "mac_programi.json")
                        if basarili:
                            st.success("Yeni program kaydedildi!")
                        else:
                            st.error(mesaj)
