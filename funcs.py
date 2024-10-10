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
                if zone_name_elem.text is not None:
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



def generate_excel(zone_tables):
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    # Create a new Excel workbook and a worksheet
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Zone Tables"

    # Start writing from the first row
    row_index = 1

    for zone_name in sorted(zone_tables.keys()):
        # Write the zone name as a header
        worksheet.cell(row=row_index, column=1, value=f"Zone: {zone_name}")
        row_index += 2  # Add some space after the header

        # Separate the tables into cooling and heating tables
        tables = zone_tables[zone_name]
        cooling_tables = [(title, df) for title, df in tables if 'Cooling' in title]
        heating_tables = [(title, df) for title, df in tables if 'Heating' in title]

        max_tables = max(len(cooling_tables), len(heating_tables))

        for i in range(max_tables):
            # Cooling Table
            if i < len(cooling_tables):
                cooling_title, cooling_df = cooling_tables[i]
                # Write title
                worksheet.cell(row=row_index, column=1, value=cooling_title)
                row_index += 1  # Move to next row
                # Write DataFrame to Excel
                for r_idx, row in enumerate(cooling_df.itertuples(index=False), start=row_index):
                    for c_idx, value in enumerate(row, start=1):
                        worksheet.cell(row=r_idx, column=c_idx, value=value)
                row_index += len(cooling_df) + 2  # Move down after the table with spacing

            # Heating Table
            if i < len(heating_tables):
                heating_title, heating_df = heating_tables[i]
                # Write title
                worksheet.cell(row=row_index, column=1, value=heating_title)
                row_index += 1  # Move to next row
                # Write DataFrame to Excel
                for r_idx, row in enumerate(heating_df.itertuples(index=False), start=row_index):
                    for c_idx, value in enumerate(row, start=1):
                        worksheet.cell(row=r_idx, column=c_idx, value=value)
                row_index += len(heating_df) + 2  # Move down after the table with spacing

            # Add a separator row
            row_index += 1  # Add an extra space between different zones

    # Auto-adjust column width for better readability
    for col in range(1, worksheet.max_column + 1):
        column_letter = get_column_letter(col)
        worksheet.column_dimensions[column_letter].width = 20

    # Save the workbook
    output_file = "zone_tables.xlsx"
    workbook.save(output_file)
    return output_file


    
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