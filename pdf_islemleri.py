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

def pdf_programi_oku_guclu(pdf_file):
    tum_maclar = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for sayfa in pdf.pages:
                words = sayfa.extract_words()
                if not words: 
                    continue

                # Kelimeleri dikey hizaya (satırlara) göre grupla
                words.sort(key=lambda w: w['top'])
                rows = []
                current_row = []
                current_top = words[0]['top']

                for w in words:
                    if abs(w['top'] - current_top) < 6:
                        current_row.append(w)
                    else:
                        rows.append(current_row)
                        current_row = [w]
                        current_top = w['top']
                if current_row:
                    rows.append(current_row)

                court_keywords = ["KORT", "KAPALI", "AÇIK", "TOPRAK", "SERT", "MERKEZ", "COURT"]
                header_row_idx = -1
                
                for i, row in enumerate(rows):
                    text_in_row = " ".join([w['text'].upper() for w in row])
                    if any(kw in text_in_row for kw in court_keywords):
                        header_row_idx = i
                        break

                if header_row_idx == -1:
                    continue

                header_row = rows[header_row_idx]
                header_row.sort(key=lambda w: w['x0'])

                # Sütun başlıklarını geniş aralık eşiği (35px) ile grupla
                columns = []
                curr_col_name = header_row[0]['text']
                curr_x0 = header_row[0]['x0']
                curr_x1 = header_row[0]['x1']

                for w in header_row[1:]:
                    if (w['x0'] - curr_x1) < 35:
                        curr_col_name += " " + w['text']
                        curr_x1 = w['x1']
                    else:
                        columns.append({"name": curr_col_name.strip(), "x0": curr_x0, "x1": curr_x1})
                        curr_col_name = w['text']
                        curr_x0 = w['x0']
                        curr_x1 = w['x1']
                columns.append({"name": curr_col_name.strip(), "x0": curr_x0, "x1": curr_x1})

                # Sütun sınırlarını belirle
                for i in range(len(columns)):
                    min_x = 0 if i == 0 else (columns[i-1]['x1'] + columns[i]['x0']) / 2
                    max_x = 9999 if i == len(columns) - 1 else (columns[i]['x1'] + columns[i+1]['x0']) / 2
                    columns[i]['min_x'] = min_x
                    columns[i]['max_x'] = max_x

                header_bottom = max([w['bottom'] for w in header_row])
                data_words = [w for w in words if w['top'] >= header_bottom - 2]

                # Her kort sütununun altındaki maçları parse et
                for col in columns:
                    c_words = [w for w in data_words if col['min_x'] <= ((w['x0'] + w['x1']) / 2) < col['max_x']]
                    if not c_words:
                        continue

                    c_words.sort(key=lambda w: w['top'])
                    c_lines = []
                    curr_line = []
                    curr_top = c_words[0]['top']

                    for w in c_words:
                        if abs(w['top'] - current_top) < 6:
                            curr_line.append(w)
                        else:
                            curr_line.sort(key=lambda x: x['x0'])
                            c_lines.append(" ".join([x['text'] for x in curr_line]))
                            curr_line = [w]
                            curr_top = w['top']
                    if curr_line:
                        curr_line.sort(key=lambda x: x['x0'])
                        c_lines.append(" ".join([x['text'] for x in curr_line]))

                    # Saat satırlarına göre maç bloklarına böl
                    match_blocks = []
                    curr_block = []
                    for line in c_lines:
                        if re.search(r'\b\d{1,2}:\d{2}\b', line) or "TAKİP" in line.upper():
                            if curr_block:
                                match_blocks.append(curr_block)
                            curr_block = [line]
                        else:
                            if curr_block:
                                curr_block.append(line)
                    if curr_block:
                        match_blocks.append(curr_block)

                    for block in match_blocks:
                        saat_match = re.search(r'\b\d{1,2}:\d{2}\b', block[0])
                        saat = saat_match.group() if saat_match else block[0].split()[0]

                        # Kulüp isimlerini (parantezli satırları) temizle
                        details = [l.strip() for l in block[1:] if not l.strip().startswith('(') and not l.strip().endswith(')') and l.strip()]
                        if not details:
                            continue

                        kategori_keywords = ["YAŞ", "YAS", "KADIN", "ERKEK", "BÜYÜK", "BUYUK", "TEK", "ÇİFT"]
                        kat_idx = -1
                        kategori = "Genel"

                        for idx, item in enumerate(details):
                            if any(kw in item.upper() for kw in kategori_keywords):
                                kat_idx = idx
                                kategori = item
                                break

                        if kat_idx != -1:
                            oyuncu1 = " ".join(details[:kat_idx])
                            oyuncu2 = " ".join(details[kat_idx+1:])
                        else:
                            if len(details) >= 3:
                                oyuncu1, kategori, oyuncu2 = details[0], details[1], details[2]
                            elif len(details) == 2:
                                oyuncu1, oyuncu2 = details[0], details[1]
                            else:
                                oyuncu1, oyuncu2 = details[0], "Bilinmiyor"

                        if oyuncu1.strip() or oyuncu2.strip():
                            tum_maclar.append({
                                "Kort": col['name'],
                                "Saat": saat,
                                "Oyuncu 1": oyuncu1.strip(),
                                "Oyuncu 2": oyuncu2.strip(),
                                "Kategori": kategori.strip()
                            })

        if not tum_maclar:
            return None, "PDF okundu ancak eşleşen maç bulunamadı."
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
    with st.spinner("Maç programı ayrıştırılıyor..."):
        df, mesaj = pdf_programi_oku_guclu(yuklenen_pdf)
    
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
