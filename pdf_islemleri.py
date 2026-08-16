import streamlit as st
import pandas as pd
import pdfplumber
import requests
import base64
import json
import re

st.set_page_config(page_title="PDF Program Yükleme", layout="wide")
st.title("📂 PDF Maç Programı Yükleme")

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

def hucreyi_ayristir(hucre_metni, kort_adi):
    if not hucre_metni or not str(hucre_metni).strip():
        return None
        
    satirlar = [s.strip() for s in str(hucre_metni).split('\n') if s.strip()]
    if not satirlar:
        return None
        
    # Saat tespiti
    saat_match = re.search(r'\b\d{1,2}:\d{2}\b', satirlar[0])
    saat = saat_match.group() if saat_match else satirlar[0].split()[0]
    
    # Kulüp isimlerini (parantezli satırları) temizle
    detaylar = [s for s in satirlar[1:] if not (s.startswith('(') and s.endswith(')'))]
    if not detaylar:
        return None
        
    kategori_keywords = ["YAŞ", "YAS", "KADIN", "ERKEK", "BÜYÜK", "BUYUK", "TEK", "ÇİFT"]
    kat_idx = -1
    kategori = "Genel"
    
    for idx, item in enumerate(detaylar):
        if any(kw in item.upper() for kw in kategori_keywords):
            kat_idx = idx
            kategori = item
            break
            
    if kat_idx != -1:
        oyuncu1 = " ".join(detaylar[:kat_idx])
        oyuncu2 = " ".join(detaylar[kat_idx+1:])
    else:
        if len(detaylar) >= 3:
            oyuncu1, kategori, oyuncu2 = detaylar[0], detaylar[1], detaylar[2]
        elif len(detaylar) == 2:
            oyuncu1, oyuncu2 = detaylar[0], detaylar[1]
        else:
            oyuncu1, oyuncu2 = detaylar[0], "Bilinmiyor"
            
    if oyuncu1.strip() or oyuncu2.strip():
        return {
            "Kort": kort_adi,
            "Saat": saat,
            "Oyuncu 1": oyuncu1.strip(),
            "Oyuncu 2": oyuncu2.strip(),
            "Kategori": kategori.strip()
        }
    return None

def pdf_programi_oku_tablo(pdf_file):
    tum_maclar = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for sayfa in pdf.pages:
                tablolar = sayfa.extract_tables()
                if not tablolar:
                    tek_tablo = sayfa.extract_table()
                    if tek_tablo:
                        tablolar = [tek_tablo]
                
                if not tablolar:
                    continue

                for tablo in tablolar:
                    if not tablo or len(tablo) < 2:
                        continue
                    
                    court_keywords = ["KORT", "KAPALI", "AÇIK", "TOPRAK", "SERT", "MERKEZ", "COURT"]
                    header_idx = -1
                    
                    # Başlık satırını tespit et
                    for r_idx, row in enumerate(tablo):
                        row_str = " ".join([str(c) for c in row if c]).upper()
                        if any(kw in row_str for kw in court_keywords):
                            header_idx = r_idx
                            break
                    
                    if header_idx == -1:
                        header_idx = 0

                    headers = [str(c).replace('\n', ' ').strip() if c else f"Kort {i+1}" for i, c in enumerate(tablo[header_idx])]
                    
                    # Hücrelerdeki maçları tara
                    for row in tablo[header_idx+1:]:
                        for col_idx, cell in enumerate(row):
                            if col_idx < len(headers) and cell:
                                kort_adi = headers[col_idx]
                                mac = hucreyi_ayristir(cell, kort_adi)
                                if mac:
                                    tum_maclar.append(mac)

        if not tum_maclar:
            return None, "PDF tablosunda maç hücresi bulunamadı."
        return pd.DataFrame(tum_maclar), "Başarılı"
    except Exception as e:
        return None, f"PDF Okuma Hatası: {e}"

# --- STREAMLIT ARAYÜZÜ ---
FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

yuklenen_pdf = st.file_uploader("TTF Maç Programı PDF Dosyasını Yükleyin", type=["pdf"])

if yuklenen_pdf is not None:
    with st.spinner("Tablo yapısı taranıyor..."):
        df, mesaj = pdf_programi_oku_tablo(yuklenen_pdf)
    
    if df is not None:
        st.success(f"Program başarıyla okundu! Toplam {len(df)} maç listelendi.")
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.subheader("⚙️ Kategori ve Format Eşleştirme")
        
        benzersiz_kategoriler = df["Kategori"].unique()
        hafiza = githubdan_veri_getir("kategori_format_hafizasi.json") or {}
        yeni_hafiza = {}
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Turnuva Kategorisi**")
        with col2:
            st.markdown("**Skor Formatı**")
            
        for i, kat in enumerate(benzersiz_kategoriler):
            if not kat or kat == "Genel": continue
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"🎾 **{kat}**")
            with c2:
                eski_secim = hafiza.get(kat, FORMAT_SECENEKLERI[0])
                idx = FORMAT_SECENEKLERI.index(eski_secim) if eski_secim in FORMAT_SECENEKLERI else 0
                secilen_format = st.selectbox(f"Format - {kat}", FORMAT_SECENEKLERI, index=idx, key=f"fmt_{i}", label_visibility="collapsed")
                yeni_hafiza[kat] = secilen_format
        
        st.divider()
        
        if st.button("✅ Programı Onayla ve Kort Hakemlerine Gönder", type="primary", use_container_width=True):
            df["Skor_Formati"] = df["Kategori"].map(yeni_hafiza).fillna(FORMAT_SECENEKLERI[0])
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
                st.success("🎉 Maç programı sisteme yüklendi!")
                st.balloons()
            else:
                if not basarili_mac: st.error(f"Hata: {msg_mac}")
                if not basarili_hafiza: st.error(f"Hata: {msg_hafiza}")
    else:
        st.error(mesaj)
