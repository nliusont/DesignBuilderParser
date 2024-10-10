# DesignBuilder Report Parser

This project is a Streamlit application that parses DesignBuilder report files in HTM format. It extracts cooling and heating load data for different zones and presents it in a user-friendly format. Users can process reports and download the extracted data as a PDF.

A public version of the app is available [here](https://maaraepulawppmtfmdiknc.streamlit.app/).

## Features

- Upload HTM or HTML files containing DesignBuilder reports.
- Extracts and displays cooling and heating load data by zone.
- Presents the data in organized tables, allowing easy comparison.
- Download extracted data as a PDF with customizable formatting.
- Progress indicators for file processing and PDF generation.

## Requirements

This project requires the following Python packages:

- Streamlit
- Pandas
- DataFrame Image
- ReportLab
- LXML

You can install the required packages using the following command:

```bash
pip install -r requirements.txt
```
## Usage
You can run it with the following command:
```bash
streamlit run app.py
```