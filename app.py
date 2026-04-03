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
@st.cache_data(ttl=60)
def get_all_data():
    try:
        res = {
            "addetti": conn.read(worksheet="Addetti"),
            "disp": conn.read(worksheet="Disponibilita"),
            "fabbisogno": conn.read(worksheet="Fabbisogno"),
            "postazioni": conn.read(worksheet="Postazioni"),
            "config": conn.read(worksheet="Config")
        }
        # CORREZIONE: Normalizzazione Date per evitare mismatch di formato
        if not res["disp"].empty:
            res["disp"]["Data"] = pd.to_datetime(res["disp"]["Data"], errors='coerce').dt.date
        if not res["fabbisogno"].empty:
            res["fabbisogno"]["Data"] = pd.to_datetime(res["fabbisogno"]["Data"], errors='coerce').dt.date
            
        if "Contestazioni" in res["addetti"].columns:
            res["addetti"]["Contestazioni"] = res["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', '<NA>'], '')
        else:
            res["addetti"]["Contestazioni"] = ""
        return res
    except Exception as e:
        st.error(f"⚠️ Errore di connessione API: {e}")
        st.stop()

data = get_all_data()

# --- ESTRAZIONE CONFIGURAZIONE ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()

try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except Exception:
    admin_pwd, user_pwd = "admin", "staff"
    data_apertura = datetime(2026, 5, 16).date()
    data_chiusura = datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    st.title("🌊 Caribe Bay - Staff Login")
    pwd_input = st.text_input("Inserisci Password", type="password")
    if st.button("Accedi"):
        if pwd_input == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
        elif pwd_input == user_pwd: st.session_state["role"] = "User"; st.rerun()
        else: st.error("❌ Password errata.")
    st.stop()

# --- VARIABILI GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys())
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- FUNZIONE CALENDARIO ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita.get(mese, 'Mese')}</b></div>", unsafe_allow_html=True)
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
                    bg, tx, label = "#f0f0f0", "#bfbfbf", f"<span style='text-decoration: line-through;'>{day}</span>"
                else:
                    stato_row = df_persona[df_persona["Data"] == curr_d]
                    bg, tx, label = "transparent", "inherit", str(day)
                    if not stato_row.empty:
                        stato_val = str(stato_row["Stato"].iloc[0]).upper()
                        if "NON" in stato_val: bg, tx = "#ff4b4b", "white"
                        elif "PERMESSO" in stato_val: bg, tx = "#00008B", "white"
                        elif "ASSENTE" in stato_val: bg, tx = "#000000", "white"
                        elif "MALATTIA" in stato_val: bg, tx = "#696969", "white"
                        elif "DISPONIBILE" in stato_val: bg, tx = "#29b05c", "white"
                    elif i == idx_riposo_fisso: 
                        bg, tx = "#ffa500", "white"
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

# --- 1. DASHBOARD (CORRETTA) ---
if menu == "📊 Dashboard":
    st.header("Stato Occupazione Postazioni")
    input_d = st.date_input("Seleziona data di riferimento:", default_date)
    
    # Range di 7 giorni a partire dalla data selezionata
    date_range = [input_d + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning(f"⚠️ Parco CHIUSO nel periodo selezionato.")
    else:
        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                curr_date = date_aperte[idx]
                g_sett = giorni_ita[curr_date.weekday()]
                
                # CORREZIONE LOGICA CONTEGGIO
                # 1. Filtro fabbisogno e disponibilità per la data del tab
                fabb_oggi = data["fabbisogno"][data["fabbisogno"]["Data"] == curr_date]
                disp_oggi = data["disp"][data["disp"]["Data"] == curr_date]
                
                # 2. Parto dallo staff totale e tolgo chi è a riposo oggi
                staff_presente = data["addetti"][data["addetti"]["GiornoRiposoSettimanale"] != g_sett].copy()
                
                # 3. Tolgo chi ha una segnalazione di assenza (NON Disponibile, Permesso, ecc.)
                if not disp_oggi.empty:
                    disp_oggi['Key'] = disp_oggi['Nome'].str.strip() + " " + disp_oggi['Cognome'].str.strip()
                    non_disp_keys = disp_oggi[~disp_oggi["Stato"].astype(str).str.contains("Disponibile", case=False, na=False)]['Key'].tolist()
                    
                    staff_presente['Key'] = staff_presente['Nome'].str.strip() + " " + staff_presente['Cognome'].str.strip()
                    staff_presente = staff_presente[~staff_presente['Key'].isin(non_disp_keys)]
                
                # 4. Visualizzazione Grid
                cols = st.columns(3)
                for i, post in enumerate(lista_postazioni):
                    presenti = staff_presente[staff_presente["Mansione"] == post]
                    f_row = fabb_oggi[fabb_oggi["Mansione"] == post]
                    req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                    num_pres = len(presenti)
                    
                    # Colore card
                    if req == 0: color_status = "#808080"
                    elif num_pres >= req: color_status = "#29b05c"
                    else: color_status = "#ff4b4b"

                    with cols[i % 3]:
                        st.markdown(f"""
                            <div style="border: 1px solid #ddd; border-radius: 10px; padding: 0px; margin-bottom: 20px; background-color: white; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                                <div style="background-color: {color_status}; color: white; padding: 10px; border-radius: 10px 10px 0 0; text-align: center; font-weight: bold; text-transform: uppercase; font-size: 14px;">{post}</div>
                                <div style="padding: 15px; text-align: center;">
                                    <span style="font-size: 24px; font-weight: bold; color: #333;">{num_pres}</span>
                                    <span style="font-size: 18px; color: #666;"> / {req}</span>
                                    <div style="margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px; text-align: left;">
                                        {"".join([f"<div style='font-size: 13px; color: #444; padding: 2px 0;'>• {r['Nome']} {r['Cognome']}</div>" for _, r in presenti.iterrows()]) if not presenti.empty else "<div style='color:#999; font-style:italic; font-size:12px;'>Nessun addetto disponibile</div>"}
                                    </div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI ---
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
                        st.markdown(f"<div style='text-align: center; background-color: rgba(31, 119, 180, 0.1); padding: 10px 5px; border-radius: 5px; margin: 10px 0px; font-size: 14px; font-weight: 500; border: 1px solid rgba(31, 119, 180, 0.3);'>{r['Nome']} {r['Cognome']}</div>", unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi Settimanali")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            for idx, row in add_m.iterrows():
                col_nome, col_scelta = st.columns([2, 1])
                col_nome.markdown(f"<div style='padding-top:10px;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = col_scelta.selectbox(f"Riposo {idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"r_rap_{idx}")
    if st.button("💾 Salva Tutte le Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Salvato!"); st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Calendario Disponibilità Individuale")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    c_cal = st.columns(5)
    for idx, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[idx]: genera_mini_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, m)

# --- 5. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Personale")
    st.dataframe(data["addetti"])

# --- 6. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno")
    dt = st.date_input("Giorno:", default_date)
    f_inputs = {p: st.number_input(f"{p}:", min_value=0, key=f"f_{p}") for p in lista_postazioni}
    if st.button("💾 Salva"):
        new_r = [{"Data": dt, "Mansione": p, "Quantita": v} for p, v in f_inputs.items()]
        old_d = data["fabbisogno"][data["fabbisogno"]["Data"] != dt]
        conn.update(worksheet="Fabbisogno", data=pd.concat([old_d, pd.DataFrame(new_r)], ignore_index=True)); st.cache_data.clear(); st.rerun()

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Configurazione")
    with st.form("s"):
        na, nc = st.date_input("Inizio:", data_apertura), st.date_input("Fine:", data_chiusura)
        if st.form_submit_button("Salva"):
            conf_agg = data["config"].copy()
            conf_agg.loc[conf_agg["Ruolo"] == "Apertura", "Password"] = str(na)
            conf_agg.loc[conf_agg["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=conf_agg); st.cache_data.clear(); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("p"):
        ap, up = st.text_input("Admin", value=admin_pwd), st.text_input("User", value=user_pwd)
        if st.form_submit_button("Salva"):
            new_conf = data["config"].copy(); new_conf.loc[new_conf["Ruolo"]=="Admin", "Password"] = ap; new_conf.loc[new_conf["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=new_conf); st.cache_data.clear(); st.rerun()
