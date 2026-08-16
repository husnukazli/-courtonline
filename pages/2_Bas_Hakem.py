import streamlit as st
import pdfplumber
import pandas as pd
import requests
import base64
import json
import time
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Bashakem Paneli", layout="wide")

# --- SCROLL'U DÜZELTEN VE ÜST BOŞLUĞU AYARLAYAN CSS ---
st.markdown("""
<style>
    .block-container {
        padding-top: 4rem !important; 
        padding-bottom: 5rem !important;
    }
    html, body, [data-testid="stAppViewContainer"], .stApp {
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

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
                    "Skor_Formati": "3 Normal Set",
                    "Oyuncu 1": oyuncu_1,
                    "Oyuncu 2": oyuncu_2,
                    "Durum": "Baslamadi",
                    "Skor": "-",
                    "Baslangic_Saati": "",
                    "Bitis_Saati": "",
                    "Kura_Kazanan": "",
                    "Kura_Tercih": "",
                    "Saha_Tarafi": "",
                    "Kazanan": "Secilmedi",
                    "Son_Hakem": "-",
                    "sure_islendi": False
                })
    return pd.DataFrame(mac_listesi)

def kazanan_kim(mac):
    kazanan_str = mac.get("Kazanan", "")
    if kazanan_str and kazanan_str != "Secilmedi":
        if kazanan_str == mac.get("Oyuncu 1"): return 1
        if kazanan_str == mac.get("Oyuncu 2"): return 2
        
    skor_str = mac.get("Skor", "-")
    if not skor_str or skor_str == "-":
        return None
    p1_sets = 0
    p2_sets = 0
    try:
        for s in skor_str.split():
            parts = s.split("/")
            if len(parts) == 2:
                g1 = int(parts[0])
                g2 = int(parts[1])
                if g1 > g2:
                    p1_sets += 1
                elif g2 > g1:
                    p2_sets += 1
    except:
        pass
    if p1_sets > p2_sets:
        return 1
    elif p2_sets > p1_sets:
        return 2
    return None

def mac_suresi_hesapla(mac):
    b_saat = mac.get("Baslangic_Saati", "")
    bit_saat = mac.get("Bitis_Saati", "")
    durum = mac.get("Durum", "")
    
    if not b_saat or b_saat == "Secilmedi":
        return None
        
    try:
        t1 = datetime.strptime(b_saat.strip(), "%H:%M")
        
        if bit_saat and bit_saat != "Secilmedi":
            t2 = datetime.strptime(bit_saat.strip(), "%H:%M")
            diff = int((t2 - t1).total_seconds() / 60)
            if diff > 0:
                return f"{diff} dk (Tamamlandı)"
        
        if durum == "Oynaniyor":
            TRT = timezone(timedelta(hours=3))
            simdi = datetime.now(TRT)
            t1_full = simdi.replace(hour=t1.hour, minute=t1.minute, second=0, microsecond=0)
            diff_sec = (simdi - t1_full).total_seconds()
            diff_dk = int(diff_sec / 60)
            if diff_dk >= 0:
                return f"{diff_dk} dk (Devam Ediyor)"
    except:
        pass
    return None

def tooltip_html_olustur(mac):
    saat = mac.get('Saat', '-')
    kategori = mac.get('Kategori', '-')
    format_bilgisi = mac.get('Skor_Formati', 'Format Seçilmedi')
    b_saat = mac.get('Baslangic_Saati', '')
    bit_saat = mac.get('Bitis_Saati', '')
    k_kazanan = mac.get('Kura_Kazanan', '')
    k_tercih = mac.get('Kura_Tercih', '')
    s_tarafi = mac.get('Saha_Tarafi', '')
    son_hakem = mac.get('Son_Hakem', '')
    
    html = f'<b style="color: #00E5FF; font-size: 14px;">Maç Detayları</b><br>'
    html += f'<b>Planlanan Saat:</b> <span style="color: #FFD700; font-weight: bold;">{saat}</span><br>'
    html += f'<b>Kategori:</b> {kategori}<br>'
    html += f'<b>Maç Formatı:</b> <span style="color: #B2FF59;">{format_bilgisi}</span>'
    
    detaylar = []
    if b_saat and b_saat != "Secilmedi":
        detaylar.append(f'<b>Başlama:</b> <span style="color: #00FF66; font-weight: bold;">{b_saat}</span>')
    if bit_saat and bit_saat != "Secilmedi":
        detaylar.append(f'<b>Bitiş:</b> <span style="color: #FF1744; font-weight: bold;">{bit_saat}</span>')
        
    sure_metni = mac_suresi_hesapla(mac)
    if sure_metni:
        detaylar.append(f'<b>Maç Süresi:</b> <span style="color: #00E5FF; font-weight: bold;">{sure_metni}</span>')
        
    if k_kazanan and k_kazanan != "Secilmedi":
        detaylar.append(f'<b>Kura Kazanan:</b> {k_kazanan}')
    if k_tercih and k_tercih != "Secilmedi":
        detaylar.append(f'<b>Tercih:</b> {k_tercih}')
    if s_tarafi and s_tarafi != "Secilmedi":
        detaylar.append(f'<b>Taraf:</b> {s_tarafi}')
        
    if detaylar:
        html += '<hr style="margin: 6px 0; border-color: #444;">'
        html += '<br>'.join(detaylar)
        
    if son_hakem and son_hakem != "-":
        html += f'<div style="margin-top: 6px; border-top: 1px dashed #555; padding-top: 4px; color: #FF9100; font-weight: bold; font-size: 12px;">Aktif Hakem: {son_hakem}</div>'
        
    return html

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
            with st.spinner("🔄 Veriler Çekiliyor..."):
                time.sleep(0.6)
                st.rerun()
    with col_cikis:
        if st.button("Cikis Yap", use_container_width=True):
            st.session_state.bashakem_giris = False
            st.rerun()

    st.divider()

    if st.session_state.bashakem_sayfa == "Akis":
        col_zoom1, _ = st.columns([2, 8])
        with col_zoom1:
            zoom_seviyesi = st.slider("Gorunum Olcegi (%)", min_value=50, max_value=150, value=120, step=10)

        st.markdown(f"""
            <style>
            .stApp {{
                zoom: {zoom_seviyesi}%;
            }}
            @media (max-width: 768px) {{
                [data-testid="stHorizontalBlock"] {{
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    overflow-x: auto !important;
                    width: 100% !important;
                    gap: 12px !important;
                    padding-bottom: 12px !important;
                    -webkit-overflow-scrolling: touch;
                }}
                [data-testid="column"] {{
                    flex: 0 0 170px !important;
                    max-width: 170px !important;
                    min-width: 170px !important;
                }}
            }}
            .tooltip-container {{
                position: relative;
                display: block;
            }}
            .tooltip-container .tooltip-text {{
                visibility: hidden;
                width: 250px;
                background-color: #1a1a1a;
                color: #e0e0e0;
                text-align: left;
                border-radius: 8px;
                padding: 12px;
                position: absolute;
                z-index: 100;
                bottom: 105%;
                left: 50%;
                transform: translateX(-50%);
                opacity: 0;
                transition: opacity 0.3s;
                font-size: 13px;
                line-height: 1.4;
                border: 1px solid #00E5FF;
                box-shadow: 0px 6px 15px rgba(0,0,0,0.7);
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
                                
                                kazanan = kazanan_kim(mac) if durum in ["Bitti", "Walkover", "Retired"] else None
                                if kazanan == 1:
                                    p1_style = "color: #ffffff; font-weight: bold;"
                                    p2_style = "color: #666666;"
                                    p1_isim = f"✓ {mac['Oyuncu 1']}"
                                    p2_isim = mac['Oyuncu 2']
                                elif kazanan == 2:
                                    p1_style = "color: #666666;"
                                    p2_style = "color: #ffffff; font-weight: bold;"
                                    p1_isim = mac['Oyuncu 1']
                                    p2_isim = f"✓ {mac['Oyuncu 2']}"
                                else:
                                    p1_style = "color: #e0e0e0;"
                                    p2_style = "color: #e0e0e0;"
                                    p1_isim = mac['Oyuncu 1']
                                    p2_isim = mac['Oyuncu 2']

                                if durum == "Oynaniyor":
                                    durum_str = "DEVAM"
                                    durum_style = "color: #00FF66; font-weight: bold;"
                                    skor_style = "color: #00FF66; font-weight: bold; font-size: 16px;"
                                elif durum in ["Bitti", "Walkover"]:
                                    durum_str = durum.upper()
                                    durum_style = "color: #FF1744; font-weight: bold;"
                                    skor_style = "color: #FF1744; font-weight: bold; font-size: 13px;"
                                elif durum == "Retired":
                                    durum_str = "RET"
                                    durum_style = "color: #FFEA00; font-weight: bold;"
                                    skor_style = "color: #FFEA00; font-weight: bold; font-size: 13px;"
                                else:
                                    durum_str = "Bekliyor"
                                    durum_style = "color: #888888;"
                                    skor_style = "color: #888888; font-size: 11px;"

                                tooltip_html = tooltip_html_olustur(mac)

                                card_html = f"""
                                <div class="tooltip-container">
                                    <div style="border: 1px solid #444; border-radius: 4px; padding: 6px; margin-bottom: 4px; background-color: #1a1a1a; color: #e0e0e0; font-size: 11px; line-height: 1.1; cursor: pointer;">
                                        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                                            <span style="font-weight: bold; color: #fff;">{mac['Saat']}</span>
                                            <span style="{durum_style}">{durum_str}</span>
                                        </div>
                                        <div style="color: #999; font-size: 9px; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{mac['Kategori']}</div>
                                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; {p1_style}">{p1_isim}</div>
                                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; {p2_style}">{p2_isim}</div>
                                        <div style="margin-top: 4px; border-top: 1px dashed #333; padding-top: 3px; text-align: center;">
                                            <span style="{skor_style}">Skor: {skor}</span>
                                        </div>
                                    </div>
                                    <span class="tooltip-text">
                                        {tooltip_html}
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

    elif st.session_state.bashakem_sayfa == "Yonetim":
        st.subheader("Turnuva Yonetim ve İstatistik Paneli")
        
        program_data = githubdan_veri_getir("mac_programi.json")
        if program_data:
            df_stat = pd.DataFrame(program_data)
            toplam_mac = len(df_stat)
            biten_mac = len(df_stat[df_stat["Durum"].isin(["Bitti", "Walkover", "Retired"])])
            devam_eden = len(df_stat[df_stat["Durum"] == "Oynaniyor"])
            baslamayan = len(df_stat[df_stat["Durum"] == "Baslamadi"])
            oran = int((biten_mac / toplam_mac * 100)) if toplam_mac > 0 else 0
            
            sureler = []
            istatistikler = githubdan_veri_getir("turnuva_istatistikleri.json")
            if isinstance(istatistikler, dict) and "sureler" in istatistikler:
                sureler.extend(istatistikler["sureler"])
            
            for _, row in df_stat.iterrows():
                if row.get("Durum") == "Bitti":
                    b_saat = row.get("Baslangic_Saati", "")
                    bit_saat = row.get("Bitis_Saati", "")
                    if b_saat and bit_saat and b_saat != "Secilmedi" and bit_saat != "Secilmedi":
                        try:
                            t1 = datetime.strptime(b_saat.strip(), "%H:%M")
                            t2 = datetime.strptime(bit_saat.strip(), "%H:%M")
                            diff = (t2 - t1).total_seconds() / 60
                            if 0 < diff < 600:
                                sureler.append(int(diff))
                        except:
                            pass

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
            
            st.markdown("### 🎾 Kategori ve Maç Formatı Eşleştirme")
            kategoriler = [k for k in df_stat["Kategori"].unique() if str(k).strip() and k != "Kategori Yok"]
            
            if kategoriler:
                hafiza = githubdan_veri_getir("kategori_format_hafizasi.json")
                if not isinstance(hafiza, dict):
                    hafiza = {}
                    
                FORMAT_SECENEKLERI = [
                    "3 Kısa Set",
                    "3 Normal Set",
                    "2 Normal Set, 3. Set 10 Puanlık Maç Tie-Break",
                    "2 Kısa Set, 3. Set 10 Puanlık Maç Tie-Break",
                    "2 Kısa Set, 3. Set 7 Puanlık Maç Tie-Break"
                ]
                
                yeni_hafiza = {}
                col_k1, col_k2 = st.columns(2)
                with col_k1: st.markdown("**Kategori / Yaş Grubu**")
                with col_k2: st.markdown("**Uygulanacak Format**")
                
                for kat in kategoriler:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"<div style='margin-top: 8px;'>• {kat}</div>", unsafe_allow_html=True)
                    with c2:
                        mevcut_f = hafiza.get(kat, FORMAT_SECENEKLERI[0])
                        idx = FORMAT_SECENEKLERI.index(mevcut_f) if mevcut_f in FORMAT_SECENEKLERI else 0
                        secilen = st.selectbox("Format", FORMAT_SECENEKLERI, index=idx, key=f"fmt_{kat}", label_visibility="collapsed")
                        yeni_hafiza[kat] = secilen
                        
                if st.button("Formatları Kaydet ve Tüm Maçlara Uygula", type="primary"):
                    with st.spinner("Buluta Kaydediliyor..."):
                        for i, row in df_stat.iterrows():
                            if row["Kategori"] in yeni_hafiza:
                                df_stat.at[i, "Skor_Formati"] = yeni_hafiza[row["Kategori"]]
                                
                        b1, m1 = github_a_kaydet(df_stat.to_dict(orient="records"), "mac_programi.json")
                        b2, m2 = github_a_kaydet(yeni_hafiza, "kategori_format_hafizasi.json")
                        
                        if b1 and b2:
                            st.success("✅ Formatlar başarıyla uygulandı!")
                            time.sleep(0.7)
                            st.rerun()
                        else:
                            st.error(f"Hata oluştu. M1: {m1}, M2: {m2}")
            else:
                st.info("Sistemde eşleştirilecek kategori bulunamadı.")
            
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
            with st.spinner("İşlem Yapılıyor..."):
                if yeni_kullanici.strip() and yeni_sifre.strip():
                    kayitli_hakemler[yeni_kullanici.strip()] = yeni_sifre.strip()
                    basarili, mesaj = github_a_kaydet(kayitli_hakemler, "hakemler.json")
                    if basarili:
                        st.success(f"✅ '{yeni_kullanici}' kaydedildi.")
                        time.sleep(0.7)
                        st.rerun()
                    else:
                        st.error(f"Kayit hatasi: {mesaj}")
                else:
                    st.warning("Kullanici adi ve sifre bos olamaz.")
                
        if kayitli_hakemler:
            st.write("Sistemde Kayitli Hakemler ve Şifreleri:")
            for hakem_adi, hakem_sifre in list(kayitli_hakemler.items()):
                col_n, col_s = st.columns([5, 1])
                with col_n:
                    st.text(f"• {hakem_adi} (Şifre: {hakem_sifre})")
                with col_s:
                    if st.button("Sil", key=f"sil_h_{hakem_adi}"):
                        with st.spinner("Siliniyor..."):
                            del kayitli_hakemler[hakem_adi]
                            basarili, mesaj = github_a_kaydet(kayitli_hakemler, "hakemler.json")
                            if basarili:
                                st.success(f"✅ '{hakem_adi}' silindi.")
                                time.sleep(0.7)
                                st.rerun()
                            else:
                                st.error(mesaj)

        st.divider()

        st.markdown("### Yeni Program (PDF) Yükleme")
        yuklenen_pdf = st.file_uploader("PDF Sec", type="pdf")
        if yuklenen_pdf:
            with st.spinner("PDF Analiz Ediliyor..."):
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
                        with st.spinner("Buluta Kaydediliyor..."):
                            basarili, mesaj = github_a_kaydet(tum_temiz_veriler.to_dict(orient="records"), "mac_programi.json")
                            if basarili:
                                st.success("✅ Yeni program başarıyla kaydedildi!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(mesaj)
