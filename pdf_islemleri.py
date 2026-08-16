import streamlit as st
import pandas as pd
import pdfplumber
import requests
import base64
import json
import re

st.set_page_config(page_title="PDF Program Yükleme", layout="wide")
st.title("📂 PDF Maç Programı Yükleme ve Format Ayarları")

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

def pdf_programi_oku_koordinat(pdf_file):
    tum_maclar = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for sayfa_no, sayfa in enumerate(pdf.pages):
                words = sayfa.extract_words()
                if not words: continue

                rows = []
                words.sort(key=lambda w: w['top'])
                current_row = []
                current_top = words[0]['top']

                for w in words:
                    if abs(w['top'] - current_top) < 4:
                        current_row.append(w)
                    else:
                        rows.append(current_row)
                        current_row = [w]
                        current_top = w['top']
                if current_row:
                    rows.append(current_row)

                court_keywords = ["TOPRAK", "SERT", "KORT", "MERKEZ", "KAPALI", "COURT", "AÇIK", "ACIK"]
                header_row_idx = -1
                
                for i, row in enumerate(rows):
                    text_in_row = " ".join([w['text'].upper() for w in row])
                    if any(kw in text_in_row for kw in court_keywords):
                        if any(char.isdigit() for char in text_in_row):
                            header_row_idx = i
                            break

                if header_row_idx == -1: continue

                header_row = rows[header_row_idx]
                header_row.sort(key=lambda w: w['x0'])

                columns = []
                current_col_text = header_row[0]['text']
                current_col_x0 = header_row[0]['x0']
                current_col_x1 = header_row[0]['x1']

                for w in header_row[1:]:
                    if w['x0'] - current_col_x1 < 15:
                        current_col_text += " " + w['text']
                        current_col_x1 = w['x1']
                    else:
                        columns.append({"name": current_col_text, "x0": current_col_x0, "x1": current_col_x1})
                        current_col_text = w['text']
                        current_col_x0 = w['x0']
                        current_col_x1 = w['x1']
                columns.append({"name": current_col_text, "x0": current_col_x0, "x1": current_col_x1})

                for i in range(len(columns)):
                    if i < len(columns) - 1:
                        columns[i]['limit_x'] = (columns[i]['x1'] + columns[i+1]['x0']) / 2
                    else:
                        columns[i]['limit_x'] = 9999

                data_words = []
                for row in rows[header_row_idx+1:]:
                    data_words.extend(row)

                col_data = {col['name']: [] for col in columns}

                for w in data_words:
                    center_x = (w['x0'] + w['x1']) / 2
                    assigned = False
                    for col in columns:
                        if center_x < col['limit_x']:
                            col_data[col['name']].append(w)
                            assigned = True
                            break
                    if not assigned and columns:
                        col_data[columns[-1]['name']].append(w)

                for col in columns:
                    c_name = col['name']
                    c_words = col_data[c_name]
                    if not c_words: continue

                    c_words.sort(key=lambda w: w['top'])
                    c_lines = []
                    curr_line = []
                    curr_top = c_words[0]['top']

                    for w in c_words:
                        if abs(w['top'] - curr_top) < 4:
                            curr_line.append(w)
                        else:
                            curr_line.sort(key=lambda x: x['x0'])
                            c_lines.append(" ".join([x['text'] for x in curr_line]))
                            curr_line = [w]
                            curr_top = w['top']
                    if curr_line:
                        curr_line.sort(key=lambda x: x['x0'])
                        c_lines.append(" ".join([x['text'] for x in curr_line]))

                    match_blocks = []
                    current_match = []

                    for line in c_lines:
                        if re.search(r'\d{2}:\d{2}', line) or "TAKİP" in line.upper():
                            if current_match:
                                match_blocks.append(current_match)
                            current_match = [line]
                        else:
                            if current_match:
                                current_match.append(line)

                    if current_match:
                        match_blocks.append(current_match)

                    for block in match_blocks:
                        if not block: continue

                        saat_line = block[0]
                        saat_match = re.search(r'\d{2}:\d{2}', saat_line)
                        saat = saat_match.group() if saat_match else saat_line.split()[0] if saat_line else ""

                        details = block[1:]
                        details = [d for d in details if not d.strip().startswith('(') and d.strip()]

                        if not details: continue

                        oyuncu1, oyuncu2, kategori = "Bilinmiyor", "Bilinmiyor", "Genel"

                        kat_index = -1
                        for idx, p in enumerate(details):
                            p_upper = p.upper()
                            if "YAŞ" in p_upper or "BÜYÜK" in p_upper or "KADIN" in p_upper or "ERKEK" in p_upper:
                                kat_index = idx
                                kategori = p
                                break

                        if kat_index != -1:
                            p1_kismi = details[:kat_index]
                            p2_kismi = details[kat_index+1:]
                            oyuncu1 = " ".join(p1_kismi) if p1_kismi else "Bilinmiyor 1"
                            oyuncu2 = " ".join(p2_kismi) if p2_kismi else "Bilinmiyor 2"
                        else:
                            if len(details) >= 3:
                                oyuncu1, kategori, oyuncu2 = details[0], details[1], details[2]
                            elif len(details) == 2:
                                oyuncu1, kategori = details[0], details[1]
                            elif len(details) == 1:
                                oyuncu1 = details[0]

                        if not oyuncu1.strip() and not oyuncu2.strip(): continue

                        tum_maclar.append({
                            "Kort": c_name,
                            "Saat": saat,
                            "Oyuncu 1": oyuncu1.strip(),
                            "Oyuncu 2": oyuncu2.strip(),
                            "Kategori": kategori.strip()
                        })

        if not tum_maclar:
            return None, "Hata: PDF'te maç okunamadı."
        df = pd.DataFrame(tum_maclar)
        return df, "Başarılı"
    except Exception as e:
        return None, f"PDF Okuma Hatası: {e}"

FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

yuklenen_pdf = st.file_uploader("TTF Maç Programı PDF Dosyasını Yükleyin", type=["pdf"])

if yuklenen_pdf is not None:
    with st.spinner("🚀 Koordinat Bazlı TTF Yapay Zeka Motoru Çalışıyor..."):
        df, mesaj = pdf_programi_oku_koordinat(yuklenen_pdf)
    
    if df is not None:
        st.success(f"PDF başarıyla okundu! Toplam {len(df)} maç tespit edildi.")
        bulunan_kortlar = df['Kort'].unique().tolist()
        st.info(f"📍 **Tespit Edilen Kortlar ({len(bulunan_kortlar)}):** {', '.join(bulunan_kortlar)}")
        
        with st.expander("PDF'ten Çekilen ve Yapılandırılan Maç Listesini Gör"):
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
                st.success("🎉 Maç programı başarıyla yüklendi!")
                st.balloons()
            else:
                if not basarili_mac: st.error(f"Hata: {msg_mac}")
                if not basarili_hafiza: st.error(f"Hata: {msg_hafiza}")
    else:
        st.error(mesaj)
