from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
from automation_script import run_automation, run_fnv_automation

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

@app.route('/process', methods=['POST'])
def process():
    try:
        city = request.form.get('city')
        delivery_date_raw = request.form.get('date')
        if not city or not delivery_date_raw:
            return jsonify({'error': 'City and Delivery Date are required'}), 400

        try:
            y, m, d = delivery_date_raw.split('-')
            delivery_date = f"{d}-{m}-{y}"
        except:
            delivery_date = delivery_date_raw

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
        city = request.form.get('city')
        delivery_date_raw = request.form.get('date')
        if not city or not delivery_date_raw:
            return jsonify({'error': 'City and Delivery Date are required'}), 400

        try:
            y, m, d = delivery_date_raw.split('-')
            delivery_date = f"{d}-{m}-{y}"
        except:
            delivery_date = delivery_date_raw

        fnv_file = request.files.get('fnv_file')
        if not fnv_file:
            return jsonify({'error': 'FnV allocation file is required'}), 400

        fnv_filename = secure_filename(fnv_file.filename)
        fnv_path = os.path.join(app.config['UPLOAD_FOLDER'], fnv_filename)
        fnv_file.save(fnv_path)

        gsheet_url = request.form.get('gsheet_url')
        if not gsheet_url:
            return jsonify({'error': 'Google Sheet URL is required'}), 400

        so_sheet = request.form.get('so_sheet')
        po_sheet = request.form.get('po_sheet')
        city_col = request.form.get('city_col') or 'City'

        output_dir = tempfile.mkdtemp()

        csv_path, xlsx_path, po_path, valid_len, na_len, total_so, po_generated = run_fnv_automation(
            fnv_alloc_path=fnv_path,
            city=city,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            so_sheet_override=so_sheet,
            po_sheet_override=po_sheet,
            city_col=city_col,
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
