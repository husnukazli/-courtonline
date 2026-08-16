import streamlit as st
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Başhakem İzleme Masası", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }
    h1, h2, h3, h4 {
        margin: 0rem 0rem 0.4rem 0rem !important;
        padding: 0rem !important;
    }
    .izgara-kapsayici {
        max-height: 78vh;
        overflow-y: auto !important;
        overflow-x: auto !important;
        padding-right: 10px;
        padding-bottom: 25px;
    }
    .kort-baslik {
        text-align: center;
        background: #1e293b;
        color: #ffffff;
        border-radius: 6px;
        padding: 6px 4px;
        font-weight: 700;
        font-size: 14px;
        margin-bottom: 10px;
        letter-spacing: 0.5px;
    }
    .mac-kart {
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 12px;
        border-left: 6px solid #64748b;
        background-color: #ffffff;
        color: #0f172a;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
    }
    .durum-baslamadi {
        border-left-color: #94a3b8 !important;
        background-color: #f8fafc !important;
    }
    .durum-oynaniyor {
        border-left-color: #eab308 !important;
        background-color: #fefce8 !important;
    }
    .durum-tamamlandi {
        border-left-color: #22c55e !important;
        background-color: #f0fdf4 !important;
    }
    .durum-iptal {
        border-left-color: #ef4444 !important;
        background-color: #fef2f2 !important;
    }
    .kart-ust-bilgi {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
        font-size: 12px;
    }
    .kart-saat {
        font-weight: 700;
        color: #334155;
        background: #e2e8f0;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .kart-kat {
        font-weight: 600;
        color: #0284c7;
    }
    .kart-oyuncu {
        font-weight: 700;
        font-size: 13px;
        margin: 3px 0;
        color: #0f172a;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .kart-alt-bilgi {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 8px;
        padding-top: 6px;
        border-top: 1px dashed #cbd5e1;
        font-size: 12px;
    }
    .kart-skor {
        font-weight: 800;
        color: #be123c;
    }
    .kart-hakem {
        color: #64748b;
        font-size: 11px;
    }
</style>
""", unsafe_allow_html=True)

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
    except Exception:
        pass
    return []

def github_a_kaydet(veri, dosya_yolu):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{dosya_yolu}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        sha = None
        cevap_get = requests.get(url, headers=headers)
        if cevap_get.status_code == 200:
            sha = cevap_get.json().get("sha")
            
        icerik_json = json.dumps(veri, indent=4, ensure_ascii=False)
        icerik_b64 = base64.b64encode(icerik_json.encode('utf-8')).decode('utf-8')
        
        payload = {"message": f"{dosya_yolu} Başhakem Güncellemesi", "content": icerik_b64}
        if sha:
            payload["sha"] = sha
            
        cevap_put = requests.put(url, headers=headers, json=payload)
        return cevap_put.status_code in [200, 201], cevap_put.text
    except Exception as e:
        return False, str(e)

# --- SOL MENÜ AYARLARI ---
with st.sidebar:
    st.title("🎛️ Başhakem Masası")
    if st.button("🔄 Ekranı Yenile", type="primary", use_container_width=True):
        st.rerun()
    
    st.divider()
    durum_filtresi = st.selectbox("Durum Filtresi", ["Tümü", "Oynaniyor", "Baslamadi", "Tamamlandi"])
    gorunum_olcegi = st.slider("Kart Boyut Ölçeği (%)", min_value=75, max_value=120, value=95, step=5)
    
    st.divider()
    st.markdown("### 📊 Hızlı İstatistik")
    tum_mac_verisi = githubdan_veri_getir("mac_programi.json") or []
    if tum_mac_verisi:
        df_ist = pd.DataFrame(tum_mac_verisi)
        toplam_sayi = len(df_ist)
        oynanan_sayi = len(df_ist[df_ist["Durum"] == "Oynaniyor"])
        biten_sayi = len(df_ist[df_ist["Durum"] == "Tamamlandi"])
        kalan_sayi = len(df_ist[df_ist["Durum"] == "Baslamadi"])
        
        st.write(f"🎾 **Toplam Maç:** {toplam_sayi}")
        st.write(f"🟡 **Oynanan:** {oynanan_sayi}")
        st.write(f"🟢 **Tamamlanan:** {biten_sayi}")
        st.write(f"⚪ **Başlamayan:** {kalan_sayi}")

# --- ANA EKRAN İÇERİĞİ ---
if not tum_mac_verisi:
    st.warning("⚠️ Sistemde yüklü maç bulunamadı. Lütfen 'Maç Programı Yükleme' sayfasından programı sisteme aktarın.")
else:
    df = pd.DataFrame(tum_mac_verisi)
    kortlar = list(df["Kort"].unique())
    
    col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
    with col_h1:
        st.markdown("### 🎾 Canlı Kort İzleme Paneli")
    with col_h2:
        st.info(f"🟡 Oynanan: {len(df[df['Durum'] == 'Oynaniyor'])}")
    with col_h3:
        st.success(f"🟢 Biten: {len(df[df['Durum'] == 'Tamamlandi'])}")

    st.markdown('<div class="izgara-kapsayici">', unsafe_allow_html=True)
    kort_sutunlari = st.columns(len(kortlar))

    for k_idx, kort_adi in enumerate(kortlar):
        with kort_sutunlari[k_idx]:
            st.markdown(f'<div class="kort-baslik">{kort_adi}</div>', unsafe_allow_html=True)
            
            kort_maclari = df[df["Kort"] == kort_adi]
            if durum_filtresi != "Tümü":
                kort_maclari = kort_maclari[kort_maclari["Durum"] == durum_filtresi]
                
            for _, mac in kort_maclari.iterrows():
                durum = mac.get("Durum", "Baslamadi")
                durum_class = "durum-baslamadi"
                durum_etiket = "Başlamadı"
                if durum == "Oynaniyor":
                    durum_class = "durum-oynaniyor"
                    durum_etiket = "Oynanıyor"
                elif durum == "Tamamlandi":
                    durum_class = "durum-tamamlandi"
                    durum_etiket = "Tamamlandı"
                elif durum == "Iptal":
                    durum_class = "durum-iptal"
                    durum_etiket = "İptal"

                hakem = mac.get("Son_Hakem", "")
                hakem_yazisi = f"👤 {hakem}" if hakem else "👤 Atanmadı"
                skor_yazisi = mac.get("Skor", "-")

                st.markdown(f"""
                <div class="mac-kart {durum_class}" style="font-size: {int(gorunum_olcegi * 0.135)}px;">
                    <div class="kart-ust-bilgi">
                        <span class="kart-saat">⏰ {mac.get('Saat', '')}</span>
                        <span class="kart-kat">{mac.get('Kategori', '')}</span>
                    </div>
                    <div class="kart-oyuncu">1. {mac.get('Oyuncu 1', '')}</div>
                    <div class="kart-oyuncu">2. {mac.get('Oyuncu 2', '')}</div>
                    <div class="kart-alt-bilgi">
                        <span class="kart-skor">Skor: {skor_yazisi}</span>
                        <span class="kart-hakem">{hakem_yazisi}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    with st.expander("🛠️ Başhakem Hızlı Müdahale ve Maç Düzenleme Alanı"):
        st.markdown("**Seçilen Maçın Durumunu veya Skorunu Doğrudan Güncelle**")
        mac_etiketleri = [f"{m.get('Kort')} | {m.get('Saat')} | {m.get('Oyuncu 1')} vs {m.get('Oyuncu 2')}" for m in tum_mac_verisi]
        secilen_mac_idx = st.selectbox("Düzenlenecek Maçı Seçin", range(len(mac_etiketleri)), format_func=lambda x: mac_etiketleri[x])
        
        if secilen_mac_idx is not None:
            secili = tum_mac_verisi[secilen_mac_idx]
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                yeni_durum = st.selectbox("Durum", ["Baslamadi", "Oynaniyor", "Tamamlandi", "Iptal"], index=["Baslamadi", "Oynaniyor", "Tamamlandi", "Iptal"].index(secili.get("Durum", "Baslamadi")))
            with col_m2:
                yeni_skor = st.text_input("Skor", value=secili.get("Skor", "-"))
            with col_m3:
                yeni_hakem = st.text_input("Hakem", value=secili.get("Son_Hakem", ""))

            if st.button("💾 Değişiklikleri GitHub'a Kaydet", type="primary"):
                tum_mac_verisi[secilen_mac_idx]["Durum"] = yeni_durum
                tum_mac_verisi[secilen_mac_idx]["Skor"] = yeni_skor
                tum_mac_verisi[secilen_mac_idx]["Son_Hakem"] = yeni_hakem
                ok, msg = github_a_kaydet(tum_mac_verisi, "mac_programi.json")
                if ok:
                    st.success("Maç başarıyla güncellendi!")
                    st.rerun()
                else:
                    st.error(f"Kayıt hatası: {msg}")
