import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar
import urllib.parse
from io import BytesIO

# --- LIBRERIE PER PDF (Originali) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Caribe Bay - Staff", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)
pd.options.mode.string_storage = "python"

# --- CSS PERSONALIZZATO PER GRAFICA ACCATTIVANTE ---
st.markdown("""
<style>
    /* Sfondo e font generale */
    .main { background-color: #f8f9fa; }
    
    /* Card moderne per la Dashboard */
    .card-container {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        background: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .card-container:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    
    /* Badge nomi */
    .name-badge {
        background: #f1f3f5;
        color: #212529;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 3px 0;
        border-left: 4px solid #1f77b4;
        display: block;
    }

    /* Pulsanti Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARICAMENTO DATI (Logica Originale) ---
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
        res["addetti"] = res["addetti"].astype(object)
        if "Contestazioni" in res["addetti"].columns:
            res["addetti"]["Contestazioni"] = res["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', '<NA>'], '')
        else: res["addetti"]["Contestazioni"] = ""
        if "Stato Rapporto" not in res["addetti"].columns: res["addetti"]["Stato Rapporto"] = "Attivo"
        if "Data Cessazione" not in res["addetti"].columns: res["addetti"]["Data Cessazione"] = ""
        if "Cellulare" not in res["addetti"].columns: res["addetti"]["Cellulare"] = ""
        else: res["addetti"]["Cellulare"] = res["addetti"]["Cellulare"].astype(str).replace(r'\.0$', '', regex=True).replace(['nan', 'None', '<NA>'], '')
        if "Email" not in res["addetti"].columns: res["addetti"]["Email"] = ""
        else: res["addetti"]["Email"] = res["addetti"]["Email"].astype(str).replace(['nan', 'None', '<NA>'], '')
        return res
    except Exception as e:
        st.error(f"⚠️ Errore di connessione: {e}"); st.stop()

data = get_all_data()

# --- UTILITY WHATSAPP ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "" or tel == "nan": return None
    if len(tel) <= 10: tel = "39" + tel
    msg = f"Ciao {row['Nome']}, "
    msg_encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{tel}?text={msg_encoded}"

# --- FUNZIONE GENERAZIONE PDF (Originale) ---
def genera_pdf_riposi(mansione, df_mansione, giorni_ita):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Riepilogo Riposi Settimanali - {mansione}", styles['Title']))
    elements.append(Spacer(1, 20))
    header = [g.upper() for g in giorni_ita]
    mappa_persone = {g: [f"{r['Nome']} {r['Cognome']}" for _, r in df_mansione[df_mansione["GiornoRiposoSettimanale"] == g].iterrows()] for g in giorni_ita}
    max_rows = max([len(v) for v in mappa_persone.values()]) if mappa_persone else 0
    data_tabella = [header]
    for i in range(max_rows):
        fila = []
        for g in giorni_ita:
            persone = mappa_persone[g]; fila.append(persone[i] if i < len(persone) else "")
        data_tabella.append(fila)
    t = Table(data_tabella, colWidths=[110]*7)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t); doc.build(elements); buffer.seek(0)
    return buffer

# --- ESTRAZIONE CONFIGURAZIONE ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
    admin_pwd, user_pwd = "admin", "staff"; data_apertura = datetime(2026, 5, 16).date(); data_chiusura = datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    col_p1, col_p2, col_p3 = st.columns([2, 1, 2])
    with col_p2: st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col_p4, col_p5, col_p6 = st.columns([1.5, 1, 1.5])
    with col_p5:
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi", use_container_width=True):
            if pwd_input == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
            elif pwd_input == user_pwd: st.session_state["role"] = "User"; st.rerun()
            else: st.error("❌ Password errata.")
    st.stop()

# --- VARIABILI GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys()); opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# --- FUNZIONE CALENDARIO ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita.get(mese, 'Mese')}</b></div>", unsafe_allow_html=True)
    mappa_lower = {k.lower(): v for k, v in mappa_giorni.items()}
    r_pulito = str(riposo_fisso).strip().lower()
    idx_riposo_fisso = mappa_lower.get(r_pulito, -1)
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    for week in cal:
        html += '<tr style="height: 30px;">'
        for i, day in enumerate(week):
            if day == 0: html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                curr_d = datetime(anno, mese, day).date(); d_str = curr_d.strftime("%Y-%m-%d")
                is_open = data_apertura <= curr_d <= data_chiusura; bg, tx, label = "transparent", "inherit", str(day)
                if not is_open: bg, tx, label = "#f0f0f0", "#bfbfbf", f"<span style='text-decoration: line-through;'>{day}</span>"
                else:
                    stato_row = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]
                    if i == idx_riposo_fisso:
                        bg, tx = "#ffa500", "white"
                        if not stato_row.empty:
                            s_val = str(stato_row["Stato"].iloc[0]).upper()
                            if "NON" in s_val: bg, tx = "#ff4b4b", "white"
                            elif "PERMESSO" in s_val: bg, tx = "#00008B", "white"
                            elif "ASSENTE" in s_val: bg, tx = "#000000", "white"
                            elif "MALATTIA" in s_val: bg, tx = "#696969", "white"
                    else:
                        if not stato_row.empty:
                            s_val = str(stato_row["Stato"].iloc[0]).upper()
                            if "NON" in s_val: bg, tx = "#ff4b4b", "white"
                            elif "PERMESSO" in s_val: bg, tx = "#00008B", "white"
                            elif "ASSENTE" in s_val: bg, tx = "#000000", "white"
                            elif "MALATTIA" in s_val: bg, tx = "#696969", "white"
                            elif "DISPONIBILE" in s_val: bg, tx = "#29b05c", "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid rgba(128,128,128,0.2); font-weight:bold;">{label}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione", "🔑 Gestione Password"]
menu = st.sidebar.radio("NAVIGAZIONE", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD (Logica Originale + Card Moderne) ---
if menu == "📊 Dashboard":
    st.title("📍 Stato Occupazione Parco")
    input_d = st.date_input("Inizio visualizzazione (settimana):", default_date)
    date_range = [input_d + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning(f"⚠️ Parco CHIUSO nel periodo selezionato.")
    else:
        def to_date_only(val):
            try: return pd.to_datetime(val).date()
            except: return None
        def norm(s):
            if pd.isna(s): return ""
            return str(s).strip().upper()
            
        def genera_card(titolo, color, num, req, staff_list):
            nomi_html = "".join([f"<div class='name-badge'>• {r['Nome']} {r['Cognome']}</div>" for _, r in staff_list.iterrows()])
            if not nomi_html: nomi_html = "<div style='color:gray; font-size:12px; font-style:italic; padding:10px;'>Nessuno disponibile</div>"
            return f"""
                <div class="card-container">
                    <div style="background: {color}; color: white; padding: 10px; border-radius: 12px 12px 0 0; text-align: center; font-weight: bold; font-size: 0.9rem;">{titolo.upper()}</div>
                    <div style="padding: 15px; text-align: center;">
                        <div style="font-size: 26px; font-weight: bold; color:#333;">{num} <span style="font-size:16px; color:#999;">/ {req}</span></div>
                        <div style="margin-top: 10px; text-align: left; border-top: 1px solid #f0f0f0; padding-top: 10px;">{nomi_html}</div>
                    </div>
                </div>
            """

        tabs = st.tabs([d.strftime("%A %d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                giorno_sett_oggi = norm(giorni_ita[d_tab.weekday()])
                df_f = data["fabbisogno"].copy(); df_f['d_pure'] = df_f['Data'].apply(to_date_only)
                fabb_oggi = df_f[df_f['d_pure'] == d_tab]
                df_dis = data["disp"].copy(); df_dis['d_pure'] = df_dis['Data'].apply(to_date_only)
                disp_oggi = df_dis[df_dis['d_pure'] == d_tab]
                disp_oggi["Stato_Norm"] = disp_oggi["Stato"].apply(norm)
                lista_nera_nomi = (disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]["Nome"].apply(norm) + disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]["Cognome"].apply(norm)).tolist()
                
                staff_base = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"].copy()
                staff_base["ID_UNICO"] = staff_base["Nome"].apply(norm) + staff_base["Cognome"].apply(norm)
                staff_base["RIPOSO_NORM"] = staff_base["GiornoRiposoSettimanale"].apply(norm)
                presenti_effettivi = staff_base[(staff_base["RIPOSO_NORM"] != giorno_sett_oggi) & (~staff_base["ID_UNICO"].isin(lista_nera_nomi))]

                col1, col2, col3 = st.columns(3)
                mansioni_target = ["Addetto Attrazioni", "Assistente Bagnanti", "Bungee Jumping", "Radio"]
                for i, m in enumerate(mansioni_target):
                    with [col1, col2, col3][i % 3]:
                        s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                        f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]; r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0; n = len(s_p)
                        c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                        st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI (Layout Corretto e Senza Errori) ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.title("📅 Piano Riposi Settimanali")
    
    for m in lista_postazioni:
        # Recupero addetti attivi per mansione
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        
        if not add_m.empty:
            col_tit, col_pdf = st.columns([5, 1])
            with col_tit:
                st.markdown(f"### 📍 {m}")
            with col_pdf:
                st.download_button("📄 PDF", genera_pdf_riposi(m, add_m, giorni_ita), f"Riposi_{m}.pdf", "application/pdf", key=f"pdf_{m}")
            
            # --- BOX 1: SETTIMANA (LUN-DOM) ---
            with st.container(border=True):
                cols = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with cols[i]:
                        st.markdown(f"""
                            <div style="background:#1f77b4; color:white; border-radius:5px; padding:2px; text-align:center; font-weight:bold; font-size:12px; margin-bottom:10px;">
                                {g[:3].upper()}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Filtro persone per il giorno specifico
                        persone_giorno = add_m[add_m["GiornoRiposoSettimanale"] == g]
                        for _, r in persone_giorno.iterrows():
                            st.markdown(f'<div class="name-badge" style="text-align:center; border-left:none; background:#f8f9fa; font-size:11px; margin-bottom:4px;">{r["Nome"]} {r["Cognome"]}</div>', unsafe_allow_html=True)

            # --- BOX 2: NON DEFINITI (SOTTO) ---
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.markdown("<p style='margin-bottom:5px; margin-top:10px; font-weight:bold; color:#666; font-size:0.9rem;'>Senza riposo assegnato:</p>", unsafe_allow_html=True)
                with st.container(border=True):
                    # Creiamo una riga di badge per i non definiti
                    badge_nd_html = ""
                    for _, r in non_def.iterrows():
                        badge_nd_html += f'<span class="name-badge" style="display:inline-block; margin-right:8px; border-left:4px solid #6c757d; padding: 4px 10px;">{r["Nome"]} {r["Cognome"]}</span>'
                    
                    st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:5px;">{badge_nd_html}</div>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)

          # --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.title("📝 Modifica Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            st.info(f"Postazione: {m}")
            for idx, row in add_m.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"<div style='padding-top:10px;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = c2.selectbox(f"Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"rap_{idx}", label_visibility="collapsed")
            st.divider()
    if st.button("💾 Salva Tutte le Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Riposi aggiornati!"); st.rerun()

# --- 4. AREA DISPONIBILITÀ STAFF ---
elif menu == "📅 Area Disponibilità Staff":
    st.title("🗓️ Calendario Disponibilità Individuale")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome'] + df_t['Stato Rapporto'].apply(lambda x: " (CESSATO)" if x != "Attivo" else "")
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

# --- 5. GESTIONE ANAGRAFICA (Ripristinata e Potenziata) ---
elif menu == "👥 Gestione Anagrafica":
    st.title("👥 Anagrafica Personale")
    
    # --- LOGICA DI EDITING ---
    if "editing_id" not in st.session_state: 
        st.session_state["editing_id"] = None

    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        with st.form("edit_form"):
            st.subheader(f"Modifica Profilo: {row['Nome']} {row['Cognome']}")
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("Nome", row['Nome'])
            ec = c2.text_input("Cognome", row['Cognome'])
            estato = c3.selectbox("Stato Rapporto", ["Attivo", "Dimesso", "Licenziato"], 
                                  index=["Attivo", "Dimesso", "Licenziato"].index(row['Stato Rapporto']) if row['Stato Rapporto'] in ["Attivo", "Dimesso", "Licenziato"] else 0)
            
            c_tel, c_mail = st.columns(2)
            etel = c_tel.text_input("Cellulare", row['Cellulare'])
            email = c_mail.text_input("Email", row['Email'])
            
            c_man, c_rip = st.columns(2)
            em = c_man.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = c_rip.selectbox("Riposo Settimanale", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 0)
            
            e_cont = st.text_area("Lettere di Contestazione / Note", row['Contestazioni'])
            
            cb1, cb2 = st.columns(2)
            if cb1.form_submit_button("💾 SALVA MODIFICHE", use_container_width=True):
                data["addetti"].at[idx, 'Nome'] = en
                data["addetti"].at[idx, 'Cognome'] = ec
                data["addetti"].at[idx, 'Stato Rapporto'] = estato
                data["addetti"].at[idx, 'Cellulare'] = etel
                data["addetti"].at[idx, 'Email'] = email
                data["addetti"].at[idx, 'Mansione'] = em
                data["addetti"].at[idx, 'GiornoRiposoSettimanale'] = er
                data["addetti"].at[idx, 'Contestazioni'] = e_cont
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.success("Dati aggiornati correttamente!")
                st.rerun()
            if cb2.form_submit_button("❌ ANNULLA", use_container_width=True):
                st.session_state["editing_id"] = None
                st.rerun()
    
    else:
        # --- VISUALIZZAZIONE ELENCO ---
        t1, t2 = st.tabs(["📋 Elenco Personale", "➕ Aggiungi Nuovo"])
        
        with t1:
            # Selezione filtro stato
            filtro_stato = st.radio("Mostra addetti:", ["Solo Attivi", "Tutti"], horizontal=True)
            
            df_display = data["addetti"].copy()
            if filtro_stato == "Solo Attivi":
                df_display = df_display[df_display["Stato Rapporto"] == "Attivo"]
            
            st.markdown(f"**Totale visualizzati: {len(df_display)}**")
            st.divider()

            for idx, r in df_display.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([3, 5, 1])
                    
                    # Colonna 1: Nome e WhatsApp
                    wa = format_wa_link(r)
                    wa_html = f' <a href="{wa}" target="_blank" style="text-decoration:none;">📲</a>' if wa else ""
                    c1.markdown(f"**{r['Nome']} {r['Cognome']}**{wa_html}", unsafe_allow_html=True)
                    c1.caption(f"📍 {r['Mansione']}")
                    
                    # Colonna 2: Dettagli (Email, Cellulare, Contestazioni)
                    info_text = f"📞 {r['Cellulare']} | 📧 {r['Email'] if r['Email'] else 'Nessuna mail'}"
                    c2.markdown(f"<div style='font-size:0.85rem; color:#555;'>{info_text}</div>", unsafe_allow_html=True)
                    c2.markdown(f"<div style='font-size:0.85rem;'><b>Riposo:</b> {r['GiornoRiposoSettimanale']} | <b>Stato:</b> {r['Stato Rapporto']}</div>", unsafe_allow_html=True)
                    
                    # Visualizzazione Contestazioni (se presenti)
                    if str(r['Contestazioni']).strip() and str(r['Contestazioni']) != "nan":
                        c2.markdown(f"""<div style="background-color:#fff5f5; border-left:3px solid #ff4b4b; padding:5px 10px; margin-top:5px; font-size:0.8rem; color:#c92a2a;">
                                        🚩 <b>Contestazioni:</b> {r['Contestazioni']}</div>""", unsafe_allow_html=True)
                    
                    # Colonna 3: Tasto Edit
                    if c3.button("✏️", key=f"btn_edit_{idx}"):
                        st.session_state["editing_id"] = idx
                        st.rerun()
                    
                    st.divider()

        with t2:
            st.subheader("Inserisci un nuovo collaboratore")
            with st.form("nuovo_addetto"):
                nc1, nc2 = st.columns(2)
                new_nome = nc1.text_input("Nome")
                new_cognome = nc2.text_input("Cognome")
                new_mansione = nc1.selectbox("Mansione", lista_postazioni)
                new_riposo = nc2.selectbox("Giorno di Riposo", opzioni_riposo)
                new_tel = nc1.text_input("Cellulare")
                new_mail = nc2.text_input("Email")
                new_cont = st.text_area("Note / Contestazioni iniziali")
                
                if st.form_submit_button("➕ AGGIUNGI COLLABORATORE", use_container_width=True):
                    if new_nome and new_cognome:
                        new_data = pd.DataFrame([{
                            "Nome": new_nome, "Cognome": new_cognome, 
                            "Mansione": new_mansione, "GiornoRiposoSettimanale": new_riposo,
                            "Contestazioni": new_cont, "Stato Rapporto": "Attivo",
                            "Data Cessazione": "", "Cellulare": new_tel, "Email": new_mail
                        }])
                        updated_df = pd.concat([data["addetti"], new_data], ignore_index=True)
                        conn.update(worksheet="Addetti", data=updated_df)
                        st.cache_data.clear()
                        st.success(f"{new_nome} aggiunto con successo!")
                        st.rerun()
                    else:
                        st.error("Nome e Cognome sono obbligatori!")

# --- 6. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.title("⚙️ Fabbisogno Giornaliero")
    dr = st.date_input("Periodo:", value=[])
    if len(dr) == 2:
        date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)]
        f_inputs = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("💾 Salva Fabbisogno"):
            new_r = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_inputs.items()]
            old_d = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old_d, pd.DataFrame(new_r)], ignore_index=True)); st.cache_data.clear(); st.success("Fabbisogno aggiornato!"); st.rerun()

# --- 7. GESTIONE POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.title("🚩 Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

# --- 8. IMPOSTAZIONI STAGIONE ---
elif menu == "⚙️ Impostazioni Stagione":
    st.title("⚙️ Configurazione")
    with st.form("config"):
        na, nc = st.date_input("Apertura:", data_apertura), st.date_input("Chiusura:", data_chiusura)
        if st.form_submit_button("Salva"):
            data["config"].loc[data["config"]["Ruolo"] == "Apertura", "Password"] = str(na)
            data["config"].loc[data["config"]["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.rerun()

# --- 9. GESTIONE PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.title("🔑 Sicurezza")
    with st.form("pwd"):
        ap, up = st.text_input("Admin", value=admin_pwd), st.text_input("User", value=user_pwd)
        if st.form_submit_button("Aggiorna Password"):
            data["config"].loc[data["config"]["Ruolo"]=="Admin", "Password"] = ap
            data["config"].loc[data["config"]["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.success("Password salvate!"); st.rerun()
