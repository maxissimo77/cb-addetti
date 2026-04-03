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
        data_dict = {
            "addetti": conn.read(worksheet="Addetti"),
            "disp": conn.read(worksheet="Disponibilita"),
            "fabbisogno": conn.read(worksheet="Fabbisogno"),
            "postazioni": conn.read(worksheet="Postazioni"),
            "config": conn.read(worksheet="Config")
        }
        # Fix dtypes per Contestazioni
        if "Contestazioni" in data_dict["addetti"].columns:
            data_dict["addetti"]["Contestazioni"] = data_dict["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', 'NAT', '<NA>'], '')
        else:
            data_dict["addetti"]["Contestazioni"] = ""
        return data_dict
    except Exception as e:
        st.error(f"⚠️ Errore API: {e}"); st.stop()

data = get_all_data()

# --- CONFIGURAZIONE LOGICA ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
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
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- SIDEBAR ---
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "👥 Gestione Anagrafica", "⚙️ Pianifica Fabbisogno", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione"]
menu = st.sidebar.radio("Menu", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Stato Occupazione Postazioni")
    input_d = st.date_input("Settimana del:", default_date)
    date_range = [input_d + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte: st.warning("Parco Chiuso.")
    else:
        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                curr_date = date_aperte[idx]
                g_sett = giorni_ita[curr_date.weekday()]
                fabb = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str).str.contains(str(curr_date), na=False)]
                staff_presente = data["addetti"][data["addetti"]["GiornoRiposoSettimanale"] != g_sett]
                
                cols = st.columns(3)
                for i, post in enumerate(lista_postazioni):
                    pres = staff_presente[staff_presente["Mansione"] == post]
                    f_row = fabb[fabb["Mansione"] == post]
                    req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                    color = "#29b05c" if len(pres) >= req and req > 0 else "#ff4b4b" if len(pres) < req else "#1f77b4"
                    with cols[i % 3]:
                        st.markdown(f'<div style="border:1px solid #ddd; border-radius:10px; margin-bottom:20px;"><div style="background:{color}; color:white; padding:10px; border-radius:10px 10px 0 0; text-align:center; font-weight:bold;">{post}</div><div style="padding:15px; text-align:center;"><span style="font-size:22px; font-weight:bold;">{len(pres)} / {req}</span><div style="text-align:left; margin-top:10px; font-size:13px;">' + "".join([f"• {r['Nome']} {r['Cognome']}<br>" for _,r in pres.iterrows()]) + '</div></div></div>', unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI (7 COLONNE + NON DEFINITI) ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Riepilogo Giorni di Riposo")
    for m in lista_postazioni:
        with st.expander(f"📍 {m}", expanded=True):
            add_m = data["addetti"][data["addetti"]["Mansione"] == m]
            c_rip = st.columns(7)
            for i, g in enumerate(giorni_ita):
                with c_rip[i]:
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.2); padding:5px; border-radius:5px;'><b>{g}</b></div>", unsafe_allow_html=True)
                    chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                    for _, r in chi.iterrows():
                        st.markdown(f"<div style='text-align:center; background:rgba(31,119,180,0.1); padding:8px 2px; border-radius:5px; margin:10px 0; border:1px solid rgba(31,119,180,0.2); font-size:13px;'>{r['Nome']} {r['Cognome']}</div>", unsafe_allow_html=True)
            
            # --- AGGIUNTA NON DEFINITI ---
            nd = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not nd.empty:
                st.markdown("<div style='margin-top:15px; font-weight:bold;'>Riposo Non Definito:</div>", unsafe_allow_html=True)
                html_nd = '<div style="display:flex; flex-wrap:wrap; gap:10px; margin-top:10px;">'
                for _, r in nd.iterrows():
                    html_nd += f"<div style='border:2px solid #ffa500; padding:5px 12px; border-radius:8px; background:rgba(255,165,0,0.1); font-weight:bold;'>{r['Nome']} {r['Cognome']}</div>"
                st.markdown(html_nd + '</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA (CON SOMMA GIORNALIERA) ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            # --- AGGIUNTA SOMMA PER GIORNO ---
            conteggi = add_m["GiornoRiposoSettimanale"].value_counts()
            c_count = st.columns(7)
            for i, g in enumerate(giorni_ita):
                n_rip = conteggi.get(g, 0)
                with c_count[i]:
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.05); border:1px solid #ddd; border-radius:5px; padding:5px;'><small>{g[:3]}</small><br><b style='color:#1f77b4;'>{n_rip}</b></div>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            for idx, row in add_m.iterrows():
                with st.container():
                    cn, cs = st.columns([2, 1])
                    with cn: st.markdown(f"<div style='padding:18px 0 10px 0; border-bottom:1px solid #eee;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                    with cs:
                        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
                        df_mod.at[idx, 'GiornoRiposoSettimanale'] = st.selectbox(f"R_{idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"rr_{idx}", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salva Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Salvato!"); st.rerun()

# --- 4. ANAGRAFICA (CON CONTESTAZIONI) ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Personale")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]; row = data["addetti"].loc[idx]
        with st.form("edit"):
            en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
            em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = st.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7)
            val_c = str(row['Contestazioni']) if pd.notna(row['Contestazioni']) else ""
            e_cont = st.text_area("Lettere di Contestazione (Note/Date)", value=val_c)
            if st.form_submit_button("Salva"):
                for col, val in zip(["Nome","Cognome","Mansione","GiornoRiposoSettimanale","Contestazioni"], [en,ec,em,er,e_cont]):
                    data["addetti"].at[idx, col] = str(val)
                conn.update(worksheet="Addetti", data=data["addetti"]); st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
            if st.form_submit_button("Annulla"): st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco", "➕ Nuovo"])
        with t1:
            for idx, r in data["addetti"].iterrows():
                c1, c2, c3 = st.columns([3, 3, 1])
                has_c = str(r['Contestazioni']).strip() != ""
                c1.markdown(f"**{r['Nome']} {r['Cognome']}** {'🚩' if has_c else ''}")
                c2.caption(f"{r['Mansione']} | Riposo: {r['GiornoRiposoSettimanale']}")
                if c3.button("✏️", key=f"e_{idx}"): st.session_state["editing_id"] = idx; st.rerun()
                if has_c: 
                    with st.expander("Dettagli contestazioni"): st.warning(r['Contestazioni'])
                st.divider()
        with t2:
            with st.form("n"):
                nn, nc = st.text_input("Nome"), st.text_input("Cognome")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                ncnt = st.text_area("Contestazioni Iniziali")
                if st.form_submit_button("Aggiungi"):
                    new = pd.DataFrame([{"Nome":str(nn),"Cognome":str(nc),"Mansione":str(nm),"GiornoRiposoSettimanale":str(nr),"Contestazioni":str(ncnt)}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new], ignore_index=True)); st.cache_data.clear(); st.rerun()

# --- ALTRE SEZIONI ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Pianifica Fabbisogno")
    dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
    if len(dr) == 2:
        date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)]
        f_in = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("Salva Fabbisogno"):
            new_f = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_in.items()]
            old = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old, pd.DataFrame(new_f)], ignore_index=True)); st.cache_data.clear(); st.success("Fabbisogno aggiornato!"); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Date Apertura/Chiusura")
    with st.form("set"):
        na, nc = st.date_input("Apertura", data_apertura), st.date_input("Chiusura", data_chiusura)
        if st.form_submit_button("Salva Date"):
            new_conf = data["config"].copy()
            new_conf.loc[new_conf["Ruolo"]=="Apertura","Password"] = str(na)
            new_conf.loc[new_conf["Ruolo"]=="Chiusura","Password"] = str(nc)
            conn.update(worksheet="Config", data=new_conf); st.cache_data.clear(); st.success("Date salvate!"); st.rerun()
