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

# --- 1. DASHBOARD (Versione Pulita con Radio sotto Bagnini) ---
if menu == "📊 Dashboard":
    st.title("Situazione giornaliera")
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
                
                # Calcolo Fabbisogno e Disponibilità
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

                # Layout a 3 Colonne
                col1, col2, col3 = st.columns(3)
                
                # Colonna 1: Addetto Attrazioni
                with col1:
                    m = "Addetto Attrazioni"
                    s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                    f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                    r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                    n = len(s_p)
                    c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                    st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)

                # Colonna 2: Assistente Bagnanti E Radio SOTTO
                with col2:
                    for m in ["Assistente Bagnanti", "Radio"]:
                        s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                        f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                        r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                        n = len(s_p)
                        c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                        st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)

                # Colonna 3: Bungee Jumping
                with col3:
                    m = "Bungee Jumping"
                    s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                    f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                    r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                    n = len(s_p)
                    c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                    st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)
# --- 2. RIEPILOGO RIPOSI (Layout Corretto e Senza Errori) ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.title("Riposi Settimanali")
    
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

     # --- 3. GESTIONE RIPOSI RAPIDA (Conteggi divisi per Mansione) ---
elif menu == "📝 Gestione Riposi Rapida":
    st.title("Modifica Rapida Riposi")
    st.info("I box mostrano quanti addetti riposano ogni giorno per la specifica mansione.")
    
    df_mod = data["addetti"].copy()
    
    # Ciclo per ogni mansione
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            
            # --- CONTEGGI SPECIFICI PER QUESTA MANSIONE ---
            conteggi_m = add_m["GiornoRiposoSettimanale"].value_counts()
            
            c_counts = st.columns(7)
            for i, g in enumerate(giorni_ita):
                num = conteggi_m.get(g, 0)
                # Cambia colore se il numero è alto (alert visivo opzionale)
                border_col = "#1f77b4" if num < 3 else "#ff4b4b" 
                
                with c_counts[i]:
                    st.markdown(f"""
                        <div style="background:white; border:1px solid #eee; border-radius:8px; padding:8px; text-align:center; border-bottom: 3px solid {border_col};">
                            <div style="font-size:10px; font-weight:bold; color:#888; text-transform:uppercase;">{g[:3]}</div>
                            <div style="font-size:18px; font-weight:bold; color:{border_col};">{num}</div>
                        </div>
                    """, unsafe_allow_html=True)
            
            # --- ELENCO DIPENDENTI MANSIONE ---
            with st.container():
                # Spazio extra per staccare dai box
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                for idx, row in add_m.iterrows():
                    col_nome, col_sel = st.columns([3, 1])
                    col_nome.markdown(f"<div style='padding-top:8px; font-size:0.95rem;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                    
                    # Selettore riposo
                    curr_val = row['GiornoRiposoSettimanale']
                    df_mod.at[idx, 'GiornoRiposoSettimanale'] = col_sel.selectbox(
                        f"Rip_{idx}", 
                        opzioni_riposo, 
                        index=opzioni_riposo.index(curr_val) if curr_val in opzioni_riposo else 7,
                        key=f"fast_edit_{idx}",
                        label_visibility="collapsed"
                    )
            st.divider()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 SALVA TUTTE LE MODIFICHE", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear()
        st.success("Modifiche salvate con successo!")
        st.rerun()

# --- 4. AREA DISPONIBILITÀ STAFF (Versione Corretta e Robusta) ---
elif menu == "📅 Disponibilità Staff":
    st.title("Area Disponibilità Staff")
    st.subheader("Inserimento Date e Stati")
    
    # Verifichiamo che i dati necessari siano caricati
    if "addetti" not in data or data["addetti"].empty:
        st.error("Errore: Nessun addetto trovato in anagrafica. Carica prima i collaboratori.")
    else:
        with st.form("form_disp"):
            # 1. Creazione lista nomi (Nome + Cognome) per il multiselect
            # Filtriamo solo gli attivi per non appesantire la lista
            lista_nomi = sorted([
                f"{r['Nome']} {r['Cognome']}" 
                for i, r in data["addetti"].iterrows() 
                if str(r.get('Stato Rapporto', '')).strip().lower() == "attivo"
            ])
            
            scelti = st.multiselect("Seleziona i Collaboratori:", lista_nomi)
            
            c1, c2 = st.columns(2)
            # Usiamo datetime.date.today() (assicurati di aver importato datetime in cima allo script)
            d_inizio = c1.date_input("Dalla data:", datetime.date.today())
            d_fine = c2.date_input("Alla data (inclusa):", datetime.date.today())
            
            stato_scelto = st.selectbox("Imposta Stato:", ["Disponibile", "Assente", "Permesso", "Malattia"])
            note_evento = st.text_input("Note (opzionale):")
            
            submit = st.form_submit_button("💾 REGISTRA DISPONIBILITÀ", use_container_width=True)
            
            if submit:
                if not scelti:
                    st.warning("Seleziona almeno un collaboratore!")
                elif d_inizio > d_fine:
                    st.error("La data di inizio non può essere successiva alla data di fine.")
                else:
                    try:
                        with st.spinner("Salvataggio in corso..."):
                            # Generazione dell'elenco delle date tra inizio e fine
                            date_list = []
                            curr = d_inizio
                            while curr <= d_fine:
                                date_list.append(curr.strftime("%d/%m/%Y"))
                                curr += datetime.timedelta(days=1)
                            
                            # Creazione dei nuovi record
                            nuovi_record = []
                            for persona in scelti:
                                # Dividiamo nome e cognome (gestendo eventuali spazi extra)
                                parti = persona.rsplit(" ", 1)
                                nome_p = parti[0]
                                cognome_p = parti[1] if len(parti) > 1 else ""
                                
                                for d_str in date_list:
                                    nuovi_record.append({
                                        "Nome": nome_p,
                                        "Cognome": cognome_p,
                                        "Data": d_str,
                                        "Stato": stato_scelto,
                                        "Note": note_evento
                                    })
                            
                            nuovi_df = pd.DataFrame(nuovi_record)
                            
                            # Unione con i dati esistenti (evitiamo di perdere lo storico)
                            old_df = data["disp"].copy()
                            df_finale = pd.concat([old_df, nuovi_df], ignore_index=True)
                            
                            # Aggiornamento su Google Sheets
                            conn.update(worksheet="Disponibilita", data=df_finale)
                            
                            # Reset e Successo
                            st.cache_data.clear()
                            st.success(f"Registrate correttamente {len(nuovi_df)} voci!")
                            time.sleep(1)
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Errore tecnico durante il salvataggio: {e}")
                        st.info("Se l'errore persiste, attendi 1 minuto (limite Google API).")

    st.divider()
    st.subheader("Riepilogo ultimi inserimenti")
    if "disp" in data and not data["disp"].empty:
        # Mostra le ultime 10 righe registrate per conferma
        st.dataframe(data["disp"].tail(10), use_container_width=True)
    else:
        st.info("Nessuna disponibilità registrata finora.")

# --- 5. GESTIONE ANAGRAFICA (Versione Ottimizzata anti-Quota 429 con Filtri) ---
elif menu == "👥 Gestione Anagrafica":
    st.title("Anagrafica")
    
    if "editing_id" not in st.session_state: 
        st.session_state["editing_id"] = None

    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        
        with st.form("edit_form_new"):
            st.subheader(f"Modifica Profilo: {row['Nome']} {row['Cognome']}")
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("Nome", row['Nome'])
            ec = c2.text_input("Cognome", row['Cognome'])
            estato = c3.selectbox("Stato Rapporto", ["Attivo", "Dimesso", "Licenziato"], 
                                 index=["Attivo", "Dimesso", "Licenziato"].index(row['Stato Rapporto']) if row['Stato Rapporto'] in ["Attivo", "Dimesso", "Licenziato"] else 0)
            
            c_tel, c_mail, c_cess = st.columns(3)
            etel = c_tel.text_input("Cellulare", row['Cellulare'])
            email = c_mail.text_input("Email", row['Email'])
            e_data_cess = c_cess.text_input("Data Cessazione (gg/mm/aaaa)", row.get('Data Cessazione', ''))
            
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
                data["addetti"].at[idx, 'Data Cessazione'] = e_data_cess
                
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.success("Dati aggiornati correttamente!")
                st.rerun()
            
            if cb2.form_submit_button("❌ ANNULLA", use_container_width=True):
                st.session_state["editing_id"] = None
                st.rerun()
    
    else:
        t1, t2 = st.tabs(["📋 Elenco Personale", "➕ Aggiungi Nuovo"])
        
        with t1:
            # --- FILTRI E ORDINAMENTO ---
            col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
            filtro_stato = col_f1.radio("Filtra Stato:", ["Solo Attivi", "Tutti"], horizontal=True, key="f_stato_anag")
            filtro_man = col_f2.selectbox("Filtra Mansione:", ["Tutte"] + lista_postazioni, key="f_man_anag")
            ordina_per = col_f3.selectbox("Ordina per:", ["Alfabetico", "Più Disponibili", "Più Assenti", "Più Permessi", "Più Malattie"])

            # --- LOGICA CALCOLO STATISTICHE LOCALE (ZERO API CALLS) ---
            df_display = data["addetti"].copy()
            df_disp_local = data["disp"].copy()
            
            # Normalizzazione dati per il matching
            df_disp_local['Nome_Match'] = df_disp_local['Nome'].astype(str).str.upper().str.strip()
            df_disp_local['Cognome_Match'] = df_disp_local['Cognome'].astype(str).str.upper().str.strip()
            df_disp_local['Stato_Match'] = df_disp_local['Stato'].astype(str).str.upper().str.strip()

            # Raggruppamento veloce
            stats = df_disp_local.groupby(['Nome_Match', 'Cognome_Match', 'Stato_Match']).size().unstack(fill_value=0)
            
            # Assicuriamoci che le colonne esistano per evitare KeyError
            for c in ["DISPONIBILE", "ASSENTE", "PERMESSO", "MALATTIA"]:
                if c not in stats.columns: stats[c] = 0

            # Funzione di mappatura locale
            def get_local_stats(r):
                n, c = str(r['Nome']).upper().strip(), str(r['Cognome']).upper().strip()
                if (n, c) in stats.index:
                    s_row = stats.loc[(n, c)]
                    return pd.Series([s_row["DISPONIBILE"], s_row["ASSENTE"], s_row["PERMESSO"], s_row["MALATTIA"]])
                return pd.Series([0, 0, 0, 0])

            # Creazione colonne per ordinamento
            df_display[["C_D", "C_A", "C_P", "C_M"]] = df_display.apply(get_local_stats, axis=1)

            # Applicazione Filtri
            if filtro_stato == "Solo Attivi":
                df_display = df_display[df_display["Stato Rapporto"] == "Attivo"]
            if filtro_man != "Tutte":
                df_display = df_display[df_display["Mansione"] == filtro_man]

            # Applicazione Ordinamento
            mappa_sort = {
                "Alfabetico": (["Cognome", "Nome"], [True, True]),
                "Più Disponibili": (["C_D", "Cognome"], [False, True]),
                "Più Assenti": (["C_A", "Cognome"], [False, True]),
                "Più Permessi": (["C_P", "Cognome"], [False, True]),
                "Più Malattie": (["C_M", "Cognome"], [False, True])
            }
            s_cols, s_asc = mappa_sort[ordina_per]
            df_display = df_display.sort_values(by=s_cols, ascending=s_asc)
            
            st.markdown(f"**Risultati trovati: {len(df_display)}**")
            st.divider()

            # Rendering della lista
            for idx, r in df_display.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([3, 5, 1])
                    
                    wa = format_wa_link(r)
                    wa_html = f' <a href="{wa}" target="_blank" style="text-decoration:none;">📲</a>' if wa else ""
                    
                    nome_style = "color: #333;" if r['Stato Rapporto'] == "Attivo" else "color: #888; text-decoration: line-through;"
                    c1.markdown(f"<span style='{nome_style} font-weight: bold;'>{r['Nome']} {r['Cognome']}</span>{wa_html}", unsafe_allow_html=True)
                    c1.caption(f"📍 {r['Mansione']}")
                    
                    # Badge Statistiche dinamici
                    stati_html = f"""
                    <div style="display: flex; gap: 4px; margin-top: 5px;">
                        <span title="Disponibile" style="background:#29b05c; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_D'])} D</span>
                        <span title="Assente" style="background:#000000; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_A'])} A</span>
                        <span title="Permesso" style="background:#00008B; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_P'])} P</span>
                        <span title="Malattia" style="background:#696969; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_M'])} M</span>
                    </div>
                    """
                    c1.markdown(stati_html, unsafe_allow_html=True)
                    
                    info_text = f"📞 {r['Cellulare']} | 📧 {r['Email'] if r['Email'] else 'Nessuna mail'}"
                    c2.markdown(f"<div style='font-size:0.85rem; color:#555;'>{info_text}</div>", unsafe_allow_html=True)
                    
                    stato_info = f"<b>Stato:</b> {r['Stato Rapporto']}"
                    if r['Stato Rapporto'] != "Attivo" and str(r.get('Data Cessazione', '')).strip() != "":
                        stato_info += f" (dal {r['Data Cessazione']})"
                    
                    c2.markdown(f"<div style='font-size:0.85rem;'><b>Riposo:</b> {r['GiornoRiposoSettimanale']} | {stato_info}</div>", unsafe_allow_html=True)
                    
                    if str(r['Contestazioni']).strip() and str(r['Contestazioni']) != "nan":
                        c2.markdown(f"""<div style="background-color:#fff5f5; border-left:3px solid #ff4b4b; padding:5px 10px; margin-top:5px; font-size:0.8rem; color:#c92a2a;">
                                    🚩 <b>Contestazioni:</b> {r['Contestazioni']}</div>""", unsafe_allow_html=True)
                    
                    if c3.button("✏️", key=f"btn_list_edit_{idx}"):
                        st.session_state["editing_id"] = idx
                        st.rerun()
                    
                    st.divider()

        with t2:
            st.subheader("Inserisci un nuovo collaboratore")
            with st.form("nuovo_addetto_form"):
                nc1, nc2, nc3 = st.columns(3)
                new_nome = nc1.text_input("Nome")
                new_cognome = nc2.text_input("Cognome")
                new_mansione = nc3.selectbox("Mansione", lista_postazioni)
                new_tel = nc1.text_input("Cellulare")
                new_mail = nc2.text_input("Email")
                new_riposo = nc3.selectbox("Giorno di Riposo", opzioni_riposo)
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

# --- 6. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.title("Fabbisogno Giornaliero")
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
    st.title("Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

# --- 8. IMPOSTAZIONI STAGIONE ---
elif menu == "⚙️ Impostazioni Stagione":
    st.title("Configurazione")
    with st.form("config"):
        na, nc = st.date_input("Apertura:", data_apertura), st.date_input("Chiusura:", data_chiusura)
        if st.form_submit_button("Salva"):
            data["config"].loc[data["config"]["Ruolo"] == "Apertura", "Password"] = str(na)
            data["config"].loc[data["config"]["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.rerun()

# --- 9. GESTIONE PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.title("Sicurezza")
    with st.form("pwd"):
        ap, up = st.text_input("Admin", value=admin_pwd), st.text_input("User", value=user_pwd)
        if st.form_submit_button("Aggiorna Password"):
            data["config"].loc[data["config"]["Ruolo"]=="Admin", "Password"] = ap
            data["config"].loc[data["config"]["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.success("Password salvate!"); st.rerun()
