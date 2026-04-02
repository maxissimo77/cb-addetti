import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="WaterPark Manager 2026", layout="wide", page_icon="🌊")
pd.options.mode.string_storage = "python"

# --- CONNESSIONE E CARICAMENTO DATI ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def get_data():
    try:
        return {
            "addetti": conn.read(worksheet="Addetti"),
            "disp": conn.read(worksheet="Disponibilita"),
            "fabbisogno": conn.read(worksheet="Fabbisogno"),
            "postazioni": conn.read(worksheet="Postazioni"),
            "config": conn.read(worksheet="Config")
        }
    except Exception as e:
        st.error(f"Errore di connessione a Google Sheets: {e}")
        st.stop()

data = get_data()
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 WaterPark Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            conf = data["config"]
            try:
                admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
                
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else:
                    st.error("Password errata.")
            except:
                st.error("Errore: Foglio 'Config' non trovato o compilato male.")
        return False
    return True

if not check_password():
    st.stop()

# --- VARIABILI GLOBALI ---
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- SIDEBAR ---
st.sidebar.title(f"👤 {st.session_state['role']}")
if st.session_state["role"] == "Admin":
    menu = st.sidebar.radio("Menu Amministratore:", ["📊 Dashboard Oggi", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "🔑 Gestione Password"])
else:
    menu = st.sidebar.radio("Menu Utente:", ["📊 Dashboard Oggi"])

if st.sidebar.button("Logout"):
    del st.session_state["role"]
    st.rerun()

# --- FUNZIONE CALENDARIO (Maggio -> Settembre) ---
def genera_mini_calendario(df_persona, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-top: 10px;'><b>{nomi_mesi_ita[mese]}</b></div>", unsafe_allow_html=True)
    
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 12px; margin-bottom: 20px;">'
    html += '<tr style="background:#f0f2f6;"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    
    for week in cal:
        html += '<tr>'
        for day in week:
            if day == 0:
                html += '<td style="border: 1px solid #eee; padding: 8px;"></td>'
            else:
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                stato = df_persona[df_persona["Data"] == d_str]["Stato"].values
                bg, tx = "white", "black"
                if len(stato) > 0:
                    bg = "#29b05c" if "NON" not in stato[0] else "#ff4b4b"
                    tx = "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid #eee; padding: 8px; font-weight:bold;">{day}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

# --- 1. DASHBOARD OGGI ---
if menu == "📊 Dashboard Oggi":
    st.header("Disponibilità del Giorno")
    d_sel = st.date_input("Data:", datetime.now())
    g_sett = giorni_ita[d_sel.weekday()]
    
    fabb = data["fabbisogno"][data["fabbisogno"]["Data"] == str(d_sel)]
    disp = data["disp"][data["disp"]["Data"] == str(d_sel)]
    staff = data["addetti"].copy()
    staff = staff[staff["GiornoRiposoSettimanale"] != g_sett]
    
    if not disp.empty:
        non_disp = disp[disp["Stato"].astype(str).str.contains("NON", na=False)]["Cognome"].tolist()
        staff = staff[~staff["Cognome"].isin(non_disp)]

    cols = st.columns(3)
    for i, post in enumerate(lista_postazioni):
        presenti = staff[staff["Mansione"] == post]
        f_row = fabb[fabb["Mansione"] == post]
        req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
        with cols[i % 3]:
            st.metric(post, f"{len(presenti)}/{req}", delta=len(presenti)-req)
            if st.session_state["role"] == "Admin":
                for _, r in presenti.iterrows(): st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. AREA DISPONIBILITÀ (ORDINE CRONOLOGICO) ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Pianificazione Stagione 2026")
    if not data["addetti"].empty:
        df_t = data["addetti"].copy()
        nomi = (df_t["Nome"].astype(str) + " " + df_t["Cognome"].astype(str)).tolist()
        scelto = st.selectbox("Seleziona dipendente per visualizzare il calendario:", nomi)
        n, c = scelto.split(" ", 1)
        df_p = data["disp"][data["disp"]["Cognome"] == c]
        
        st.info("🟢 Verde: Disponibile | 🔴 Rosso: NON Disponibile (Ferie/Riposo)")
        
        # ORDINE RICHIESTO: Maggio, Giugno, Luglio, Agosto, Settembre
        mesi_ordine = [5, 6, 7, 8, 9]
        cols_cal = st.columns(5) # Visualizzazione orizzontale dei 5 mesi
        
        for idx, m in enumerate(mesi_ordine):
            with cols_cal[idx]:
                genera_mini_calendario(df_p, 2026, m)
        
        st.divider()
        with st.expander("📝 AGGIORNA DISPONIBILITÀ"):
            dr = st.date_input("Periodo (Seleziona inizio e fine):", value=[], min_value=datetime(2026,5,1), max_value=datetime(2026,9,30))
            st_r = st.radio("Stato da assegnare:", ["Disponibile", "NON Disponibile"])
            if st.button("Salva nel Calendario"):
                if len(dr) == 2:
                    d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
                    nuovi = pd.DataFrame([{"Nome": n, "Cognome": c, "Data": d, "Stato": st_r} for d in d_list])
                    old = data["disp"][~((data["disp"]["Cognome"] == c) & (data["disp"]["Data"].isin(d_list)))]
                    conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi]))
                    st.cache_data.clear()
                    st.success("Dati inviati a Google Sheets!")
                    st.rerun()
                else:
                    st.warning("Seleziona sia la data di inizio che quella di fine.")
    else:
        st.warning("Aggiungi personale in Anagrafica prima di procedere.")

# --- 3. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianifica Turni")
    tab1, tab2 = st.tabs(["Giorno Singolo", "Copia Massiva"])
    with tab1:
        dt = st.date_input("Giorno da configurare:", datetime.now())
        f_list = []
        for p in lista_postazioni:
            v = st.number_input(f"Addetti necessari per {p}:", min_value=0, key=p)
            f_list.append({"Data": str(dt), "Mansione": p, "Quantita": v})
        if st.button("Salva Fabbisogno"):
            old = data["fabbisogno"][data["fabbisogno"]["Data"] != str(dt)]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_list)]))
            st.cache_data.clear()
            st.rerun()
    with tab2:
        src = st.date_input("Copia DA (Modello):", datetime.now() - timedelta(1))
        dst = st.date_input("Incolla A (Destinazione - seleziona più date):", value=[])
        if st.button("Esegui Copia"):
            mod = data["fabbisogno"][data["fabbisogno"]["Data"] == str(src)]
            if not mod.empty and dst:
                new = []
                for d in dst:
                    for _, r in mod.iterrows(): new.append({"Data": str(d), "Mansione": r["Mansione"], "Quantita": r["Quantita"]})
                old = data["fabbisogno"][~data["fabbisogno"]["Data"].isin([str(x) for x in dst])]
                conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new)]))
                st.cache_data.clear()
                st.rerun()

# --- 4. ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Staff")
    with st.form("staff"):
        fn, ln = st.text_input("Nome"), st.text_input("Cognome")
        ms = st.selectbox("Postazione Assegnata", lista_postazioni)
        rp = st.selectbox("Giorno di Riposo Fisso", giorni_ita)
        if st.form_submit_button("Aggiungi Addetto"):
            new = pd.DataFrame([{"Nome": fn, "Cognome": ln, "Mansione": ms, "GiornoRiposoSettimanale": rp}])
            conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new], ignore_index=True))
            st.cache_data.clear()
            st.rerun()
    st.dataframe(data["addetti"], use_container_width=True)

# --- 5. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni Parco")
    np = st.text_input("Nome Nuova Postazione (es. Toboga, Bar, Ingresso)")
    if st.button("Salva Postazione"):
        if np:
            new = pd.DataFrame([{"Nome Postazione": np}])
            conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], new], ignore_index=True))
            st.cache_data.clear()
            st.rerun()
    st.table(data["postazioni"])

# --- 6. GESTIONE PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.header("Cambio Password")
    with st.form("pwd"):
        a_p = st.text_input("Password Amministratore", value=data["config"][data["config"]["Ruolo"]=="Admin"]["Password"].values[0])
        u_p = st.text_input("Password Utente (Dashboard)", value=data["config"][data["config"]["Ruolo"]=="User"]["Password"].values[0])
        if st.form_submit_button("Aggiorna Password"):
            new_c = pd.DataFrame([{"Ruolo": "Admin", "Password": a_p}, {"Ruolo": "User", "Password": u_p}])
            conn.update(worksheet="Config", data=new_c)
            st.cache_data.clear()
            st.success("Password salvate correttamente!")
            st.rerun()
