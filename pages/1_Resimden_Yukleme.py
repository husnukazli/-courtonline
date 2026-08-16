import streamlit as st
import pandas as pd
import requests
import base64
import json
import google.generativeai as genai
from PIL import Image

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Fotoğraftan Program Yükleme", layout="wide")
st.title("📸 Fotoğraftan Maç Programı Yükleme (Gemini AI Destekli)")

# --- YARDIMCI FONKSİYONLAR ---
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
    return None

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
        
        payload = {"message": f"{dosya_yolu} Güncellemesi", "content": icerik_b64}
        if sha:
            payload["sha"] = sha
            
        cevap_put = requests.put(url, headers=headers, json=payload)
        if cevap_put.status_code in [200, 201]:
            return True, "Başarılı"
        else:
            return False, cevap_put.text
    except Exception as e:
        return False, str(e)

def resmi_ai_ile_oku(resim_dosyasi):
    """Görüntüyü Google Gemini API'sine gönderir ve desteklenen modeli otomatik bulup okuma yapar."""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # ÇÖZÜM: Hesabının desteklediği aktif modeli otomatik tespit et (404 hatasını bitirir)
        uygun_model = None
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name.lower() or 'pro' in m.name.lower():
                    uygun_model = m.name
                    break
        
        if not uygun_model:
            return None, "Hata: Hesabınızda içerik üretebilecek uygun bir Gemini modeli bulunamadı."
            
        model = genai.GenerativeModel(uygun_model)
        img = Image.open(resim_dosyasi)
        
        prompt = """
        Bu görsel bir tenis turnuvası maç programıdır. Lütfen bu tabloyu çok dikkatli incele ve maçları tespit et.
        Her hücredeki veriyi şu kurallara göre ayır:
        1. Sütun başlıkları Kort isimleridir (Örn: Kort 1, Kort 2).
        2. Hücre içindeki saati bul (Örn: 09:00, En Erken 10:30, Müteakiben).
        3. Hücre içindeki Oyuncu 1, Oyuncu 2 ve Kategoriyi (Örn: Erkek 10 Yaş T, Kadın 9 Yaş Ç) bul.
        4. Parantez içindeki kulüp isimlerini (FERDİ, ATK vb.) YOK SAY, listeye ekleme.
        
        Çıktıyı SADECE geçerli bir JSON array formatında ver. Başka hiçbir açıklama yazma.
        Format şu şekilde olmalıdır:
        [
            {"Kort": "Kort 1", "Saat": "09:00", "Oyuncu 1": "SÜLEYMAN YİĞİT ÜYE", "Oyuncu 2": "KIVANÇ İSLEK", "Kategori": "Erkek 10 Yaş T"},
            ...
        ]
        """
        
        response = model.generate_content([prompt, img])
        json_metni = response.text.strip()
        
        if json_metni.startswith("```json"):
            json_metni = json_metni[7:-3]
        elif json_metni.startswith("```"):
            json_metni = json_metni[3:-3]
            
        veri = json.loads(json_metni.strip())
        return pd.DataFrame(veri), "Başarılı"
        
    except Exception as e:
        return None, f"AI Görüntü İşleme Hatası: {e}"

# --- SİSTEM DEĞİŞKENLERİ ---
FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

# --- YÜKLEME ALANI ---
yuklenen_resim = st.file_uploader("Maç Programının Ekran Görüntüsünü (PNG/JPG) Yükleyin", type=["png", "jpg", "jpeg"])

if yuklenen_resim is not None:
    st.image(yuklenen_resim, caption="Yüklenen Tablo", use_container_width=True)
    
    if st.button("🤖 Yapay Zeka ile Tabloyu Çözümle", type="primary"):
        with st.spinner("Gemini aktif modeli bularak tabloyu inceliyor... Lütfen bekleyin."):
            df, mesaj = resmi_ai_ile_oku(yuklenen_resim)
            
            if df is not None:
                st.session_state.temp_df = df
                st.success(f"Harika! Yapay zeka toplam {len(df)} maç tespit etti.")
            else:
                st.error(mesaj)

if "temp_df" in st.session_state:
    df = st.session_state.temp_df
    
    with st.expander("AI Tarafından Çıkarılan Maç Listesi"):
        st.dataframe(df)
    
    st.divider()
    st.subheader("⚙️ Kategori ve Format Eşleştirme")
    
    kategori_sutunu = "Kategori"
    benzersiz_kategoriler = df[kategori_sutunu].unique()
    
    hafiza = githubdan_veri_getir("kategori_format_hafizasi.json") or {}
    yeni_hafiza = {}
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Tespit Edilen Yaş/Grup Kategorisi**")
    with col2:
        st.markdown("**Uygulanacak Skor Formatı (Kurallar)**")
        
    for i, kat in enumerate(benzersiz_kategoriler):
        if not kat or kat == "Genel": continue
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div style='padding-top: 10px; font-size: 18px;'>🎾 <b>{kat}</b></div>", unsafe_allow_html=True)
        with c2:
            eski_secim = hafiza.get(kat, FORMAT_SECENEKLERI[0])
            idx = FORMAT_SECENEKLERI.index(eski_secim) if eski_secim in FORMAT_SECENEKLERI else 0
            secilen_format = st.selectbox(f"Format - {kat}", FORMAT_SECENEKLERI, index=idx, key=f"fmt_{i}", label_visibility="collapsed")
            yeni_hafiza[kat] = secilen_format
    
    st.divider()
    
    if st.button("✅ Programı Onayla ve Kort Hakemlerine Gönder", type="primary", use_container_width=True):
        df["Skor_Formati"] = df[kategori_sutunu].map(yeni_hafiza)
        df["Skor_Formati"] = df["Skor_Formati"].fillna(FORMAT_SECENEKLERI[0])
        
        df["Durum"] = "Baslamadi"
        df["Skor"] = "-"
        df["Kura_Kazanan"] = "Secilmedi"
        df["Kura_Tercih"] = "Secilmedi"
        df["Saha_Tarafi"] = "Secilmedi"
        df["Baslangic_Saati"] = ""
        df["Bitis_Saati"] = ""
        df["Son_Hakem"] = ""
        df["Kazanan"] = "Secilmedi"
        
        basarili_mac, msg_mac = github_a_kaydet(df.to_dict(orient="records"), "mac_programi.json")
        basarili_hafiza, msg_hafiza = github_a_kaydet(yeni_hafiza, "kategori_format_hafizasi.json")
        
        if basarili_mac and basarili_hafiza:
            st.success("🎉 Maç programı sisteme başarıyla yüklendi!")
            st.balloons()
            del st.session_state.temp_df 
        else:
            if not basarili_mac: st.error(f"Maç programı kaydedilirken hata: {msg_mac}")
            if not basarili_hafiza: st.error(f"Hafıza kaydedilirken hata: {msg_hafiza}")
