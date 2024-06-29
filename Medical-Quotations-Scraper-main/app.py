from flask import Flask, render_template, request, send_file
from bs4 import BeautifulSoup
import csv
import tabula
import pandas as pd
import os

app = Flask(__name__)

def process_html_file(html_file, trader_name):
    data = []
    print(html_file)

    soup = BeautifulSoup(html_file, 'html.parser')
    headings = soup.find_all("tr", class_="heading")

    for i, heading in enumerate(headings):
        heading_name = heading.find('td').text.strip()
        next_heading = headings[i + 1] if i + 1 < len(headings) else None
        items = heading.find_next_siblings('tr', class_='item')
        for item in items:
            snum = item.find('td', align='center').text.strip()
            item_name = item.find("td", style=" text-align: left;").text.strip()
                
            # Check if item_name is empty
            if not item_name:
                item_name = "No Name"
                    
            w = item_name.split()
                
            percentage_index = next((i for i, x in enumerate(w) if x.endswith('%')), None)            
            if percentage_index is not None:
                if w[-1].endswith('%'):
                    offer = w[-1]  
                    tp = w[-2]     
                    item_name = ' '.join(w[:-2])  
                    bonus = ''  
                else:
                    offer = w[percentage_index]
                    bonus = ' '.join(w[percentage_index+1:])
                    tp = w[percentage_index-1]
                    item_name = ' '.join(w[:percentage_index-1])
            else:
                try:
                    offer = item.find_all("td", align="center")[2].text.strip()
                except IndexError:
                    offer = ""
                try:
                    bonus = item.find_all("td", align="center")[3].text.strip()
                except IndexError:
                    bonus = ""
                try:
                    tp = item.find_all("td", align="center")[4].text.strip()
                except IndexError:
                    tp = ""
            data.append({'Code': snum, 'Item Name': item_name, 'Pharmaceutical': heading_name, 'Offer': offer, 'Bonus': bonus, 'T.P': tp, 'Trader': trader_name})  # Append trader_name to each row
            if next_heading is not None and item.find_next_sibling('tr') == next_heading:
                break

    return data

def process_txt_file(txt_file, trader_name):
    data = []

    lines = txt_file.split('\n')

    # Find the index where item details start
    start_index = None
    for i, line in enumerate(lines):
        if "LIST #" in line:
            start_index = i + 3  # Skip the header and move to the next line
            break

    # Extract item details
    if start_index is not None:
        for line in lines[start_index:]:
            if "End of List" in line:
                break
            parts = line.split('|')
            if len(parts) >= 4:
                code = parts[1].strip()
                item_name = parts[2].strip()
                discount = parts[4].strip()
                data.append({'Code': code, 'Item Name': item_name, 'Pharmaceutical': '', 'Offer': discount, 'Bonus': '', 'T.P': '', 'Trader': trader_name})  # Append trader_name to each row

    return data

def process_pdf_file(pdf_file, trader_name):
    data = []
    tables = tabula.read_pdf(pdf_file, pages='all', multiple_tables=True)
    df = pd.concat(tables)
    df.reset_index(drop=True, inplace=True)
    # Check if 'Items' column exists, if not, check for 'Item(s)' column
    if 'Items' in df.columns:
        item_column = 'Items'
    elif 'Item(s)' in df.columns:
        item_column = 'Item(s)'
    else:
        print("oopsie")  # Return empty list if neither column exists


    if 'Disc.' in df.columns:
        disc_column = 'Disc.'
    elif 'Disc' in df.columns:
        disc_column = 'Disc'
    else:
        print("oopsie")


    if 'Bonus/Net' in df.columns:
        bonus_col = 'Bonus/Net'
    elif 'Disc / Bonus' in df.columns:
        bonus_col = 'Disc / Bonus'
    else:
        print("oopsie")
    
    for i in range(len(df)):
        data.append({
            'Code': '',
            'Item Name': df[item_column][i],
            'Pharmaceutical': '',
            'Offer': df[disc_column][i],
            'Bonus': '' if pd.isna(df[bonus_col][i]) else df[bonus_col][i],
            'T.P': '',
            'Trader': trader_name
        })   

    return data 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return "No file part"
    
    files = request.files.getlist('files')
    
    if not files:
        return "No selected file"
    
    output_filename = 'combined_output.csv'  # Output CSV file name
    data = []

    # Process each file
    for file in files:
        filename = file.filename
        trader_name = os.path.splitext(filename)[0]
        if filename.lower().endswith('.htm'):
            data.extend(process_html_file(file.read(), trader_name))
        elif filename.lower().endswith('.txt'):
            data.extend(process_txt_file(file.read().decode('utf-8'), trader_name))
        elif filename.lower().endswith('.pdf'):
            data.extend(process_pdf_file(file, trader_name))

    
    # Sort the data alphabetically by the first word of 'Item Name' and then by 'Offer' in descending order
    sorted_data = sorted(data, key=lambda x: (x['Item Name'].split()[0].lower() if x['Item Name'] else "No Name",
                                          -float(str(x['Offer']).rstrip('%')) if x['Offer'] else 0))
    
    # Write the sorted data to the CSV file
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.DictWriter(csvfile, fieldnames=['Code', 'Item Name', 'Pharmaceutical', 'Offer', 'Bonus', 'T.P', 'Trader'])
        csv_writer.writeheader()
        csv_writer.writerows(sorted_data)

    # Serve the generated CSV file for download
    return send_file(output_filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
