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
        # Pulizia stringhe per evitare spazi bianchi invisibili
        for df_name in ["addetti", "disp"]:
            res[df_name]["Nome"] = res[df_name]["Nome"].astype(str).str.strip()
            res[df_name]["Cognome"] = res[df_name]["Cognome"].astype(str).str.strip()
        
        # Conversione forzata a date pure (senza orario) per i confronti
        res["disp"]["Data"] = pd.to_datetime(res["disp"]["Data"], errors='coerce').dt.date
        res["fabbisogno"]["Data"] = pd.to_datetime(res["fabbisogno"]["Data"], errors='coerce').dt.date
        
        if "Contestazioni" in res["addetti"].columns:
            res["addetti"]["Contestazioni"] = res["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', '<NA>'], '')
        else:
            res["addetti"]["Contestazioni"] = ""
        return res
    except Exception as e:
        st.error(f"⚠️ Errore caricamento: {e}")
        st.stop()

data = get_all_data()

# --- CONFIGURAZIONE ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except Exception:
    admin_pwd, user_pwd = "admin", "staff"
    data_apertura, data_chiusura = datetime(2026, 5, 16).date(), datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    st.title("🌊 Caribe Bay - Staff Login")
    pwd_input = st.text_input("Password", type="password")
    if st.button("Accedi"):
        if pwd_input == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
        elif pwd_input == user_pwd: st.session_state["role"] = "User"; st.rerun()
        else: st.error("❌ Password errata.")
    st.stop()

# --- GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys())
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist()

# --- FUNZIONE CALENDARIO (Originale) ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita.get(mese, 'Mese')}</b></div>", unsafe_allow_html=True)
    idx_riposo_fisso = mappa_giorni.get(riposo_fisso, -1)
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    for week in cal:
        html += '<tr>'
        for i, day in enumerate(week):
            if day == 0: html += '<td></td>'
            else:
                curr_d = datetime(anno, mese, day).date()
                bg, tx, label = "transparent", "inherit", str(day)
                if not (data_apertura <= curr_d <= data_chiusura):
                    bg, tx = "#f0f0f0", "#ccc"
                else:
                    stato_row = df_persona[df_persona["Data"] == curr_d]
                    if not stato_row.empty:
                        s = str(stato_row["Stato"].iloc[0]).upper()
                        if "NON" in s: bg, tx = "#ff4b4b", "white"
                        elif "PERMESSO" in s: bg, tx = "#00008B", "white"
                        elif "ASSENTE" in s: bg, tx = "#000000", "white"
                        elif "MALATTIA" in s: bg, tx = "#696969", "white"
                        elif "DISPONIBILE" in s: bg, tx = "#29b05c", "white"
                    elif i == idx_riposo_fisso: bg, tx = "#ffa500", "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid #eee;">{label}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=180)
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione", "🔑 Gestione Password"]
menu = st.sidebar.radio("Navigazione", menu_options)

# --- 1. DASHBOARD (CORREZIONE APPLICATA QUI) ---
if menu == "📊 Dashboard":
    st.header("Dashboard Occupazione")
    input_d = st.date_input("Settimana del:", default_date)
    date_range = [input_d + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning("Parco chiuso.")
    else:
        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                curr_date = date_aperte[idx]
                g_sett = giorni_ita[curr_date.weekday()]
                
                # Filto Disponibilità per la DATA esatta del TAB
                disp_oggi = data["disp"][data["disp"]["Data"] == curr_date]
                fabb_oggi = data["fabbisogno"][data["fabbisogno"]["Data"] == curr_date]
                
                # Calcolo staff
                staff_presente = data["addetti"][data["addetti"]["GiornoRiposoSettimanale"] != g_sett].copy()
                
                if not disp_oggi.empty:
                    # Creazione chiave per match sicuro
                    disp_oggi['Key'] = disp_oggi['Nome'] + " " + disp_oggi['Cognome']
                    # Escludiamo chiunque abbia uno stato NON "Disponibile"
                    assenti_keys = disp_oggi[~disp_oggi["Stato"].astype(str).str.contains("Disponibile", case=False, na=False)]['Key'].tolist()
                    
                    staff_presente['Key'] = staff_presente['Nome'] + " " + staff_presente['Cognome']
                    staff_presente = staff_presente[~staff_presente['Key'].isin(assenti_keys)]
                
                cols = st.columns(3)
                for i, post in enumerate(lista_postazioni):
                    presenti = staff_presente[staff_presente["Mansione"] == post]
                    f_row = fabb_oggi[fabb_oggi["Mansione"] == post]
                    req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                    num = len(presenti)
                    
                    color = "#29b05c" if num >= req and req > 0 else "#ff4b4b" if num < req else "#808080"
                    with cols[i % 3]:
                        st.markdown(f"""
                            <div style="border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px;">
                                <div style="background:{color}; color:white; padding:8px; text-align:center; font-weight:bold; border-radius: 8px 8px 0 0;">{post}</div>
                                <div style="padding:15px; text-align:center;">
                                    <span style="font-size:22px; font-weight:bold;">{num} / {req}</span>
                                    <div style="text-align:left; font-size:12px; margin-top:10px; border-top:1px solid #eee; padding-top:5px;">
                                        {"".join([f"• {r['Nome']} {r['Cognome']}<br>" for _, r in presenti.iterrows()]) if not presenti.empty else "Nessuno"}
                                    </div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

# --- ALTRE SEZIONI (Originali) ---
elif menu == "📅 Riepilogo Riposi":
    st.header("Riepilogo Riposi")
    for m in lista_postazioni:
        with st.expander(f"Postazione: {m}"):
            c = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c[i]:
                    st.bold(g)
                    chi = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["GiornoRiposoSettimanale"] == g)]
                    for _, r in chi.iterrows(): st.write(f"{r['Nome']} {r['Cognome']}")

elif menu == "📝 Gestione Riposi Rapida":
    st.header("Modifica Riposi")
    df_mod = data["addetti"].copy()
    for idx, row in df_mod.iterrows():
        c1, c2 = st.columns([3, 1])
        c1.write(f"{row['Nome']} {row['Cognome']} ({row['Mansione']})")
        df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox("Giorno", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 0, key=f"r_{idx}")
    if st.button("Salva Modifiche"):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.rerun()

elif menu == "📅 Area Disponibilità Staff":
    st.header("Calendario Individuale")
    staff_list = (data["addetti"]["Nome"] + " " + data["addetti"]["Cognome"]).tolist()
    sel = st.selectbox("Seleziona Addetto", staff_list)
    nome, cognome = sel.split(" ", 1)
    row_p = data["addetti"][(data["addetti"]["Nome"] == nome) & (data["addetti"]["Cognome"] == cognome)].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == nome) & (data["disp"]["Cognome"] == cognome)]
    c_cal = st.columns(5)
    for i, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[i]: genera_mini_calendario(df_p, row_p['GiornoRiposoSettimanale'], 2026, m)
    with st.expander("Inserisci Assenza/Permesso"):
        d_in = st.date_input("Date", value=[])
        st_in = st.radio("Stato", ["NON Disponibile", "Permesso", "Assente", "Malattia", "Disponibile"])
        if st.button("Aggiorna") and len(d_in) == 2:
            days = [d_in[0] + timedelta(days=x) for x in range((d_in[1]-d_in[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": nome, "Cognome": cognome, "Data": d, "Stato": st_in} for d in days])
            old = data["disp"][~((data["disp"]["Nome"] == nome) & (data["disp"]["Cognome"] == cognome) & (data["disp"]["Data"].isin(days)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi])); st.cache_data.clear(); st.rerun()

elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno Giornaliero")
    d_fabb = st.date_input("Giorno", default_date)
    f_vals = {p: st.number_input(p, min_value=0, step=1) for p in lista_postazioni}
    if st.button("Salva Fabbisogno"):
        new_f = pd.DataFrame([{"Data": d_fabb, "Mansione": p, "Quantita": v} for p, v in f_vals.items()])
        old_f = data["fabbisogno"][data["fabbisogno"]["Data"] != d_fabb]
        conn.update(worksheet="Fabbisogno", data=pd.concat([old_f, new_f])); st.cache_data.clear(); st.rerun()

elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica")
    st.dataframe(data["addetti"])
    with st.form("nuovo"):
        n, c, m, r = st.text_input("Nome"), st.text_input("Cognome"), st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
        if st.form_submit_button("Aggiungi"):
            new_a = pd.concat([data["addetti"], pd.DataFrame([{"Nome": n, "Cognome": c, "Mansione": m, "GiornoRiposoSettimanale": r}])])
            conn.update(worksheet="Addetti", data=new_a); st.cache_data.clear(); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    st.table(data["postazioni"])
    nuova_p = st.text_input("Nuova Postazione")
    if st.button("Aggiungi Postazione"):
        new_p = pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": nuova_p}])])
        conn.update(worksheet="Postazioni", data=new_p); st.cache_data.clear(); st.rerun()

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Date Apertura")
    with st.form("stagione"):
        ap, ch = st.date_input("Apertura", data_apertura), st.date_input("Chiusura", data_chiusura)
        if st.form_submit_button("Salva"):
            conf = data["config"].copy()
            conf.loc[conf["Ruolo"] == "Apertura", "Password"] = str(ap)
            conf.loc[conf["Ruolo"] == "Chiusura", "Password"] = str(ch)
            conn.update(worksheet="Config", data=conf); st.cache_data.clear(); st.rerun()

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("pwd"):
        a_p, u_p = st.text_input("Admin", admin_pwd), st.text_input("User", user_pwd)
        if st.form_submit_button("Salva"):
            conf = data["config"].copy()
            conf.loc[conf["Ruolo"] == "Admin", "Password"] = a_p
            conf.loc[conf["Ruolo"] == "User", "Password"] = u_p
            conn.update(worksheet="Config", data=conf); st.cache_data.clear(); st.rerun()
