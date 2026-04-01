import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="WaterPark Staff Manager 2026", layout="wide", page_icon="🌊")

# Ottimizzazione Pandas per evitare conflitti con PyArrow
pd.options.mode.string_storage = "python"

# --- LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Accesso Riservato")
        pwd = st.text_input("Password Aziendale", type="password")
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

# --- CONNESSIONE E CARICAMENTO DATI ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # TTL impostato a 10 secondi per bilanciare aggiornamento e quote Google
        return {
            "addetti": conn.read(worksheet="Addetti", ttl=10),
            "disp": conn.read(worksheet="Disponibilita", ttl=10),
            "fabbisogno": conn.read(worksheet="Fabbisogno", ttl=10),
            "postazioni": conn.read(worksheet="Postazioni", ttl=10)
        }
    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ Troppe richieste a Google! Attendi 10 secondi e ricarica.")
        else:
            st.error(f"Errore connessione: {e}")
        st.stop()

data = get_data()
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# --- FUNZIONE GENERAZIONE CALENDARIO HTML ---
def genera_mini_calendario(df_persona, anno, mese):
    nomi_mesi_ita = {5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto", 9: "Settembre"}
    st.markdown(f"<h4 style='text-align: center; color: #1f77b4;'>{nomi_mesi_ita[mese]}</h4>", unsafe_allow_html=True)
    
    settimana_header = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    cal = calendar.monthcalendar(anno, mese)
    
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 12px; border: 1px solid #eee;">'
    html += '<tr style="background-color: #f8f9fa;">' + ''.join([f'<th style="padding:4px; border: 1px solid #eee;">{g}</th>' for g in settimana_header]) + '</tr>'
    
    for week in cal:
        html += '<tr>'
        for day in week:
            if day == 0:
                html += '<td style="border: 1px solid #eee; padding: 8px;"></td>'
            else:
                data_str = f"{anno}-{mese:02d}-{day:02d}"
                stato_giorno = df_persona[df_persona["Data"] == data_str]["Stato"].values
                
                bg_color = "white"
                txt_color = "black"
                if len(stato_giorno) > 0:
                    if "NON" in stato_giorno[0]:
                        bg_color = "#ff4b4b" # Rosso
                        txt_color = "white"
                    else:
                        bg_color = "#29b05c" # Verde
                        txt_color = "white"
                
                html += f'<td style="border: 1px solid #eee; padding: 8px; background-color: {bg_color}; color: {txt_color}; font-weight: bold;">{day}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

# --- LOGICA POSTAZIONI ---
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- SIDEBAR MENU ---
st.sidebar.title("🌊 WaterPark Menu")
menu = st.sidebar.radio("Vai a:", ["📊 Dashboard Oggi", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni"])

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard Oggi":
    st.header("Situazione Giornaliera")
    data_sel = st.date_input("Seleziona Giorno:", datetime.now())
    giorno_sett = giorni_ita[data_sel.weekday()]
    
    df_fabb = data["fabbisogno"][data["fabbisogno"]["Data"] == str(data_sel)]
    df_disp = data["disp"][data["disp"]["Data"] == str(data_sel)]
    
    staff = data["addetti"].copy()
    staff = staff[staff["GiornoRiposoSettimanale"] != giorno_sett]
    
    if not df_disp.empty:
        non_disp = df_disp[df_disp["Stato"].astype(str).str.contains("NON", na=False)]["Cognome"].tolist()
        staff = staff[~staff["Cognome"].isin(non_disp)]

    cols = st.columns(3)
    for i, post in enumerate(lista_postazioni):
        presenti = staff[staff["Mansione"] == post]
        fabb_row = df_fabb[df_fabb["Mansione"] == post]
        n_richiesti = int(fabb_row["Quantita"].iloc[0]) if not fabb_row.empty else 0
        
        with cols[i % 3]:
            st.metric(post, f"{len(presenti)}/{n_richiesti}", delta=len(presenti)-n_richiesti)
            for _, r in presenti.iterrows():
                st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. AREA DISPONIBILITÀ (CALENDARIO MAGGIO-SETTEMBRE) ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Disponibilità Stagione Estiva 2026")
    
    if not data["addetti"].empty:
        # Preparazione nomi
        df_t = data["addetti"].copy()
        nomi = (df_t["Nome"].astype(str) + " " + df_t["Cognome"].astype(str)).tolist()
        scelto = st.selectbox("Seleziona il tuo nome:", nomi)
        n, c = scelto.split(" ", 1)
        
        df_persona = data["disp"][data["disp"]["Cognome"] == c]
        
        st.info("🟢 Verde: Disponibile | 🔴 Rosso: NON Disponibile | ⚪ Bianco: Da definire")
        
        # Visualizzazione a 3 colonne per i 5 mesi
        m_estivi = [5, 6, 7, 8, 9]
        cols_cal = st.columns(3)
        for idx, m in enumerate(m_estivi):
            with cols_cal[idx % 3]:
                genera_mini_calendario(df_persona, 2026, m)
        
        st.divider()
        with st.expander("📝 AGGIORNA DATE (Seleziona intervallo)"):
            c1, c2 = st.columns(2)
            with c1:
                dr = st.date_input("Intervallo:", value=[], min_value=datetime(2026, 5, 1), max_value=datetime(2026, 9, 30))
            with c2:
                st_radio = st.radio("Tua disponibilità:", ["Disponibile", "NON Disponibile (Riposo/Ferie)"])
            
            if st.button("Salva nel Calendario"):
                if isinstance(dr, tuple) and len(dr) == 2:
                    s_d, e_d = dr
                    date_list = []
                    curr = s_d
                    while curr <= e_d:
                        date_list.append(str(curr))
                        curr += timedelta(days=1)
                    
                    nuovi = pd.DataFrame([{"Nome": n, "Cognome": c, "Data": d, "Stato": st_radio} for d in date_list])
                    old = data["disp"][~((data["disp"]["Cognome"] == c) & (data["disp"]["Data"].isin(date_list)))]
                    conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True))
                    st.cache_data.clear()
                    st.success("Calendario aggiornato!")
                    st.rerun()
                else:
                    st.warning("Seleziona inizio e fine sul calendario.")
    else:
        st.warning("Aggiungi personale in Anagrafica.")

# --- 3. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianifica Fabbisogno")
    t1, t2 = st.tabs(["Inserimento Singolo", "🚀 Copia Massiva"])
    
    with t1:
        df_f = st.date_input("Data:", datetime.now(), key="f_sing")
        f_rows = []
        for p in lista_postazioni:
            v = st.number_input(f"Servono a: {p}", min_value=0, step=1, key=f"in_{p}")
            f_rows.append({"Data": str(df_f), "Mansione": p, "Quantita": v})
        if st.button("Salva"):
            old = data["fabbisogno"][data["fabbisogno"]["Data"] != str(df_f)]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_rows)], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

    with t2:
        src = st.date_input("Copia DA:", datetime.now() - timedelta(days=1))
        dst = st.date_input("Incolla A (Seleziona più date):", value=[])
        if st.button("Esegui Copia"):
            modello = data["fabbisogno"][data["fabbisogno"]["Data"] == str(src)]
            if not modello.empty and dst:
                new_data = []
                for d in dst:
                    for _, r in modello.iterrows():
                        new_data.append({"Data": str(d), "Mansione": r["Mansione"], "Quantita": r["Quantita"]})
                old = data["fabbisogno"][~data["fabbisogno"]["Data"].isin([str(x) for x in dst])]
                conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new_data)], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

# --- 4. ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Personale")
    with st.form("new_staff"):
        n_in = st.text_input("Nome")
        c_in = st.text_input("Cognome")
        m_in = st.selectbox("Postazione Predefinita", lista_postazioni)
        r_in = st.selectbox("Riposo Fisso", giorni_ita)
        if st.form_submit_button("Aggiungi"):
            new_row = pd.DataFrame([{"Nome": n_in, "Cognome": c_in, "Mansione": m_in, "GiornoRiposoSettimanale": r_in}])
            conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new_row], ignore_index=True))
            st.cache_data.clear()
            st.rerun()
    st.dataframe(data["addetti"])

# --- 5. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni Parco")
    nuova_p = st.text_input("Nome Postazione")
    if st.button("Aggiungi"):
        if nuova_p:
            new_p = pd.DataFrame([{"Nome Postazione": nuova_p}])
            conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], new_p], ignore_index=True))
            st.cache_data.clear()
            st.rerun()
    st.table(data["postazioni"])
