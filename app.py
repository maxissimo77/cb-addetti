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

# --- CARICAMENTO DATI (CORRETTO) ---
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
    
    # Ricaviamo l'indice del riposo (0=Lunedì, 6=Domenica)
    idx_riposo_fisso = mappa_giorni.get(riposo_fisso, -1)
    
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    
    for week in cal:
        html += '<tr style="height: 30px;">'
        for i, day in enumerate(week): # i va da 0 (Lunedì) a 6 (Domenica)
            if day == 0: 
                html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                curr_d = datetime(anno, mese, day).date()
                d_str = f"{anno}-{mese:02d}-{day:02d}"
                is_open = data_apertura <= curr_d <= data_chiusura
                
                if not is_open:
                    bg, tx, label = "#f0f0f0", "#bfbfbf", f"<span style='text-decoration: line-through;'>{day}</span>"
                else:
                    # Cerchiamo se esiste uno stato specifico nel foglio Disponibilità
                    stato_row = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]
                    label = str(day)
                    
                    if not stato_row.empty:
                        stato_val = str(stato_row["Stato"].iloc[0]).upper()
                        if "NON" in stato_val: bg, tx = "#ff4b4b", "white"
                        elif "PERMESSO" in stato_val: bg, tx = "#00008B", "white"
                        elif "ASSENTE" in stato_val: bg, tx = "#000000", "white"
                        elif "MALATTIA" in stato_val: bg, tx = "#696969", "white"
                        elif "DISPONIBILE" in stato_val: bg, tx = "#29b05c", "white"
                        else: bg, tx = "transparent", "inherit"
                    # SE non c'è uno stato specifico, controlliamo se è il giorno di riposo fisso
                    elif i == idx_riposo_fisso:
                        bg, tx = "#ffa500", "white" # ARANCIONE per il riposo
                    else:
                        bg, tx = "transparent", "inherit"
                
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
    st.header("Stato Occupazione Postazioni")
    input_d = st.date_input("Inizio visualizzazione (settimana):", default_date)
    
    data_inizio = input_d
    date_range = [data_inizio + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning(f"⚠️ Parco CHIUSO nel periodo selezionato.")
    else:
        # Funzioni helper
        def to_date_only(val):
            try: return pd.to_datetime(val).date()
            except: return None

        def norm(s):
            if pd.isna(s): return ""
            return str(s).strip().upper()

        # Funzione interna per generare la card HTML
        def genera_card(titolo, color, num, req, staff_list):
            nomi_html = "".join([f"<div style='font-size: 13px; border-bottom: 1px solid #f0f0f0; padding: 4px 0; color: #444;'>• {r['Nome']} {r['Cognome']}</div>" for _, r in staff_list.iterrows()])
            if not nomi_html: nomi_html = "<div style='color:gray; font-size:12px; font-style:italic;'>Nessuno disponibile</div>"
            
            return f"""
                <div style="border: 1px solid #ddd; border-radius: 10px; margin-bottom: 15px; background: white; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <div style="background: {color}; color: white; padding: 8px; border-radius: 10px 10px 0 0; text-align: center; font-weight: bold; font-size: 13px;">{titolo.upper()}</div>
                    <div style="padding: 12px; text-align: center;">
                        <div style="font-size: 22px; font-weight: bold; color: #333;">{num} / {req}</div>
                        <div style="margin-top: 8px; text-align: left; border-top: 1px solid #eee; padding-top: 5px;">{nomi_html}</div>
                    </div>
                </div>
            """

        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                giorno_sett_oggi = norm(giorni_ita[d_tab.weekday()])
                
                # 1. FILTRI DATI
                df_f = data["fabbisogno"].copy()
                df_f['d_pure'] = df_f['Data'].apply(to_date_only)
                fabb_oggi = df_f[df_f['d_pure'] == d_tab]
                
                df_dis = data["disp"].copy()
                df_dis['d_pure'] = df_dis['Data'].apply(to_date_only)
                disp_oggi = df_dis[df_dis['d_pure'] == d_tab]
                disp_oggi["Stato_Norm"] = disp_oggi["Stato"].apply(norm)
                
                nomi_assenti = disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]
                lista_nera_nomi = (nomi_assenti["Nome"].apply(norm) + nomi_assenti["Cognome"].apply(norm)).tolist()

                # 2. COSTRUZIONE LISTA PRESENTI
                staff_base = data["addetti"].copy()
                staff_base["ID_UNICO"] = staff_base["Nome"].apply(norm) + staff_base["Cognome"].apply(norm)
                staff_base["RIPOSO_NORM"] = staff_base["GiornoRiposoSettimanale"].apply(norm)

                presenti_effettivi = staff_base[
                    (staff_base["RIPOSO_NORM"] != giorno_sett_oggi) & 
                    (~staff_base["ID_UNICO"].isin(lista_nera_nomi))
                ].copy()

                # 3. LAYOUT A 3 COLONNE "MASONRY"
                col1, col2, col3 = st.columns(3)

                # --- COLONNA 1: ATTRAZIONI ---
                with col1:
                    m = "Addetto Attrazioni"
                    s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                    f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                    r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                    n = len(s_p)
                    c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                    st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)

                # --- COLONNA 2: BAGNANTI + BUNGEE (Insieme per stare vicini) ---
                with col2:
                    # Assistente Bagnanti
                    m1 = "Assistente Bagnanti"
                    s_p1 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m1)]
                    f_r1 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m1)]
                    r1 = int(f_r1["Quantita"].iloc[0]) if not f_r1.empty else 0
                    n1 = len(s_p1)
                    c1 = "#29b05c" if n1 >= r1 and r1 > 0 else "#ff4b4b" if n1 < r1 else "#808080"
                    st.markdown(genera_card(m1, c1, n1, r1, s_p1), unsafe_allow_html=True)

                    # Bungee Jumping (Subito sotto nella stessa colonna)
                    m2 = "Bungee Jumping"
                    s_p2 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m2)]
                    f_r2 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m2)]
                    r2 = int(f_r2["Quantita"].iloc[0]) if not f_r2.empty else 0
                    n2 = len(s_p2)
                    c2 = "#29b05c" if n2 >= r2 and r2 > 0 else "#ff4b4b" if n2 < r2 else "#808080"
                    st.markdown(genera_card(m2, c2, n2, r2, s_p2), unsafe_allow_html=True)

                # --- COLONNA 3: RADIO ---
                with col3:
                    m3 = "Radio"
                    s_p3 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m3)]
                    f_r3 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m3)]
                    r3 = int(f_r3["Quantita"].iloc[0]) if not f_r3.empty else 0
                    n3 = len(s_p3)
                    c3 = "#29b05c" if n3 >= r3 and r3 > 0 else "#ff4b4b" if n3 < r3 else "#808080"
                    st.markdown(genera_card(m3, c3, n3, r3, s_p3), unsafe_allow_html=True)
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
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.markdown("<div style='margin-top: 25px; border-top: 1px solid rgba(128,128,128,0.3); padding-top: 15px;'><b>Riposo Non Definito:</b></div>", unsafe_allow_html=True)
                html_nd = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; margin-bottom: 20px;">'
                for _, r in non_def.iterrows():
                    html_nd += f"<div style='border: 2px solid #ffa500; padding: 8px 15px; border-radius: 8px; font-weight: bold; background-color: rgba(255, 165, 0, 0.1); color: #333;'>{r['Nome']} {r['Cognome']}</div>"
                st.markdown(html_nd + '</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi Settimanali")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[df_mod["Mansione"] == m]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            conteggi = add_m["GiornoRiposoSettimanale"].value_counts()
            cols_c = st.columns(7)
            for i, g in enumerate(giorni_ita):
                n_rip = conteggi.get(g, 0)
                with cols_c[i]: 
                    st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.05); border: 1px solid rgba(128,128,128,0.1); border-radius:5px; padding:5px;'><small>{g[:3]}</small><br><b style='color:#1f77b4;'>{n_rip}</b></div>", unsafe_allow_html=True)
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            for idx, row in add_m.iterrows():
                with st.container():
                    col_nome, col_scelta = st.columns([2, 1])
                    with col_nome:
                        st.markdown(f"""<div style="padding-top: 15px; padding-bottom: 10px; border-bottom: 1px solid #f0f2f6;"><span style="font-size: 16px;">{row['Nome']} <b>{row['Cognome']}</b></span></div>""", unsafe_allow_html=True)
                    with col_scelta:
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        df_mod.at[idx, 'GiornoRiposoSettimanale'] = st.selectbox(f"Riposo {idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"r_rap_{idx}", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
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
    with st.expander("Modifica Disponibilità / Assenze"):
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
        st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile", "Permesso", "Assente", "Malattia"], horizontal=True)
        if st.button("Salva Date") and len(dr) == 2:
            d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": row_d['Nome'], "Cognome": row_d['Cognome'], "Data": d, "Stato": st_r} for d in d_list])
            old = data["disp"][~((data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True)); st.cache_data.clear(); st.rerun()

# --- 5. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Personale")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        with st.form("edit"):
            st.subheader(f"Modifica: {row['Nome']} {row['Cognome']}")
            c1, c2 = st.columns(2)
            en, ec = c1.text_input("Nome", row['Nome']), c2.text_input("Cognome", row['Cognome'])
            em = c1.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = c2.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7)
            val_cont = str(row['Contestazioni']) if 'Contestazioni' in row and pd.notna(row['Contestazioni']) else ""
            e_cont = st.text_area("Lettere di Contestazione", value=val_cont)
            cb1, cb2, _ = st.columns([1,1,2])
            if cb1.form_submit_button("💾 Salva"):
                new_data_row = [en, ec, em, er, e_cont]
                cols_target = ["Nome", "Cognome", "Mansione", "GiornoRiposoSettimanale", "Contestazioni"]
                for i, col in enumerate(cols_target):
                    data["addetti"].at[idx, col] = new_data_row[i]
                conn.update(worksheet="Addetti", data=data["addetti"]); st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
            if cb2.form_submit_button("❌ Annulla"):
                st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco Staff", "➕ Nuovo Addetto"])
        with t1:
            for idx, r in data["addetti"].iterrows():
                disp_addetto = data["disp"][(data["disp"]["Nome"] == r['Nome']) & (data["disp"]["Cognome"] == r['Cognome'])]
                conteggi = disp_addetto["Stato"].value_counts()
                
                # MODIFICA RICHIESTA: Font ingrandito (15px) e grassetto
                sum_str = f"✅ Disponibile: {conteggi.get('Disponibile', 0)} | 🔵 Permessi: {conteggi.get('Permesso', 0)} | ⚫ Assente: {conteggi.get('Assente', 0)} | 🔘 Malattia: {conteggi.get('Malattia', 0)}"

                with st.container():
                    c1, c2, c3 = st.columns([3, 3, 1])
                    has_cont = 'Contestazioni' in r and pd.notna(r['Contestazioni']) and str(r['Contestazioni']).strip() != ""
                    c1.markdown(f"**{r['Nome']} {r['Cognome']}**{' 🚩' if has_cont else ''}")
                    c2.caption(f"{r['Mansione']} | Riposo: {r['GiornoRiposoSettimanale']}")
                    if c3.button("✏️", key=f"ed_{idx}"): st.session_state["editing_id"] = idx; st.rerun()
                    
                    # RIGA MODIFICATA (Font ingrandito a 15px e Bold)
                    st.markdown(f"<div style='font-size: 15px; font-weight: bold; color: #444; margin-top: -10px; margin-bottom: 5px;'>{sum_str}</div>", unsafe_allow_html=True)
                    
                    if has_cont:
                        with st.expander("Vedi contestazioni"): st.warning(r['Contestazioni'])
                    st.divider()
        with t2:
            with st.form("n"):
                nn, nc = st.text_input("Nome"), st.text_input("Cognome")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                ncnt = st.text_area("Contestazioni iniziali")
                if st.form_submit_button("Aggiungi"):
                    new_member = pd.DataFrame([{"Nome":nn, "Cognome":nc, "Mansione":nm, "GiornoRiposoSettimanale":nr, "Contestazioni":ncnt}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new_member], ignore_index=True))
                    st.cache_data.clear(); st.rerun()

# --- ALTRE SEZIONI ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno")
    tipo = st.radio("Modalità:", ["Giorno Singolo", "Intervallo"], horizontal=True)
    if tipo == "Giorno Singolo":
        dt = st.date_input("Giorno:", default_date); date_list = [dt]
    else:
        dr = st.date_input("Periodo:", value=[]); date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)] if len(dr) == 2 else []
    if date_list:
        f_inputs = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("💾 Salva"):
            new_r = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_inputs.items()]
            old_d = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
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
