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
                st.error("⚠️ Errore nel foglio 'Config'.")
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
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita[mese]}</b></div>", unsafe_allow_html=True)
    idx_riposo_fisso = mappa_giorni.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    for week in cal:
        html += '<tr style="height: 30px;">'
        for i, day in enumerate(week):
            if day == 0: html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                stato_serie = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]["Stato"]
                bg, tx = "transparent", "inherit"
                is_not_available = not stato_serie[stato_serie.astype(str).str.contains("NON", case=False, na=False)].empty
                if is_not_available: bg, tx = "#ff4b4b", "white"
                else:
                    if i == idx_riposo_fisso: bg, tx = "#ffa500", "white"
                    elif not stato_serie.empty: bg, tx = "#29b05c", "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid rgba(128,128,128,0.2); font-weight:bold;">{day}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "🔑 Gestione Password"]

menu = st.sidebar.radio("Vai a:", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Dashboard")
    data_inizio = st.date_input("Inizio:", datetime.now())
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

# --- 2. RIEPILOGO RIPOSI (BOX VERSION) ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Riepilogo Giorni di Riposo")
    for m in lista_postazioni:
        with st.expander(f"📍 {m}", expanded=True):
            add_m = data["addetti"][data["addetti"]["Mansione"] == m]
            c_rip = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c_rip[i]:
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.2); padding:5px; border-radius:5px; margin-bottom:12px;'><b>{g}</b></div>", unsafe_allow_html=True)
                    chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                    for _, r in chi.iterrows():
                        st.markdown(f"<div style='text-align: center; background-color: rgba(31, 119, 180, 0.1); padding: 10px 5px; border-radius: 5px; margin-top: 8px; margin-bottom: 10px; font-size: 14px; font-weight: 500; border: 1px solid rgba(31, 119, 180, 0.3);'>{r['Nome']} {r['Cognome']}</div>", unsafe_allow_html=True)
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.markdown("<div style='margin-top: 20px; border-top: 1px solid rgba(128,128,128,0.3); padding-top: 10px;'><b>Riposo Non Definito:</b></div>", unsafe_allow_html=True)
                html_non_def = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; margin-bottom: 20px;">'
                for _, r in non_def.iterrows():
                    html_non_def += f"<div style='border: 2px solid #ffa500; padding: 6px 15px; border-radius: 8px; font-weight: bold; background-color: rgba(255, 165, 0, 0.1); display: inline-block;'>{r['Nome']} {r['Cognome']}</div>"
                st.markdown(html_non_def + '</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA (CON CONTEGGI) ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.subheader(f"📍 {m}")
            # --- CONTEGGI ---
            conteggi = add_m["GiornoRiposoSettimanale"].value_counts()
            cols_count = st.columns(len(giorni_ita))
            for i, g in enumerate(giorni_ita):
                n_rip = conteggi.get(g, 0)
                with cols_count[i]:
                    st.markdown(f"<div style='text-align:center; border: 1px solid rgba(128,128,128,0.2); border-radius:5px; padding:5px; margin-bottom:15px;'><small>{g[:3]}</small><br><b style='color: {'#ffa500' if n_rip > 0 else 'inherit'};'>{n_rip}</b></div>", unsafe_allow_html=True)
            # --- INPUT ---
            for idx, row in add_m.iterrows():
                c1, c2 = st.columns([2, 1])
                c1.write(f"**{row['Nome']} {row['Cognome']}**")
                idx_r = opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox(f"Riposo {idx}", opzioni_riposo, index=idx_r, key=f"r_rap_{idx}", label_visibility="collapsed")
            st.markdown("---")
    if st.button("💾 Salva Tutte le Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear()
        st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Gestione Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    st.markdown("""<div style='display: flex; gap: 15px; margin-bottom: 15px;'><div style='background:#ff4b4b; color:white; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>🔴 NON Disponibile</b></div><div style='background:#ffa500; color:white; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>🟠 Riposo Fisso</b></div><div style='background:#29b05c; color:white; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>🟢 Disponibile</b></div></div>""", unsafe_allow_html=True)
    c_cal = st.columns(5)
    for idx, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[idx]: genera_mini_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, m)
    with st.expander("Modifica Disponibilità"):
        dr = st.date_input("Periodo:", value=[], min_value=datetime(2026,5,1), max_value=datetime(2026,9,30))
        st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile"])
        if st.button("Salva Date") and len(dr) == 2:
            d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": row_d['Nome'], "Cognome": row_d['Cognome'], "Data": d, "Stato": st_r} for d in d_list])
            old = data["disp"][~((data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

# --- 6. GESTIONE ANAGRAFICA (FLUIDA) ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Anagrafica")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        if st.button("⬅️ Torna alla Lista"):
            st.session_state["editing_id"] = None
            st.rerun()
        st.subheader(f"Modifica Profilo: {row['Nome']} {row['Cognome']}")
        with st.form("edit_staff"):
            en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
            em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            idx_r = opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7
            er = st.selectbox("Riposo", opzioni_riposo, index=idx_r)
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾 Salva"):
                data["addetti"].loc[idx] = [en, ec, em, er]
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.rerun()
            if c2.form_submit_button("🗑️ Elimina"):
                conn.update(worksheet="Addetti", data=data["addetti"].drop(idx))
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.rerun()
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
                    if col4.button("✏️ Modifica", key=f"edit_l_{idx}"):
                        st.session_state["editing_id"] = idx
                        st.rerun()
        with t2:
            with st.form("new_s"):
                nn, nc = st.text_input("Nome"), st.text_input("Cognome")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                if st.form_submit_button("Inserisci"):
                    nuovo = pd.DataFrame([{"Nome": nn, "Cognome": nc, "Mansione": nm, "GiornoRiposoSettimanale": nr}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], nuovo], ignore_index=True))
                    st.cache_data.clear()
                    st.rerun()

# --- ALTRE VOCI ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno")
    dt = st.date_input("Giorno:", datetime.now())
    f_list = []
    for p in lista_postazioni:
        esist = data["fabbisogno"][(data["fabbisogno"]["Data"].astype(str).str.contains(str(dt), na=False)) & (data["fabbisogno"]["Mansione"] == p)]
        val = int(esist["Quantita"].iloc[0]) if not esist.empty else 0
        v = st.number_input(f"{p}:", min_value=0, value=val, key=f"f_{p}")
        f_list.append({"Data": str(dt), "Mansione": p, "Quantita": v})
    if st.button("Salva"):
        old = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str) != str(dt)]
        conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(f_list)], ignore_index=True))
        st.cache_data.clear()
        st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nome")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True))
        st.cache_data.clear()
        st.rerun()
    st.table(data["postazioni"])

elif menu == "🔑 Gestione Password":
    st.header("Password")
    conf = conn.read(worksheet="Config", ttl=0)
    with st.form("pwd"):
        ap = st.text_input("Admin", value=str(conf[conf["Ruolo"]=="Admin"]["Password"].values[0]))
        up = st.text_input("User", value=str(conf[conf["Ruolo"]=="User"]["Password"].values[0]))
        if st.form_submit_button("Aggiorna"):
            conn.update(worksheet="Config", data=pd.DataFrame([{"Ruolo":"Admin","Password":ap}, {"Ruolo":"User","Password":up}]))
            st.success("Fatto!")
