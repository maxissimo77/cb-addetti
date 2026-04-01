Ecco il file app.py completo e corretto, integrando la gestione dinamica delle postazioni, la funzione copia, e i fix per gli errori di dati (PyArrow/NaN) che abbiamo visto finora.

Copia questo codice integralmente nel tuo file:

Python
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestionale WaterPark Pro", layout="wide", page_icon="🌊")

# Forza Pandas a gestire le stringhe in modo classico per evitare errori PyArrow
pd.options.mode.string_storage = "python"

# --- LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Accesso Riservato")
        pwd = st.text_input("Inserisci la password aziendale", type="password")
        if st.button("Entra"):
            if pwd == "PARCO2026": 
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Password errata")
        return False
    return True

if not check_password():
    st.stop()

# --- CONNESSIONE DATI ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    # ttl=0 assicura che i dati siano sempre aggiornati dal foglio Google
    try:
        return {
            "addetti": conn.read(worksheet="Addetti", ttl=0),
            "disp": conn.read(worksheet="Disponibilita", ttl=0),
            "fabbisogno": conn.read(worksheet="Fabbisogno", ttl=0),
            "postazioni": conn.read(worksheet="Postazioni", ttl=0)
        }
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
        st.stop()

data = get_data()
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- GESTIONE DINAMICA POSTAZIONI ---
# Estraiamo le postazioni reali dal foglio dedicato
lista_postazioni = []
if not data["postazioni"].empty:
    lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist()

if not lista_postazioni:
    lista_postazioni = ["Generico"] # Valore di backup se il foglio è vuoto

# --- SIDEBAR ---
st.sidebar.title("🌊 WaterPark Menu")
menu = st.sidebar.radio("Seleziona Area:", [
    "📊 Dashboard Oggi", 
    "📅 Area Disponibilità Staff", 
    "⚙️ Pianifica Fabbisogno", 
    "👥 Gestione Anagrafica",
    "🚩 Gestione Postazioni"
])

# --- 1. DASHBOARD OGGI ---
if menu == "📊 Dashboard Oggi":
    st.header("Situazione Personale Giornaliera")
    data_sel = st.date_input("Controlla data:", datetime.now())
    giorno_sett = giorni_ita[data_sel.weekday()]
    
    # Filtro Disponibilità
    df_disp_oggi = data["disp"][data["disp"]["Data"] == str(data_sel)]
    df_fabb_oggi = data["fabbisogno"][data["fabbisogno"]["Data"] == str(data_sel)]
    
    # Calcolo disponibili effettivi
    staff = data["addetti"].copy()
    staff = staff[staff["GiornoRiposoSettimanale"] != giorno_sett]
    
    # Fix per colonna Stato (evita errori se vuoto)
    if not df_disp_oggi.empty:
        non_disp = df_disp_oggi[df_disp_oggi["Stato"].astype(str).str.contains("NON", na=False)]["Cognome"].tolist()
        staff = staff[~staff["Cognome"].isin(non_disp)]

    st.subheader(f"Analisi per {giorno_sett} {data_sel}")
    
    # Mostra le metriche basate sulle POSTAZIONI REALI
    cols = st.columns(3) # Organizzato in 3 colonne per leggibilità
    for i, post in enumerate(lista_postazioni):
        presenti = staff[staff["Mansione"] == post]
        n_presenti = len(presenti)
        
        req_row = df_fabb_oggi[df_fabb_oggi["Mansione"] == post]
        n_richiesti = int(req_row["Quantita"].iloc[0]) if not req_row.empty else 0
        
        diff = n_presenti - n_richiesti
        with cols[i % 3]:
            st.metric(post, f"{n_presenti}/{n_richiesti}", delta=diff)
            for _, r in presenti.iterrows():
                st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. AREA DISPONIBILITÀ STAFF ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Inserimento Disponibilità Multipla")
    
    # Fix per unione Nome + Cognome (evita errori NumPy/PyArrow)
    if not data["addetti"].empty:
        df_temp = data["addetti"].copy()
        df_temp["Nome"] = df_temp["Nome"].astype(str).replace('nan', '')
        df_temp["Cognome"] = df_temp["Cognome"].astype(str).replace('nan', '')
        nomi = (df_temp["Nome"] + " " + df_temp["Cognome"]).tolist()
        
        scelto = st.selectbox("Chi sei?", nomi)
        date_multiple = st.date_input("Seleziona i giorni:", value=[])
        stato = st.radio("Tua disponibilità:", ["Disponibile", "NON Disponibile (Riposo/Ferie)"])
        
        if st.button("Salva Date"):
            if date_multiple:
                n, c = scelto.split(" ", 1)
                nuovi = pd.DataFrame([{"Nome": n, "Cognome": c, "Data": str(d), "Stato": stato} for d in date_multiple])
                date_str = [str(d) for d in date_multiple]
                old_disp = data["disp"][~((data["disp"]["Cognome"] == c) & (data["disp"]["Data"].isin(date_str)))]
                final = pd.concat([old_disp, nuovi], ignore_index=True)
                conn.update(worksheet="Disponibilita", data=final)
                st.cache_data.clear()
                st.success("Calendario aggiornato!")
                st.rerun()
    else:
        st.warning("Nessun addetto in anagrafica.")

# --- 3. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianificazione Fabbisogno")
    t1, t2 = st.tabs(["Inserimento Giorno", "🚀 Copia Turni (Massivo)"])
    
    with t1:
        data_f = st.date_input("Data da configurare:", datetime.now(), key="f1")
        fabb_list = []
        # Qui usiamo la lista postazioni
        for post in lista_postazioni:
            val = st.number_input(f"Addetti necessari per: {post}", min_value=0, step=1, key=f"f_{post}")
            fabb_list.append({"Data": str(data_f), "Mansione": post, "Quantita": val})
        
        if st.button("Salva Fabbisogno"):
            old_f = data["fabbisogno"][data["fabbisogno"]["Data"] != str(data_f)]
            final_f = pd.concat([old_f, pd.DataFrame(fabb_list)], ignore_index=True)
            conn.update(worksheet="Fabbisogno", data=final_f)
            st.cache_data.clear()
            st.success("Fabbisogno salvato!")
            st.rerun()

    with t2:
        st.subheader("Copia configurazione")
        src = st.date_input("Copia DA (Giorno Modello):", datetime.now() - timedelta(days=1))
        dst = st.date_input("Incolla A (Seleziona date):", value=[])
        
        if st.button("Esegui Copia Massiva"):
            modello = data["fabbisogno"][data["fabbisogno"]["Data"] == str(src)]
            if not modello.empty and dst:
                new_rows = []
                for d in dst:
                    for _, row in modello.iterrows():
                        new_rows.append({"Data": str(d), "Mansione": row["Mansione"], "Quantita": row["Quantita"]})
                
                date_dst_str = [str(d) for d in dst]
                df_clean = data["fabbisogno"][~data["fabbisogno"]["Data"].isin(date_dst_str)]
                final_copy = pd.concat([df_clean, pd.DataFrame(new_rows)], ignore_index=True)
                conn.update(worksheet="Fabbisogno", data=final_copy)
                st.cache_data.clear()
                st.success(f"Copiato su {len(dst)} giorni!")
                st.rerun()

# --- 4. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Personale")
    with st.form("new_staff"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome")
        c = c2.text_input("Cognome")
        # QUI: Mansione scelta dalle Postazioni
        m = st.selectbox("Assegna a Postazione Predefinita", lista_postazioni)
        r = st.selectbox("Riposo Fisso", giorni_ita)
        if st.form_submit_button("Aggiungi"):
            new_s = pd.DataFrame([{"Nome": n, "Cognome": c, "Mansione": m, "GiornoRiposoSettimanale": r}])
            final_s = pd.concat([data["addetti"], new_s], ignore_index=True)
            conn.update(worksheet="Addetti", data=final_s)
            st.cache_data.clear()
            st.success("Staff aggiornato!")
            st.rerun()
    st.dataframe(data["addetti"])

# --- 5. GESTIONE POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Configurazione Postazioni Parco")
    st.info("Aggiungi qui le zone del parco (es. Toboga, Bar, Ingresso).")
    
    with st.form("add_post"):
        nuova_p = st.text_input("Nome Nuova Postazione")
        if st.form_submit_button("Aggiungi Postazione"):
            if nuova_p:
                new_p = pd.DataFrame([{"Nome Postazione": nuova_p}])
                final_p = pd.concat([data["postazioni"], new_p], ignore_index=True)
                conn.update(worksheet="Postazioni", data=final_p)
                st.cache_data.clear()
                st.success(f"Postazione '{nuova_p}' aggiunta!")
                st.rerun()
    
    st.write("Postazioni attuali:")
    st.table(data["postazioni"])
