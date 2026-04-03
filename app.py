import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar

# --- CONFIGURAZIONE E COSTANTI ---
STAGIONE_ANNO = 2026
MAPPA_GIORNI = {
    "Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, 
    "Venerdì": 4, "Sabato": 5, "Domenica": 6
}
GIORNI_ITA = list(MAPPA_GIORNI.keys())

st.set_page_config(
    page_title="Caribe Bay - Staff", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)

# --- FUNZIONI DI SERVIZIO ---

@st.cache_data(ttl=60)
def load_all_data():
    """Carica tutti i fogli necessari dal Google Sheet."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        return {
            "addetti": conn.read(worksheet="Addetti"),
            "disp": conn.read(worksheet="Disponibilita"),
            "fabbisogno": conn.read(worksheet="Fabbisogno"),
            "postazioni": conn.read(worksheet="Postazioni"),
            "config": conn.read(worksheet="Config")
        }
    except Exception as e:
        st.error(f"Errore nel caricamento dati: {e}")
        return None

def save_to_gsheets(worksheet_name, df):
    """Utility per aggiornare i dati e pulire la cache."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

def get_config_value(df, ruolo, default):
    """Recupera valori di configurazione in modo sicuro."""
    try:
        val = df[df["Ruolo"] == ruolo]["Password"].values[0]
        return val
    except:
        return default

# --- LOGICA DI AUTENTICAZIONE ---

def check_password(config_df):
    if "role" not in st.session_state:
        st.title("🌊 Caribe Bay - Staff Login")
        with st.container(border=True):
            pwd_input = st.text_input("Inserisci Password", type="password")
            if st.button("Accedi", use_container_width=True):
                admin_pwd = str(get_config_value(config_df, "Admin", "admin123"))
                user_pwd = str(get_config_value(config_df, "User", "user123"))
                
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else:
                    st.error("❌ Password errata.")
        return False
    return True

# --- COMPONENTI UI ---

def ui_mini_calendario(df_persona, riposo_fisso, mese, d_apertura, d_chiusura):
    """Genera la tabella HTML del calendario mensile."""
    nomi_mesi = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    idx_riposo = MAPPA_GIORNI.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(STAGIONE_ANNO, mese)
    
    st.markdown(f"""
        <div style='text-align: center; background-color: #1f77b4; color: white; 
        padding: 5px; border-radius: 5px; font-weight: bold; margin-bottom: 5px;'>
            {nomi_mesi.get(mese, "")}
        </div>
    """, unsafe_allow_html=True)
    
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed;">'
    html += '<tr style="background:#f0f2f6;"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    
    for week in cal:
        html += '<tr>'
        for i, day in enumerate(week):
            if day == 0:
                html += '<td style="border:1px solid #eee;"></td>'
                continue
            
            curr_date = datetime(STAGIONE_ANNO, mese, day).date()
            d_str = curr_date.strftime("%Y-%m-%d")
            is_open = d_apertura <= curr_date <= d_chiusura
            
            bg, color, label = "white", "black", str(day)
            
            if not is_open:
                bg, color, label = "#f9f9f9", "#ccc", f"<s>{day}</s>"
            else:
                # Controllo disponibilità specifica
                disp_check = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]
                if not disp_check.empty and "NON" in str(disp_check["Stato"].values[0]).upper():
                    bg, color = "#ff4b4b", "white"
                elif i == idx_riposo:
                    bg, color = "#ffa500", "white"
                elif not disp_check.empty:
                    bg, color = "#29b05c", "white"
            
            html += f'<td style="background:{bg}; color:{color}; border:1px solid #eee; padding:5px; font-weight:bold;">{label}</td>'
        html += '</tr>'
    
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- MAIN APP ---

def main():
    data = load_all_data()
    if not data: return

    # Configurazione date stagione
    d_apertura = pd.to_datetime(get_config_value(data["config"], "Apertura", "2026-05-16")).date()
    d_chiusura = pd.to_datetime(get_config_value(data["config"], "Chiusura", "2026-09-13")).date()

    if not check_password(data["config"]):
        return

    # Sidebar Navigation
    st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=180)
    st.sidebar.markdown(f"**Ruolo:** {st.session_state['role']}")
    
    menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi"]
    if st.session_state["role"] == "Admin":
        menu_options += ["📝 Gestione Rapida", "🗓️ Disponibilità Staff", "⚙️ Fabbisogno", "👥 Anagrafica", "🚩 Postazioni", "🔧 Config Stagione"]

    choice = st.sidebar.radio("Navigazione", menu_options)
    
    if st.sidebar.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # --- ROUTING ---

    if choice == "📊 Dashboard":
        st.header("📊 Dashboard Giornaliera")
        sel_date = st.date_input("Data di riferimento", datetime.now().date())
        if not (d_apertura <= sel_date <= d_chiusura):
            st.warning(f"Il parco risulta chiuso in data {sel_date.strftime('%d/%m/%Y')}")
        else:
            st.success(f"Visualizzazione dati per: {sel_date.strftime('%A %d %B %Y')}")

    elif choice == "📅 Riepilogo Riposi":
        st.header("📅 Riepilogo Riposi Settimanali")
        postazioni = data["postazioni"]["Nome Postazione"].dropna().unique()
        for p in postazioni:
            with st.expander(f"📍 {p}", expanded=True):
                cols = st.columns(7)
                for i, giorno in enumerate(GIORNI_ITA):
                    with cols[i]:
                        st.markdown(f"**{giorno}**")
                        staff = data["addetti"][(data["addetti"]["Mansione"] == p) & (data["addetti"]["GiornoRiposoSettimanale"] == giorno)]
                        for _, r in staff.iterrows():
                            st.info(f"{r['Nome']} {r['Cognome']}")

    elif choice == "📝 Gestione Rapida":
        st.header("📝 Modifica Rapida Riposi")
        df_mod = data["addetti"].copy()
        postazioni = data["postazioni"]["Nome Postazione"].dropna().unique()
        
        for p in postazioni:
            st.subheader(f"Reparto: {p}")
            staff_p = df_mod[df_mod["Mansione"] == p]
            for idx, row in staff_p.iterrows():
                c1, c2 = st.columns([3, 2])
                c1.write(f"{row['Nome']} {row['Cognome']}")
                current_rip = row["GiornoRiposoSettimanale"]
                opts = GIORNI_ITA + ["Non Definito"]
                new_val = c2.selectbox("Riposo", opts, index=opts.index(current_rip) if current_rip in opts else len(opts)-1, key=f"rip_{idx}", label_visibility="collapsed")
                df_mod.at[idx, "GiornoRiposoSettimanale"] = new_val
            st.divider()
        
        if st.button("💾 Salva Modifiche", type="primary"):
            save_to_gsheets("Addetti", df_mod)
            st.success("Dati aggiornati correttamente!")
            st.rerun()

    elif choice == "🗓️ Disponibilità Staff":
        st.header("🗓️ Calendario Disponibilità")
        data["addetti"]["Full"] = data["addetti"]["Nome"] + " " + data["addetti"]["Cognome"]
        persona = st.selectbox("Seleziona Membro Staff", data["addetti"]["Full"].tolist())
        
        row = data["addetti"][data["addetti"]["Full"] == persona].iloc[0]
        disp_pers = data["disp"][(data["disp"]["Nome"] == row["Nome"]) & (data["disp"]["Cognome"] == row["Cognome"])]
        
        cols = st.columns(5)
        for i, m in enumerate([5, 6, 7, 8, 9]):
            with cols[i]:
                ui_mini_calendario(disp_pers, row["GiornoRiposoSettimanale"], m, d_apertura, d_chiusura)

    elif choice == "🔧 Config Stagione":
        st.header("🔧 Impostazioni Stagione")
        with st.form("config_form"):
            new_ap = st.date_input("Inizio Stagione", d_apertura)
            new_ch = st.date_input("Fine Stagione", d_chiusura)
            if st.form_submit_button("Aggiorna Date"):
                conf_df = data["config"].copy()
                conf_df.loc[conf_df["Ruolo"] == "Apertura", "Password"] = str(new_ap)
                conf_df.loc[conf_df["Ruolo"] == "Chiusura", "Password"] = str(new_ch)
                save_to_gsheets("Config", conf_df)
                st.success("Configurazione salvata!")

if __name__ == "__main__":
    main()
