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
@st.cache_data(ttl=5) # Ridotto il TTL per aggiornamenti più rapidi
def get_data():
    return {
        "addetti": conn.read(worksheet="Addetti"),
        "disp": conn.read(worksheet="Disponibilita"),
        "fabbisogno": conn.read(worksheet="Fabbisogno"),
        "postazioni": conn.read(worksheet="Postazioni"),
        "config": conn.read(worksheet="Config")
    }

data = get_data()

# --- LOGICA DATE STAGIONE (MIGLIORATA) ---
conf_df = data["config"].copy()
conf_df.columns = conf_df.columns.str.strip()

def get_config_val(ruolo, default):
    try:
        val = conf_df[conf_df["Ruolo"] == ruolo]["Password"].values[0]
        return pd.to_datetime(val).date()
    except:
        return pd.to_datetime(default).date()

data_apertura = get_config_val("Apertura", "2026-05-16")
data_chiusura = get_config_val("Chiusura", "2026-09-13")

# --- SISTEMA DI LOGIN ---
def check_password():
    if "role" not in st.session_state:
        st.title("🌊 Caribe Bay - Staff Login")
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi"):
            try:
                admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
                user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
                if pwd_input == admin_pwd:
                    st.session_state["role"] = "Admin"
                    st.rerun()
                elif pwd_input == user_pwd:
                    st.session_state["role"] = "User"
                    st.rerun()
                else: st.error("❌ Password errata.")
            except: st.error("⚠️ Errore nel caricamento delle credenziali.")
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
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita.get(mese, '')}</b></div>", unsafe_allow_html=True)
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

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Dashboard Copertura")
    dt_sel = st.date_input("Seleziona Giorno:", datetime.now())
    if not (data_apertura <= dt_sel <= data_chiusura):
        st.error(f"❌ IL PARCO È CHIUSO. (Periodo apertura: {data_apertura.strftime('%d/%m')} - {data_chiusura.strftime('%d/%m')})")
    # Logica dashboard...

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
                        st.markdown(f"<div style='text-align: center; background-color: rgba(31, 119, 180, 0.1); padding: 10px 5px; border-radius: 5px; margin-top: 8px; margin-bottom: 10px; font-size: 14px; font-weight: 500; border: 1px solid rgba(31, 119, 180, 0.3);'>{r['Nome']} {r['Cognome']}</div>", unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA ---
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
                n_rip = conteggi.get(g, 0)
                with cols_c[i]:
                    st.markdown(f"<div style='text-align:center; border: 1px solid rgba(128,128,128,0.2); border-radius:5px; padding:5px; margin-bottom:15px;'><small>{g[:3]}</small><br><b style='color: {'#ffa500' if n_rip > 0 else 'inherit'};'>{n_rip}</b></div>", unsafe_allow_html=True)
            for idx, row in add_m.iterrows():
                c1, c2 = st.columns([2, 1])
                c1.write(f"**{row['Nome']} {row['Cognome']}**")
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox(f"Riposo {idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"r_r_{idx}", label_visibility="collapsed")
            st.markdown("---")
    if st.button("💾 Salva Modifiche"):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear(); st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Gestione Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    
    st.info(f"Stagione Caribe Bay 2026: **{data_apertura.strftime('%d/%m')}** - **{data_chiusura.strftime('%d/%m')}**")
    st.markdown("""<div style='display: flex; gap: 15px; margin-bottom: 15px;'><div style='background:#e0e0e0; color:#9e9e9e; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>⚪ Parco Chiuso</b></div><div style='background:#ff4b4b; color:white; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>🔴 NON Disponibile</b></div><div style='background:#ffa500; color:white; padding:5px 12px; border-radius:5px; font-size: 14px;'><b>🟠 Riposo Fisso</b></div></div>""", unsafe_allow_html=True)
    
    c_cal = st.columns(5)
    for idx, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[idx]: genera_mini_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, m)

# --- 5. IMPOSTAZIONI STAGIONE (FIXED) ---
elif menu == "⚙️ Impostazioni Stagione":
    st.header("Configurazione Stagione Operativa")
    st.write("Queste date influenzano i calendari e la dashboard.")
    with st.form("season_form"):
        new_ap = st.date_input("Data Apertura Parco:", data_apertura)
        new_ch = st.date_input("Data Chiusura Parco:", data_chiusura)
        if st.form_submit_button("💾 Applica e Salva Date"):
            # Creiamo un nuovo dataframe config per essere sicuri della struttura
            current_config = data["config"].copy()
            
            # Funzione per aggiornare o aggiungere
            def update_conf(ruolo, valore):
                global current_config
                if ruolo in current_config["Ruolo"].values:
                    current_config.loc[current_config["Ruolo"] == ruolo, "Password"] = str(valore)
                else:
                    new_row = pd.DataFrame([{"Ruolo": ruolo, "Password": str(valore)}])
                    current_config = pd.concat([current_config, new_row], ignore_index=True)

            update_conf("Apertura", str(new_ap))
            update_conf("Chiusura", str(new_ch))
            
            conn.update(worksheet="Config", data=current_config)
            st.cache_data.clear()
            st.success("✅ Date salvate con successo! I calendari sono stati aggiornati.")
            st.rerun()

# --- 6. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno Personale")
    tipo = st.radio("Modalità:", ["Giorno Singolo", "Intervallo"], horizontal=True)
    if tipo == "Giorno Singolo": date_list = [st.date_input("Giorno:", datetime.now())]
    else:
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
        date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)] if len(dr) == 2 else []
    
    if date_list:
        f_in = {p: st.number_input(f"{p}:", min_value=0, key=f"f_{p}") for p in lista_postazioni}
        if st.button("Salva"):
            new = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_in.items()]
            old = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new)], ignore_index=True))
            st.cache_data.clear(); st.rerun()

# --- 7. ALTRE VOCI ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica")
    # Logica anagrafica (come prima)...
    st.info("Gestisci qui i dipendenti e i loro riposi fissi.")

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True))
        st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("pwd"):
        ap = st.text_input("Admin", value=str(conf_df[conf_df["Ruolo"]=="Admin"]["Password"].values[0]))
        up = st.text_input("User", value=str(conf_df[conf_df["Ruolo"]=="User"]["Password"].values[0]))
        if st.form_submit_button("Aggiorna"):
            new_c = conf_df.copy()
            new_c.loc[new_c["Ruolo"] == "Admin", "Password"] = ap
            new_c.loc[new_c["Ruolo"] == "User", "Password"] = up
            conn.update(worksheet="Config", data=new_c); st.success("Salvate!"); st.rerun()
