import streamlit as st
import pandas as pd
import requests
import base64
import json

st.set_page_config(page_title="Başhakem İzleme Masası", layout="wide")

# --- KOMPAKT EKRAN VE KAYDIRMA DÜZENİ ---
st.markdown("""
<style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    h1, h2, h3, h4 {
        margin: 0rem 0rem 0.3rem 0rem !important;
        padding: 0rem !important;
    }
    .izgara-alani {
        max-height: 82vh;
        overflow-y: auto !important;
        overflow-x: auto !important;
        padding-right: 8px;
    }
    .mac-kart {
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 8px;
        border-left: 5px solid #888;
        background-color: #f8f9fa;
        color: #111;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .durum-baslamadi { border-left-color: #6c757d; background-color: #fdfdfe; }
    .durum-oynaniyor { border-left-color: #ffc107; background-color: #fff9db; }
    .durum-tamamlandi { border-left-color: #28a745; background-color: #e6fcf5; }
    .kart-saat { font-weight: bold; font-size: 13px; color: #495057; }
    .kart-kat { font-size: 12px; color: #0c8599; font-weight: 600; }
    .kart-oyuncu { font-weight: bold; font-size: 14px; margin: 2px 0; }
    .kart-skor { font-size: 13px; font-weight: bold; color: #d6336c; }
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

# --- SOL MENÜ KONTROLLERİ ---
with st.sidebar:
    st.title("🎛️ Başhakem Masası")
    if st.button("🔄 Ekranı Yenile", type="primary", use_container_width=True):
        st.rerun()
    
    st.divider()
    durum_filtre = st.selectbox("Durum Filtresi", ["Tümü", "Oynanıyor", "Baslamadi", "Tamamlandi"])
    kart_boyut = st.slider("Görünüm Ölçeği (%)", min_value=70, max_value=115, value=90, step=5)

# --- VERİ ÇEKME ---
maclar = githubdan_veri_getir("mac_programi.json")

if not maclar:
    st.warning("Henüz sistemde aktif bir maç programı bulunamadı. Lütfen 'mac_programi.json' dosyasını güncelleyin.")
else:
    df = pd.DataFrame(maclar)
    
    # Başlık ve Hızlı Özet
    toplam_mac = len(df)
    oynanan_mac = len(df[df["Durum"] == "Oynaniyor"])
    biten_mac = len(df[df["Durum"] == "Tamamlandi"])
    
    col_t1, col_t2, col_t3 = st.columns([3, 1, 1])
    with col_t1:
        st.subheader("🎾 Kort ve Maç Canlı Takip Paneli")
    with col_t2:
        st.info(f"🟡 Oynanan: {oynanan_mac} / {toplam_mac}")
    with col_t3:
        st.success(f"🟢 Biten: {biten_mac} / {toplam_mac}")

    st.divider()

    # Kort Sütunları
    kortlar = df["Kort"].unique().tolist()
    
    st.markdown('<div class="izgara-alani">', unsafe_allow_html=True)
    kort_kolonlari = st.columns(len(kortlar))
    
    for idx, kort in enumerate(kortlar):
        with kort_kolonlari[idx]:
            st.markdown(f"<div style='text-align:center; background:#212529; color:white; border-radius:5px; padding:4px; font-weight:bold; margin-bottom:8px;'>{kort}</div>", unsafe_allow_html=True)
            
            kort_maclari = df[df["Kort"] == kort]
            if durum_filtre != "Tümü":
                kort_maclari = kort_maclari[kort_maclari["Durum"] == durum_filtre]
                
            for _, m in kort_maclari.iterrows():
                durum_sinif = "durum-baslamadi"
                if m.get("Durum") == "Oynaniyor":
                    durum_sinif = "durum-oynaniyor"
                elif m.get("Durum") == "Tamamlandi":
                    durum_sinif = "durum-tamamlandi"
                
                hakem_bilgi = f"<span style='color:#555;'>Hakem: {m.get('Son_Hakem', '-')}</span>" if m.get("Son_Hakem") else ""
                
                st.markdown(f"""
                <div class="mac-kart {durum_sinif}" style="font-size: {int(kart_boyut * 0.14)}px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span class="kart-saat">⏰ {m.get('Saat')}</span>
                        <span class="kart-kat">{m.get('Kategori')}</span>
                    </div>
                    <div class="kart-oyuncu">1. {m.get('Oyuncu 1')}</div>
                    <div class="kart-oyuncu">2. {m.get('Oyuncu 2')}</div>
                    <div style="display:flex; justify-content:space-between; margin-top:4px;">
                        <span class="kart-skor">Skor: {m.get('Skor', '-')}</span>
                        {hakem_bilgi}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
    st.markdown('</div>', unsafe_allow_html=True)
