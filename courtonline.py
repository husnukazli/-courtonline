
import streamlit as st

# Sayfa ayarları her zaman en üstte olmalı
st.set_page_config(page_title="Tenis Canlı Skor", page_icon="🎾", layout="wide")

st.title("🎾 Tenis Turnuva Yönetim Sistemi")
st.write("Sol taraftaki menüden ilgili panele geçiş yapabilirsiniz.")

st.info("""
* **Kort Hakemleri:** Kura atışı ve anlık skor girişi için sol menüden 'Kort Hakemi' sayfasını seçin.
* **Başhakem:** Maç programı yükleme ve tüm kortları canlı takip etmek için 'Baş Hakem' sayfasını seçin.
""")
