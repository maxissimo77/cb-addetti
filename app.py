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
        st.error(f"Errore di connessione: {e}")
        st.stop()

data = get_data()
mappa_giorni = {
    "Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, 
    "Venerdì": 4, "Sabato": 5, "Domenica": 6
}
giorni_ita = list(mappa_giorni.keys())

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 WaterPark Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            conf = data["config"]
            try:
                conf["Ruolo"] = conf["Ruolo"].astype(str).str.strip()
                conf["Password"] = conf["Password"].astype(str).str.strip()
                admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else: st.error("Password errata.")
            except: st.error("Errore nel foglio 'Config'.")
        return False
    return True

if not check_password():
    st.stop()

# --- VARIABILI GLOBALI ---
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- SIDEBAR ---
st.sidebar.title(f"👤 {st.session_state['role']}")
if st.session_state["role"] == "Admin":
    menu = st.sidebar.radio("Menu:", ["📊 Dashboard Oggi", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "🔑 Gestione Password"])
else:
    menu = st.sidebar.radio("Menu:", ["📊 Dashboard Oggi"])

if st.sidebar.button("Logout"):
    del st.session_state["role"]
    st.rerun()

# --- FUNZIONE CALENDARIO CON PRIORITÀ RIPOSO ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px;'><b>{nomi_mesi_ita[mese]}</b></div>", unsafe_allow_html=True)
    
    idx_riposo = mappa_giorni.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(anno, mese)
    
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px;">'
    html += '<tr style="background:#f0f2f6;"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    
    for week in cal:
        html += '<tr>'
        for i, day in enumerate(week):
            if day == 0: 
                html += '<td></td>'
            else:
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                stato = df_persona[df_persona["Data"] == d_str]["Stato"].values
                
                # NUOVA GERARCHIA PRIORITÀ:
                # 1. RIPOSO FISSO (Arancione) vince su tutto
                # 2. SE NON È RIPOSO -> STATO MANUALE (Verde/Rosso)
                # 3. DEFAULT (Bianco)
                
                if i == idx_riposo:
                    bg = "#ffa500" # Arancione
                    tx = "white"
                elif len(stato) > 0:
                    bg = "#29b05c" if "NON" not in stato[0] else "#ff4b4b"
                    tx = "white"
                else:
                    bg = "white"
                    tx = "black"
                
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid #eee; padding:5px; font-weight:bold;">{day}</td>'
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
    
    # Rimuoviamo chi ha il riposo fisso oggi
    staff = staff[staff["GiornoRiposoSettimanale"] != g_sett]
    
    # Rimuoviamo chi ha segnato NON DISPONIBILE (se non è già stato rimosso dal riposo)
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

# --- 2. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Pianificazione Stagione 2026")
    if not data["addetti"].empty:
        df_t = data["addetti"].copy()
        nomi = (df_t["Nome"].astype(str) + " " + df_t["Cognome"].astype(str)).tolist()
        scelto = st.selectbox("Seleziona dipendente:", nomi)
        n, c = scelto.split(" ", 1)
        
        riposo_persona = df_t[df_t["Cognome"] == c]["GiornoRiposoSettimanale"].values[0]
        df_p = data["disp"][data["disp"]["Cognome"] == c]
        
        st.write(f"**Giorno di riposo fisso:** {riposo_persona}")
        st.caption("🟠 Riposo Fisso (Priorità) | 🟢 Disponibile | 🔴 Non Disponibile")
        
        cols_cal = st.columns(5)
        for idx, m in enumerate([5, 6, 7, 8, 9]):
            with cols_cal[idx]: 
                genera_mini_calendario(df_p, riposo_persona, 2026, m)
        
        with st.expander("📝 Aggiorna Disponibilità Straordinaria"):
            dr = st.date_input("Periodo:", value=[], min_value=datetime(2026,5,1), max_value=datetime(2026,9,30))
            st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile"])
            if st.button("Salva"):
                if len(dr) == 2:
                    d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
                    nuovi = pd.DataFrame([{"Nome": n, "Cognome": c, "Data": d, "Stato": st_r} for d in d_list])
                    old = data["disp"][~((data["disp"]["Cognome"] == c) & (data["disp"]["Data"].isin(d_list)))]
                    conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi]))
                    st.cache_data.clear()
                    st.rerun()

# --- 3. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianifica Turni")
    t1, t2 = st.tabs(["Giorno Singolo", "Copia Massiva"])
    with t1:
        dt = st.date_input("Giorno:", datetime.now())
        f_list = []
        for p in lista_postazioni:
            v = st.number_input(f"Servono a {p}:", min_value=0, key=p)
            f_list.append({"Data": str(dt), "Mansione": p, "Quantita": v})
        if st.button("Salva Fabbisogno"):
            old = data["fabbisogno"][data["fabbisogno"]["Data"] != str(dt)]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_list)]))
            st.cache_data.clear()
            st.rerun()
    with t2:
        src = st.date_input("DA (Modello):", datetime.now() - timedelta(1))
        dst = st.date_input("A (Destinazione):", value=[])
        if st.button("Copia"):
            mod = data["fabbisogno"][data["fabbisogno"]["Data"] == str(src)]
            if not mod.empty and dst:
                new = []
                for d in dst:
                    for _, r in mod.iterrows(): new.append({"Data": str(d), "Mansione": r["Mansione"], "Quantita": r["Quantita"]})
                old = data["fabbisogno"][~data["fabbisogno"]["Data"].isin([str(x) for x in dst])]
                conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new)]))
                st.cache_data.clear()
                st.rerun()

# --- 4. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Staff")
    t_add, t_edit = st.tabs(["➕ Aggiungi", "✏️ Modifica"])
    with t_add:
        with st.form("new"):
            n_in, c_in = st.text_input("Nome"), st.text_input("Cognome")
            m_in, r_in = st.selectbox("Postazione", lista_postazioni), st.selectbox("Riposo", giorni_ita)
            if st.form_submit_button("Inserisci"):
                new = pd.DataFrame([{"Nome": n_in, "Cognome": c_in, "Mansione": m_in, "GiornoRiposoSettimanale": r_in}])
                conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new], ignore_index=True))
                st.cache_data.clear()
                st.rerun()
    with t_edit:
        if not data["addetti"].empty:
            df_e = data["addetti"].copy()
            df_e['Full'] = df_e['Nome'] + " " + df_e['Cognome']
            sel = st.selectbox("Chi modificare?", df_e['Full'].tolist())
            row = df_e[df_e['Full'] == sel].iloc[0]
            idx = int(row.name)
            with st.form("edit"):
                en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
                em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
                er = st.selectbox("Riposo", giorni_ita, index=giorni_ita.index(row['GiornoRiposoSettimanale']))
                c_s, c_d = st.columns(2)
                if c_s.form_submit_button("Salva"):
                    data["addetti"].loc[idx] = [en, ec, em, er]
                    conn.update(worksheet="Addetti", data=data["addetti"])
                    st.cache_data.clear()
                    st.rerun()
                if c_d.form_submit_button("Elimina"):
                    conn.update(worksheet="Addetti", data=data["addetti"].drop(idx))
                    st.cache_data.clear()
                    st.rerun()
    st.dataframe(data["addetti"], use_container_width=True)

# --- 5. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni Parco")
    np = st.text_input("Nome Postazione")
    if st.button("Salva"):
        new = pd.DataFrame([{"Nome Postazione": np}])
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], new]))
        st.cache_data.clear()
        st.rerun()
    st.table(data["postazioni"])

# --- 6. PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.header("Cambio Password")
    with st.form("pwd"):
        a_p = st.text_input("Admin", value=data["config"][data["config"]["Ruolo"]=="Admin"]["Password"].values[0])
        u_p = st.text_input("User", value=data["config"][data["config"]["Ruolo"]=="User"]["Password"].values[0])
        if st.form_submit_button("Aggiorna"):
            new_c = pd.DataFrame([{"Ruolo": "Admin", "Password": a_p}, {"Ruolo": "User", "Password": u_p}])
            conn.update(worksheet="Config", data=new_c)
            st.cache_data.clear()
            st.rerun()
