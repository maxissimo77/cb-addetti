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

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=10)
def get_data():
    return {
        "addetti": conn.read(worksheet="Addetti"),
        "disp": conn.read(worksheet="Disponibilita"),
        "fabbisogno": conn.read(worksheet="Fabbisogno"),
        "postazioni": conn.read(worksheet="Postazioni"),
        "config": conn.read(worksheet="Config")
    }

data = get_data()

# --- LOGICA DATE STAGIONE ---
try:
    conf_df = data["config"]
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
    data_apertura = datetime(2026, 5, 16).date()
    data_chiusura = datetime(2026, 9, 13).date()

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 Caribe Bay - Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            try:
                conf = data["config"]
                conf.columns = conf.columns.str.strip()
                admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else: st.error("❌ Password errata.")
            except: st.error("⚠️ Errore nel foglio 'Config'.")
        return False
    return True

if not check_password():
    st.stop()

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
                curr_d = datetime(anno, mese, day).date()
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                is_open = data_apertura <= curr_d <= data_chiusura
                if not is_open:
                    bg, tx, label = "#e0e0e0", "#9e9e9e", f"<del>{day}</del>"
                else:
                    stato_s = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]["Stato"]
                    bg, tx, label = "transparent", "inherit", str(day)
                    if not stato_s[stato_s.astype(str).str.contains("NON", case=False, na=False)].empty:
                        bg, tx = "#ff4b4b", "white"
                    elif i == idx_riposo_fisso: bg, tx = "#ffa500", "white"
                    elif not stato_s.empty: bg, tx = "#29b05c", "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid rgba(128,128,128,0.2); font-weight:bold;">{label}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione", "🔑 Gestione Password"]

menu = st.sidebar.radio("Vai a:", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- SEZIONI ---
if menu == "📊 Dashboard":
    st.header("Dashboard")
    dt_sel = st.date_input("Giorno:", datetime.now())
    if not (data_apertura <= dt_sel <= data_chiusura):
        st.warning("⚠️ Attenzione: Il parco risulta CHIUSO nella data selezionata.")
    st.info("Visualizzazione copertura giornaliera basata su fabbisogno e disponibilità.")

elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Riepilogo Giorni di Riposo")
    for m in lista_postazioni:
        with st.expander(f"📍 {m}", expanded=True):
            add_m = data["addetti"][data["addetti"]["Mansione"] == m]
            
            # --- PARTE 1: GIORNI DA LUNEDÌ A DOMENICA ---
            c_rip = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c_rip[i]:
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.2); padding:5px; border-radius:5px; margin-bottom:12px;'><b>{g}</b></div>", unsafe_allow_html=True)
                    chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                    for _, r in chi.iterrows():
                        st.markdown(f"""
                            <div style='text-align: center; background-color: rgba(31, 119, 180, 0.1); 
                            padding: 10px 5px; border-radius: 5px; margin: 10px 0px; 
                            font-size: 14px; font-weight: 500; border: 1px solid rgba(31, 119, 180, 0.3);'>
                                {r['Nome']} {r['Cognome']}
                            </div>
                        """, unsafe_allow_html=True)
            
            # --- PARTE 2: RIPOSO NON DEFINITO ---
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.markdown("<div style='margin-top: 25px; border-top: 1px solid rgba(128,128,128,0.3); padding-top: 15px;'><b>Riposo Non Definito:</b></div>", unsafe_allow_html=True)
                
                # Costruiamo l'HTML in una variabile per evitare interruzioni di rendering
                html_nd = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; margin-bottom: 20px;">'
                for _, r in non_def.iterrows():
                    html_nd += f"""
                        <div style='border: 2px solid #ffa500; padding: 8px 15px; border-radius: 8px; 
                        font-weight: bold; background-color: rgba(255, 165, 0, 0.1); color: #333;'>
                            {r['Nome']} {r['Cognome']}
                        </div>
                    """
                html_nd += '</div>'
                st.markdown(html_nd, unsafe_allow_html=True)

elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.subheader(f"📍 {m}")
            conteggi = add_m["GiornoRiposoSettimanale"].value_counts()
            cols_c = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with cols_c[i]: st.metric(g[:3], conteggi.get(g, 0))
            for idx, row in add_m.iterrows():
                c1, c2 = st.columns([2, 1])
                c1.write(f"**{row['Nome']} {row['Cognome']}**")
                idx_r = opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox(f"Riposo {idx}", opzioni_riposo, index=idx_r, key=f"r_r_{idx}", label_visibility="collapsed")
    if st.button("💾 Salva Modifiche"):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear()
        st.rerun()

elif menu == "📅 Area Disponibilità Staff":
    st.header("Gestione Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    st.info(f"Stagione Caribe Bay 2026: dal {data_apertura.strftime('%d/%m')} al {data_chiusura.strftime('%d/%m')}")
    st.markdown("""<div style='display: flex; gap: 10px; margin-bottom: 10px;'><div style='background:#e0e0e0; color:#9e9e9e; padding:5px 10px; border-radius:5px;'><b>Parco Chiuso</b></div><div style='background:#ff4b4b; color:white; padding:5px 10px; border-radius:5px;'><b>NON Disponibile</b></div><div style='background:#ffa500; color:white; padding:5px 10px; border-radius:5px;'><b>Riposo Fisso</b></div></div>""", unsafe_allow_html=True)
    c_cal = st.columns(5)
    for idx, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[idx]: genera_mini_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, m)
    with st.expander("Modifica Disponibilità"):
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
        st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile"])
        if st.button("Salva Date") and len(dr) == 2:
            d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": row_d['Nome'], "Cognome": row_d['Cognome'], "Data": d, "Stato": st_r} for d in d_list])
            old = data["disp"][~((data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno Personale")
    tipo = st.radio("Modalità:", ["Giorno Singolo", "Intervallo"], horizontal=True)
    if tipo == "Giorno Singolo": date_list = [st.date_input("Giorno:", datetime.now())]
    else:
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
        date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)] if len(dr) == 2 else []
    if date_list:
        f_in = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("Salva Fabbisogno"):
            new = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_in.items()]
            old = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new)], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

elif menu == "👥 Gestione Anagrafica":
    st.header("Gestione Anagrafica")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        if st.button("⬅️ Torna"): st.session_state["editing_id"] = None; st.rerun()
        df_p_edit = data["disp"][(data["disp"]["Nome"] == row['Nome']) & (data["disp"]["Cognome"] == row['Cognome'])]
        cc = st.columns(5)
        for i_m, m_v in enumerate([5,6,7,8,9]): 
            with cc[i_m]: genera_mini_calendario(df_p_edit, row['GiornoRiposoSettimanale'], 2026, m_v)
        with st.form("edit"):
            en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
            em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = st.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7)
            if st.form_submit_button("💾 Salva"):
                data["addetti"].loc[idx] = [en, ec, em, er]
                conn.update(worksheet="Addetti", data=data["addetti"]); st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco", "➕ Nuovo"])
        with t1:
            for idx, r in data["addetti"].iterrows():
                c = st.columns([3, 2, 1])
                c[0].write(f"**{r['Nome']} {r['Cognome']}** ({r['Mansione']})")
                c[1].caption(f"Riposo: {r['GiornoRiposoSettimanale']}")
                if c[2].button("Modifica", key=f"ed_{idx}"): st.session_state["editing_id"] = idx; st.rerun()

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Configurazione Stagione Operativa")
    with st.form("set_season"):
        nuova_ap = st.date_input("Data Apertura Parco:", data_apertura)
        nuova_ch = st.date_input("Data Chiusura Parco:", data_chiusura)
        if st.form_submit_button("Salva Date Stagione"):
            conf_agg = data["config"].copy()
            conf_agg.loc[conf_agg["Ruolo"] == "Apertura", "Password"] = str(nuova_ap)
            conf_agg.loc[conf_agg["Ruolo"] == "Chiusura", "Password"] = str(nuova_ch)
            conn.update(worksheet="Config", data=conf_agg)
            st.cache_data.clear(); st.success("Date stagione aggiornate!"); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True))
        st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("p"):
        ap = st.text_input("Admin", value=str(data["config"][data["config"]["Ruolo"]=="Admin"]["Password"].values[0]))
        up = st.text_input("User", value=str(data["config"][data["config"]["Ruolo"]=="User"]["Password"].values[0]))
        if st.form_submit_button("Aggiorna"):
            new_conf = data["config"].copy()
            new_conf.loc[new_conf["Ruolo"] == "Admin", "Password"] = ap
            new_conf.loc[new_conf["Ruolo"] == "User", "Password"] = up
            conn.update(worksheet="Config", data=new_conf); st.success("Salvate!"); st.rerun()
