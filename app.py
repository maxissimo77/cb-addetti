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
        # Forza pulizia dtypes per evitare l'errore TypeError
        if "Contestazioni" in data_dict["addetti"].columns:
            data_dict["addetti"]["Contestazioni"] = data_dict["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', 'NAT', '<NA>'], '')
        else:
            data_dict["addetti"]["Contestazioni"] = ""
        return data_dict
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
except:
    admin_pwd, user_pwd = "admin", "staff"
    data_apertura, data_chiusura = datetime(2026, 5, 16).date(), datetime(2026, 9, 13).date()

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

# --- 1. DASHBOARD (POSTAZIONI IN ALTO) ---
if menu == "📊 Dashboard":
    st.header("Stato Occupazione Postazioni")
    input_d = st.date_input("Inizio visualizzazione (settimana):", default_date)
    data_inizio = input_d.date() if hasattr(input_d, 'date') else input_d
    date_range = [data_inizio + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning(f"⚠️ Parco CHIUSO nel periodo selezionato.")
    else:
        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                curr_date = date_aperte[idx]
                g_sett = giorni_ita[curr_date.weekday()]
                fabb = data["fabbisogno"][data["fabbisogno"]["Data"].astype(str).str.contains(str(curr_date), na=False)]
                disp = data["disp"][data["disp"]["Data"].astype(str).str.contains(str(curr_date), na=False)]
                staff_totale = data["addetti"].copy()
                staff_presente = staff_totale[staff_totale["GiornoRiposoSettimanale"] != g_sett]
                
                if not disp.empty:
                    disp['Key'] = disp['Nome'] + " " + disp['Cognome']
                    non_disp_keys = disp[disp["Stato"].astype(str).str.contains("NON", case=False, na=False)]['Key'].tolist()
                    staff_presente['Key'] = staff_presente['Nome'] + " " + staff_presente['Cognome']
                    staff_presente = staff_presente[~staff_presente['Key'].isin(non_disp_keys)]
                
                cols = st.columns(3)
                for i, post in enumerate(lista_postazioni):
                    presenti = staff_presente[staff_presente["Mansione"] == post]
                    f_row = fabb[fabb["Mansione"] == post]
                    req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                    num_pres = len(presenti)
                    color = "#29b05c" if num_pres >= req and req > 0 else "#ff4b4b" if num_pres < req else "#1f77b4"
                    if req == 0: color = "#808080"
                    with cols[i % 3]:
                        st.markdown(f"""
                            <div style="border: 1px solid #ddd; border-radius: 10px; padding: 0px; margin-bottom: 20px; background-color: white;">
                                <div style="background-color: {color}; color: white; padding: 10px; border-radius: 10px 10px 0 0; text-align: center; font-weight: bold;">{post}</div>
                                <div style="padding: 15px; text-align: center;">
                                    <span style="font-size: 24px; font-weight: bold;">{num_pres} / {req}</span>
                                    <div style="margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px; text-align: left;">
                                        {"".join([f"<div style='font-size: 13px;'>• {r['Nome']} {r['Cognome']}</div>" for _, r in presenti.iterrows()]) if not presenti.empty else "<i>Nessuno</i>"}
                                    </div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI (7 COLONNE) ---
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
                        st.markdown(f"<div style='text-align: center; background-color: rgba(31,119,180,0.1); padding: 8px 2px; border-radius: 5px; margin: 10px 0; border: 1px solid rgba(31,119,180,0.2); font-size: 13px;'>{r['Nome']} {r['Cognome']}</div>", unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA (SPAZIATURE FISSA) ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            for idx, row in add_m.iterrows():
                with st.container():
                    c_n, c_s = st.columns([2, 1])
                    with c_n:
                        st.markdown(f"<div style='padding: 18px 0 10px 0; border-bottom: 1px solid #eee; font-size: 16px;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                    with c_s:
                        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
                        df_mod.at[idx, 'GiornoRiposoSettimanale'] = st.selectbox(f"R_{idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"rr_{idx}", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salva Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Salvato!"); st.rerun()

# --- 5. GESTIONE ANAGRAFICA (CON FIX TYPEERROR) ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]; row = data["addetti"].loc[idx]
        with st.form("edit"):
            en, ec = st.text_input("Nome", row['Nome']), st.text_input("Cognome", row['Cognome'])
            em = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = st.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7)
            val_c = str(row['Contestazioni']) if pd.notna(row['Contestazioni']) else ""
            e_cont = st.text_area("Contestazioni", value=val_c)
            if st.form_submit_button("Salva"):
                for c, v in zip(["Nome","Cognome","Mansione","GiornoRiposoSettimanale","Contestazioni"], [en,ec,em,er,e_cont]):
                    data["addetti"].at[idx, c] = str(v)
                conn.update(worksheet="Addetti", data=data["addetti"]); st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
            if st.form_submit_button("Annulla"): st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["Elenco", "Nuovo"])
        with t1:
            for idx, r in data["addetti"].iterrows():
                c1, c2, c3 = st.columns([3, 3, 1])
                has_c = str(r['Contestazioni']).strip() != ""
                c1.markdown(f"**{r['Nome']} {r['Cognome']}** {'🚩' if has_c else ''}")
                c2.caption(f"{r['Mansione']} | {r['GiornoRiposoSettimanale']}")
                if c3.button("✏️", key=f"e_{idx}"): st.session_state["editing_id"] = idx; st.rerun()
                if has_c: 
                    with st.expander("Dettagli contestazioni"): st.warning(r['Contestazioni'])
                st.divider()
        with t2:
            with st.form("n"):
                nn, nc = st.text_input("Nome"), st.text_input("Cognome")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                ncnt = st.text_area("Contestazioni")
                if st.form_submit_button("Aggiungi"):
                    new = pd.DataFrame([{"Nome":str(nn),"Cognome":str(nc),"Mansione":str(nm),"GiornoRiposoSettimanale":str(nr),"Contestazioni":str(ncnt)}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new], ignore_index=True)); st.cache_data.clear(); st.rerun()

# --- ALTRE SEZIONI ---
# (Pianifica Fabbisogno, Impostazioni, Password, Postazioni rimangono come prima)
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno")
    tipo = st.radio("Modalità:", ["Giorno Singolo", "Intervallo"], horizontal=True)
    if tipo == "Giorno Singolo":
        dt = st.date_input("Giorno:", default_date, min_value=data_apertura, max_value=data_chiusura); date_list = [dt]
    else:
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura); date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)] if len(dr) == 2 else []
    if date_list:
        f_inputs = {p: st.number_input(f"{p}:", min_value=0, key=f"f_{p}") for p in lista_postazioni}
        if st.button("💾 Salva", type="primary"):
            new_r = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_inputs.items()]
            old_d = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old_d, pd.DataFrame(new_r)], ignore_index=True)); st.cache_data.clear(); st.rerun()

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Configurazione Stagione")
    with st.form("s"):
        na = st.date_input("Inizio:", data_apertura); nc = st.date_input("Fine:", data_chiusura)
        if st.form_submit_button("Salva"):
            conf_agg = data["config"].copy()
            conf_agg.loc[conf_agg["Ruolo"] == "Apertura", "Password"] = str(na)
            conf_agg.loc[conf_agg["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=conf_agg); st.cache_data.clear(); st.rerun()

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("p"):
        ap = st.text_input("Admin", value=admin_pwd); up = st.text_input("User", value=user_pwd)
        if st.form_submit_button("Salva"):
            new_conf = data["config"].copy(); new_conf.loc[new_conf["Ruolo"]=="Admin", "Password"] = ap; new_conf.loc[new_conf["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=new_conf); st.cache_data.clear(); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])
