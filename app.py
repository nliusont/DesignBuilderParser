import streamlit as st
from funcs import extract_tables_from_html, count_zones_in_toc, generate_pdf, process_dataframe_for_styler

st.set_page_config(layout="wide")

st.title("DesignBuilder Report Parser")

uploaded_file = st.file_uploader("Choose an HTM file", type=['htm', 'html'])

# Initialize session state variables if they don't exist
if 'zone_tables' not in st.session_state:
    st.session_state['zone_tables'] = None
    st.session_state['uploaded_file_content'] = None

if uploaded_file is not None:
    # Read the uploaded file
    file_content = uploaded_file.read()

    # Check if the uploaded file has changed
    if 'uploaded_file_content' in st.session_state:
        if st.session_state['uploaded_file_content'] != file_content:
            st.session_state['uploaded_file_content'] = file_content
            st.session_state['zone_tables'] = None  # Reset zone_tables since the file has changed
    else:
        st.session_state['uploaded_file_content'] = file_content
        st.session_state['zone_tables'] = None  # Initialize zone_tables

    # Provide a button to process the report
    if st.button("Process Report"):
        # Count the number of zones from the table of contents
        total_zones = count_zones_in_toc(file_content)
        if total_zones == 0:
            st.warning("No zones found in the Table of Contents.")
        else:
            # Create a progress bar
            progress_bar = st.progress(0)

            # Process the file and get the data
            status_text = st.empty()
            st.session_state['zone_tables'] = extract_tables_from_html(
                    file_content, progress_bar, total_zones, status_text
                )
            status_text.write("Processing complete!")
            progress_bar.empty()
else:
    st.write("Please upload an HTM file.")

# Check if zone_tables is available in session state
if st.session_state['zone_tables']:
    zone_tables = st.session_state['zone_tables']
    zone_names = sorted(zone_tables.keys())
    selected_zone = st.selectbox("Select a Zone", zone_names)

    if selected_zone:
        tables = zone_tables[selected_zone]

        # Separate the tables into cooling and heating tables
        cooling_tables = [(title, df) for title, df in tables if 'Cooling' in title]
        heating_tables = [(title, df) for title, df in tables if 'Heating' in title]

        # Create two columns
        st.markdown(f"<h2 style='text-align: center;'>{selected_zone}</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"<h3 style='text-align: center;'>Cooling Tables</h3>", unsafe_allow_html=True)
            for title, df in cooling_tables:
                st.write(f"#### {title}")
                df = df.round(2).fillna('')
                styled_df = df.style.set_table_styles(
                    [{'selector': 'th', 'props': [('white-space', 'normal'), ('word-wrap', 'break-word')]}]
                )
                st.write(styled_df.to_html(), unsafe_allow_html=True)

        with col2:
            st.markdown(f"<h3 style='text-align: center;'>Heating Tables</h3>", unsafe_allow_html=True)
            for title, df in heating_tables:
                st.write(f"#### {title}")
                df = df.round(2).fillna('')
                styled_df = df.style.set_table_styles(
                    [{'selector': 'th', 'props': [('white-space', 'normal'), ('word-wrap', 'break-word')]}]
                )
                st.write(styled_df.to_html(), unsafe_allow_html=True)

            # Add a Download PDF button
    if st.button("Download PDF"):
        with st.spinner("Generating PDF..."):
            # Create a progress bar
            pdf_progress_bar = st.progress(0)
            pdf_data = generate_pdf(zone_tables, pdf_progress_bar)
            pdf_progress_bar.empty()  # Remove the progress bar after completion
            st.success("PDF generated successfully!")
            st.download_button(
                label="Download PDF",
                data=pdf_data,
                file_name="zone_tables.pdf",
                mime="application/pdf"
            )

else:
    if uploaded_file is not None:
        st.write("No zones processed yet. Please click 'Process Report'.")
    else:
        st.write("No zones processed yet. Please upload a file and click 'Process Report'.")