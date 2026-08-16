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
        return cevap_put.status_code in [200, 201], cevap_put.text
    except Exception as e:
        return False, str(e)

# --- ESKİ VERİLERİ SIFIRLAMA ALANI ---
with st.sidebar:
    st.markdown("### ⚙️ Sistem Yönetimi")
    if st.button("🗑️ Eski Maç Programını Sıfırla", type="secondary", use_container_width=True):
        basarili, _ = github_a_kaydet([], "mac_programi.json")
        if basarili:
            st.success("Sistemdeki eski maç verileri temizlendi!")
            st.rerun()
        else:
            st.error("Sıfırlama başarısız oldu.")

def pdf_programi_oku_kesin(pdf_file):
    tum_maclar = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for sayfa in pdf.pages:
                words = sayfa.extract_words()
                if not words:
                    continue

                # Kelimeleri satırlara diz
                words.sort(key=lambda w: w['top'])
                rows = []
                curr_row = [words[0]]
                curr_top = words[0]['top']

                for w in words[1:]:
                    if abs(w['top'] - curr_top) < 5:
                        curr_row.append(w)
                    else:
                        rows.append(curr_row)
                        curr_row = [w]
                        curr_top = w['top']
                if curr_row:
                    rows.append(curr_row)

                # Kort satırını bul
                court_kw = ["KORT", "KAPALI", "AÇIK", "TOPRAK", "SERT", "MERKEZ"]
                header_idx = -1
                for idx, row in enumerate(rows):
                    satir_metin = " ".join([w['text'].upper() for w in row])
                    if any(kw in satir_metin for kw in court_kw):
                        header_idx = idx
                        break

                if header_idx == -1:
                    continue

                header_row = rows[header_idx]
                header_row.sort(key=lambda w: w['x0'])

                # Kort sütun isimlerini birleştir
                sutunlar = []
                c_name = header_row[0]['text']
                c_x0 = header_row[0]['x0']
                c_x1 = header_row[0]['x1']

                for w in header_row[1:]:
                    if w['x0'] - c_x1 < 40:
                        c_name += " " + w['text']
                        c_x1 = w['x1']
                    else:
                        sutunlar.append({"name": c_name.strip(), "x0": c_x0, "x1": c_x1})
                        c_name = w['text']
                        c_x0 = w['x0']
                        c_x1 = w['x1']
                sutunlar.append({"name": c_name.strip(), "x0": c_x0, "x1": c_x1})

                # Sütun sınır koordinatları
                for i in range(len(sutunlar)):
                    sutunlar[i]['min_x'] = 0 if i == 0 else (sutunlar[i-1]['x1'] + sutunlar[i]['x0']) / 2
                    sutunlar[i]['max_x'] = 9999 if i == len(sutunlar)-1 else (sutunlar[i]['x1'] + sutunlar[i+1]['x0']) / 2

                header_bottom = max([w['bottom'] for w in header_row])
                data_words = [w for w in words if w['top'] >= header_bottom - 2]

                # Her sütun altındaki maç bloklarını topla
                for col in sutunlar:
                    c_words = [w for w in data_words if col['min_x'] <= ((w['x0'] + w['x1']) / 2) < col['max_x']]
                    if not c_words:
                        continue

                    c_words.sort(key=lambda w: w['top'])
                    c_lines = []
                    line = [c_words[0]]
                    l_top = c_words[0]['top']

                    for w in c_words[1:]:
                        if abs(w['top'] - l_top) < 5:
                            line.append(w)
                        else:
                            line.sort(key=lambda x: x['x0'])
                            c_lines.append(" ".join([x['text'] for x in line]))
                            line = [w]
                            l_top = w['top']
                    if line:
                        line.sort(key=lambda x: x['x0'])
                        c_lines.append(" ".join([x['text'] for x in line]))

                    # Saat satırına göre maçları ayır
                    blocks = []
                    curr_b = []
                    for l in c_lines:
                        if re.search(r'\b\d{1,2}:\d{2}\b', l) or "TAKİP" in l.upper():
                            if curr_b:
                                blocks.append(curr_b)
                            curr_b = [l]
                        else:
                            if curr_b:
                                curr_b.append(l)
                    if curr_b:
                        blocks.append(curr_b)

                    for b in blocks:
                        saat_m = re.search(r'\b\d{1,2}:\d{2}\b', b[0])
                        saat = saat_m.group() if saat_m else b[0].split()[0]

                        # Kulüp kısaltmalarını temizle
                        satirlar = [s.strip() for s in b[1:] if not (s.strip().startswith('(') and s.strip().endswith(')')) and s.strip()]
                        if not satirlar:
                            continue

                        kat_kw = ["YAŞ", "YAS", "KADIN", "ERKEK", "BÜYÜK", "TEK", "ÇİFT"]
                        kat_idx = -1
                        kategori = "Genel"

                        for k_i, s in enumerate(satirlar):
                            if any(kw in s.upper() for kw in kat_kw):
                                kat_idx = k_i
                                kategori = s
                                break

                        if kat_idx != -1:
                            oyuncu1 = " ".join(satirlar[:kat_idx])
                            oyuncu2 = " ".join(satirlar[kat_idx+1:])
                        else:
                            oyuncu1 = satirlar[0] if len(satirlar) > 0 else "Bilinmiyor"
                            oyuncu2 = satirlar[1] if len(satirlar) > 1 else "Bilinmiyor"

                        tum_maclar.append({
                            "Kort": col['name'],
                            "Saat": saat,
                            "Oyuncu 1": oyuncu1.strip(),
                            "Oyuncu 2": oyuncu2.strip(),
                            "Kategori": kategori.strip()
                        })

        if not tum_maclar:
            return None, "PDF dosyasından maç verisi çıkarılamadı."
        return pd.DataFrame(tum_maclar), "Başarılı"
    except Exception as e:
        return None, f"Hata: {e}"

FORMAT_SECENEKLERI = [
    "Normal (6) + 10 Puanlık Maç Tie-Break", 
    "Normal (6) + 3. Set Tam Oynanır", 
    "Kısa Set (4) + 10 Puanlık Maç Tie-Break",
    "Kısa Set (4) + 7 Puanlık Maç Tie-Break",
    "3 Kısa Set (4)"
]

yuklenen_pdf = st.file_uploader("TTF Maç Programı PDF Dosyasını Yükleyin", type=["pdf"])

if yuklenen_pdf is not None:
    with st.spinner("PDF ayrıştırılıyor..."):
        df, mesaj = pdf_programi_oku_kesin(yuklenen_pdf)
    
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
