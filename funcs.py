def extract_tables_from_html(file_content, progress_bar, total_zones, status_text):
    from lxml import etree
    from io import BytesIO, StringIO
    import pandas as pd
    import streamlit as st
    from funcs import process_dataframe_for_styler

    # Process the file content and extract tables
    zone_tables = {}  # Dictionary to store tables for each zone
    context = etree.iterparse(BytesIO(file_content), html=True, events=('start', 'end'))
    zone_name = None
    tables = []
    collecting = False
    table_title = ''
    table_count = 0
    processed_zones = 0

    for event, elem in context:
        if event == 'start':
            if elem.tag == 'p' and 'For:' in ''.join(elem.itertext()) and 'Entire Facility' not in ''.join(elem.itertext()):
                zone_name_elem = elem.find('b')
                if zone_name_elem is not None:
                    zone_name = zone_name_elem.text.strip()
                else:
                    zone_name = 'Unknown Zone'
                collecting = True
                status_text.write(f"Processing zone: {zone_name}")
                tables = []
                table_count = 0
            elif collecting and elem.tag == 'b':
                table_title = ''.join(elem.itertext()).strip()
            elif collecting and elem.tag == 'table':
                table_html = etree.tostring(elem, encoding='unicode')
                try:
                    # Update pd.read_html to skip the first row, use the second row as headers,
                    # and set the first column as index
                    df = pd.read_html(
                        StringIO(table_html),
                        flavor='lxml',
                        header=0,
                        index_col=0
                    )[0]

                    df = process_dataframe_for_styler(df)

                    tables.append((table_title, df))
                except Exception as e:
                    print(f"Failed to read table '{table_title}' for zone '{zone_name}': {e}")
                table_count += 1
                if table_count == 6:
                    collecting = False
                    # Store the tables for the zone
                    zone_tables[zone_name] = tables
                    tables = []
                    table_count = 0
                    # Update the progress bar
                    processed_zones += 1
                    if total_zones > 0:
                        progress = processed_zones / total_zones
                        progress_bar.progress(progress)
        elem.clear()
    del context
    return zone_tables

def count_zones_in_toc(file_content):
    from io import StringIO
    import re

    # Read the file content line by line up to a reasonable limit
    max_lines = 2000  # Adjust as needed based on file structure
    toc_started = False
    toc_content = ''
    zone_links = []
    
    # Decode the file content for line-by-line processing
    content_stream = StringIO(file_content.decode('utf-8', errors='ignore'))

    for _ in range(max_lines):
        line = content_stream.readline()
        if not line:
            break  # End of file reached
        if '<p><b>Zone Component Load Summary' in line:
            toc_started = True
        elif toc_started and '<p><b>' in line and 'Zone Component Load Summary' not in line:
            break  # End of Table of Contents
        if toc_started:
            toc_content += line

    # Use regex to find all zone links in the TOC
    zone_links = re.findall(r'<a href="#ZoneComponentLoadSummary::(.*?)">', toc_content)
    return len(zone_links)

def generate_pdf(zone_tables, progress_bar):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Paragraph, PageBreak, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors
    from io import BytesIO
    import dataframe_image as dfi
    import tempfile
    import os
    from funcs import clean_filename

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    styles['Heading1'].alignment = TA_CENTER
    styles['Heading3'].alignment = TA_CENTER

    total_zones = len(zone_tables)
    processed_zones = 0

    # Create a temporary directory for all images
    with tempfile.TemporaryDirectory() as tmpdirname:
        for zone_name in sorted(zone_tables.keys()):
            elements.append(Paragraph(zone_name, styles['Heading1']))
            elements.append(Spacer(1, 12))

            # Separate the tables into cooling and heating tables
            tables = zone_tables[zone_name]
            cooling_tables = [(title, df) for title, df in tables if 'Cooling' in title]
            heating_tables = [(title, df) for title, df in tables if 'Heating' in title]

            # Create temporary images for the tables
            cooling_images = []
            heating_images = []

            for title, df in cooling_tables:
                img_filename = f"{clean_filename(zone_name)}_{clean_filename(title)}.png"
                img_path = os.path.join(tmpdirname, img_filename)
                dfi.export(df, img_path, max_cols=-1, max_rows=-1, table_conversion='matplotlib')
                cooling_images.append((title, img_path))

            for title, df in heating_tables:
                img_filename = f"{clean_filename(zone_name)}_{clean_filename(title)}.png"
                img_path = os.path.join(tmpdirname, img_filename)
                dfi.export(df, img_path, max_cols=-1, max_rows=-1, table_conversion='matplotlib')
                heating_images.append((title, img_path))

            # Determine the maximum number of tables to align them
            max_tables = max(len(cooling_images), len(heating_images))

            for i in range(max_tables):
                data = []

                # Cooling Table
                if i < len(cooling_images):
                    cooling_title = Paragraph(cooling_images[i][0], styles['Heading3'])
                    # Get image dimensions
                    cooling_img = cooling_images[i][1]
                    cooling_image_reader = ImageReader(cooling_img)
                    iw, ih = cooling_image_reader.getSize()
                    aspect = ih / float(iw)
                    cooling_image = Image(cooling_img, width=250, height=250*aspect)
                    cooling_cell = [cooling_title, cooling_image]
                else:
                    cooling_cell = [Spacer(1, 1), Spacer(1, 1)]

                # Heating Table
                if i < len(heating_images):
                    heating_title = Paragraph(heating_images[i][0], styles['Heading3'])
                    heating_img = heating_images[i][1]
                    heating_image_reader = ImageReader(heating_img)
                    iw, ih = heating_image_reader.getSize()
                    aspect = ih / float(iw)
                    heating_image = Image(heating_img, width=250, height=250*aspect)
                    heating_cell = [heating_title, heating_image]
                else:
                    heating_cell = [Spacer(1, 1), Spacer(1, 1)]

                # Create a table row
                data.append([cooling_cell, heating_cell])

                # Flatten the data for the Table (since each cell contains a list)
                table_data = []
                for row in data:
                    table_row = []
                    for cell in row:
                        table_row.append(cell)
                    table_data.append(table_row)

                # Create a table with the data
                table = Table(table_data, colWidths=[260, 260])
                table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))

            elements.append(PageBreak())

            # Update the progress bar
            processed_zones += 1
            progress = processed_zones / total_zones
            progress_bar.progress(progress)

        # Build the PDF after all elements are added
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    
def clean_filename(name):
    import re
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def process_dataframe_for_styler(df):
    import pandas as pd
    import re

    """
    Convert applicable columns to floats, round them, and convert back to strings with two decimal places.
    
    Parameters:
    - df (pd.DataFrame): The original DataFrame.
    
    Returns:
    - pd.DataFrame: The processed DataFrame with formatted strings.
    """
    # Identify numeric columns based on dtypes
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    
    # Additionally, identify columns with numeric data stored as objects
    for col in df.columns:
        if df[col].dtype == 'object':
            # Attempt to detect if the column is numeric by checking the first non-null value
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if sample is not None and re.match(r'^-?\d+(\.\d+)?$', str(sample)):
                numeric_cols.append(col)
    
    # Remove duplicates
    numeric_cols = list(set(numeric_cols))
    
    # Process each numeric column
    for col in numeric_cols:
        # Remove non-numeric characters if any
        df[col] = df[col].astype(str).apply(lambda x: re.sub(r'[^\d\.\-]', '', x))
        
        # Convert to float, coercing errors to NaN
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Round to two decimal places
        df[col] = df[col].round(2)
        
        # Convert back to string with two decimal places
        df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
    
    return df