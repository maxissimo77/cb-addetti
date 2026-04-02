import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="WaterPark Manager 2026", layout="wide", page_icon="🌊")

# --- CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 WaterPark Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            try:
                conf = conn.read(worksheet="Config", ttl=0)
                conf.columns = conf.columns.str.strip()
                admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
                if pwd_input == str(admin_pwd):
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == str(user_pwd):
                    st.session_state["role"] = "User"
                    st.rerun()
                else: st.error("❌ Password errata.")
            except: st.error("⚠️ Errore nel foglio 'Config'.")
        return False
    return True

if not check_password():
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=5)
def get_data():
    return {
        "addetti": conn.read(worksheet="Addetti"),
        "disp": conn.read(worksheet="Disponibilita"),
        "fabbisogno": conn.read(worksheet="Fabbisogno"),
        "postazioni": conn.read(worksheet="Postazioni")
    }

data = get_data()
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys())
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- FUNZIONE CALENDARIO (ROBUSTA) ---
def visualizza_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"### {nomi_mesi[mese]}")
    
    idx_riposo = mappa_giorni.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(anno, mese)
    
    # Intestazione Giorni
    cols_header = st.columns(7)
    giorni_sett = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    for i, g in enumerate(giorni_sett):
        cols_header[i].caption(f"**{g}**")
    
    # Righe Calendario
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                # Cerchiamo se c'è una nota di disponibilità
                stato_serie = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]["Stato"]
                stato = stato_serie.values[0] if not stato_serie.empty else None
                
                # Scegliamo il colore
                color = "transparent"
                if i == idx_riposo:
                    color = "#ffa500" # Arancione (Riposo)
                elif stato:
                    color = "#29b05c" if "NON" not in str(stato).upper() else "#ff4b4b" # Verde o Rosso
                
                # Usiamo un piccolo HTML inline molto semplice che Streamlit non può sbagliare
                cols[i].markdown(f"""
                <div style="text-align:center; border:1px solid #f0f2f6; padding:2px; border-radius:5px;">
                    <span style="font-size:14px; font-weight:bold;">{day}</span><br>
                    <div style="height:8px; width:8px; background-color:{color}; border-radius:50%; display:inline-block;"></div>
                </div>
                """, unsafe_allow_html=True)

# --- MENU LATERALE ---
menu_options = ["📊 Dashboard Oggi", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "🔑 Gestione Password"]

menu = st.sidebar.radio("Navigazione:", menu_options)
if st.sidebar.button("Logout"):
    del st.session_state["role"]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard Oggi":
    st.header("Situazione Giornaliera")
    d_sel = st.date_input("Data:", datetime.now())
    g_sett = giorni_ita[d_sel.weekday()]
    
    fabb = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str).str.contains(str(d_sel), na=False)]
    disp = data["disp"][data["disp"]["Data"].astype(str).str.contains(str(d_sel), na=False)]
    staff = data["addetti"].copy()
    
    # Filtro Riposo Fisso
    staff = staff[staff["GiornoRiposoSettimanale"] != g_sett]
    # Filtro NON Disponibili
    if not disp.empty:
        non_disp = disp[disp["Stato"].astype(str).str.contains("NON", case=False, na=False)]["Cognome"].tolist()
        staff = staff[~staff["Cognome"].isin(non_disp)]
    
    cols = st.columns(3)
    for i, post in enumerate(lista_postazioni):
        presenti = staff[staff["Mansione"] == post]
        f_row = fabb[fabb["Mansione"] == post]
        req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
        with cols[i % 3]:
            st.metric(post, f"{len(presenti)}/{req}", delta=len(presenti)-req)
            for _, r in presenti.iterrows():
                st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. RIEPILOGO RIPOSI ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Giorni di Riposo Staff")
    for m in lista_postazioni:
        with st.expander(f"Postazione: {m}", expanded=True):
            add_m = data["addetti"][data["addetti"]["Mansione"] == m]
            c_rip = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c_rip[i]:
                    st.markdown(f"**{g}**")
                    chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                    for _, r in chi.iterrows(): st.info(f"{r['Nome']} {r['Cognome']}")

# --- 3. AREA DISPONIBILITÀ (ADMIN) ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Gestione Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][data["disp"]["Cognome"] == row_d['Cognome']]
    
    st.info("🟡 Riposo Fisso | 🟢 Disponibile | 🔴 NON Disponibile")
    
    # Calendari mesi
    for mese in [5, 6, 7, 8, 9]:
        visualizza_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, mese)
        st.write("---")
    
    with st.expander("Modifica Disponibilità"):
        dr = st.date_input("Periodo:", value=[], min_value=datetime(2026,5,1), max_value=datetime(2026,9,30))
        st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile"])
        if st.button("Salva Date"):
            if len(dr) == 2:
                d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
                nuovi = pd.DataFrame([{"Nome": row_d['Nome'], "Cognome": row_d['Cognome'], "Data": d, "Stato": st_r} for d in d_list])
                old = data["disp"][~((data["disp"]["Cognome"] == row_d['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
                conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

# --- 4. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno Staff")
    dt = st.date_input("Giorno:", datetime.now())
    f_list = []
    for p in lista_postazioni:
        esist = data["fabbisogno"][(data["fabbisogno"]["Data"].astype(str).str.contains(str(dt), na=False)) & (data["fabbisogno"]["Mansione"] == p)]
        val = int(esist["Quantita"].iloc[0]) if not esist.empty else 0
        v = st.number_input(f"{p}:", min_value=0, value=val, key=f"f_{p}")
        f_list.append({"Data": str(dt), "Mansione": p, "Quantita": v})
    if st.button("Salva Fabbisogno"):
        old = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).str.contains(str(dt), na=False)]
        conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_list)], ignore_index=True))
        st.cache_data.clear()
        st.rerun()

# --- 5. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica")
    with st.form("nuovo"):
        st.subheader("Aggiungi Dipendente")
        n, c = st.text_input("Nome"), st.text_input("Cognome")
        m, r = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
        if st.form_submit_button("Inserisci"):
            new = pd.DataFrame([{"Nome": n, "Cognome": c, "Mansione": m, "GiornoRiposoSettimanale": r}])
            conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new], ignore_index=True))
            st.cache_data.clear()
            st.rerun()
    st.dataframe(data["addetti"], use_container_width=True)

# --- 6. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True))
        st.cache_data.clear()
        st.rerun()
    st.table(data["postazioni"])

# --- 7. PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.header("Gestione Password")
    conf_p = conn.read(worksheet="Config", ttl=0)
    with st.form("p"):
        ap = st.text_input("Admin Password", value=str(conf_p[conf_p["Ruolo"]=="Admin"]["Password"].values[0]))
        up = st.text_input("User Password", value=str(conf_p[conf_p["Ruolo"]=="User"]["Password"].values[0]))
        if st.form_submit_button("Aggiorna Password"):
            conn.update(worksheet="Config", data=pd.DataFrame([{"Ruolo":"Admin","Password":ap}, {"Ruolo":"User","Password":up}]))
            st.rerun()
