import streamlit as st
import pandas as pd
import pdfplumber
import requests
import base64
import json

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="PDF Program Yükleme", layout="wide")
st.title("📂 PDF Maç Programı Yükleme ve Format Ayarları")

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

def pdf_programi_oku(pdf_file):
    """TTF Maç programı PDF'ini metin hizalama (text strategy) ile hatasız okur."""
    tum_maclar = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for sayfa in pdf.pages:
                
                # ÇÖZÜM NOKTASI: PDF çizgilerini yoksay, sadece yazılan metinlerin aralığına bak!
                ayarlar = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text"
                }
                
                tablolar = sayfa.extract_tables(ayarlar)
                
                for tablo in tablolar:
                    if not tablo: continue
                    
                    # 1. Aşama: Kort İsimlerinin Olduğu Başlık Satırını Bul
                    header_idx = -1
                    for i, satir in enumerate(tablo):
                        satir_metni = " ".join([str(h).lower() for h in satir if h])
                        if "kort" in satir_metni or "toprak" in satir_metni or "sert" in satir_metni:
                            header_idx = i
                            break
                            
                    if header_idx == -1: continue
                    
                    headers = tablo[header_idx]
                    # İlk sütun saattir, boşsa doldur
                    if not headers[0] or str(headers[0]).strip() == "":
                        headers[0] = "Saat"
                        
                    headers = [str(h).replace('\n', ' ').strip() if h else f"Sutun_{i}" for i, h in enumerate(headers)]
                    
                    # 2. Aşama: Maç Satırlarını Oku
                    for satir_idx in range(header_idx + 1, len(tablo)):
                        satir = tablo[satir_idx]
                        if not satir: continue
                        
                        saat_hucre = str(satir[0]).strip() if satir[0] else ""
                        saat = saat_hucre.split()[0] if saat_hucre else ""
                        
                        # Saat formatı değilse satırı atla
                        if not saat or ":" not in saat:
                            continue
                            
                        # 3. Aşama: Sütunlardaki (Kortlardaki) Maçları Ayrıştır
                        for col_idx in range(1, min(len(headers), len(satir))):
                            kort_adi = headers[col_idx]
                            hucre = str(satir[col_idx]).strip() if satir[col_idx] else ""
                            
                            if not hucre or hucre.lower() in ["none", "nan", ""]: 
                                continue
                            
                            # Hücre içini böl (Oyuncu 1 \n Kategori \n Oyuncu 2)
                            satir_parcalari = [s.strip() for s in hucre.split('\n') if s.strip()]
                            
                            oyuncu1, oyuncu2, kategori = "Bilinmiyor", "Bilinmiyor", "Genel"
                            
                            kat_index = -1
                            for idx, p in enumerate(satir_parcalari):
                                p_upper = p.upper()
                                if "YAŞ" in p_upper or "BÜYÜK" in p_upper or " KADIN" in p_upper or " ERKEK" in p_upper:
                                    kat_index = idx
                                    kategori = p
                                    break
                            
                            if kat_index != -1:
                                # Kategori bulundu: Üstündekiler O1, Altındakiler O2
                                p1_kismi = satir_parcalari[:kat_index]
                                p2_kismi = satir_parcalari[kat_index+1:]
                                
                                # Kulüp adlarını at
                                oyuncu1 = " ".join([p for p in p1_kismi if not p.startswith("(")]) if p1_kismi else "Bilinmiyor 1"
                                oyuncu2 = " ".join([p for p in p2_kismi if not p.startswith("(")]) if p2_kismi else "Bilinmiyor 2"
                            else:
                                if len(satir_parcalari) >= 3:
                                    oyuncu1, kategori, oyuncu2 = satir_parcalari[0], satir_parcalari[1], satir_parcalari[2]
                                elif len(satir_parcalari) == 2:
                                    oyuncu1, kategori = satir_parcalari[0], satir_parcalari[1]
                                elif len(satir_parcalari) == 1:
                                    oyuncu1 = satir_parcalari[0]
                            
                            tum_maclar.append({
                                "Kort": kort_adi,
                                "Saat": saat,
                                "Oyuncu 1": oyuncu1.strip(),
                                "Oyuncu 2": oyuncu2.strip(),
                                "Kategori": kategori.strip()
                            })
                            
        if not tum_maclar:
            return None, "Hata: PDF tabloları okunamadı. Program formatında olmayabilir."
            
        df = pd.DataFrame(tum_maclar)
        return df, "Başarılı"
        
    except Exception as e:
        return None, f"PDF Okuma Hatası: {e}"

# --- SİSTEM DEĞİŞKENLERİ ---
FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

# --- PDF YÜKLEME ALANI ---
yuklenen_pdf = st.file_uploader("TTF Maç Programı PDF Dosyasını Yükleyin", type=["pdf"])

if yuklenen_pdf is not None:
    with st.spinner("PDF Bütün Sütunlara Ayrılarak Analiz Ediliyor..."):
        df, mesaj = pdf_programi_oku(yuklenen_pdf)
    
    if df is not None:
        st.success(f"PDF başarıyla okundu! Toplam {len(df)} maç tespit edildi.")
        
        # Kullanıcıya tespit edilen kortları güven amaçlı listele
        bulunan_kortlar = df['Kort'].unique().tolist()
        st.info(f"📍 **Tespit Edilen Kortlar ({len(bulunan_kortlar)}):** {', '.join(bulunan_kortlar)}")
        
        with st.expander("PDF'ten Çekilen ve Yapılandırılan Maç Listesini Gör"):
            st.dataframe(df)
        
        st.divider()
        st.subheader("⚙️ Kategori ve Format Eşleştirme")
        st.info("Kategorileri sistemdeki skor formatlarıyla eşleştirin. Sistem yaptığınız seçimleri hafızaya alacak ve yarınki PDF'te otomatik getirecektir.")
        
        kategori_sutunu = "Kategori"
        benzersiz_kategoriler = df[kategori_sutunu].unique()
        
        # Geçmiş hafızayı GitHub'dan çek
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
        st.warning("⚠️ DİKKAT: 'Programı Onayla ve Kaydet' butonuna bastığınızda, sahadaki mevcut maç programı SIFIRLANACAK ve yerine bu PDF'teki maçlar yüklenecektir. Hakemler ve turnuva istatistikleri korunacaktır.")
        
        if st.button("✅ Programı Onayla ve Kort Hakemlerine Gönder", type="primary", use_container_width=True):
            df["Skor_Formati"] = df[kategori_sutunu].map(yeni_hafiza)
            
            # Boş veya hatalı kategori eşleşmelerini varsayılanla doldur
            df["Skor_Formati"] = df["Skor_Formati"].fillna(FORMAT_SECENEKLERI[0])
            
            # Kort Hakeminin ihtiyaç duyduğu boş sütunları tanımla
            df["Durum"] = "Baslamadi"
            df["Skor"] = "-"
            df["Kura_Kazanan"] = "Secilmedi"
            df["Kura_Tercih"] = "Secilmedi"
            df["Saha_Tarafi"] = "Secilmedi"
            df["Baslangic_Saati"] = ""
            df["Bitis_Saati"] = ""
            df["Son_Hakem"] = ""
            df["Kazanan"] = "Secilmedi"
            
            # 1. Maç Programını GitHub'a Kaydet
            basarili_mac, msg_mac = github_a_kaydet(df.to_dict(orient="records"), "mac_programi.json")
            
            # 2. Format Hafızasını Kaydet
            basarili_hafiza, msg_hafiza = github_a_kaydet(yeni_hafiza, "kategori_format_hafizasi.json")
            
            if basarili_mac and basarili_hafiza:
                st.success("🎉 Mükemmel! Maç programı, hakemlerin format kurallarıyla birlikte sisteme başarıyla yüklendi!")
                st.balloons()
            else:
                if not basarili_mac: st.error(f"Maç programı kaydedilirken hata: {msg_mac}")
                if not basarili_hafiza: st.error(f"Hafıza kaydedilirken hata: {msg_hafiza}")
                
    else:
        st.error(mesaj)
