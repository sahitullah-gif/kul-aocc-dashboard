import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime
import plotly.express as px

# ==========================================
# KONFIGURASI HALAMAN DASHBOARD AOCC
# ==========================================
st.set_page_config(page_title="AOCC Flight Delay Dashboard", layout="wide")
st.title("✈️ Airport Operation Control Center (AOCC) Dashboard")
st.subheader("✈️Flight Delay & Gate Monitoring System")

# Nama fail tegar atau auto-detect fail .csv di dalam folder
CSV_FILE = "data_kul.csv"

if os.path.exists(CSV_FILE):
    # Membaca data sebenar KUL
    df_raw = pd.read_csv(CSV_FILE)
    df_raw.columns = df_raw.columns.str.strip()
    
    st.info(f"📊 Sistem Berjaya Membaca Fail Data Industri: **{CSV_FILE}**")
    
    # Dictionary untuk menukarkan kod Operator/Airline kepada Nama Penuh (Bagi nampak profesional)
    airline_mapping = {
        'AK': 'AirAsia', 'MH': 'Malaysia Airlines', 'OD': 'Batik Air',
        'D7': 'AirAsia X', 'QZ': 'Indonesia AirAsia', 'SQ': 'Singapore Airlines',
        'CZ': 'China Southern Airlines', 'FY': 'Firefly', 'TR': 'Scoot', 'CX': 'Cathay Pacific', 'MK': 'Air Mauritius / MK Cargo'
    }
    
    # ==========================================
    # LANGKAH 1: PEMBINAAN DATA & FORMULA (REPLICATE EXCEL)
    # ==========================================
    # Bersihkan simbol '?' daripada data masa jika ada
    df_raw['STAD_clean'] = df_raw['STAD'].astype(str).str.replace('?', ' ', regex=False)
    df_raw['ATAD_clean'] = df_raw['ATAD'].astype(str).str.replace('?', ' ', regex=False)
    
    # Tukar kepada bentuk datetime object untuk pengiraan minit
    df_raw['STD_dt'] = pd.to_datetime(df_raw['STAD_clean'], format='%b %d, %Y, %I:%M:%S %p', errors='coerce')
    df_raw['ATD_dt'] = pd.to_datetime(df_raw['ATAD_clean'], format='%b %d, %Y, %I:%M:%S %p', errors='coerce')
    
    # Logik Formula Excel: =IF(E2>D2, (E2-D2)*1440, 0)
    # Di dalam Python, perbezaan masa saat ditukar kepada minit (total_seconds / 60)
    def kira_minit_delay(row):
        if pd.isna(row['ATD_dt']) or pd.isna(row['STD_dt']):
            return 0
        if row['ATD_dt'] > row['STD_dt']:
            diff = row['ATD_dt'] - row['STD_dt']
            return int(diff.total_seconds() / 60)
        return 0

    # Membina struktur 7 lajur utama tepat seperti kehendak Langkah 1
    df = pd.DataFrame()
    df['Flight No'] = df_raw['FLIGHTNO']
    df['Airline'] = df_raw['OPERATOR'].map(airline_mapping).fillna(df_raw['OPERATOR'])
    df['Gate'] = df_raw['GATE']
    df['STD'] = df_raw['STD_dt'].dt.strftime('%H:%M')
    df['ATD'] = df_raw['ATD_dt'].dt.strftime('%H:%M').fillna('-')
    df['Delay (Minits)'] = df_raw.apply(kira_minit_delay, axis=1)
    
    # Logik Formula Excel: =IF(F2>0, "Delayed", "On-Time")
    df['Status'] = df['Delay (Minits)'].apply(lambda x: 'Delayed' if x > 0 else 'On-Time')

    # ==========================================
    # LANGKAH 3: DASHBOARD RINGKAS (PIVOT & CHARTS)
    # ==========================================
    # Pengiraan KPI Ringkas untuk dipaparkan di bahagian atas
    total_flights = len(df)
    on_time_count = len(df[df['Status'] == 'On-Time'])
    otp_percentage = (on_time_count / total_flights) * 100 if total_flights > 0 else 0
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Total Flights Monitored", total_flights)
    col_kpi2.metric("Overall On-Time Performance", f"{otp_percentage:.1f}%")
    col_kpi3.metric("Flights with Critical Delay (>30m)", len(df[df['Delay (Minits)'] > 30]))
    
    st.markdown("---")
    
    # Pembahagian Ruang Carta
    col_left, col_right = st.columns(2)
    
    with col_left:
        # 1. % On-Time (Donut Chart)
        st.write("### 🍩 % On-Time Performance Status")
        status_counts = df['Status'].value_counts()
        fig_donut = px.pie(
            names=status_counts.index,
            values=status_counts.values,
            hole=0.5,
            color=status_counts.index,
            color_discrete_map={'On-Time': '#2ecc71', 'Delayed': '#e74c3c'}
        )
        fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
        st.plotly_chart(fig_donut, use_container_width=True)
        
        # 2. Top 3 Airline Paling Delay (Bar Chart - Horizontal/Melintang)
        st.write("### 📊 Top 3 Airline Paling Delay (Average Delay)")
        # Mengira purata kelewatan bagi setiap airline (Pivot Table Concept)
        df_departed = df[df['ATD'] != '-'] # Hanya ambil flight yang sudah ada data pelepasan sebenar
        avg_delay = df_departed.groupby('Airline')['Delay (Minits)'].mean().sort_values(ascending=False).head(3)
        
        fig_bar = px.bar(
            x=avg_delay.values,
            y=avg_delay.index,
            orientation='h',
            labels={'x': 'Purata Kelewatan (Minit)', 'y': 'Airline'},
            color=avg_delay.values,
            color_continuous_scale='Reds'
        )
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=250, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        # 3. Gate Paling Congested (Column Chart - Vertical/Menegak)
        st.write("### 🏛️ Top 10 Gate Paling Congested (Flight Count)")
        # Tapis gate yang tidak sah '-' (Pivot Table Concept)
        gate_counts = df[df['Gate'] != '-']['Gate'].value_counts().head(10)
        
        fig_column = px.bar(
            x=gate_counts.index,
            y=gate_counts.values,
            orientation='v',
            labels={'x': 'Nama Gate / Bay', 'y': 'Jumlah Penerbangan (Count)'},
            color=gate_counts.values,
            color_continuous_scale='Blues'
        )
        fig_column.update_layout(height=540, showlegend=False)
        st.plotly_chart(fig_column, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # LANGKAH 2: CONDITIONAL FORMATTING (AUTO ALERT)
    # ==========================================
    st.write("### 📋 Tab: Data_Flight (Live Status Table)")
    
    # Fungsi mewarnakan sel lajur 'Delay (Minits)' jika nilai > 30 (Light Red Fill with Dark Red Text)
    def highlight_delay_column(s):
        is_delayed = s > 30
        return ['background-color: #ffcccc; color: #990000; font-weight: bold;' if v else '' for v in is_delayed]

    # Mengaplikasikan warna amaran khusus pada lajur 'Delay (Minits)' seperti arahan Langkah 2
    styled_df = df.style.apply(highlight_delay_column, subset=['Delay (Minits)'])
    st.dataframe(styled_df, use_container_width=True)

else:
    st.error(f"❌ Fail '{CSV_FILE}' tidak dijumpai di dalam folder projek! Sila pastikan fail data seline anda diletakkan bersama dengan fail app.py.")
