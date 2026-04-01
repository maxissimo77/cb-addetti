import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestionale WaterPark Pro", layout="wide", page_icon="🌊")

# --- LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Accesso Riservato")
        pwd = st.text_input("Inserisci la password aziendale", type="password")
        if st.button("Entra"):
            if pwd == "PARCO2026": # Modifica questa password a tuo piacimento
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
    return {
        "addetti": conn.read(worksheet="Addetti"),
        "disp": conn.read(worksheet="Disponibilita"),
        "fabbisogno": conn.read(worksheet="Fabbisogno"),
        "postazioni": conn.read(worksheet="Postazioni")
    }

data = get_data()
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

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
    # 1. Tutti i dipendenti
    staff = data["addetti"].copy()
    # 2. Rimuovi chi ha riposo fisso oggi
    staff = staff[staff["GiornoRiposoSettimanale"] != giorno_sett]
    # 3. Rimuovi chi ha segnato NON DISPONIBILE
    non_disp = df_disp_oggi[df_disp_oggi["Stato"].str.contains("NON", na=False)]["Cognome"].tolist()
    staff = staff[~staff["Cognome"].isin(non_disp)]
    # 4. Aggiungi chi ha segnato DISPONIBILE esplicitamente (se non già presenti)
    # (Logica semplificata: chi non è rimosso è considerato presente se non è il suo riposo)

    st.subheader(f"Analisi per {giorno_sett} {data_sel}")
    
    mansioni = data["addetti"]["Mansione"].unique()
    cols = st.columns(len(mansioni))
    
    for i, m in enumerate(mansioni):
        presenti = staff[staff["Mansione"] == m]
        n_presenti = len(presenti)
        
        req_row = df_fabb_oggi[df_fabb_oggi["Mansione"] == m]
        n_richiesti = int(req_row["Quantita"].iloc[0]) if not req_row.empty else 0
        
        diff = n_presenti - n_richiesti
        with cols[i]:
            st.metric(m, f"{n_presenti}/{n_richiesti}", delta=diff)
            st.write("**In servizio:**")
            for _, r in presenti.iterrows():
                st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. AREA DISPONIBILITÀ STAFF ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Inserimento Disponibilità Multipla")
    nomi = (data["addetti"]["Nome"] + " " + data["addetti"]["Cognome"]).tolist()
    scelto = st.selectbox("Chi sei?", nomi)
    
    date_multiple = st.date_input("Seleziona i giorni (clicca o trascina):", value=[])
    stato = st.radio("Tua disponibilità per questi giorni:", ["Disponibile", "NON Disponibile (Riposo/Ferie)"])
    
    if st.button("Salva Date"):
        if date_multiple:
            n, c = scelto.split(" ", 1)
            nuovi = pd.DataFrame([{"Nome": n, "Cognome": c, "Data": str(d), "Stato": stato} for d in date_multiple])
            # Pulizia duplicati
            date_str = [str(d) for d in date_multiple]
            old_disp = data["disp"][~((data["disp"]["Cognome"] == c) & (data["disp"]["Data"].isin(date_str)))]
            final = pd.concat([old_disp, nuovi], ignore_index=True)
            conn.update(worksheet="Disponibilita", data=final)
            st.success("Calendario aggiornato!")
            st.rerun()

# --- 3. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianificazione Fabbisogno")
    t1, t2 = st.tabs(["Inserimento Giorno", "🚀 Copia Turni"])
    
    with t1:
        data_f = st.date_input("Data da configurare:", datetime.now(), key="f1")
        mansioni = data["addetti"]["Mansione"].unique()
        fabb_list = []
        for m in mansioni:
            val = st.number_input(f"Quanti addetti per {m}?", min_value=0, step=1, key=f"m_{m}")
            fabb_list.append({"Data": str(data_f), "Mansione": m, "Quantita": val})
        
        if st.button("Salva Fabbisogno"):
            old_f = data["fabbisogno"][data["fabbisogno"]["Data"] != str(data_f)]
            final_f = pd.concat([old_f, pd.DataFrame(fabb_list)], ignore_index=True)
            conn.update(worksheet="Fabbisogno", data=final_f)
            st.success("Fabbisogno salvato!")
            st.rerun()

    with t2:
        st.subheader("Copia configurazione esistente")
        src = st.date_input("Copia DA (Giorno Modello):", datetime.now() - timedelta(days=1))
        dst = st.date_input("Incolla A (Seleziona date di destinazione):", value=[])
        
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
                st.success(f"Copiato su {len(dst)} giorni!")
                st.rerun()

# --- 4. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Personale")
    with st.form("new_staff"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome")
        c = c2.text_input("Cognome")
        m = st.selectbox("Mansione", ["Bagnino", "Bar", "Cassa", "Manutenzione", "Pulizie"])
        r = st.selectbox("Riposo Fisso", giorni_ita)
        if st.form_submit_button("Aggiungi"):
            new_s = pd.DataFrame([{"Nome": n, "Cognome": c, "Mansione": m, "GiornoRiposoSettimanale": r}])
            final_s = pd.concat([data["addetti"], new_s], ignore_index=True)
            conn.update(worksheet="Addetti", data=final_s)
            st.success("Staff aggiornato!")
            st.rerun()
    st.dataframe(data["addetti"])

# --- 5. GESTIONE POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni del Parco")
    nuova_p = st.text_input("Nome Postazione")
    if st.button("Aggiungi Postazione"):
        new_p = pd.DataFrame([{"Nome Postazione": nuova_p}])
        final_p = pd.concat([data["postazioni"], new_p], ignore_index=True)
        conn.update(worksheet="Postazioni", data=final_p)
        st.success("Postazione inserita!")
        st.rerun()
    st.table(data["postazioni"])