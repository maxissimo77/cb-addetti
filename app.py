import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Caribe Bay - Staff", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)
pd.options.mode.string_storage = "python"

# --- CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 Caribe Bay - Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            try:
                conf = conn.read(worksheet="Config", ttl=0)
                conf.columns = conf.columns.str.strip()
                admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else:
                    st.error("❌ Password errata.")
            except Exception:
                st.error("⚠️ Errore nel foglio 'Config'. Assicurati che esista il foglio 'Config' con colonne 'Ruolo' e 'Password'.")
        return False
    return True

if not check_password():
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=10)
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

# --- FUNZIONE CALENDARIO ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 3px; border-radius: 5px; margin-bottom: 5px; font-size: 0.8em;'><b>{nomi_mesi_ita[mese]}</b></div>", unsafe_allow_html=True)
    
    idx_riposo_fisso = mappa_giorni.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(anno, mese)
    
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 10px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    
    for week in cal:
        html += '<tr style="height: 25px;">'
        for i, day in enumerate(week):
            if day == 0: 
                html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                stato_serie = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]["Stato"]
                bg, tx = "transparent", "inherit"
                
                is_not_available = not stato_serie[stato_serie.astype(str).str.contains("NON", case=False, na=False)].empty
                
                if is_not_available:
                    bg, tx = "#ff4b4b", "white"
                else:
                    if i == idx_riposo_fisso:
                        bg, tx = "#ffa500", "white"
                    elif not stato_serie.empty:
                        bg, tx = "#29b05c", "white"
                
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid rgba(128,128,128,0.2); font-weight:bold;">{day}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
st.sidebar.markdown("---")

menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "🔑 Gestione Password"]

menu = st.sidebar.radio("Vai a:", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Dashboard Operativa")
    data_inizio = st.date_input("Giorno:", datetime.now())
    date_range = [data_inizio + timedelta(days=i) for i in range(7)]
    tabs = st.tabs([d.strftime("%d/%m") for d in date_range])

    for idx, t in enumerate(tabs):
        with t:
            curr_date = date_range[idx]
            g_sett = giorni_ita[curr_date.weekday()]
            fabb = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str).str.contains(str(curr_date), na=False)]
            disp = data["disp"][data["disp"]["Data"].astype(str).str.contains(str(curr_date), na=False)]
            
            staff = data["addetti"].copy()
            staff = staff[staff["GiornoRiposoSettimanale"] != g_sett]
            
            if not disp.empty:
                disp['Key'] = disp['Nome'] + " " + disp['Cognome']
                non_disp_keys = disp[disp["Stato"].astype(str).str.contains("NON", case=False, na=False)]['Key'].tolist()
                staff['Key'] = staff['Nome'] + " " + staff['Cognome']
                staff = staff[~staff['Key'].isin(non_disp_keys)]
            
            cols = st.columns(3)
            for i, post in enumerate(lista_postazioni):
                presenti = staff[staff["Mansione"] == post]
                f_row = fabb[fabb["Mansione"] == post]
                req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                with cols[i % 3]:
                    st.metric(post, f"{len(presenti)}/{req}", delta=len(presenti)-req)
                    for _, r in presenti.iterrows(): st.caption(f"• {r['Nome']} {r['Cognome']}")

# --- 2. RIEPILOGO RIPOSI ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Riepilogo Giorni di Riposo")
    for m in lista_postazioni:
        with st.expander(f"📍 {m}", expanded=True):
            add_m = data["addetti"][data["addetti"]["Mansione"] == m]
            c_rip = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c_rip[i]:
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.1); padding:5px; border-radius:5px;'><b>{g[:3]}</b></div>", unsafe_allow_html=True)
                    chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                    for _, r in chi.iterrows():
                        st.markdown(f"<div style='text-align:center; font-size:12px; margin-top:5px;'>{r['Nome']}</div>", unsafe_allow_html=True)
            
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.write("---")
                st.caption("Senza riposo assegnato:")
                st.write(", ".join([f"{r['Nome']} {r['Cognome']}" for _, r in non_def.iterrows()]))

# --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Modifica Veloce Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.subheader(f"📍 {m}")
            for idx, row in add_m.iterrows():
                c1, c2 = st.columns([2, 1])
                c1.write(f"{row['Nome']} {row['Cognome']}")
                idx_r = opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox(f"Riposo {idx}", opzioni_riposo, index=idx_r, key=f"fast_{idx}", label_visibility="collapsed")
    if st.button("Salva Tutto", type="primary"):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear()
        st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Calendario Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel = st.selectbox("Dipendente:", df_t['Full'].tolist())
    row = df_t[df_t['Full'] == sel].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row['Nome']) & (data["disp"]["Cognome"] == row['Cognome'])]
    
    c = st.columns(5)
    for i, m in enumerate([5, 6, 7, 8, 9]):
        with c[i]: genera_mini_calendario(df_p, row['GiornoRiposoSettimanale'], 2026, m)
    
    with st.expander("Aggiungi Assenza (Malattia/Permesso)"):
        dr = st.date_input("Periodo:", value=[], min_value=datetime(2026,5,1), max_value=datetime(2026,9,30))
        if st.button("Registra NON Disponibilità") and len(dr) == 2:
            d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": row['Nome'], "Cognome": row['Cognome'], "Data": d, "Stato": "NON Disponibile"} for d in d_list])
            old = data["disp"][~((data["disp"]["Nome"] == row['Nome']) & (data["disp"]["Cognome"] == row['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

# --- 5. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno Personale")
    dt = st.date_input("Seleziona Giorno:", datetime.now())
    f_list = []
    for p in lista_postazioni:
        esist = data["fabbisogno"][(data["fabbisogno"]["Data"].astype(str).str.contains(str(dt), na=False)) & (data["fabbisogno"]["Mansione"] == p)]
        val = int(esist["Quantita"].iloc[0]) if not esist.empty else 0
        v = st.number_input(f"{p}:", min_value=0, value=val)
        f_list.append({"Data": str(dt), "Mansione": p, "Quantita": v})
    if st.button("Salva Configurazione"):
        old = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str) != str(dt)]
        conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_list)], ignore_index=True))
        st.cache_data.clear()
        st.rerun()

# --- 6. GESTIONE ANAGRAFICA (VERSIONE FLUIDA) ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Anagrafica")
    
    # Inizializza lo stato se non esiste
    if "editing_id" not in st.session_state:
        st.session_state["editing_id"] = None

    # --- SCHEDA DI MODIFICA (Appare solo se editing_id è settato) ---
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        
        if st.button("⬅️ Annulla e Torna alla Lista"):
            st.session_state["editing_id"] = None
            st.rerun()
            
        st.subheader(f"Modifica Profilo: {row['Nome']} {row['Cognome']}")
        
        # Calendario integrato
        st.write("### Disponibilità 2026")
        df_p_edit = data["disp"][(data["disp"]["Nome"] == row['Nome']) & (data["disp"]["Cognome"] == row['Cognome'])]
        c_cal = st.columns(5)
        for i_c, m_c in enumerate([5, 6, 7, 8, 9]):
            with c_cal[i_c]: genera_mini_calendario(df_p_edit, row['GiornoRiposoSettimanale'], 2026, m_c)
        
        st.write("---")
        with st.form("edit_form"):
            en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
            em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            idx_r = opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7
            er = st.selectbox("Giorno Riposo Fisso", opzioni_riposo, index=idx_r)
            
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾 Salva Modifiche", use_container_width=True):
                data["addetti"].loc[idx] = [en, ec, em, er]
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.rerun()
            if c2.form_submit_button("🗑️ Elimina Addetto", use_container_width=True):
                conn.update(worksheet="Addetti", data=data["addetti"].drop(idx))
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.rerun()

    # --- LISTA E AGGIUNTA ---
    else:
        t1, t2 = st.tabs(["📋 Elenco Personale", "➕ Aggiungi Nuovo"])
        
        with t1:
            if not data["addetti"].empty:
                df_l = data["addetti"].copy().sort_values(by="Mansione")
                for idx, r in df_l.iterrows():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    col1.write(f"**{r['Nome']} {r['Cognome']}**")
                    col2.caption(f"📍 {r['Mansione']}")
                    col3.caption(f"📅 Riposo: {r['GiornoRiposoSettimanale']}")
                    if col4.button("✏️ Modifica", key=f"edit_btn_{idx}"):
                        st.session_state["editing_id"] = idx
                        st.rerun()
            else:
                st.info("Nessun addetto inserito.")

        with t2:
            with st.form("new_staff"):
                nn, nc = st.text_input("Nome"), st.text_input("Cognome")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                if st.form_submit_button("Registra Nuovo Addetto"):
                    if nn and nc:
                        nuovo = pd.DataFrame([{"Nome": nn, "Cognome": nc, "Mansione": nm, "GiornoRiposoSettimanale": nr}])
                        conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], nuovo], ignore_index=True))
                        st.cache_data.clear()
                        st.rerun()
                    else: st.error("Inserisci Nome e Cognome!")

# --- 7. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.header("Configurazione Posti di Lavoro")
    np = st.text_input("Nome Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True))
        st.cache_data.clear()
        st.rerun()
    st.table(data["postazioni"])

# --- 8. PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.header("Sicurezza Accessi")
    conf = conn.read(worksheet="Config", ttl=0)
    with st.form("pwd"):
        ap = st.text_input("Password Admin", value=str(conf[conf["Ruolo"]=="Admin"]["Password"].values[0]))
        up = st.text_input("Password User", value=str(conf[conf["Ruolo"]=="User"]["Password"].values[0]))
        if st.form_submit_button("Aggiorna Password"):
            conn.update(worksheet="Config", data=pd.DataFrame([{"Ruolo":"Admin","Password":ap}, {"Ruolo":"User","Password":up}]))
            st.success("Password aggiornate correttamente!")
