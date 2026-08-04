from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
import pandas as pd
from automation_script import run_automation
from fnv_automation import process_all_fnv_cities

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

GENERATED_FILES = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/<run_id>/<file_type>')
def download_file(run_id, file_type):
    if run_id not in GENERATED_FILES or file_type not in GENERATED_FILES[run_id]:
        return "File not found", 404
        
    file_path = GENERATED_FILES[run_id][file_type]
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/download/<run_id>/fnv/<city>/<file_type>')
def download_city_file(run_id, city, file_type):
    if run_id not in GENERATED_FILES or 'city_stats' not in GENERATED_FILES[run_id]:
        return "Run not found", 404
    
    city_stats = GENERATED_FILES[run_id]['city_stats']
    if city not in city_stats:
        return "City not found", 404
        
    path_key = f"{file_type}_path"
    if path_key not in city_stats[city] or not city_stats[city][path_key]:
        return "File not found", 404
        
    file_path = city_stats[city][path_key]
    if not file_path or not os.path.exists(file_path):
        return "File not found on disk", 404
        
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/detect-city', methods=['POST'])
def detect_city():
    alloc_file = request.files.get('file')
    if not alloc_file:
        return jsonify({'error': 'No file'}), 400
        
    filename = alloc_file.filename.lower()
    city = None
    
    if 'blr' in filename or 'bangalore' in filename or 'bengaluru' in filename: city = 'Bangalore'
    elif 'chn' in filename or 'chennai' in filename: city = 'Chennai'
    elif 'mum' in filename or 'mumbai' in filename: city = 'Mumbai'
    elif 'hyd' in filename or 'hyderabad' in filename: city = 'Hyderabad'
    elif 'try' in filename or 'trichy' in filename: city = 'Trichy'
    elif 'cbe' in filename or 'coimbatore' in filename: city = 'Coimbatore'
        
    if not city:
        try:
            df = pd.read_excel(alloc_file, nrows=10)
            city_cols = [c for c in df.columns if 'city' in str(c).lower()]
            if city_cols:
                first_city = str(df[city_cols[0]].dropna().iloc[0]).lower()
                if 'blr' in first_city or 'bangal' in first_city or 'bengal' in first_city: city = 'Bangalore'
                elif 'che' in first_city or 'chn' in first_city: city = 'Chennai'
                elif 'mum' in first_city: city = 'Mumbai'
                elif 'hyd' in first_city: city = 'Hyderabad'
                elif 'tri' in first_city or 'try' in first_city: city = 'Trichy'
                elif 'coim' in first_city or 'cbe' in first_city: city = 'Coimbatore'
        except:
            pass

    return jsonify({'city': city})

@app.route('/process', methods=['POST'])
def process():
    try:
        city = request.form.get('city')
        delivery_date_raw = request.form.get('date')
        if not city or not delivery_date_raw:
            return jsonify({'error': 'City and Delivery Date are required'}), 400

        # Automatically set delivery date to today + 1 day
        from datetime import datetime, timedelta
        delivery_date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")

        alloc_file = request.files.get('allocation_file')
        if not alloc_file:
            return jsonify({'error': 'Allocation file is required'}), 400
        
        alloc_filename = secure_filename(alloc_file.filename)
        alloc_path = os.path.join(app.config['UPLOAD_FOLDER'], alloc_filename)
        alloc_file.save(alloc_path)

        gsheet_url = request.form.get('gsheet_url')
        if not gsheet_url:
            return jsonify({'error': 'Google Sheet URL is required'}), 400

        so_sheet = request.form.get('so_sheet')
        po_sheet = request.form.get('po_sheet')

        output_dir = tempfile.mkdtemp()

        csv_path, xlsx_path, po_path, valid_len, na_len, total_so, po_generated = run_automation(
            allocation_path=alloc_path,
            ecom_path=None,
            city=city,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            so_sheet_override=so_sheet,
            po_sheet_override=po_sheet
        )

        run_id = str(uuid.uuid4())
        GENERATED_FILES[run_id] = {
            'csv': csv_path,
            'xlsx': xlsx_path,
            'po': po_path
        }

        return jsonify({
            'success': True,
            'run_id': run_id,
            'stats': {
                'total': total_so,
                'valid': valid_len,
                'na': na_len,
                'po': po_generated
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/process_fnv', methods=['POST'])
def process_fnv():
    try:
        # Automatically set delivery date to today + 1 day
        from datetime import datetime, timedelta
        delivery_date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")

        fnv_file = request.files.get('fnv_file')
        if not fnv_file:
            return jsonify({'error': 'FnV allocation file is required'}), 400

        fnv_filename = secure_filename(fnv_file.filename)
        fnv_path = os.path.join(app.config['UPLOAD_FOLDER'], fnv_filename)
        fnv_file.save(fnv_path)

        gsheet_url = request.form.get('gsheet_url')
        if not gsheet_url:
            return jsonify({'error': 'Google Sheet URL is required'}), 400

        output_dir = tempfile.mkdtemp()

        zip_path, valid_len, na_len, total_so, po_generated, city_stats = process_all_fnv_cities(
            fnv_alloc_path=fnv_path,
            delivery_date=delivery_date,
            gsheet_url=gsheet_url,
            output_dir=output_dir
        )

        run_id = str(uuid.uuid4())
        GENERATED_FILES[run_id] = {
            'zip': zip_path,
            'city_stats': city_stats
        }

        return jsonify({
            'success': True,
            'run_id': run_id,
            'stats': {
                'total': total_so,
                'valid': valid_len,
                'na': na_len,
                'po': po_generated
            },
            'city_stats': city_stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
