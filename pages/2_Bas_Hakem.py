import streamlit as st

st.set_page_config(page_title="Baş Hakem", page_icon="👑", layout="wide")

st.title("👑 Başhakem Kontrol Paneli")
st.write("Burada PDF yükleme ekranı ve tüm kortların anlık durumu görünecek.")

# Test için PDF yükleme butonu taslağı
yuklenen_pdf = st.file_uploader("Maç Programı (PDF) Yükle", type="pdf")
if yuklenen_pdf:
    st.success("PDF başarıyla yüklendi. (Okuma işlemi yakında eklenecek)")
